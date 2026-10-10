import asyncio
import logging
import sys
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import config
import database as db
from handlers import user, reviewer, admin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def handle_ping(request):
    return web.Response(text="Bot is running! 🚀", content_type="text/plain")

async def start_web_server():
    # Запускаем встроенный легкий веб-сервер для поддержки хостингов (например Render Web Service)
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.PORT)
    await site.start()
    logger.info(f"Healthcheck HTTP сервер запущен на порту {config.PORT}")
    return runner

async def main():
    if not config.BOT_TOKEN:
        logger.error("КРИТИЧЕСКАЯ ОШИБКА: BOT_TOKEN не указан в файле .env!")
        logger.error("Пожалуйста, отредактируйте файл .env и укажите BOT_TOKEN=ваш_токен")
        sys.exit(1)

    # Инициализация базы данных SQLite
    await db.init_db()
    logger.info("База данных успешно инициализирована.")

    # Запуск легкого web-сервера для healthcheck (Render / PaaS)
    web_runner = await start_web_server()

    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрация роутеров
    dp.include_router(admin.router)
    dp.include_router(reviewer.router)
    dp.include_router(user.router)

    # Получаем информацию о боте
    try:
        me = await bot.get_me()
        logger.info(f"Бот успешно запущен: @{me.username} ({me.full_name})")
    except Exception as e:
        logger.error(f"Не удалось подключиться к Telegram API: {e}")
        sys.exit(1)
    
    # Сброс старых апдейтов
    await bot.delete_webhook(drop_pending_updates=True)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await web_runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
