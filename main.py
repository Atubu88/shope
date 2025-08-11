import asyncio
import os

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.bot import DefaultBotProperties
from dotenv import load_dotenv, find_dotenv

# === Загружаем .env или .env.prod и ПЕРЕПИСЫВАЕМ системные переменные ===
env_file = ".env.prod" if os.getenv("ENV") == "prod" else ".env"
load_dotenv(find_dotenv(env_file), override=True)
print(f"[Bot] Загружен файл переменных: {env_file}")

from middlewares.db import DataBaseSession
from database.engine import session_maker  # единый session_maker из одного места
from common.bot_cmds_list import user_commands

# Routers
from handlers.user_private import user_private_router
from handlers.admin_private import admin_router
from handlersadmin.add_product import add_product_router
from handlersadmin.products import products_router
from handlersadmin.categories import categories_router
from handlersadmin.banner import banner_router
from handlersadmin.banner_description import banner_text_router
from handlersadmin.settings import settings_router
from handlersadmin.orders import orders_router
from handlers.order_processing import order_router
from handlers.salon_creation import salon_creation_router
from handlersadmin.menu import admin_menu_router
from handlers.inline_mode import inline_router
from handlers.invite_creation import invite_creation_router
from handlers.invite_link import invite_link_router


TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise RuntimeError("TOKEN is not set")

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()

# Подключаем роутеры
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
    await bot.set_my_commands(user_commands, scope=types.BotCommandScopeAllPrivateChats())
    print("[Bot] Запущен!")

async def on_shutdown(bot: Bot):
    print("[Bot] Остановлен.")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # ВАЖНО: используем ровно тот session_maker, что создаётся в database.engine
    dp.update.middleware(DataBaseSession(session_pool=session_maker))

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
