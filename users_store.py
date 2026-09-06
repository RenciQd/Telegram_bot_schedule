from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

DEFAULT_PATH = Path(__file__).parent / "data" / "users.json"


class UsersStore:
    def __init__(self, path: Path | str = DEFAULT_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, dict] = self.load()

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

    def set_url(self, chat_id: int, url: str) -> None:
        key = str(chat_id)
        existing_muted = self._data.get(key, {}).get("muted", False)
        self._data[key] = {
            "url": url,
            "muted": existing_muted,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.save()

    def get_url(self, chat_id: int) -> Optional[str]:
        entry = self._data.get(str(chat_id))
        return entry["url"] if entry else None

    def set_muted(self, chat_id: int, muted: bool) -> bool:
        key = str(chat_id)
        entry = self._data.get(key)
        if not entry:
            return False
        entry["muted"] = muted
        self._save()
        return True

    def is_muted(self, chat_id: int) -> bool:
        entry = self._data.get(str(chat_id))
        return bool(entry.get("muted")) if entry else False

    def remove(self, chat_id: int) -> bool:
        key = str(chat_id)
        if key in self._data:
            del self._data[key]
            self._save()
            return True
        return False

    def items(self) -> list[tuple[int, str]]:
        return [(int(chat_id), entry["url"]) for chat_id, entry in self._data.items()]
