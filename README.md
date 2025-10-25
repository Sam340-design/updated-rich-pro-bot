UPDATED_RICH PRO Signals - Production package

Important: Do NOT hardcode secrets. Set these environment variables on Render:

BOT_TOKEN = your Telegram bot token
PAYSTACK_PUBLIC_KEY = pk_live_...
PAYSTACK_SECRET_KEY = sk_live_...
PUBLIC_BASE_URL = https://updated-rich-pro-bot-1.onrender.com
ADMIN_TELEGRAM_ID = your numeric Telegram id
SIGNAL_BOT_USERNAME = minesprosignal_bot
SUBSCRIPTION_AMOUNT_GHS = 60
SUBSCRIPTION_DISPLAY_AMOUNT = $5.00

Deploy notes:
- Root directory: .
- Build command: pip install -r requirements.txt
- Start command: gunicorn main:app

After deploy make sure to set:
- Telegram webhook: https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook?url=https://updated-rich-pro-bot-1.onrender.com/webhook
- Paystack webhook (live): https://updated-rich-pro-bot-1.onrender.com/paystack/webhook

Testing:
- Use /start to confirm bot responds
- Use /pay to generate a Paystack checkout

Security:
- This app stores Telegram IDs and IP addresses in a local SQLite DB. Use responsibly.
