"""UPDATED_RICH PRO Signals - Payment Gate (Option A: deep-link + verification token)

Replace placeholders via environment variables on Render.
"""
import os
import time
import hmac
import hashlib
import secrets
import sqlite3
from threading import Thread
from urllib.parse import quote_plus

import requests
from flask import Flask, request, jsonify, send_file
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext

BOT_TOKEN = os.environ.get('BOT_TOKEN', 'YOUR_BOT_TOKEN')
PAYSTACK_SECRET_KEY = os.environ.get('PAYSTACK_SECRET_KEY', 'YOUR_PAYSTACK_SECRET_KEY')
PAYSTACK_PUBLIC_KEY = os.environ.get('PAYSTACK_PUBLIC_KEY', 'YOUR_PAYSTACK_PUBLIC_KEY')
PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL', 'https://YOUR_APP.onrender.com')
ADMIN_TELEGRAM_ID = int(os.environ.get('ADMIN_TELEGRAM_ID', '0'))

SIGNAL_BOT_USERNAME = 'minesprosignal_bot'
CURRENCY = 'GHS'
PRICE_GHS = 60
PRICE_USD_DISPLAY = 5
SUB_DAYS = 10
DB_PATH = 'payments.db'

app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            username TEXT,
            amount INTEGER,
            currency TEXT,
            reference TEXT UNIQUE,
            paid_at INTEGER,
            expiry INTEGER,
            ip_address TEXT,
            token TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_payment(telegram_id, username, amount, currency, reference, paid_at, expiry, ip_address, token):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO payments (telegram_id, username, amount, currency, reference, paid_at, expiry, ip_address, token) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', (telegram_id, username, amount, currency, reference, paid_at, expiry, ip_address, token))
    conn.commit()
    conn.close()

def get_active(telegram_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = int(time.time())
    c.execute('SELECT expiry FROM payments WHERE telegram_id = ? ORDER BY paid_at DESC LIMIT 1', (telegram_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return False
    return now < row[0]

def init_paystack_transaction(telegram_id):
    url = 'https://api.paystack.co/transaction/initialize'
    headers = {'Authorization': f'Bearer {PAYSTACK_SECRET_KEY}', 'Content-Type': 'application/json'}
    payload = {'email': f'{telegram_id}@example.com', 'amount': int(PRICE_GHS*100), 'currency': CURRENCY, 'callback_url': f'{PUBLIC_BASE_URL}/payment-success', 'metadata': {'telegram_id': telegram_id}}
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()

def verify_paystack_signature(request_body_bytes, signature_header):
    if not signature_header:
        return False
    computed = hmac.new(PAYSTACK_SECRET_KEY.encode(), request_body_bytes, hashlib.sha512).hexdigest()
    return hmac.compare_digest(computed, signature_header)

@app.route('/')
def home():
    return 'UPDATED_RICH PRO Signals (payment gate) is running', 200

@app.route('/banner.png')
def banner():
    return send_file('banner.png', mimetype='image/png')

@app.route('/payment-success')
def payment_success():
    return '<html><body><h2>Payment completed — return to Telegram.</h2></body></html>'

@app.route('/paystack/webhook', methods=['POST'])
def paystack_webhook():
    raw = request.get_data()
    sig = request.headers.get('x-paystack-signature')
    if not verify_paystack_signature(raw, sig):
        return 'Invalid signature', 400
    data = request.json
    if data.get('event') == 'charge.success':
        pdata = data.get('data', {})
        ref = pdata.get('reference')
        amount = pdata.get('amount')
        currency = pdata.get('currency')
        metadata = pdata.get('metadata') or {}
        telegram_id = int(metadata.get('telegram_id')) if metadata.get('telegram_id') else None
        username = pdata.get('customer', {}).get('email') or metadata.get('username')
        paid_at = int(time.time())
        expiry = paid_at + SUB_DAYS*24*3600
        ip_addr = request.remote_addr
        token = secrets.token_urlsafe(12)
        add_payment(telegram_id, username, amount, currency, ref, paid_at, expiry, ip_addr, token)
        deep = f'https://t.me/{SIGNAL_BOT_USERNAME}?start={quote_plus(token)}'
        try:
            bot.send_message(chat_id=telegram_id, text='✅ Payment confirmed — connecting you now...')
            kb = [[InlineKeyboardButton('🔓 Open signal bot', url=deep)]]
            bot.send_message(chat_id=telegram_id, text='Tap to open your signal bot:', reply_markup=InlineKeyboardMarkup(kb))
        except Exception as e:
            app.logger.exception('Failed to message user: %s', e)
    return jsonify({'status': 'ok'})

def cmd_start(update, context: CallbackContext):
    user = update.effective_user
    tid = user.id
    if get_active(tid):
        context.bot.send_message(chat_id=tid, text='✅ Welcome back. You have access to the signals.')
    else:
        msg = ('✨ *WELCOME TO UPDATED_RICH PRO Signals* ✨\nWin Smarter\n\n' 'To access premium signals, pay ₵{0} (≈ ${1}). Use /pay to subscribe.').format(PRICE_GHS, PRICE_USD_DISPLAY)
        try:
            context.bot.send_photo(chat_id=tid, photo=open('banner.png','rb'), caption=msg, parse_mode='Markdown')
        except:
            context.bot.send_message(chat_id=tid, text=msg, parse_mode='Markdown')

def cmd_pay(update, context: CallbackContext):
    user = update.effective_user
    tid = user.id
    try:
        init = init_paystack_transaction(tid)
        auth = init.get('data', {}).get('authorization_url')
        kb = [[InlineKeyboardButton(f'💳 Pay {PRICE_USD_DISPLAY} (₵{PRICE_GHS})', url=auth)]]
        context.bot.send_message(chat_id=tid, text='Click to pay:', reply_markup=InlineKeyboardMarkup(kb))
    except Exception as e:
        context.bot.send_message(chat_id=tid, text='Failed to create payment. Try again later.')

def admin_list(update, context: CallbackContext):
    user = update.effective_user
    if user.id != ADMIN_TELEGRAM_ID:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT telegram_id, expiry, token FROM payments ORDER BY paid_at DESC LIMIT 50')
    rows = c.fetchall()
    conn.close()
    lines = []
    for r in rows:
        lines.append(f'{r[0]} | expires: {time.ctime(r[1])} | token: {r[2]}')
    msg = '\n'.join(lines) or 'No paid users yet.'
    context.bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=msg)

def admin_revoke(update, context: CallbackContext):
    user = update.effective_user
    if user.id != ADMIN_TELEGRAM_ID:
        return
    args = context.args
    if not args:
        context.bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text='Usage: /revoke <telegram_id>')
        return
    tid = int(args[0])
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE payments SET expiry = 0 WHERE telegram_id = ?', (tid,))
    conn.commit()
    conn.close()
    context.bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=f'Revoked {tid}')

def check_expirations_and_prompt():
    while True:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        now = int(time.time())
        c.execute('SELECT telegram_id FROM payments WHERE expiry <= ? AND expiry > 0', (now,))
        rows = c.fetchall()
        for r in rows:
            tid = r[0]
            try:
                kb = [[InlineKeyboardButton('🔁 Renew ₵60', url=f'{PUBLIC_BASE_URL}/renew')]]
                bot.send_message(chat_id=tid, text='⏳ Your access has ended. Tap to renew.', reply_markup=InlineKeyboardMarkup(kb))
                c.execute('UPDATE payments SET expiry = 0 WHERE telegram_id = ?', (tid,))
            except Exception:
                pass
        conn.commit()
        conn.close()
        time.sleep(3600)

def run_telegram():
    updater = Updater(token=BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler('start', cmd_start))
    dp.add_handler(CommandHandler('pay', cmd_pay))
    dp.add_handler(CommandHandler('admin_list', admin_list))
    dp.add_handler(CommandHandler('revoke', admin_revoke))
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    init_db()
    Thread(target=run_telegram, daemon=True).start()
    Thread(target=check_expirations_and_prompt, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
if __name__ == "__main__":
    from waitress import serve  # production-ready WSGI server
    import os
    port = int(os.environ.get("PORT", 10000))
    serve(app, host="0.0.0.0", port=port)
