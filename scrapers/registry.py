from datetime import date
from typing import Optional

from . import generic, miit
from .base import Lesson, fetch_html as fetch_html

SCRAPERS = [miit, generic]

def pick_scraper(url: str):
    for scraper in SCRAPERS:
        if scraper.matches(url):
            return scraper
    return generic

def engine_name(url: str) -> str:
    return pick_scraper(url).NAME

def is_generic(url: str) -> bool:
    return pick_scraper(url) is generic


def fetch_html(url: str, timeout: int = 20) -> str:
    return fetch_html(url, timeout=timeout)

def parse_html(url: str, html: str, today: Optional[date] = None) -> list[Lesson]:
    return pick_scraper(url).parse_html(html, today=today)

def looks_like_schedule_page(url: str, html: str) -> bool:
    return pick_scraper(url).looks_like_page(html)

def fetch_lessons(url: str, today: Optional[date] = None) -> list[Lesson]:
    html = fetch_html(url)
    return parse_html(url, html, today=today)
