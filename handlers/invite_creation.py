# handlersadm/create_salon.py
from __future__ import annotations
from sqlalchemy import select
from io import BytesIO
import qrcode
from aiogram.utils.i18n import I18n
from aiogram import F, Router, types
from aiogram.filters import Command, Filter, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.utils.i18n import I18n
from aiogram.utils.keyboard import InlineKeyboardBuilder

from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User

from database.orm_query import (
    orm_create_salon,
    init_default_salon_content,
    orm_add_user,
)
from filters.chat_types import ChatTypeFilter
from utils.slug import generate_unique_slug
from utils.i18n import _
# Роутер для инвайтов — подключай в main.py до общего старт-хендлера
invite_creation_router = Router()
invite_creation_router.message.filter(ChatTypeFilter(["private"]))  # только личка для сообщений
# Специально НЕ вешаем ChatTypeFilter на callback_query

# --- Фильтр для /start с payload "invite_..." ---
class InviteFilter(Filter):
    """Allow /start only when payload starts with a given prefix (default: 'invite_')."""
    def __init__(self, prefix: str = "invite_") -> None:
        self.prefix = prefix

    async def __call__(self, message: types.Message) -> bool:
        text = message.text or ""
        parts = text.split(maxsplit=1)
        if len(parts) != 2:
            return False  # нужен payload
        payload = parts[1]
        return payload.lower().startswith(self.prefix.lower())

class AddSalon(StatesGroup):
    language = State()
    name = State()
    slug = State()
    currency = State()
    timezone = State()
    phone = State()  # шаг контакта владельца

# --- Валюты ---
# --- Валюты ---
def get_currency_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="₽ RUB", callback_data="currency_RUB"),  # Россия
            InlineKeyboardButton(text="$ USD", callback_data="currency_USD"),  # ОАЭ (доллары для интернац.)
            InlineKeyboardButton(text="€ EUR", callback_data="currency_EUR"),  # Швеция (для евро-зон)
        ],
        [
            InlineKeyboardButton(text="🇸🇪 SEK", callback_data="currency_SEK"),  # Швеция — крона
            InlineKeyboardButton(text="🇺🇦 UAH", callback_data="currency_UAH"),  # Украина — гривна
            InlineKeyboardButton(text="🇰🇿 KZT", callback_data="currency_KZT"),  # Казахстан — тенге
        ],
        [
            InlineKeyboardButton(text="🇰🇬 KGS", callback_data="currency_KGS"),  # Кыргызстан — сом
            InlineKeyboardButton(text="🇺🇿 UZS", callback_data="currency_UZS"),  # Узбекистан — сум
            InlineKeyboardButton(text="🇦🇪 AED", callback_data="currency_AED"),  # ОАЭ — дирхам
        ]
    ])
    return kb


# --- Тайм-зоны (фикс) ---
TIMEZONES = [
    ("Europe/Stockholm", "🇸🇪 Швеция — Стокгольм"),
    ("Europe/Moscow",    "🇷🇺 Россия — Москва"),
    ("Europe/Kyiv",      "🇺🇦 Украина — Киев"),
    ("Asia/Tashkent",    "🇺🇿 Узбекистан — Ташкент"),
    ("Asia/Almaty",      "🇰🇿 Казахстан — Алматы"),
    ("Asia/Bishkek",     "🇰🇬 Кыргызстан — Бишкек"),
    ("Asia/Dubai",       "🇦🇪 ОАЭ — Дубай"),
]

def get_tz_fixed_kb() -> InlineKeyboardMarkup:
    kb = [[InlineKeyboardButton(text=label, callback_data=f"tz_pick:{tz}")]
          for tz, label in TIMEZONES]
    return InlineKeyboardMarkup(inline_keyboard=kb)

# --- Клавиатура запроса контакта ---
def contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📞 Отправить контакт", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

# ================== СТАРТ ПО ИНВАЙТУ (ТОЛЬКО invite_...) ==================
@invite_creation_router.message(CommandStart(), InviteFilter())  # prefix по умолчанию = "invite_"
async def start_via_invite(
    message: types.Message,
    state: FSMContext,
    session: AsyncSession,
    i18n: I18n,
) -> None:
    await state.clear()  # гасим висящие стейты
    user_id = message.from_user.id
    try:
        stmt = select(User).where(User.user_id == user_id)
        user = (await session.execute(stmt)).scalar_one_or_none()
    except AttributeError:
        # Fallback for simple session stubs without execute()
        user = await session.get(User, user_id)
    if user:
        if user.language:
            i18n.ctx_locale.set(user.language)
        await message.answer(
            _("Введите название салона:"), reply_markup=ReplyKeyboardRemove()
        )
        await state.set_state(AddSalon.name)
        return

    kb = InlineKeyboardBuilder()
    kb.button(text=_("Русский"), callback_data="setlang_ru")
    kb.button(text=_("English"), callback_data="setlang_en")
    kb.adjust(2)
    await message.answer(_("Выберите язык"), reply_markup=kb.as_markup())
    await state.set_state(AddSalon.language)

# ================== FSM ==================
@invite_creation_router.callback_query(AddSalon.language, F.data.startswith("setlang_"))
async def invite_set_language(
    callback: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    i18n: I18n,
) -> None:
    lang = callback.data.split("_", 1)[1]

    # Устанавливаем язык в контексте
    i18n.ctx_locale.set(lang)

    # Создаём пользователя или обновляем язык, если он уже существует
    user_id = callback.from_user.id
    try:
        stmt = select(User).where(User.user_id == user_id)
        user = (await session.execute(stmt)).scalar_one_or_none()
    except AttributeError:
        user = await session.get(User, user_id)
    if user:
        user.language = lang
    else:
        session.add(User(user_id=user_id, language=lang))
    await session.commit()

    # Удаляем сообщение с выбором языка
    await callback.message.delete()
    await callback.answer()

    # Продолжаем цепочку вручную
    await callback.message.answer(
        _("Введите название салона:"), reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(AddSalon.name)



@invite_creation_router.callback_query(AddSalon.language)
async def invite_set_language_invalid(callback: types.CallbackQuery) -> None:
    await callback.answer("Выберите язык", show_alert=True)

@invite_creation_router.message(AddSalon.language)
async def invite_language_message_invalid(message: types.Message) -> None:
    kb = InlineKeyboardBuilder()
    kb.button(text="Русский", callback_data="setlang_ru")
    kb.button(text="English", callback_data="setlang_en")
    kb.adjust(2)
    await message.answer(_("Выберите язык"), reply_markup=kb.as_markup())

@invite_creation_router.message(AddSalon.name, F.text)
async def salon_name(message: types.Message, state: FSMContext) -> None:
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Название слишком короткое, попробуйте ещё раз")
        return
    await state.update_data(name=name)
    await message.answer('Введите slug или "-" для автоматического создания')
    await state.set_state(AddSalon.slug)

@invite_creation_router.message(AddSalon.name)
async def salon_name_invalid(message: types.Message) -> None:
    await message.answer('Отправьте текстовое название или "отмена"')

@invite_creation_router.message(AddSalon.slug, F.text)
async def salon_slug(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    name = data["name"]
    slug_raw = message.text.strip()
    slug_source = slug_raw if slug_raw and slug_raw != "-" else name
    slug = await generate_unique_slug(session, slug_source)
    await state.update_data(slug=slug)
    await message.answer("Выберите валюту салона:", reply_markup=get_currency_kb())
    await state.set_state(AddSalon.currency)

@invite_creation_router.message(AddSalon.slug)
async def salon_slug_invalid(message: types.Message) -> None:
    await message.answer('Введите slug текстом или "-" для авто')

# Валюта -> тайм-зона
@invite_creation_router.callback_query(AddSalon.currency, F.data.startswith("currency_"))
async def salon_currency(callback: types.CallbackQuery, state: FSMContext) -> None:
    currency = callback.data.split("_")[-1]
    await state.update_data(currency=currency)
    await callback.message.edit_text("Выберите ваш часовой пояс:", reply_markup=get_tz_fixed_kb())
    await state.set_state(AddSalon.timezone)
    await callback.answer()

@invite_creation_router.callback_query(AddSalon.currency)
async def salon_currency_invalid(callback: types.CallbackQuery) -> None:
    await callback.answer("Используйте кнопки для выбора валюты", show_alert=True)

# Тайм-зона -> просим контакт
@invite_creation_router.callback_query(AddSalon.timezone, F.data.startswith("tz_pick:"))
async def tz_pick(callback: types.CallbackQuery, state: FSMContext) -> None:
    tz = callback.data.split(":", 1)[1]
    await state.update_data(timezone=tz)

    await callback.message.delete()
    await callback.message.answer(
        "Отправьте контакт владельца салона:",
        reply_markup=contact_keyboard(),
    )
    await state.set_state(AddSalon.phone)
    await callback.answer()

@invite_creation_router.callback_query(AddSalon.timezone)
async def tz_invalid(callback: types.CallbackQuery) -> None:
    await callback.answer("Пожалуйста, выберите тайм-зону кнопками", show_alert=True)

# Контакт -> создаём салон, сохраняем владельца, шлём QR
@invite_creation_router.message(AddSalon.phone, F.contact)
async def salon_phone(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()

    name = data["name"]
    slug = data["slug"]
    currency = data["currency"]
    timezone_name = data["timezone"]

    phone = message.contact.phone_number
    first_name = message.contact.first_name
    last_name = message.contact.last_name

    try:
        salon = await orm_create_salon(session, name, slug, currency, timezone_name)
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
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        is_salon_admin=True,
    )

    bot_username = (await message.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={salon.slug}"

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

@invite_creation_router.message(AddSalon.phone)
async def salon_phone_invalid(message: types.Message) -> None:
    await message.answer(
        "Пожалуйста, отправьте контакт кнопкой ниже",
        reply_markup=contact_keyboard(),
    )