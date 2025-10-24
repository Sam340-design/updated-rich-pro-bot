UPDATED_RICH PRO Signals - Payment Gate (Option A: deep-link + verification token)


Files included:
- main.py  (use env vars for keys)
- requirements.txt
- banner.png


Quick setup (Render):

1) In Render, create a Web Service and connect repo or upload files.
- Build command: pip install -r requirements.txt
- Start command: gunicorn main:app
- Root directory: .

2) Environment variables (Render):
   BOT_TOKEN, PAYSTACK_PUBLIC_KEY, PAYSTACK_SECRET_KEY, PUBLIC_BASE_URL, ADMIN_TELEGRAM_ID

3) Paystack webhook: set to https://<your-app>/paystack/webhook
   Callback (optional): https://<your-app>/payment-success

4) Behavior:
   - /pay produces an inline Pay button showing USD equivalent but charges ₵60 (GHS)
   - After Paystack confirms payment, the webhook stores user and generates a token
     and sends a deep-link to the main signal bot: https://t.me/minesprosignal_bot?start=TOKEN
   - Expiry is hidden; when it ends user gets a renewal prompt.

Security notes:
- The DB stores IP addresses and tokens. Treat as personal data.
- Do not publish secret keys.
