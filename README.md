# UPDATED_RICH PRO Signals - Payment Gate (Paystack + Telegram)

This package contains a ready-to-deploy Python app that acts as a payment gate using Paystack Mobile Money (GHS) and a Telegram bot.

Files:
- `main.py` - Main application (Flask webhook + Telegram bot)
- `requirements.txt` - Python dependencies
- `banner.png` - Branded banner used in /start

STEP 1 - Edit configuration (important)
--------------------------------------
Open `main.py` and replace the placeholder values at the top with your keys, or set the following environment variables on your host:

- BOT_TOKEN
- PAYSTACK_SECRET_KEY
- PAYSTACK_PUBLIC_KEY
- PUBLIC_BASE_URL  (e.g. https://yourapp.onrender.com)

Make sure the webhook URL is set in Paystack dashboard to: `https://<PUBLIC_BASE_URL>/paystack/webhook`

STEP 2 - Deploy (Render example)
--------------------------------
1. Create a new GitHub repo and push these files.
2. Create a new Web Service on Render and connect the repo.
3. Set environment variables on Render (BOT_TOKEN, PAYSTACK keys, PUBLIC_BASE_URL).
4. Start command: `python main.py`
5. Deploy. When live, set Paystack webhook to: `https://<PUBLIC_BASE_URL>/paystack/webhook`

STEP 3 - Test
-------------
1. In Telegram, open your bot and use /start.
2. Click the Pay button to create a Paystack checkout for ₵60.
3. Complete payment (use Paystack test keys for testing if desired).
4. On successful payment, the bot will send the user the signal bot link: https://t.me/minesprosignal_bot

SECURITY NOTES
--------------
- NEVER commit your secret keys to public repos. Use environment variables.
- The app stores IP addresses and payment metadata in SQLite; ensure you comply with privacy rules.
- This project is a starting point. For production, run with a proper WSGI server and HTTPS handling.
