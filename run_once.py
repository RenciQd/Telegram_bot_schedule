import asyncio
import json
from pathlib import Path

import state_crypto
state_crypto.decrypt_state()

import bot

OFFSET_PATH = Path(__file__).parent / "data" / "update_offset.json"

log = bot.log


def load_offset() -> int:
    if not OFFSET_PATH.exists():
        return 0
    try:
        return json.loads(OFFSET_PATH.read_text(encoding="utf-8")).get("offset", 0)
    except (json.JSONDecodeError, OSError):
        return 0


def save_offset(offset: int) -> None:
    OFFSET_PATH.parent.mkdir(parents=True, exist_ok=True)
    OFFSET_PATH.write_text(json.dumps({"offset": offset}), encoding="utf-8")


async def main() -> None:
    offset = load_offset()

    updates = await bot.bot.get_updates(offset=offset or None, timeout=0)
    if updates:
        for update in updates:
            try:
                await bot.dp.feed_update(bot.bot, update)
            except Exception:
                log.exception("Не удалось обработать update_id=%s", update.update_id)
            offset = update.update_id + 1
        save_offset(offset)
        log.info("Обработано апдейтов: %d, новый offset: %d", len(updates), offset)
    else:
        log.info("Новых апдейтов нет")

    await bot.run_reminder_check()
    await bot.bot.session.close()
    state_crypto.encrypt_state()

if __name__ == "__main__":
    asyncio.run(main())
