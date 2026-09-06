import re
from datetime import date, time
from typing import Optional

from bs4 import BeautifulSoup

from .base import (
    DAY_MONTH_RE,
    MONTHS_RU,
    NUMERIC_DATE_RE,
    TIME_RANGE_RE,
    WEEKDAY_NAMES_RU,
    Lesson,
    resolve_year,
)

NAME = "универсальный парсер"
TEACHER_RE = re.compile(r"[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.\s?[А-ЯЁ]?\.?")
ROOM_RE = re.compile(
    r"(ауд(?:итория)?\.?\s*\S+|каб(?:инет)?\.?\s*\S+|корп(?:ус)?\.?\s*\S+)",
    re.IGNORECASE,
)

STRICT_TAGS = ["tr", "li"]
BROAD_TAGS = ["tr", "li", "div", "p"]


def matches(url: str) -> bool:
    return True


def extract_time_range(text: str) -> Optional[tuple[time, time]]:
    m = TIME_RANGE_RE.search(text)
    if not m:
        return None
    h1, m1, h2, m2 = (int(x) for x in m.groups())
    try:
        return time(h1, m1), time(h2, m2)
    except ValueError:
        return None


def extract_date(text: str, today: date) -> Optional[date]:
    m = DAY_MONTH_RE.search(text)
    if m:
        day = int(m.group(1))
        month = MONTHS_RU.get(m.group(2).lower())
        if month:
            try:
                return date(resolve_year(day, month, today), month, day)
            except ValueError:
                pass
    m = NUMERIC_DATE_RE.search(text)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        if not (1 <= month <= 12):
            return None
        year_str = m.group(3)
        if year_str:
            year = int(year_str)
            if year < 100:
                year += 2000
        else:
            year = resolve_year(day, month, today)
        try:
            return date(year, month, day)
        except ValueError:
            return None
    return None


def guess_weekday(text: str) -> str:
    lowered = text.lower()
    for name in WEEKDAY_NAMES_RU:
        if name in lowered:
            return name.capitalize()
    return ""


def strip_known_bits(text: str) -> str:
    text = TIME_RANGE_RE.sub(" ", text)
    text = NUMERIC_DATE_RE.sub(" ", text)

    text = DAY_MONTH_RE.sub(
        lambda m: " " if m.group(2).lower() in MONTHS_RU else m.group(0), text
    )
    for name in WEEKDAY_NAMES_RU:
        text = re.sub(re.escape(name), " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip(" ,.-—–\t")


def split_subject_teacher_room(text: str) -> tuple[str, str, str]:
    teacher = ""
    m = TEACHER_RE.search(text)
    if m:
        teacher = m.group(0).strip()
        text = text.replace(m.group(0), " ")

    room = ""
    m = ROOM_RE.search(text)
    if m:
        room = m.group(0).strip()
        text = text.replace(m.group(0), " ")

    subject = re.sub(r"\s+", " ", text).strip(" ,.-—–\t")
    if len(subject) > 200:
        subject = subject[:200].rstrip() + "…"
    return subject, teacher, room


def try_grid_parse(soup: BeautifulSoup, today: date) -> list[Lesson]:
    lessons: list[Lesson] = []

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        header_cells = rows[0].find_all(["th", "td"])
        if len(header_cells) < 2:
            continue
        day_columns: list[Optional[date]] = []
        any_date_found = False
        for cell in header_cells[1:]:
            d = extract_date(cell.get_text(" ", strip=True), today)
            if d:
                any_date_found = True
            day_columns.append(d)
        if not any_date_found:
            continue  
        known_idx = next((i for i, d in enumerate(day_columns) if d is not None), None)
        if known_idx is not None:
            for i in range(len(day_columns)):
                if day_columns[i] is None:
                    offset = i - known_idx
                    day_columns[i] = date.fromordinal(
                        day_columns[known_idx].toordinal() + offset
                    )

        for row in rows[1:]:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            time_range = extract_time_range(cells[0].get_text(" ", strip=True))
            if not time_range:
                continue
            start_time, end_time = time_range

            for col_idx, cell in enumerate(cells[1:]):
                if col_idx >= len(day_columns) or day_columns[col_idx] is None:
                    continue
                cell_text = cell.get_text(" ", strip=True)
                if not cell_text:
                    continue
                stripped = strip_known_bits(cell_text)
                subject, teacher, room = split_subject_teacher_room(stripped)
                if not subject:
                    continue
                lessons.append(
                    Lesson(
                        date=day_columns[col_idx],
                        weekday_name="",
                        pair_number=None,
                        start_time=start_time,
                        end_time=end_time,
                        lesson_type="",
                        subject=subject,
                        teacher=teacher,
                        room=room,
                    )
                )

    lessons.sort(key=lambda l: (l.date, l.start_time))
    return lessons


def find_lesson_elements(soup: BeautifulSoup, tags: list[str]) -> list:
    matched = [
        el for el in soup.find_all(tags) if TIME_RANGE_RE.search(el.get_text(" ", strip=True))
    ]
    matched_ids = {id(e) for e in matched}
    result = []
    for el in matched:
        has_matched_descendant = any(
            id(desc) in matched_ids for desc in el.find_all(tags)
        )
        if not has_matched_descendant:
            result.append(el)
    return result


def parse_html(html: str, today: Optional[date] = None) -> list[Lesson]:
    if today is None:
        today = date.today()

    soup = BeautifulSoup(html, "html.parser")

    grid_lessons = try_grid_parse(soup, today)
    if grid_lessons:
        return grid_lessons

    lesson_elements = find_lesson_elements(soup, STRICT_TAGS)
    if not lesson_elements:
        lesson_elements = find_lesson_elements(soup, BROAD_TAGS)
    if not lesson_elements:
        return []

    lesson_ids = {id(e) for e in lesson_elements}

    current_date: Optional[date] = None
    lessons: list[Lesson] = []
    seen_keys: set[tuple] = set()

    for el in soup.find_all(True):
        if id(el) in lesson_ids:
            full_text = el.get_text(" ", strip=True)
            time_range = extract_time_range(full_text)
            if not time_range:
                continue
            start_time, end_time = time_range

            lesson_date = extract_date(full_text, today) or current_date
            if lesson_date is None:
                continue 

            weekday_name = guess_weekday(full_text)
            stripped = strip_known_bits(full_text)
            subject, teacher, room = split_subject_teacher_room(stripped)
            if not subject:
                continue

            key = (lesson_date, start_time, subject)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            lessons.append(
                Lesson(
                    date=lesson_date,
                    weekday_name=weekday_name,
                    pair_number=None,
                    start_time=start_time,
                    end_time=end_time,
                    lesson_type="",
                    subject=subject,
                    teacher=teacher,
                    room=room,
                )
            )
        else:
            own_text = " ".join(
                t.strip() for t in el.find_all(string=True, recursive=False) if t.strip()
            )
            if own_text:
                found_date = extract_date(own_text, today)
                if found_date:
                    current_date = found_date

    lessons.sort(key=lambda l: (l.date, l.start_time))
    return lessons


def looks_like_page(html: str) -> bool:
    try:
        return len(parse_html(html)) > 0
    except Exception:
        return False
