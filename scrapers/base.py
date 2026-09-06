from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Optional

import requests

MONTHS_RU = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}

TIME_RANGE_RE = re.compile(
    r"(\d{1,2}):(\d{2})\s*[-—–]\s*(\d{1,2}):(\d{2})"
)

PAIR_NUM_RE = re.compile(r"(\d+)\s*пара")
DAY_MONTH_RE = re.compile(r"(\d{1,2})\s+([а-яё]+)", re.IGNORECASE)
NUMERIC_DATE_RE = re.compile(r"(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?")

WEEKDAY_NAMES_RU = [
    "понедельник",
    "вторник",
    "среда",
    "четверг",
    "пятница",
    "суббота",
    "воскресенье",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}


@dataclass
class Lesson:
    date: date
    weekday_name: str
    pair_number: Optional[int]
    start_time: time
    end_time: time
    lesson_type: str  
    subject: str
    teacher: str
    room: str

    @property
    def start_dt(self) -> datetime:
        return datetime.combine(self.date, self.start_time)

    def format_for_telegram(self) -> str:
        parts = [
            f"<b>{self.start_time.strftime('%H:%M')}–{self.end_time.strftime('%H:%M')}</b>"
            f" (за час до начала)"
        ]
        header = self.subject
        if self.lesson_type:
            header = f"{self.lesson_type}: {header}"
        parts.append(header)
        if self.teacher:
            parts.append(f"{self.teacher}")
        if self.room:
            parts.append(f"{self.room}")
        return "\n".join(parts)


def resolve_year(day: int, month: int, today: date) -> int:
    candidate = date(today.year, month, day)
    delta_days = (candidate - today).days
    if delta_days < -300:
        candidate = date(today.year + 1, month, day)
    elif delta_days > 300:
        candidate = date(today.year - 1, month, day)
    return candidate.year


def fetch_html(url: str, timeout: int = 20) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text
