from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Optional

import requests
from bs4 import BeautifulSoup

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


def parse_date_cell(th, today: date) -> Optional[date]:
    small = th.find("small")
    if not small:
        return None
    m = DAY_MONTH_RE.search(small.get_text(" ", strip=True))
    if not m:
        return None
    day = int(m.group(1))
    month_name = m.group(2).lower()
    month = MONTHS_RU.get(month_name)
    if not month:
        return None
    year = resolve_year(day, month, today)
    return date(year, month, day)


def parse_time_range(cell_text: str) -> Optional[tuple[time, time]]:
    m = TIME_RANGE_RE.search(cell_text)
    if not m:
        return None
    h1, m1, h2, m2 = (int(x) for x in m.groups())
    return time(h1, m1), time(h2, m2)


def parse_lesson_cell(td) -> Optional[dict]:
    lesson_div = td.find("div", class_="timetable__grid-day-lesson")
    if lesson_div is None:
        return None

    lesson_type = ""
    type_span = lesson_div.find("span")
    if type_span:
        lesson_type = type_span.get_text(strip=True)
        type_span.extract()

    subject = lesson_div.get_text(" ", strip=True)
    if not subject:
        return None 

    teacher = ""
    teacher_link = td.find("a", class_="icon-academic-cap")
    if teacher_link:
        teacher = teacher_link.get(
            "title", teacher_link.get_text(strip=True)
        ).strip()

    room = ""
    room_link = td.find("a", class_="icon-location")
    if room_link:
        room = room_link.get_text(strip=True)
        building_room = room_link.get("title", "").strip()
        if building_room:
            room = f"{room} ({building_room})"

    return {
        "lesson_type": lesson_type,
        "subject": subject,
        "teacher": teacher,
        "room": room,
    }


def parse_html(html: str, today: Optional[date] = None) -> list[Lesson]:
    if today is None:
        today = date.today()

    soup = BeautifulSoup(html, "html.parser")
    lessons: list[Lesson] = []

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue

        header_cells = rows[0].find_all("th")
        if len(header_cells) < 2:
            continue

        day_columns: list[tuple[str, Optional[date]]] = []
        for th in header_cells[1:]:
            weekday_name = th.get_text(" ", strip=True)
            small = th.find("small")
            if small:
                date_text = small.get_text(strip=True)
                weekday_name = weekday_name.replace(date_text, "").strip()
            col_date = parse_date_cell(th, today)
            day_columns.append((weekday_name, col_date))
        known_idx = next(
            (i for i, (_, d) in enumerate(day_columns) if d is not None), None
        )
        if known_idx is not None:
            for i in range(len(day_columns)):
                if day_columns[i][1] is None:
                    offset = i - known_idx
                    name = day_columns[i][0]
                    day_columns[i] = (
                        name,
                        day_columns[known_idx][1].fromordinal(
                            day_columns[known_idx][1].toordinal() + offset
                        ),
                    )

        for row in rows[1:]:
            cells = row.find_all("td")
            if not cells:
                continue
            time_cell_text = cells[0].get_text(" ", strip=True)
            pair_match = PAIR_NUM_RE.search(time_cell_text)
            pair_number = int(pair_match.group(1)) if pair_match else None
            time_range = parse_time_range(time_cell_text)
            if not time_range:
                continue
            start_time, end_time = time_range

            for col_idx, day_cell in enumerate(cells[1:]):
                if col_idx >= len(day_columns):
                    break
                weekday_name, col_date = day_columns[col_idx]
                if col_date is None:
                    continue
                parsed = parse_lesson_cell(day_cell)
                if parsed is None:
                    continue
                lessons.append(
                    Lesson(
                        date=col_date,
                        weekday_name=weekday_name,
                        pair_number=pair_number,
                        start_time=start_time,
                        end_time=end_time,
                        lesson_type=parsed["lesson_type"],
                        subject=parsed["subject"],
                        teacher=parsed["teacher"],
                        room=parsed["room"],
                    )
                )

    lessons.sort(key=lambda l: (l.date, l.start_time))
    return lessons


def looks_like_schedule_page(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="timetable__grid")
    if table is None:
        return False
    header_cells = table.find("tr")
    return header_cells is not None and len(header_cells.find_all("th")) >= 2


def fetch_html(url: str, timeout: int = 20) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def fetch_lessons(url: str, today: Optional[date] = None) -> list[Lesson]:
    html = fetch_html(url)
    return parse_html(html, today=today)


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "https://www.miit.ru/timetable/189527"
    for lesson in fetch_lessons(target):
        print(lesson.date, lesson.weekday_name, lesson.start_time, lesson.end_time, lesson.lesson_type, lesson.subject, "|", lesson.teacher, "|", lesson.room)
