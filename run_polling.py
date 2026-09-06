import asyncio
import bot
import config

log = bot.log

async def reminder_loop() -> None:
    while True:
        try:
            await bot.run_reminder_check()
        except Exception:
            log.exception("Ошибка в цикле напоминаний")
        await asyncio.sleep(config.CHECK_INTERVAL_SECONDS)


async def main() -> None:
    log.info("Бот запущен (режим: вечный процесс), слежу за расписаниями...")
    asyncio.create_task(reminder_loop())
    await bot.dp.start_polling(bot.bot)


if __name__ == "__main__":
    asyncio.run(main())
