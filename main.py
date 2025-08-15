import asyncio
import os

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.bot import DefaultBotProperties
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

from middlewares.db import DataBaseSession
from database.engine import  session_maker

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
# ALLOWED_UPDATES = ['message', 'edited_message', 'callback_query']

# ✅ Новый способ передачи parse_mode
bot = Bot(
    token=os.getenv('TOKEN'),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)


dp = Dispatcher()

dp.include_router(user_private_router)
dp.include_router(admin_menu_router)
dp.include_router(add_product_router)
dp.include_router(banner_router)
dp.include_router(banner_text_router)
dp.include_router(products_router)
dp.include_router(categories_router)
dp.include_router(settings_router)
dp.include_router(orders_router)
#dp.include_router(admin_router)
#dp.include_router(salon_creation_router)
dp.include_router(order_router)
dp.include_router(inline_router)
dp.include_router(invite_link_router)
dp.include_router(invite_creation_router)

async def on_startup(bot):
    pass

async def on_shutdown(bot):
    print('бот лег')

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    dp.update.middleware(DataBaseSession(session_pool=session_maker))

    await bot.delete_webhook(drop_pending_updates=True)
    # await bot.delete_my_commands(scope=types.BotCommandScopeAllPrivateChats())
    # await bot.set_my_commands(commands=private, scope=types.BotCommandScopeAllPrivateChats())
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

asyncio.run(main())