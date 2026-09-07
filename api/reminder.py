import asyncio
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import bot as bot_module

CRON_SECRET = os.getenv("CRON_SECRET")


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if CRON_SECRET:
            query = parse_qs(urlparse(self.path).query)
            token = (query.get("token") or [None])[0]
            if token != CRON_SECRET:
                self.send_response(401)
                self.end_headers()
                return

        try:
            asyncio.run(bot_module.run_reminder_check())
            ok = True
        except Exception:
            bot_module.log.exception("Ошибка в проверке напоминаний")
            ok = False

        self.send_response(200 if ok else 500)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true}' if ok else b'{"ok": false}')
