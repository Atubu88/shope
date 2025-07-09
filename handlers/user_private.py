from aiogram import F, types, Router
from aiogram.filters import CommandStart

from sqlalchemy.ext.asyncio import AsyncSession
from database.orm_query import (
    orm_add_to_cart,
    orm_add_user,
    orm_get_salons,
    orm_get_user,
)

from filters.chat_types import ChatTypeFilter
from handlers.menu_processing import get_menu_content
from kbds.inline import MenuCallBack, get_callback_btns, SalonCallBack, get_salon_btns



user_private_router = Router()
user_private_router.message.filter(ChatTypeFilter(["private"]))


@user_private_router.message(CommandStart())
async def start_cmd(message: types.Message, session: AsyncSession):
    args = message.text.split()
    salon_id = int(args[1]) if len(args) > 1 else None
    user = await orm_get_user(session, message.from_user.id)
    if salon_id is None and user:
        salon_id = user.salon_id
    if salon_id is None:
        salons = await orm_get_salons(session)
        await message.answer("Выберите салон", reply_markup=get_salon_btns(salons))
        return
    await orm_add_user(
        session,
        user_id=message.from_user.id,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        phone=None,
        salon_id=salon_id,
    )
    media, reply_markup = await get_menu_content(session, level=0, menu_name="main", user_id=message.from_user.id)
    await message.answer_photo(media.media, caption=media.caption, reply_markup=reply_markup)


async def add_to_cart(callback: types.CallbackQuery, callback_data: MenuCallBack, session: AsyncSession):
    user = callback.from_user
    await orm_add_user(
        session,
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=None,
        salon_id=(await orm_get_user(session, user.id)).salon_id if await orm_get_user(session, user.id) else None,
    )
    await orm_add_to_cart(session, user_id=user.id, product_id=callback_data.product_id)
    await callback.answer("Товар добавлен в корзину.")


@user_private_router.callback_query(SalonCallBack.filter())
async def choose_salon(callback: types.CallbackQuery, callback_data: SalonCallBack, session: AsyncSession):
    await orm_add_user(
        session,
        user_id=callback.from_user.id,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name,
        phone=None,
        salon_id=callback_data.salon_id,
    )
    media, reply_markup = await get_menu_content(
        session,
        level=0,
        menu_name="main",
        user_id=callback.from_user.id,
    )
    await callback.message.edit_text("Салон выбран")
    await callback.message.answer_photo(media.media, caption=media.caption, reply_markup=reply_markup)


@user_private_router.callback_query(MenuCallBack.filter())
async def user_menu(callback: types.CallbackQuery, callback_data: MenuCallBack, session: AsyncSession):

    if callback_data.menu_name == "add_to_cart":
        await add_to_cart(callback, callback_data, session)
        return

    media, reply_markup = await get_menu_content(
        session,
        level=callback_data.level,
        menu_name=callback_data.menu_name,
        category=callback_data.category,
        page=callback_data.page,
        product_id=callback_data.product_id,
        user_id=callback.from_user.id,
    )

    await callback.message.edit_media(media=media, reply_markup=reply_markup)
    await callback.answer()