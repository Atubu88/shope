import os
import asyncio
import logging
from dotenv import find_dotenv, load_dotenv

# Сразу грузим .env
load_dotenv(find_dotenv())

# Базовая настройка логгера (единая для всего проекта)
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s %(levelname)s:%(name)s:%(message)s",
)

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.bot import DefaultBotProperties
from aiogram.types.error_event import ErrorEvent

# 🟢 Middleware
from middlewares.db import DataBaseSession
from middlewares.user_locale import UserLocaleMiddleware
from database.engine import session_maker

# 🟢 Роутеры
from handlers.user_private import user_private_router
from handlersadmin.add_product import add_product_router
from handlersadmin.products import products_router
from handlersadmin.categories import categories_router
from handlersadmin.banner import banner_router
from handlersadmin.banner_description import banner_text_router
from handlersadmin.settings import settings_router
from handlersadmin.orders import orders_router
from handlers.order_processing import order_router
from handlersadmin.menu import admin_menu_router
from handlers.inline_mode import inline_router
from handlers.invite_creation import invite_creation_router
from handlers.invite_link import invite_link_router

# ✅ Проверка токена заранее
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    logging.critical("TOKEN is not set")
    raise SystemExit(1)

# ВАЖНО: не создаём новый I18n здесь — используем utils/i18n
bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

dp = Dispatcher()

# ✅ Подключение роутеров
dp.include_router(user_private_router)
dp.include_router(admin_menu_router)
dp.include_router(add_product_router)
dp.include_router(banner_router)
dp.include_router(banner_text_router)
dp.include_router(products_router)
dp.include_router(categories_router)
dp.include_router(settings_router)
dp.include_router(orders_router)
dp.include_router(order_router)
dp.include_router(inline_router)
dp.include_router(invite_link_router)
dp.include_router(invite_creation_router)


async def on_startup(bot: Bot):
    logging.info("✅ Бот запущен")


async def on_shutdown(bot: Bot):
    logging.info("❌ Бот остановлен")


async def on_error(event: ErrorEvent):
    # Глобальный лог необработанных ошибок
    logging.exception("Unhandled error: %s", event)


async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    dp.errors.register(on_error)

    # 1) сначала БД — кладёт session в data
    dp.update.middleware(DataBaseSession(session_pool=session_maker))

    # 2) язык — навешиваем на message и callback_query (надёжнее, чем update)
    dp.message.middleware(UserLocaleMiddleware())
    dp.callback_query.middleware(UserLocaleMiddleware())

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        logging.exception("Fatal error in main")
        raise
