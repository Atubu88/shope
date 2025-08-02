from __future__ import annotations

from html import escape
from typing import Optional

from aiogram import Router, F
from aiogram.client.bot import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Salon
from database.orm_query import orm_get_user_salons

# ──────────────────────────────────────────────────────────────────────────

admin_menu_router = Router()


# ─────────────────────────── клавиатура админ‑меню ───────────────────────
def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить товар",
                                  callback_data="admin_add_product")],
            [InlineKeyboardButton(text="📋 Ассортимент",
                                  callback_data="admin_products")],
            [InlineKeyboardButton(text="\uD83D\uDCC2 Категории",
                                  callback_data="admin_categories")],
            [InlineKeyboardButton(text="🎨 Добавить/Изменить баннер",
                                  callback_data="admin_banners")],
            [InlineKeyboardButton(text="✏️ Описание баннера",
                                  callback_data="admin_banner_text")],
            [InlineKeyboardButton(text="🛒 Заказы",
                                  callback_data="admin_orders")],
            [InlineKeyboardButton(text="🏠 Создать салон",
                                  callback_data="admin_create_salon")],
            [InlineKeyboardButton(text="⚙️ Настройки",
                                  callback_data="admin_settings")],
        ]
    )


# ─────────────────────────── показываем админ‑меню ───────────────────────
async def show_admin_menu(state: FSMContext,
                          chat_id: int,
                          bot: Bot,
                          session: AsyncSession) -> None:
    """
    • Пытается отредактировать старое сообщение‑меню.
    • Если не удаётся (удалено, медиа, устарело) – создаёт новое и
      сохраняет его `message_id` в FSM.
    • Название салона экранируется через `html.escape`, чтобы избежать
      ошибки «Unsupported start tag».
    """
    data = await state.get_data()
    message_id: Optional[int] = data.get("main_message_id")

    # ───── 1. определяем salon_id ────────────────────────────────────────
    salon_id: Optional[int] = data.get("salon_id")
    if salon_id is None:                                 # не было в FSM
        user_salons = await orm_get_user_salons(session, chat_id)
        if user_salons:
            salon_id = user_salons[0].salon_id
            await state.update_data(salon_id=salon_id)

    # ───── 2. получаем (или задаём по умолчанию) имя салона ──────────────
    if salon_id:
        salon: Optional[Salon] = await session.get(Salon, salon_id)
        raw_name = salon.name if salon else "Салон"
    else:
        raw_name = "Салон"

    safe_name = escape(str(raw_name))
    text = f"Добро пожаловать в админ панель <b>{safe_name}</b>!"
    kb = admin_keyboard()

    # ───── 3. пытаемся отредактировать старое сообщение меню ─────────────
    if message_id:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=kb,
                parse_mode="HTML",
            )
            return                                  # успех – выходим
        except TelegramBadRequest:
            # Возможно, сообщение медиа, удалено или старше 48 ч
            try:
                await bot.delete_message(chat_id, message_id)
            except TelegramBadRequest:
                pass                                # игнорируем, если и удалить не смогли

    # ───── 4. создаём новое сообщение меню ───────────────────────────────
    msg = await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=kb,
        parse_mode="HTML",
    )
    await state.update_data(main_message_id=msg.message_id)


# ─────────────────────────── хендлеры «/admin» и callback ────────────────
@admin_menu_router.message(Command("admin"))
async def open_admin(message: Message,
                     state: FSMContext,
                     session: AsyncSession) -> None:
    """
    Вход в админ‑панель по команде /admin.
    Сохраняем salon_id пользователя в FSM, чтобы им могли пользоваться
    другие модули (товары, баннеры и др.).
    """
    user_salons = await orm_get_user_salons(session, message.from_user.id)
    if user_salons:
        await state.update_data(salon_id=user_salons[0].salon_id)

    await show_admin_menu(state, message.chat.id, message.bot, session)


@admin_menu_router.callback_query(F.data == "admin_menu")
async def cb_admin_menu(callback: CallbackQuery,
                        state: FSMContext,
                        session: AsyncSession) -> None:
    """Кнопка «⬅️ В меню» из других разделов."""
    await show_admin_menu(state, callback.message.chat.id, callback.bot, session)
    await callback.answer()