from __future__ import annotations

import json
from datetime import date, datetime, time
from pathlib import Path
from typing import Optional

from scraper import Lesson

DEFAULT_PATH = Path(__file__).parent / "data" / "schedule_cache.json"


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


class ScheduleCacheStore:
    def __init__(self, path: Path | str = DEFAULT_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, dict] = self._load()

    def load(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def save(self) -> None:
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get(self, chat_id: int) -> Optional[tuple[list[Lesson], datetime]]:
        entry = self._data.get(str(chat_id))
        if not entry:
            return None
        try:
            lessons = [lesson_from_dict(x) for x in entry["lessons"]]
            fetched_at = datetime.fromisoformat(entry["fetched_at"])
        except (KeyError, ValueError):
            return None
        return lessons, fetched_at

    def set(self, chat_id: int, lessons: list[Lesson], fetched_at: datetime) -> None:
        self._data[str(chat_id)] = {
            "lessons": [lesson_to_dict(l) for l in lessons],
            "fetched_at": fetched_at.isoformat(),
        }
        self._save()

    def forget(self, chat_id: int) -> None:
        if self._data.pop(str(chat_id), None) is not None:
            self._save()
