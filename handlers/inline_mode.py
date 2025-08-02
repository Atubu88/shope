# handlers/inline_mode.py
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
    orm_get_salon_by_id,
)
from utils.currency import get_currency_symbol

inline_router = Router()

# ——— Кэш file_id → https-URL Telegram ———
THUMB_CACHE: dict[str, str] = {}      # {file_id: thumb_url}

async def get_telegram_file_url(bot, file_id: str) -> str:
    file = await bot.get_file(file_id)
    return f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"

async def get_thumb(bot, file_id: str) -> str:
    if file_id not in THUMB_CACHE:
        THUMB_CACHE[file_id] = await get_telegram_file_url(bot, file_id)
    return THUMB_CACHE[file_id]

# ——— Инлайн-режим ———
@inline_router.inline_query()
async def answer_products_inline(inline_query: InlineQuery, session: AsyncSession):
    """Отдаёт товары в инлайн‑режиме с фото из Supabase или Telegram."""
    user_salons = await orm_get_user_salons(session, inline_query.from_user.id)

    query = inline_query.query.strip()
    salon_id: int | None = None
    category_id: int | None = None
    for part in query.split():
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

    if salon_id is None:
        if len(user_salons) == 1:
            salon_id = user_salons[0].salon_id
        else:
            await inline_query.answer([], cache_time=1, is_personal=True)
            return
    elif not any(us.salon_id == salon_id for us in user_salons):
        await inline_query.answer([], cache_time=1, is_personal=True)
        return

    # Получаем товары
    if category_id is not None:
        products = await orm_get_products(session, category_id, salon_id)
    else:
        products = []
        categories = await orm_get_categories(session, salon_id)
        for c in categories:
            products.extend(await orm_get_products(session, c.id, salon_id))

    salon = await orm_get_salon_by_id(session, salon_id)
    currency = get_currency_symbol(salon.currency) if salon else "RUB"

    results = []
    for prod in products[:50]:
        if str(prod.image).startswith("http"):
            thumbnail_url = prod.image
        else:
            thumbnail_url = await get_thumb(inline_query.bot, prod.image)

        message_text = (
            f"<b>{prod.name}</b>\n"
            f"{prod.description or ''}\n"
            f"Цена: <b>{float(prod.price):.2f}{currency}</b>\n"
            f'<a href="{thumbnail_url}">&#8205;</a>'  # невидимый символ, чтобы фото было сверху
        )
        results.append(
            InlineQueryResultArticle(
                id=str(prod.id),
                title=prod.name,
                description=f"{float(prod.price):.2f}{currency}",
                thumbnail_url=thumbnail_url,
                input_message_content=InputTextMessageContent(
                    message_text=f"/product_{prod.id}",  # <-- вот так!
                ),
            )
        )
    if not results:
        results.append(
            InlineQueryResultArticle(
                id="no_products",
                title="Нет товаров",
                description="В этой категории пока нет товаров.",
                input_message_content=InputTextMessageContent(
                    message_text="В этой категории пока нет товаров.",
                ),
            )
        )
    await inline_query.answer(results, cache_time=1, is_personal=True)
