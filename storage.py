from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

DEFAULT_PATH = Path(__file__).parent / "data" / "notified.json"


def lesson_key(lesson_date: date, start_time_iso: str, subject: str) -> str:
    return f"{lesson_date.isoformat()}|{start_time_iso}|{subject}"


class NotifiedStore:
    def __init__(self, path: Path | str = DEFAULT_PATH, keep_days: int = 3):
        self.path = Path(path)
        self.keep_days = keep_days
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._keys: set[str] = self.load()

    def load(self) -> set[str]:
        if not self.path.exists():
            return set()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return set(data)
        except (json.JSONDecodeError, OSError):
            return set()

    def save(self) -> None:
        cutoff = date.today() - timedelta(days=self.keep_days)
        pruned = set()
        for key in self._keys:
            _, _, rest = key.partition("::")
            date_part = rest.split("|", 1)[0]
            try:
                key_date = date.fromisoformat(date_part)
            except ValueError:
                continue
            if key_date >= cutoff:
                pruned.add(key)
        self._keys = pruned
        self.path.write_text(
            json.dumps(sorted(self._keys), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def make_key(chat_id: int, lesson) -> str:
        return f"{chat_id}::{lesson_key(lesson.date, lesson.start_time.isoformat(), lesson.subject)}"

    def contains(self, key: str) -> bool:
        return key in self._keys

    def add(self, key: str) -> None:
        self._keys.add(key)
        self.save()
