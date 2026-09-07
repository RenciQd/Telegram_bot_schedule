from __future__ import annotations

import asyncio
import logging
import re
from datetime import date, datetime, timedelta
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, Update

import config
from scrapers import Lesson, fetch_html, is_generic, looks_like_schedule_page, parse_html
from schedule_cache_store import ScheduleCacheStore
from storage import NotifiedStore
from users_store import UsersStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("miit_schedule_bot")

URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)


def now() -> datetime:
    return datetime.now(config.TIMEZONE)


users_store = UsersStore()
notified_store = NotifiedStore()
schedule_cache = ScheduleCacheStore()

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()


async def process_webhook_update(data: dict) -> None:
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)


async def refresh_cache_if_needed(chat_id: int, url: str, force: bool = False) -> None:
    cached = await schedule_cache.get(chat_id)
    if cached and not force:
        _, fetched_at = cached
        if now() - fetched_at <= timedelta(minutes=config.REFRESH_SCHEDULE_MINUTES):
            return
    try:
        html = await asyncio.to_thread(fetch_html, url)
        lessons = parse_html(url, html, today=date.today())
        await schedule_cache.set(chat_id, lessons, now())
        log.info("Обновил расписание для %s, пар в кэше: %d", chat_id, len(lessons))
    except Exception:
        log.exception("Не удалось обновить расписание для %s", chat_id)


async def lessons_for(chat_id: int, target_date: date) -> Optional[list[Lesson]]:
    url = await users_store.get_url(chat_id)
    if not url:
        return None
    await refresh_cache_if_needed(chat_id, url)
    cached = await schedule_cache.get(chat_id)
    if not cached:
        return []
    lessons, _ = cached
    return [l for l in lessons if l.date == target_date]


def notifications_keyboard(muted: bool) -> InlineKeyboardMarkup:
    if muted:
        button = InlineKeyboardButton(text="🔔 Включить уведомления", callback_data="unmute")
    else:
        button = InlineKeyboardButton(text="🔕 Остановить уведомления", callback_data="mute")
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


def format_day(target_date: date, lessons: list[Lesson]) -> str:
    if not lessons:
        return f"На {target_date.strftime('%d.%m.%Y')} пар нет"
    lines = [f"Расписание на {target_date.strftime('%d.%m.%Y')}:"]
    for l in lessons:
        header = l.subject if not l.lesson_type else f"{l.lesson_type}: {l.subject}"
        line = f"\n{l.start_time.strftime('%H:%M')}–{l.end_time.strftime('%H:%M')} — {header}"
        if l.teacher:
            line += f"\n {l.teacher}"
        if l.room:
            line += f"\n {l.room}"
        lines.append(line)
    return "\n".join(lines)


async def try_register(message: Message, url: str) -> None:
    url = url.strip()
    if not URL_RE.match(url):
        await message.answer(
            "Это не похоже на ссылку. Пришли адрес страницы"
            "расписания целиком, например:\nhttps://www.miit.ru/timetable/12345"
        )
        return

    status = await message.answer("Проверяю ссылку, пару сек...")
    try:
        html = await asyncio.to_thread(fetch_html, url)
    except Exception as e:
        log.warning("Не удалось скачать присланную ссылку: %s", e)
        await status.edit_text(
            f"Не получилось загрузить страницу ({e}).\n"
            "Проверь ссылку (открывается ли она в браузере) и пришли ещё раз."
        )
        return

    if not looks_like_schedule_page(url, html):
        await status.edit_text(
            "Страница загрузилась, но я не нашёл в ней знакомую таблицу "
            "расписания. Убедись, что это ссылка вида и пришли ещё раз"
        )
        return

    lessons = parse_html(url, html, today=date.today())
    await users_store.set_url(message.chat.id, url)
    await schedule_cache.set(message.chat.id, lessons, now())
    muted = await users_store.is_muted(message.chat.id)

    heads_up = ""
    if is_generic(url):
        heads_up = (
            "Такой тип расписания я вижу впервые и ещё не умею его анализировать. Пожалуйста, подождите следующего обновления и я обязательно научусь :)\n\n"
        )
    await status.edit_text(
        f"Готово, запомнил эту ссылку!\n"
        f"На ближайшие две недели нашёл пар: {len(lessons)}.\n"
        f"Буду присылать напоминание за {config.REMIND_BEFORE_MINUTES} мин до начала каждой.\n\n"
        "/today — расписание на сегодня\n"
        "/tomorrow — расписание на завтра\n"
        "/refresh — перечитать расписание с сайта прямо сейчас\n"
        "/forget — забыть эту ссылку",
        reply_markup=notifications_keyboard(muted),
    )


@dp.message(Command("start"))
async def cmd_start(message: Message) -> None:
    existing = await users_store.get_url(message.chat.id)
    if existing:
        muted = await users_store.is_muted(message.chat.id)
        status_line = "🔕 сейчас выключены" if muted else "🔔 сейчас включены"
        await message.answer(
            f"У тебя уже есть это расписание \n{existing}\n"
            f"Уведомления {status_line}.\n\n"
            "Если это не та ссылка — просто пришли новую, я заменю.\n\n"
            "/today /tomorrow /refresh /forget",
            reply_markup=notifications_keyboard(muted),
        )
        return
    await message.answer(
        "Хело, я твой личный помощник в расписании вуза, пока я только тестовая модель "
        "так что не злитесь на меня слишком сильно(я буду плакать)\n\n"
        "Пришли мне ссылку на страницу расписания своей группы и я постараюсь быть полезным"
    )


@dp.message(Command("link"))
async def cmd_link(message: Message, command: CommandObject) -> None:
    if not command.args:
        await message.answer(
            "Пришли ссылку вот так: /link https://www.miit.ru/timetable/12345"
        )
        return
    await try_register(message, command.args)


@dp.message(Command("today"))
async def cmd_today(message: Message) -> None:
    today = date.today()
    lessons = await lessons_for(message.chat.id, today)
    if lessons is None:
        await message.answer(
            "Сначала пришли мне ссылку на расписание — просто вставь её "
            "текстом, например https://www.miit.ru/timetable/12345"
        )
        return
    await message.answer(format_day(today, lessons))


@dp.message(Command("tomorrow"))
async def cmd_tomorrow(message: Message) -> None:
    tomorrow = date.today() + timedelta(days=1)
    lessons = await lessons_for(message.chat.id, tomorrow)
    if lessons is None:
        await message.answer(
            "Сначала пришли мне ссылку на расписание — просто вставь её "
            "текстом, например https://www.miit.ru/timetable/12345"
        )
        return
    await message.answer(format_day(tomorrow, lessons))


@dp.message(Command("refresh"))
async def cmd_refresh(message: Message) -> None:
    url = await users_store.get_url(message.chat.id)
    if not url:
        await message.answer("Сначала пришли ссылку на расписание.")
        return
    await refresh_cache_if_needed(message.chat.id, url, force=True)
    cached = await schedule_cache.get(message.chat.id)
    count = len(cached[0]) if cached else 0
    await message.answer(f"Готово, обновил. Пар в кэше: {count}")


@dp.message(Command("forget"))
async def cmd_forget(message: Message) -> None:
    removed = await users_store.remove(message.chat.id)
    await schedule_cache.forget(message.chat.id)
    if removed:
        await message.answer("Забыл эту ссылку. Пришли новую, когда понадобится.")
    else:
        await message.answer("У тебя и так не было сохранённой ссылки.")


@dp.message(Command("mute"))
async def cmd_mute(message: Message) -> None:
    if not await users_store.set_muted(message.chat.id, True):
        await message.answer("У тебя ещё нет сохранённой ссылки на расписание.")
        return
    await message.answer(
        "🔕 Уведомления выключены. Ссылку и расписание я не забыл — когда "
        "захочешь вернуть напоминания, нажми кнопку ниже или пришли /unmute.",
        reply_markup=notifications_keyboard(muted=True),
    )


@dp.message(Command("unmute"))
async def cmd_unmute(message: Message) -> None:
    if not await users_store.set_muted(message.chat.id, False):
        await message.answer("У тебя ещё нет сохранённой ссылки на расписание.")
        return
    await message.answer(
        "🔔 Уведомления снова включены — буду слать напоминания как раньше.",
        reply_markup=notifications_keyboard(muted=False),
    )


@dp.callback_query(F.data.in_({"mute", "unmute"}))
async def handle_mute_button(callback: CallbackQuery) -> None:
    chat_id = callback.message.chat.id
    muted = callback.data == "mute"
    if not await users_store.set_muted(chat_id, muted):
        await callback.answer("У тебя ещё нет сохранённой ссылки на расписание.", show_alert=True)
        return
    text = (
        "🔕 Уведомления выключены. Ссылку и расписание я не забыл — нажми "
        "кнопку ниже, когда захочешь вернуть напоминания."
        if muted
        else "🔔 Уведомления снова включены — буду слать напоминания как раньше."
    )
    await callback.message.edit_text(text, reply_markup=notifications_keyboard(muted))
    await callback.answer("Готово")


@dp.message(F.text)
async def handle_text(message: Message) -> None:
    text = message.text.strip()
    if text.startswith("/"):
        await message.answer("Я такое не умею, я глупи. /start поможет.")
        return
    await try_register(message, text)


async def run_reminder_check() -> None:
    window = timedelta(minutes=config.REMINDER_WINDOW_MINUTES)
    remind_before = timedelta(minutes=config.REMIND_BEFORE_MINUTES)
    current = now()

    for chat_id, url in await users_store.items():
        if await users_store.is_muted(chat_id):
            continue
        try:
            await refresh_cache_if_needed(chat_id, url)
        except Exception:
            log.exception("Не удалось обновить расписание для %s в проверке напоминаний", chat_id)
            continue
        cached = await schedule_cache.get(chat_id)
        if not cached:
            continue
        lessons, _ = cached
        for lesson in lessons:
            start_dt = datetime.combine(lesson.date, lesson.start_time, tzinfo=config.TIMEZONE)
            delta = start_dt - current
            if remind_before - window <= delta <= remind_before + window:
                key = notified_store.make_key(chat_id, lesson)
                if not await notified_store.contains(key):
                    try:
                        await bot.send_message(chat_id, lesson.format_for_telegram())
                        await notified_store.add(key)
                        log.info("Отправлено напоминание %s: %s", chat_id, key)
                    except Exception:
                        log.exception("Не удалось отправить напоминание %s", chat_id)
