from __future__ import annotations

import json
from datetime import date, datetime, time
from typing import Optional

from redis_client import redis
from scrapers import Lesson


def lesson_to_dict(lesson: Lesson) -> dict:
    return {
        "date": lesson.date.isoformat(),
        "weekday_name": lesson.weekday_name,
        "pair_number": lesson.pair_number,
        "start_time": lesson.start_time.isoformat(),
        "end_time": lesson.end_time.isoformat(),
        "lesson_type": lesson.lesson_type,
        "subject": lesson.subject,
        "teacher": lesson.teacher,
        "room": lesson.room,
    }


def lesson_from_dict(d: dict) -> Lesson:
    return Lesson(
        date=date.fromisoformat(d["date"]),
        weekday_name=d["weekday_name"],
        pair_number=d["pair_number"],
        start_time=time.fromisoformat(d["start_time"]),
        end_time=time.fromisoformat(d["end_time"]),
        lesson_type=d["lesson_type"],
        subject=d["subject"],
        teacher=d["teacher"],
        room=d["room"],
    )


def cache_key(chat_id: int) -> str:
    return f"schedule_cache:{chat_id}"


class ScheduleCacheStore:
    async def get(self, chat_id: int) -> Optional[tuple[list[Lesson], datetime]]:
        raw = await redis.get(cache_key(chat_id))
        if not raw:
            return None
        try:
            entry = json.loads(raw)
            lessons = [lesson_from_dict(x) for x in entry["lessons"]]
            fetched_at = datetime.fromisoformat(entry["fetched_at"])
        except (KeyError, ValueError, json.JSONDecodeError):
            return None
        return lessons, fetched_at

    async def set(self, chat_id: int, lessons: list[Lesson], fetched_at: datetime) -> None:
        payload = json.dumps(
            {
                "lessons": [lesson_to_dict(l) for l in lessons],
                "fetched_at": fetched_at.isoformat(),
            },
            ensure_ascii=False,
        )
        await redis.set(cache_key(chat_id), payload)

    async def forget(self, chat_id: int) -> None:
        await redis.delete(cache_key(chat_id))
