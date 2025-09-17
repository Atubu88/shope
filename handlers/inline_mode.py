# handlers/inline_mode.py
# ---------------------------------------------------------------------------
# Инлайн-режим «многосалонной» версии: один пользователь может быть клиентом
# нескольких салонов.  В запросе он *может* уточнить нужный салон и/или
# категорию, но если ничего не указано, бот старается выбрать салон сам.
# ---------------------------------------------------------------------------

from aiogram import Router
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query import (
    orm_get_user_salons,
    orm_get_products,
    orm_get_categories,
)
from database.repositories import SalonRepository
from utils.currency import get_currency_symbol

inline_router = Router()

# ---------- Telegram-файлы: кэш превью ------------------------------------
THUMB_CACHE: dict[str, str] = {}          # {file_id: ready_url}


async def _tg_file_url(bot, file_id: str) -> str:
    file = await bot.get_file(file_id)
    return f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"


async def _thumb(bot, file_id: str) -> str:
    if file_id not in THUMB_CACHE:
        THUMB_CACHE[file_id] = await _tg_file_url(bot, file_id)
    return THUMB_CACHE[file_id]


# ---------- Инлайн-ответ ---------------------------------------------------
@inline_router.inline_query()
async def answer_products_inline(inline_query: InlineQuery, session: AsyncSession) -> None:
    user_id = inline_query.from_user.id
    user_salons = await orm_get_user_salons(session, user_id)
    repo = SalonRepository(session)

    q = inline_query.query.strip()

    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    # ВОТ ЗДЕСЬ — ПРОВЕРКА!
    # Если строка запроса пуста — не показываем ничего.
    if not q:
        await inline_query.answer([], cache_time=1, is_personal=True)
        return
    # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<

    salon_id: int | None = None
    category_id: int | None = None

    for part in q.split():
        if part.startswith("salon_"):
            try:
                salon_id = int(part.split("_", 1)[1])
            except (ValueError, IndexError):
                pass
        elif part.startswith("cat_"):
            try:
                category_id = int(part.split("_", 1)[1])
            except (ValueError, IndexError):
                pass

    # Если категория указана, а салон нет — определяем салон по категории (НЕ РЕКОМЕНДУЮТ!)
    if salon_id is None and category_id is not None:
        for us in user_salons:
            categories = await orm_get_categories(session, us.salon_id)
            allowed_category_ids = [c.id for c in categories]
            if category_id in allowed_category_ids:
                salon_id = us.salon_id
                break

    if salon_id is None:
        if not user_salons:
            await inline_query.answer([], cache_time=1, is_personal=True)
            return
        salon_id = user_salons[0].salon_id
    else:
        if not any(us.salon_id == salon_id for us in user_salons):
            await inline_query.answer([], cache_time=1, is_personal=True)
            return

    if category_id is not None:
        categories = await orm_get_categories(session, salon_id)
        allowed_category_ids = [c.id for c in categories]
        if category_id in allowed_category_ids:
            products = await orm_get_products(session, category_id, salon_id)
        else:
            products = []
    else:
        products = await orm_get_products(session, salon_id=salon_id)

    salon = await repo.get_by_id(salon_id)
    currency = get_currency_symbol(salon.currency) if salon else "RUB"

    results = []
    for prod in products[:50]:
        thumb_url = (
            prod.image if str(prod.image).startswith(("http://", "https://"))
            else await _thumb(inline_query.bot, prod.image)
        )
        results.append(
            InlineQueryResultArticle(
                id=str(prod.id),
                title=prod.name,
                description=f"{float(prod.price):.2f}{currency}",
                thumbnail_url=thumb_url,
                input_message_content=InputTextMessageContent(
                    message_text=f"/product_{prod.id}",
                ),
            )
        )

    if not results:
        results.append(
            InlineQueryResultArticle(
                id="no_products",
                title="Нет товаров",
                description="В этом салоне/категории пока нет товаров.",
                input_message_content=InputTextMessageContent(
                    message_text="В этой категории пока нет товаров.",
                ),
            )
        )

    await inline_query.answer(results, cache_time=1, is_personal=True)
