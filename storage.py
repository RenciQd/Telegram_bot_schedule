from __future__ import annotations

from datetime import date

from redis_client import redis

KEEP_DAYS_DEFAULT = 3


def lesson_key(lesson_date: date, start_time_iso: str, subject: str) -> str:
    return f"{lesson_date.isoformat()}|{start_time_iso}|{subject}"


class NotifiedStore:
    def __init__(self, keep_days: int = KEEP_DAYS_DEFAULT):
        self.keep_days = keep_days

    @staticmethod
    def make_key(chat_id: int, lesson) -> str:
        return f"notified:{chat_id}::{lesson_key(lesson.date, lesson.start_time.isoformat(), lesson.subject)}"

    async def contains(self, key: str) -> bool:
        return bool(await redis.exists(key))

    async def add(self, key: str) -> None:
        await redis.set(key, "1", ex=self.keep_days * 86400)
