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
from database.orm_query import orm_get_user
from database.repositories import SalonRepository
from filters.chat_types import IsAdmin
from aiogram import types
from aiogram.filters import Command, CommandObject

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
        repo = SalonRepository(session)
        await repo.update_location(
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




@settings_router.message(Command("set_group"))
async def set_group(message: types.Message, command: CommandObject, session: AsyncSession):
    # Команду нужно писать в самой группе
    if message.chat.type not in ("group", "supergroup"):
        await message.reply("Отправь эту команду в нужной группе.")
        return

    # /set_group <slug>
    slug = (command.args or "").strip()
    if not slug:
        await message.reply("Укажи салон в формате: /set_group slug", parse_mode=None)
        return

    # Ищем салон по slug
    repo = SalonRepository(session)
    salon = await repo.get_by_slug(slug)
    if not salon:
        await message.reply("Салон не найден. Проверь slug.", parse_mode=None)
        return

    # Сохраняем chat_id группы в салон
    await repo.update_group_chat(salon.id, message.chat.id)

    await message.reply(f"Группа привязана к салону: {salon.name}", parse_mode=None)




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
