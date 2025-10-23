"""UPDATED_RICH PRO Signals - Payment Gate (Paystack + Telegram)

IMPORTANT: This file intentionally contains PLACEHOLDER values for secret keys and tokens.
PLEASE replace these placeholders with your real BOT_TOKEN and PAYSTACK keys BEFORE deploying.
"""

import os
import hmac
import hashlib
import sqlite3
import threading
import datetime
from urllib.parse import urljoin

import requests
from flask import Flask, request, jsonify, send_file
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

# ---------------------- CONFIG (FILL THESE) ----------------------
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
PAYSTACK_SECRET_KEY = os.environ.get('PAYSTACK_SECRET_KEY', 'YOUR_PAYSTACK_SECRET_KEY_HERE')
PAYSTACK_PUBLIC_KEY = os.environ.get('PAYSTACK_PUBLIC_KEY', 'YOUR_PAYSTACK_PUBLIC_KEY_HERE')
PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL', 'https://YOUR_PUBLIC_DOMAIN_HERE')
# Signal bot link to grant access after payment
SIGNAL_BOT_LINK = "https://t.me/minesprosignal_bot"
BOT_NAME = "UPDATED_RICH PRO Signals"
# Webhook path
PAYSTACK_WEBHOOK_PATH = "/paystack/webhook"
# Pricing
CURRENCY = "GHS"
PRICE_GHS = 60
PRICE_USD = 5  # display only
SUBSCRIPTION_DAYS = 10

# Paystack endpoints
PAYSTACK_INIT_URL = "https://api.paystack.co/transaction/initialize"
PAYSTACK_VERIFY_URL = "https://api.paystack.co/transaction/verify/"  # append reference
DB_PATH = "paid_users.db"

app = Flask(__name__)

# ---------------------- DATABASE HELPERS ----------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            username TEXT,
            email TEXT,
            amount INTEGER,
            currency TEXT,
            reference TEXT UNIQUE,
            paid_at TEXT,
            expiry TEXT,
            ip_address TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_payment(telegram_id, username, email, amount, currency, reference, paid_at, expiry, ip_address):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO payments (telegram_id, username, email, amount, currency, reference, paid_at, expiry, ip_address)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', (telegram_id, username, email, amount, currency, reference, paid_at, expiry, ip_address))
    conn.commit()
    conn.close()

def get_user_active(telegram_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.datetime.utcnow()
    c.execute('SELECT expiry FROM payments WHERE telegram_id = ? ORDER BY paid_at DESC LIMIT 1', (telegram_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return False
    expiry = datetime.datetime.fromisoformat(row[0])
    return now < expiry

# ---------------------- PAYSTACK HELPERS ----------------------
def paystack_initialize_transaction(email, amount_ghs, metadata=None, callback_url=None):
    amount_subunit = int(amount_ghs * 100)
    payload = {"email": email or "no-reply@example.com", "amount": amount_subunit, "currency": CURRENCY}
    if metadata:
        payload["metadata"] = metadata
    if callback_url:
        payload["callback_url"] = callback_url
    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}", "Content-Type": "application/json"}
    resp = requests.post(PAYSTACK_INIT_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()

def verify_paystack_signature(request_body_bytes, signature_header):
    if not signature_header:
        return False
    computed = hmac.new(PAYSTACK_SECRET_KEY.encode(), request_body_bytes, hashlib.sha512).hexdigest()
    return hmac.compare_digest(computed, signature_header)

def paystack_verify_transaction(reference):
    url = PAYSTACK_VERIFY_URL + reference
    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()

# ---------------------- FLASK WEBHOOK ----------------------
@app.route(PAYSTACK_WEBHOOK_PATH, methods=["POST"])
def paystack_webhook():
    raw_body = request.get_data()
    sig = request.headers.get("x-paystack-signature")
    if not verify_paystack_signature(raw_body, sig):
        app.logger.warning("Invalid paystack signature")
        return ("", 400)

    data = request.get_json()
    event = data.get("event")
    if event == "charge.success":
        payload = data.get("data", {})
        reference = payload.get("reference")
        amount = payload.get("amount")
        currency = payload.get("currency")
        metadata = payload.get("metadata") or {}
        telegram_id = metadata.get("telegram_id")
        username = metadata.get("telegram_username")
        email = payload.get("customer", {}).get("email") if payload.get("customer") else metadata.get("email")
        paid_at = datetime.datetime.utcnow()
        expiry = paid_at + datetime.timedelta(days=SUBSCRIPTION_DAYS)
        ip_addr = request.remote_addr
        add_payment(int(telegram_id) if telegram_id else None, username, email, amount, currency, reference, paid_at.isoformat(), expiry.isoformat(), ip_addr)
        if telegram_id:
            try:
                from telegram import Bot
                bot = Bot(token=BOT_TOKEN)
                human_amount = amount / 100.0
                text = f"✅ Payment confirmed. Reference: {reference}\nAmount: {human_amount} {CURRENCY}\nExpiry: {expiry.date()}\n\nAccess your signals here: {SIGNAL_BOT_LINK}"
                bot.send_message(chat_id=int(telegram_id), text=text)
            except Exception as e:
                app.logger.exception("Failed to send Telegram notification: %s", e)
    return jsonify({"status": "ok"})

# serve banner image
@app.route('/banner.png')
def banner():
    return send_file('banner.png', mimetype='image/png')

# ---------------------- TELEGRAM BOT ----------------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    telegram_id = user.id
    username = user.username or user.first_name or ''
    if get_user_active(telegram_id):
        await update.message.reply_text("✅ Welcome back — your subscription is active. Use /signals to get predictions.")
        return
    usd_equiv = PRICE_USD
    keyboard = [[InlineKeyboardButton(f"💳 Pay ${usd_equiv} (₵{PRICE_GHS}) for {SUBSCRIPTION_DAYS} days", callback_data="PAY_SUB")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    # send banner then message
    try:
        await context.bot.send_photo(chat_id=telegram_id, photo=open('banner.png','rb'), caption=f"💰 Welcome to {BOT_NAME}\nWin Smarter\n\nTo access premium signals, pay ₵{PRICE_GHS} (≈ ${usd_equiv}) for {SUBSCRIPTION_DAYS} days.", reply_markup=reply_markup)
    except Exception:
        await update.message.reply_text(f"Hello @{username}! To access signals you must pay ₵{PRICE_GHS} (≈ ${usd_equiv}) for {SUBSCRIPTION_DAYS} days.", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user
    if data == "PAY_SUB":
        metadata = {"telegram_id": user.id, "telegram_username": user.username}
        try:
            callback = urljoin(PUBLIC_BASE_URL, "/payments/callback")
            init = paystack_initialize_transaction(email=None, amount_ghs=PRICE_GHS, metadata=metadata, callback_url=callback)
            auth_url = init["data"]["authorization_url"]
            await query.message.reply_text(f"🔗 Follow this link to pay ₵{PRICE_GHS} (≈ ${PRICE_USD}): {auth_url}\nAfter payment completes you will receive access automatically.")
        except Exception as e:
            await query.message.reply_text("Failed to initialize payment. Try again later.")
            app.logger.exception("paystack init error: %s", e)

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    active = get_user_active(user.id)
    if active:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT expiry FROM payments WHERE telegram_id = ? ORDER BY paid_at DESC LIMIT 1', (user.id,))
        row = c.fetchone()
        conn.close()
        expiry = row[0] if row else "unknown"
        await update.message.reply_text(f"✅ Active. Expires: {expiry}")
    else:
        await update.message.reply_text("❌ No active subscription. Use /start to purchase.")

async def cmd_signals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not get_user_active(user.id):
        await update.message.reply_text("Your subscription isn't active. Please pay to access signals.")
        return
    # Forward the user to the signal bot or give instructions
    await update.message.reply_text(f"📈 Your access link: {SIGNAL_BOT_LINK}\nOpen the link and start the signal bot.")

def start_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

async def start_bot():
    global app_bot
    init_db()
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("signals", cmd_signals))
    app_bot = application
    await application.initialize()
    await application.start()
    await application.updater.start_polling()

def main():
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()
    import asyncio
    asyncio.run(start_bot())

if __name__ == "__main__":
    print("Starting app. Edit config values at the top or set environment variables before running.")
    main()
