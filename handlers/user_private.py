from aiogram import types, Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from database.orm_query import (
    orm_get_user_salons,
    orm_get_salon_by_slug,
    orm_get_user_salon,
    orm_add_user,
    orm_touch_user_salon,   # MRU: пометить «последний»
)

user_private_router = Router()

def salons_choice_kb(pairs: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=title, callback_data=f"choose_salon:{slug}")]
            for title, slug in pairs]
    return InlineKeyboardMarkup(inline_keyboard=rows)

@user_private_router.message(CommandStart())
async def start_cmd(message: types.Message, session: AsyncSession):
    """/start <slug?> — регистрируем юзера, при наличии slug — привязываем и помечаем MRU.
       Если slug нет — сразу даём выбор салона.
    """
    tg_id = message.from_user.id

    # 1) создать User, если нет
    result = await session.execute(select(User).where(User.user_id == tg_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(user_id=tg_id, language=message.from_user.language_code or "ru")
        session.add(user)
        await session.commit()

    # 2) поймать payload после /start (если пришли по ?startapp=<slug>)
    parts = (message.text or "").split(maxsplit=1)
    slug = parts[1] if len(parts) > 1 else None
    if slug:
        salon = await orm_get_salon_by_slug(session, slug)
        if salon:
            link = await orm_get_user_salon(session, tg_id, salon.id)
            if not link:
                await orm_add_user(
                    session,
                    user_id=tg_id,
                    salon_id=salon.id,
                    first_name=message.from_user.first_name,
                    last_name=message.from_user.last_name,
                )
            # MRU: пометить как «последний использованный»
            await orm_touch_user_salon(session, tg_id, salon.id)
            await message.answer(
                f"Салон <b>{salon.name}</b> подключён ✅\n"
                f"Нажми встроенную кнопку «Открыть» в меню Mini App.",
                parse_mode="HTML",
            )
            return

    # 3) без payload — сразу показать список салонов для выбора
    rows = await orm_get_user_salons(session, tg_id)
    salons: list[tuple[str, str]] = []
    for row in rows:
        if hasattr(row, "salon") and row.salon:
            salons.append((row.salon.name, row.salon.slug))
        elif hasattr(row, "name") and hasattr(row, "slug"):
            salons.append((row.name, row.slug))

    if not salons:
        await message.answer("У тебя пока нет привязанных салонов.")
        return

    await message.answer("Выбери салон:", reply_markup=salons_choice_kb(salons))


@user_private_router.message(Command("salon"))
async def cmd_salon(message: types.Message, session: AsyncSession):
    tg_id = message.from_user.id
    rows = await orm_get_user_salons(session, tg_id)  # верни список Salon или UserSalon.salon
    salons: list[tuple[str, str]] = []
    for row in rows:
        if hasattr(row, "salon") and row.salon:
            salons.append((row.salon.name, row.salon.slug))
        elif hasattr(row, "name") and hasattr(row, "slug"):
            salons.append((row.name, row.slug))

    if not salons:
        return await message.answer("У тебя пока нет привязанных салонов.")

    await message.answer("Выбери салон:", reply_markup=salons_choice_kb(salons))

@user_private_router.callback_query(F.data.startswith("choose_salon:"))
async def choose_salon_callback(cb: types.CallbackQuery, session: AsyncSession):
    slug = cb.data.split(":", 1)[1]
    tg_id = cb.from_user.id
    salon = await orm_get_salon_by_slug(session, slug)
    if not salon:
        await cb.answer("Салон не найден", show_alert=True)
        return

    # Убедимся, что есть связь, если нет — создадим
    link = await orm_get_user_salon(session, tg_id, salon.id)
    if not link:
        await orm_add_user(session, user_id=tg_id, salon_id=salon.id)

    # MRU: пометить как «последний»
    await orm_touch_user_salon(session, tg_id, salon.id)

    await cb.message.answer(
        f"Выбран салон <b>{salon.name}</b> ✅\n"
        f"Теперь нажми встроенную кнопку «Открыть» в меню Mini App.",
        parse_mode="HTML",
    )
    await cb.answer()
