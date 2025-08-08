"""Salon creation via invite links."""
from __future__ import annotations

from io import BytesIO
from aiogram import Router, types, F
from aiogram.filters import Filter, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from sqlalchemy.ext.asyncio import AsyncSession

from filters.chat_types import ChatTypeFilter
from kbds.inline import get_currency_kb, get_tz_groups_kb, get_tz_list_kb
from utils.slug import generate_unique_slug
from database.orm_query import (
    orm_create_salon,
    init_default_salon_content,
    orm_add_user,
)


class InviteFilter(Filter):
    """Allow /start commands with payload starting with ``invite_``."""

    async def __call__(self, message: types.Message) -> bool:
        if not message.text:
            return False
        parts = message.text.split(maxsplit=1)
        return len(parts) == 2 and parts[1].startswith("invite_")


class InviteSalon(StatesGroup):
    name = State()
    slug = State()
    currency = State()
    timezone = State()
    phone = State()


def contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📞 Отправить контакт", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


invite_creation_router = Router()
invite_creation_router.message.filter(ChatTypeFilter(["private"]))


@invite_creation_router.message(StateFilter(None), CommandStart(), InviteFilter())
async def start_invite(message: types.Message, state: FSMContext) -> None:
    await message.answer("Введите название салона:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(InviteSalon.name)


@invite_creation_router.message(InviteSalon.name, F.text)
async def salon_name(message: types.Message, state: FSMContext) -> None:
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Название слишком короткое, попробуйте ещё раз")
        return
    await state.update_data(name=name)
    await message.answer("Введите slug или '-' для авто")
    await state.set_state(InviteSalon.slug)


@invite_creation_router.message(InviteSalon.name)
async def salon_name_invalid(message: types.Message) -> None:
    await message.answer("Пожалуйста, отправьте название текстом")


@invite_creation_router.message(InviteSalon.slug, F.text)
async def salon_slug(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    slug_raw = message.text.strip()
    data = await state.get_data()
    slug_source = slug_raw if slug_raw and slug_raw != "-" else data["name"]
    slug = await generate_unique_slug(session, slug_source)
    await state.update_data(slug=slug)
    await message.answer("Выберите валюту:", reply_markup=get_currency_kb())
    await state.set_state(InviteSalon.currency)


@invite_creation_router.message(InviteSalon.slug)
async def salon_slug_invalid(message: types.Message) -> None:
    await message.answer("Введите slug текстом или '-' для автоматического")


@invite_creation_router.callback_query(InviteSalon.currency, F.data.startswith("currency_"))
async def salon_currency(callback: CallbackQuery, state: FSMContext) -> None:
    currency = callback.data.split("_")[-1]
    await state.update_data(currency=currency)
    await callback.message.edit_text(
        "Выберите регион:", reply_markup=get_tz_groups_kb()
    )
    await state.set_state(InviteSalon.timezone)
    await callback.answer()


@invite_creation_router.callback_query(InviteSalon.currency)
async def salon_currency_invalid(callback: CallbackQuery) -> None:
    await callback.answer("Используйте кнопки для выбора валюты", show_alert=True)


@invite_creation_router.callback_query(InviteSalon.timezone, F.data.startswith("tz_group:"))
async def tz_group(callback: CallbackQuery, state: FSMContext) -> None:
    group = callback.data.split(":", 1)[1]
    await callback.message.edit_text(
        "Выберите тайм-зону:", reply_markup=get_tz_list_kb(group)
    )
    await callback.answer()


@invite_creation_router.callback_query(InviteSalon.timezone, F.data == "tz_back_groups")
async def tz_back(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "Выберите регион:", reply_markup=get_tz_groups_kb()
    )
    await callback.answer()


@invite_creation_router.callback_query(InviteSalon.timezone, F.data.startswith("tz_pick:"))
async def tz_pick(callback: CallbackQuery, state: FSMContext) -> None:
    tz = callback.data.split(":", 1)[1]
    await state.update_data(timezone=tz)
    await callback.message.delete()
    await callback.message.answer(
        "Отправьте контакт владельца салона:",
        reply_markup=contact_keyboard(),
    )
    await state.set_state(InviteSalon.phone)
    await callback.answer()


@invite_creation_router.callback_query(InviteSalon.timezone)
async def tz_invalid(callback: CallbackQuery) -> None:
    await callback.answer("Пожалуйста, выберите тайм-зону кнопками", show_alert=True)


@invite_creation_router.message(InviteSalon.phone, F.contact)
async def salon_phone(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    phone = message.contact.phone_number
    try:
        salon = await orm_create_salon(
            session,
            data["name"],
            data["slug"],
            data["currency"],
            data.get("timezone"),
        )
    except ValueError:
        await message.answer(
            "Салон с таким названием или слагом уже существует.",
            reply_markup=ReplyKeyboardRemove(),
        )
        await state.clear()
        return

    await init_default_salon_content(session, salon.id)
    await orm_add_user(
        session,
        user_id=message.from_user.id,
        salon_id=salon.id,
        first_name=message.contact.first_name,
        last_name=message.contact.last_name,
        phone=phone,
        is_salon_admin=True,
    )

    bot_username = (await message.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={salon.slug}"

    import qrcode

    img = qrcode.make(link)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    await message.answer_photo(
        types.BufferedInputFile(buf.getvalue(), filename="qr.png"),
        caption=(
            f"Салон '{salon.name}' создан!\n"
            f"Часовой пояс: {salon.timezone}\n"
            f"{link}"
        ),
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.clear()


@invite_creation_router.message(InviteSalon.phone)
async def salon_phone_invalid(message: types.Message) -> None:
    await message.answer(
        "Пожалуйста, отправьте контакт кнопкой ниже",
        reply_markup=contact_keyboard(),
    )