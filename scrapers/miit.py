# Отдельно для Миит(ради него создавался весь этот прикол)
from datetime import date
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .base import DAY_MONTH_RE, MONTHS_RU, PAIR_NUM_RE, TIME_RANGE_RE, Lesson, resolve_year

NAME = "РутМиит"


def matches(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == "miit.ru" or host.endswith(".miit.ru")

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


def parse_time_range(cell_text: str):
    m = TIME_RANGE_RE.search(cell_text)
    if not m:
        return None
    h1, m1, h2, m2 = (int(x) for x in m.groups())
    from datetime import time as _time

    return _time(h1, m1), _time(h2, m2)


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


def looks_like_page(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="timetable__grid")
    if table is None:
        return False
    header_cells = table.find("tr")
    return header_cells is not None and len(header_cells.find_all("th")) >= 2
