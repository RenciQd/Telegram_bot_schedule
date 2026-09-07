import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("BOT_TOKEN не задан (проверь .env)")
        sys.exit(1)
    if len(sys.argv) < 2:
        print("Использование: python scripts/set_webhook.py https://<project>.vercel.app/api/webhook")
        sys.exit(1)

    url = sys.argv[1]
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    payload = {"url": url, "allowed_updates": ["message", "callback_query"]}
    if secret:
        payload["secret_token"] = secret

    resp = requests.post(f"https://api.telegram.org/bot{token}/setWebhook", json=payload)
    print(resp.status_code, resp.json())


if __name__ == "__main__":
    main()
