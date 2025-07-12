from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    Message,
)
from aiogram.client.bot import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Salon
from database.orm_query import orm_get_user

admin_menu_router = Router()

def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить товар", callback_data="admin_add_product")],
            [InlineKeyboardButton(text="📋 Ассортимент", callback_data="admin_products")],
            [InlineKeyboardButton(text="🎨 Добавить/Изменить баннер", callback_data="admin_banners")],
            [InlineKeyboardButton(text="🏠 Создать салон", callback_data="admin_create_salon")],
        ]
    )

async def show_admin_menu(state: FSMContext, chat_id: int, bot: Bot, session: AsyncSession):
    data = await state.get_data()
    message_id = data.get("main_message_id")

    # Получаем salon_id из FSMContext или из базы по user_id
    salon_id = data.get("salon_id")
    if not salon_id:
        # fallback: берем salon_id из пользователя
        user = await orm_get_user(session, chat_id)
        salon_id = user.salon_id if user else None
        if salon_id:
            await state.update_data(salon_id=salon_id)

    salon_name = "Салон"
    if salon_id:
        salon = await session.get(Salon, salon_id)
        if salon:
            salon_name = salon.name

    text = f"Добро пожаловать в админ панель <b>{salon_name}</b>!"
    kb = admin_keyboard()

    # Надежная обработка ситуации: сообщение - текст/медиа
    if message_id:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=kb,
                parse_mode="HTML",
            )
        except Exception:
            # Если не получилось редактировать (например, сообщение было медиа), удаляем и создаём новое
            await bot.delete_message(chat_id, message_id)
            msg = await bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")
            await state.update_data(main_message_id=msg.message_id)
    else:
        msg = await bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")
        await state.update_data(main_message_id=msg.message_id)

@admin_menu_router.message(Command("admin"))
async def open_admin(message: Message, state: FSMContext, session: AsyncSession):
    # Получаем user и его salon_id, чтобы сохранить его в FSM (для будущих переходов)
    user = await orm_get_user(session, message.from_user.id)
    salon_id = user.salon_id if user else None
    if salon_id:
        await state.update_data(salon_id=salon_id)
    await show_admin_menu(state, message.chat.id, message.bot, session)

@admin_menu_router.callback_query(F.data == "admin_menu")
async def cb_admin_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await show_admin_menu(state, callback.message.chat.id, callback.bot, session)
    await callback.answer()
