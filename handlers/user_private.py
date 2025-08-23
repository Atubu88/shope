from aiogram import F, types, Router
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from utils.i18n import _, i18n  # ✅ единый i18n и gettext
from common.bot_cmds_list import set_commands
from database.models import Salon, User, UserSalon
from database.orm_query import (
    orm_add_to_cart,
    orm_add_user,
    orm_get_salons,
    orm_get_user_salons,
    orm_get_salon_by_slug,
    orm_get_product,
    orm_get_products,
    orm_get_user,
    orm_set_user_language,
)

from filters.chat_types import ChatTypeFilter
from handlers.invite_creation import InviteFilter
from handlers.menu_processing import get_menu_content, products
from kbds.inline import MenuCallBack, SalonCallBack, get_salon_btns


user_private_router = Router()
user_private_router.message.filter(ChatTypeFilter(["private"]))



@user_private_router.message(CommandStart())
async def start_cmd(message: types.Message, session: AsyncSession):
    user_id = message.from_user.id

    # Регистрируем пользователя в БД (если его нет)
    result = await session.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            user_id=user_id,
            language=message.from_user.language_code or "ru",
        )
        session.add(user)
        await session.commit()

    # Обработка deep-link /start с параметром (в т.ч. startapp)
    args = message.get_args()
    slug = None
    if args:
        # startapp передаёт параметр как "app=<slug>"
        if args.startswith("app="):
            slug = args[4:]
        else:
            slug = args

    if slug:
        salon = await orm_get_salon_by_slug(session, slug)
        if salon:
            # Создаём/обновляем связь User↔Salon и отмечаем как MRU
            await orm_add_user(
                session,
                user_id=user_id,
                salon_id=salon.id,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
            )
            await session.execute(
                update(UserSalon)
                .where(
                    UserSalon.user_id == user_id,
                    UserSalon.salon_id == salon.id,
                )
                .values(updated=func.now())
            )
            await session.commit()

    await message.answer(
        f"Привет, {message.from_user.first_name}!\n\n"
        "Добро пожаловать 👋\n"
        "Нажми кнопку внизу «Открыть приложение»."
    )