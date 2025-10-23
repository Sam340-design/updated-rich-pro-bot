import os
import time
import json
import requests
from threading import Thread
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext

# ------------------------------
# Config / Environment Variables
# ------------------------------
BOT_TOKEN = os.environ['BOT_TOKEN']
PAYSTACK_SECRET_KEY = os.environ['PAYSTACK_SECRET_KEY']
PAYSTACK_PUBLIC_KEY = os.environ['PAYSTACK_PUBLIC_KEY']
PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL', '')

bot = Bot(token=BOT_TOKEN)
app = Flask(__name__)

# Store paid users: {user_id: expiry_timestamp}
paid_users = {}

# ------------------------------
# Telegram Bot Logic
# ------------------------------
def start(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    now = int(time.time())

    # Check subscription
    if user_id in paid_users and paid_users[user_id] > now:
        remaining = paid_users[user_id] - now
        days = remaining // 86400
        hours = (remaining % 86400) // 3600
        minutes = (remaining % 3600) // 60
        message = (
            "✨ *WELCOME TO UPDATED_RICH PRO Signals* ✨\n"
            "Win Smarter — Get Accurate Signals Every Day!\n\n"
            f"✅ *Subscription Active!* ⏱️\n"
            f"🗓️ Days: {days} | ⏰ Hours: {hours} | ⏱️ Minutes: {minutes}"
        )
    else:
        message = (
            "✨ *WELCOME TO UPDATED_RICH PRO Signals* ✨\n"
            "Win Smarter — Get Accurate Signals Every Day!\n\n"
            "💰 You need to pay ₵60 for 10 days to access signals.\n"
            "Use /pay to subscribe."
        )

    # Send banner if available
    try:
        with open("banner.png", "rb") as f:
            context.bot.send_photo(chat_id=user_id, photo=f, caption=message, parse_mode="Markdown")
    except:
        context.bot.send_message(chat_id=user_id, text=message, parse_mode="Markdown")


def pay(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id

    # Create Paystack payment link dynamically
    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "email": f"{user_id}@example.com",  # dummy email
        "amount": 6000,  # ₵60 in Kobo
        "currency": "GHS",
        "callback_url": f"{PUBLIC_BASE_URL}/payment-success",
        "metadata": {"user_id": user_id}
    }
    response = requests.post("https://api.paystack.co/transaction/initialize",
                             headers=headers, json=payload)
    if response.status_code == 200:
        data = response.json()
        if data.get("status"):
            pay_url = data["data"]["authorization_url"]

            # Create inline button
            keyboard = [[InlineKeyboardButton("💳 Pay ₵60 for 10 days", url=pay_url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            context.bot.send_message(
                chat_id=user_id,
                text="Click the button below to complete your payment:",
                reply_markup=reply_markup
            )
        else:
            context.bot.send_message(chat_id=user_id,
                                     text="❌ Payment initialization failed. Try again later.")
    else:
        context.bot.send_message(chat_id=user_id,
                                 text="❌ Payment request failed. Check network or keys.")


def run_telegram_bot():
    updater = Updater(token=BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CommandHandler('pay', pay))
    updater.start_polling()
    updater.idle()

# ------------------------------
# Flask Webhook for Paystack
# ------------------------------
@app.route("/paystack/webhook", methods=['POST'])
def paystack_webhook():
    data = request.json
    if not data:
        return "No data", 400

    event = data.get("event")
    if event == "charge.success":
        payment_data = data.get("data", {})
        metadata = payment_data.get("metadata", {})
        user_id = int(metadata.get("user_id", 0))
        if user_id:
            # Grant 10-day subscription
            paid_users[user_id] = int(time.time()) + 10 * 24 * 3600
            print(f"✅ User {user_id} payment verified and subscription granted")
    return "OK", 200

# ------------------------------
# Payment Success Page
# ------------------------------
@app.route("/payment-success")
def payment_success():
    return """
    <html>
        <head>
            <title>Payment Successful</title>
            <style>
                body { 
                    font-family: Arial, sans-serif; 
                    text-align: center; 
                    margin-top: 50px; 
                    background-color: #f7f7f7;
                }
                h1 { color: #28a745; }
                p { font-size: 18px; }
                a {
                    display: inline-block;
                    margin-top: 20px;
                    padding: 10px 20px;
                    background-color: #007bff;
                    color: white;
                    text-decoration: none;
                    border-radius: 5px;
                }
                a:hover { background-color: #0056b3; }
            </style>
        </head>
        <body>
            <h1>🎉 Payment Successful!</h1>
            <p>You now have access to <strong>UPDATED_RICH PRO Signals</strong>.</p>
            <a href="https://t.me/UPDATED_RICH_PRO_Signals_bot">Go to Bot</a>
        </body>
    </html>
    """

# Optional: Simple route to test server
@app.route("/")
def home():
    return "UPDATED_RICH PRO Signals Bot is running! 🟢", 200

# ------------------------------
# Start Telegram Bot in Background
# ------------------------------
if __name__ == "__main__":
    Thread(target=run_telegram_bot).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
