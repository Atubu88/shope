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
    orm_get_salon_by_id,
)
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
    """
    Отдаёт товары в инлайн-режиме с учётом «многосалонности».

    Поддерживаемые шаблоны запроса:
      • ``""`` (пусто)                     → салон выберется автоматически
      • ``salon_<id>``                    → конкретный салон
      • ``salon_<id> cat_<id>``           → конкретный салон + категория
      • ``cat_<id>``                      → текущий / авто-выбранный салон,
                                            но конкретная категория
    """

    user_id = inline_query.from_user.id
    user_salons = await orm_get_user_salons(session, user_id)   # List[UserSalon]

    # ── 1. Разбираем текст запроса --------------------------------------
    q = inline_query.query.strip()
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

    # ── 2. Определяем салон --------------------------------------------
    if salon_id is None:
        # пользователь ничего не указал → пытаемся выбрать
        if not user_salons:                         # нет ни одного салона
            await inline_query.answer([], cache_time=1, is_personal=True)
            return
        elif len(user_salons) == 1:                 # ровно один салон
            salon_id = user_salons[0].salon_id
        else:                                       # несколько салонов
            # 👉 *Стратегия по-умолчанию*: берём первый.
            #    Можно заменить на выбор «салона по-умолчанию» из профиля
            #    или отправлять пустой ответ, предлагая уточнить salon_<id>.
            salon_id = user_salons[0].salon_id
    else:
        # в запросе указан salon_<id> — проверяем, имеет ли к нему доступ
        if not any(us.salon_id == salon_id for us in user_salons):
            # чужой салон → ничего не показываем
            await inline_query.answer([], cache_time=1, is_personal=True)
            return

    # ── 3. Получаем товары ---------------------------------------------
    if category_id is not None:
        products = await orm_get_products(session, category_id, salon_id)
    else:
        products = []
        categories = await orm_get_categories(session, salon_id)
        for c in categories:
            products.extend(await orm_get_products(session, c.id, salon_id))

    salon = await orm_get_salon_by_id(session, salon_id)
    currency = get_currency_symbol(salon.currency) if salon else "RUB"

    # ── 4. Формируем результаты ----------------------------------------
    results = []
    for prod in products[:50]:                       # Telegram-лимит = 50
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
                    message_text=f"/product_{prod.id}",   # наше «шифрованное» сообщение
                ),
            )
        )

    # если товаров нет — отдаём «заглушку»
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

    # ── 5. Ответ --------------------------------------------------------
    await inline_query.answer(results, cache_time=1, is_personal=True)
