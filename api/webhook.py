import asyncio
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import bot as bot_module

WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET")


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"ok")

    def do_POST(self) -> None:
        if WEBHOOK_SECRET:
            got = self.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if got != WEBHOOK_SECRET:
                self.send_response(401)
                self.end_headers()
                return

        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"

        try:
            data = json.loads(raw or b"{}")
            asyncio.run(bot_module.process_webhook_update(data))
        except Exception:
            bot_module.log.exception("Ошибка обработки webhook-апдейта")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true}')
