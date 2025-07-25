from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from .menu import show_admin_menu
from database.orm_query import orm_update_salon_location, orm_get_user, orm_update_salon_group_chat
from filters.chat_types import IsAdmin
from aiogram import types
from aiogram.filters import Command

settings_router = Router()


class LocationFSM(StatesGroup):
    waiting_location = State()


def settings_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="\U0001F4CD Указать адрес салона",
                                   callback_data="set_salon_location")],
            [InlineKeyboardButton(text="\u2B05\uFE0F В меню",
                                   callback_data="admin_menu")],
        ]
    )


@settings_router.callback_query(F.data == "admin_settings")
async def open_settings(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    message_id = data.get("main_message_id") or callback.message.message_id
    salon_id = data.get("salon_id")
    await state.clear()
    await state.update_data(main_message_id=message_id, salon_id=salon_id)
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=message_id,
        text="Меню настроек:",
        reply_markup=settings_kb(),
    )
    await callback.answer()


@settings_router.callback_query(F.data == "set_salon_location")
async def ask_location(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    message_id = data.get("main_message_id") or callback.message.message_id
    await state.set_state(LocationFSM.waiting_location)
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=message_id,
        text="Отправьте геолокацию салона:",
    )
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Отправить геолокацию", request_location=True)],
            [KeyboardButton(text="Отмена")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await callback.message.answer("Нажмите кнопку ниже и отправьте локацию", reply_markup=kb)
    await callback.answer()


@settings_router.message(LocationFSM.waiting_location, F.location)
async def save_location(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    salon_id = data.get("salon_id")
    if salon_id:
        await orm_update_salon_location(
            session,
            salon_id,
            message.location.latitude,
            message.location.longitude,
        )
    await message.answer("Адрес успешно сохранён.", reply_markup=ReplyKeyboardRemove())
    await state.clear()
    await state.update_data(main_message_id=data.get("main_message_id"), salon_id=salon_id)
    await show_admin_menu(state, message.chat.id, message.bot, session)


@settings_router.message(LocationFSM.waiting_location)
async def cancel_location(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if message.text and message.text.lower() in {"отмена", "/cancel"}:
        data = await state.get_data()
        salon_id = data.get("salon_id")
        await state.clear()
        await state.update_data(main_message_id=data.get("main_message_id"), salon_id=salon_id)
        await message.answer("Отменено", reply_markup=ReplyKeyboardRemove())
        await show_admin_menu(state, message.chat.id, message.bot, session)
    else:
        await message.answer("Нажмите кнопку отправки геолокации или 'Отмена'.")




@settings_router.message(Command("set_group"), IsAdmin())
async def set_group(message: types.Message, session: AsyncSession):
    user = await orm_get_user(session, message.from_user.id)
    salon_id = user.salon_id if user else None
    if not salon_id:
        await message.reply("Ваш аккаунт не привязан к салону.")
        return
    await orm_update_salon_group_chat(session, salon_id, message.chat.id)
    await message.reply("Группа успешно привязана")


TELEGRAPH_ABOUT_URL = "https://telegra.ph/aucacuva-07-18"

@settings_router.message(Command("about"))
async def about_command(message: Message):
    """
    Отправляет ссылку на страницу с описанием бота.
    """
    await message.answer(
        "ℹ️ Подробное описание и возможности демо‑бота:\n"
        f"{TELEGRAPH_ABOUT_URL}"
    )