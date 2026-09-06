import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv() 

def get_required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Не задана переменная окружения {name}. "
            f"Скопируй .env.example в .env и заполни его."
        )
    return value


def get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


BOT_TOKEN: str = get_required("BOT_TOKEN")

REMIND_BEFORE_MINUTES: int = get_int("REMIND_BEFORE_MINUTES", 60) #время начала пары
CHECK_INTERVAL_SECONDS: int = get_int("CHECK_INTERVAL_SECONDS", 60)
REFRESH_SCHEDULE_MINUTES: int = get_int("REFRESH_SCHEDULE_MINUTES", 20)
TIMEZONE = ZoneInfo(os.getenv("TIMEZONE", "Europe/Moscow"))
REMINDER_WINDOW_MINUTES: int = get_int("REMINDER_WINDOW_MINUTES", 3)
