from aiogram import Router
from aiogram.types import InlineQuery, InlineQueryResultCachedPhoto
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query import (
    orm_get_user,
    orm_get_products,
    orm_get_categories,
    orm_get_salon_by_id,
)
from utils.currency import get_currency_symbol

inline_router = Router()


@inline_router.inline_query()
async def answer_products_inline(inline_query: InlineQuery, session: AsyncSession):
    """Return products in inline mode based on query."""
    user = await orm_get_user(session, inline_query.from_user.id)
    salon_id = user.salon_id if user else None
    if not salon_id:
        await inline_query.answer([], cache_time=1, is_personal=True)
        return

    query = inline_query.query.strip()
    category_id = None
    if query.startswith("cat_"):
        try:
            category_id = int(query.split("_", 1)[1])
        except (ValueError, IndexError):
            category_id = None

    products = []
    if category_id is not None:
        products = await orm_get_products(session, category_id, salon_id)
    else:
        categories = await orm_get_categories(session, salon_id)
        for c in categories:
            products.extend(await orm_get_products(session, c.id, salon_id))

    salon = await orm_get_salon_by_id(session, salon_id)
    currency = get_currency_symbol(salon.currency) if salon else "RUB"

    results = []
    for product in products[:50]:
        caption = (
            f"<b>{product.name}</b>\n"
            f"{product.description}\n"
            f"Цена: <b>{float(product.price):.2f}{currency}</b>"
        )
        results.append(
            InlineQueryResultCachedPhoto(
                id=str(product.id),
                photo_file_id=product.image,
                caption=caption,
                parse_mode="HTML",
            )
        )

    await inline_query.answer(results, cache_time=1)