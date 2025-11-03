import os
from math import ceil
from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from aiogram.types import InputMediaPhoto, FSInputFile

from database.orm_query import (
    orm_add_to_cart,
    orm_delete_from_cart,
    orm_get_banner,
    orm_get_category,
    orm_get_categories,
    orm_get_products,
    orm_get_user_carts,
    orm_reduce_product_in_cart,
)
from database.repositories import SalonRepository
from kbds.inline import (
    get_product_detail_btns,
    get_product_list_btns,
    get_user_cart,
    get_user_catalog_btns,
    get_user_main_btns,
)
from utils.paginator import Paginator
from utils.currency import get_currency_symbol
from database.models import UserSalon, User
from utils.i18n import _, i18n  # ✅ gettext + i18n
from common.texts_for_db import get_default_banner_description


def get_image_banner(
    image: Optional[str],
    description: str,
    extra_description: Optional[str] = None,
) -> InputMediaPhoto | str:
    """
    Возвращает InputMediaPhoto, если есть фото, иначе просто текст (caption).
    Это убирает дефолтную заглушку "NO PHOTO".
    """
    caption = description.rstrip()
    if extra_description:
        caption = f"{caption}\n{extra_description}"

    # Если есть фото — показываем
    if image and image.startswith("AgACAg"):
        return InputMediaPhoto(media=image, caption=caption)
    elif image and (image.startswith("http://") or image.startswith("https://")):
        return InputMediaPhoto(media=image, caption=caption)
    elif image and os.path.exists(image):
        return InputMediaPhoto(media=FSInputFile(image), caption=caption)

    # 🚫 Фото нет — просто возвращаем текст без картинки
    return caption



def resolve_banner_description(banner, page: str) -> str:
    """
    Если у баннера есть описание — используем его, иначе возвращаем локализованный дефолт.
    """
    if banner and banner.description:
        return banner.description
    return get_default_banner_description(page)


async def _ensure_locale_from_user_salon(session: AsyncSession, user_salon_id: Optional[int]) -> None:
    """
    Страховка: принудительно устанавливаем локаль пользователя,
    взяв её из БД по user_salon_id. Работает для message/callback.
    """
    if not user_salon_id:
        return
    lang = await session.scalar(
        select(User.language)
        .join(UserSalon, User.user_id == UserSalon.user_id)
        .where(UserSalon.id == user_salon_id)
    )
    if lang:
        # нормализация en-US -> en
        base = lang.split("-")[0].lower()
        i18n.ctx_locale.set(base)


async def main_menu(session: AsyncSession, level: int, menu_name: str, salon_id: int):
    banner = await orm_get_banner(session, menu_name, salon_id)
    description = resolve_banner_description(banner, menu_name)
    image = get_image_banner(banner.image if banner else None, description)
    kbds = get_user_main_btns(level=level)
    return image, kbds


async def catalog(session: AsyncSession, level: int, menu_name: str, salon_id: int):
    banner = await orm_get_banner(session, menu_name, salon_id)
    description = resolve_banner_description(banner, menu_name)
    image = get_image_banner(banner.image if banner else None, description)
    categories = await orm_get_categories(session, salon_id)
    kbds = get_user_catalog_btns(level=level, categories=categories)
    return image, kbds


PRODUCTS_PER_PAGE = 3



def pages(paginator: Paginator) -> list[tuple[str, str]]:
    """
    Возвращает список пар (текст, действие) для пагинации.
    Тексты локализованы.
    """
    btns: list[tuple[str, str]] = []
    if paginator.has_previous():
        btns.append((_("◀ Пред."), "previous"))
    if paginator.has_next():
        btns.append((_("След. ▶"), "next"))
    return btns


def _number_to_emoji(number: int) -> str:
    """Возвращает числовой индекс, оформленный эмодзи, для списка товаров."""

    mapping = {
        0: "0️⃣",
        1: "1️⃣",
        2: "2️⃣",
        3: "3️⃣",
        4: "4️⃣",
        5: "5️⃣",
        6: "6️⃣",
        7: "7️⃣",
        8: "8️⃣",
        9: "9️⃣",
        10: "🔟",
    }
    if number in mapping:
        return mapping[number]
    return f"{number}."


def format_product_list(
    *,
    category_name: str,
    products: Sequence,
    currency: str,
    start_index: int,
) -> str:
    """Формирует текст списка товаров для вывода в каталоге."""

    if not products:
        return _("Пока нет товаров для отображения.")

    lines = [_("🛍 Категория: {category}").format(category=category_name), ""]
    for offset, product in enumerate(products):
        position = start_index + offset
        price = round(product.price, 2)
        lines.append(
            _("{index} {name} — {price} {currency}").format(
                index=_number_to_emoji(position),
                name=product.name,
                price=price,
                currency=currency,
            )
        )

    return "\n".join(lines)


def format_product_list_caption(
    *,
    category_name: str,
    current_page: int,
    total_pages: int,
) -> str:
    """Возвращает подпись для списка товаров с категорией и номером страницы."""

    header = _("Категория: {category}").format(category=category_name)
    pages_info = _("Список товаров: {current} из {total}").format(
        current=current_page,
        total=total_pages,
    )
    return "\n".join((header, pages_info))


async def products(
    session: AsyncSession,
    level: int,
    menu_name: str,
    category: int,
    page: int,
    product_id: Optional[int],
    salon_id: int,
):
    repo = SalonRepository(session)
    try:
        items = await orm_get_products(session, category_id=category, salon_id=salon_id)
        category_obj = await orm_get_category(session, category, salon_id)
        category_name = category_obj.name if category_obj else _("Категория")
        salon = await repo.get_by_id(salon_id)
        currency = get_currency_symbol(salon.currency) if salon else get_currency_symbol("RUB")

        if menu_name == "product_detail" and items:
            if product_id is not None:
                for idx, item in enumerate(items, start=1):
                    if item.id == product_id:
                        page = idx
                        break
            total_items = len(items)
            page = max(1, min(page, total_items))
            detail_paginator = Paginator(items, page=page, per_page=1)
            page_items = detail_paginator.get_page()
            product = page_items[0]

            list_page = ceil(page / PRODUCTS_PER_PAGE) if total_items else 1

            image = get_image_banner(
                product.image,
                _("<strong>{name}</strong>\n{description}\nСтоимость: {price} {currency}\n").format(
                    name=product.name,
                    description=product.description or "",
                    price=round(product.price, 2),
                    currency=currency,
                ),
                _("<strong>Товар {page} из {pages}</strong>").format(
                    page=detail_paginator.page,
                    pages=detail_paginator.pages,
                ),
            )

            pagination_btns = pages(detail_paginator)
            kbds = get_product_detail_btns(
                level=level,
                category=category,
                page=detail_paginator.page,
                pagination_btns=pagination_btns,
                product_id=product.id,
                list_page=list_page,
                category_menu_name=category_name,
            )
            return image, kbds

        list_paginator = Paginator(items, page=page, per_page=PRODUCTS_PER_PAGE)
        page = max(1, min(page, max(list_paginator.pages, 1)))
        list_paginator.page = page
        page_items = list_paginator.get_page()

        if not page_items:
            return (
                get_image_banner(
                    None,
                    _("В этой категории пока нет товаров. Попробуйте позже или выберите другую категорию."),
                ),
                get_user_catalog_btns(level=1, categories=await orm_get_categories(session, salon_id)),
            )

        start_index = (list_paginator.page - 1) * list_paginator.per_page + 1
        banner = await orm_get_banner(session, category_name, salon_id)
        # Только заголовок категории без списка товаров
        # 🚫 Всегда без фото
        # Только заголовок категории без списка товаров и без фото
        # 🖼 Для списка товаров используем узкий баннер "Список товаров"
        if menu_name != "product_detail":
            caption = format_product_list(
                category_name=category_name,
                products=page_items,
                currency=currency,
                start_index=start_index,
            )

            # 🖼 Узкий баннер "Список товаров" + подпись с названием категории
            image = InputMediaPhoto(
                media=FSInputFile("banners/product_list.png"),
                caption=format_product_list_caption(
                    category_name=category_name,
                    current_page=list_paginator.page,
                    total_pages=max(list_paginator.pages, 1),
                ),
            )

        pagination_btns = pages(list_paginator)
        kbds = get_product_list_btns(
            level=level,
            category=category,
            page=list_paginator.page,
            pagination_btns=pagination_btns,
            products=page_items,
            category_menu_name="product_list",
            start_index=start_index,
        )
        return image, kbds

    except Exception as e:
        # Логируем и показываем локализованное сообщение об ошибке
        print(f"[products] Ошибка: {e}")
        return (
            get_image_banner(
                None,
                _("Произошла непредвиденная ошибка при загрузке товаров. Попробуйте позже."),
            ),
            get_user_catalog_btns(level=1, categories=[]),
        )


async def carts(
    session: AsyncSession,
    level: int,
    menu_name: str,
    page: int,
    user_salon_id: int,
    product_id: Optional[int],
    salon_id: int,
):
    repo = SalonRepository(session)
    # Мутации корзины
    if menu_name == "delete" and product_id is not None:
        await orm_delete_from_cart(session, user_salon_id, product_id)
        if page > 1:
            page -= 1
    elif menu_name == "decrement" and product_id is not None:
        is_cart = await orm_reduce_product_in_cart(session, user_salon_id, product_id)
        if page > 1 and not is_cart:
            page -= 1
    elif menu_name == "increment" and product_id is not None:
        await orm_add_to_cart(session, user_salon_id, product_id)

    carts_list = await orm_get_user_carts(session, user_salon_id)

    if not carts_list:
        # Пустая корзина — баннер "cart" + кнопки без пагинации
        banner = await orm_get_banner(session, "cart", salon_id)
        desc = resolve_banner_description(banner, "cart")
        image = get_image_banner(
            banner.image if banner else None,
            f"<strong>{desc}</strong>",
        )
        kbds = get_user_cart(level=level, page=None, pagination_btns=None, product_id=None)
        return image, kbds

    # Есть позиции в корзине
    paginator = Paginator(carts_list, page=page)
    page_items = paginator.get_page()
    cart = page_items[0]

    salon = await repo.get_by_id(salon_id)
    currency = get_currency_symbol(salon.currency) if salon else get_currency_symbol("RUB")

    cart_price = round(cart.quantity * cart.product.price, 2)
    total_price = round(sum(c.quantity * c.product.price for c in carts_list), 2)

    image = get_image_banner(
        cart.product.image,
        _("<strong>{name}</strong>\n{price}{currency} x {qty} = {sum}{currency}\n").format(
            name=cart.product.name,
            price=round(cart.product.price, 2),
            currency=currency,
            qty=cart.quantity,
            sum=cart_price,
        ),
        _("Товар {page} из {pages} в корзине.\nОбщая стоимость: {total}{currency}").format(
            page=paginator.page, pages=paginator.pages, total=total_price, currency=currency
        ),
    )

    pagination_btns = pages(paginator)
    kbds = get_user_cart(
        level=level,
        page=page,
        pagination_btns=pagination_btns,
        product_id=cart.product.id,
    )
    return image, kbds


async def get_menu_content(
    session: AsyncSession,
    level: int,
    menu_name: str,
    category: Optional[int] = None,
    page: Optional[int] = None,
    product_id: Optional[int] = None,
    user_salon_id: Optional[int] = None,
    salon_id: Optional[int] = None,
):
    """
    Возвращает (image, keyboard) для заданного уровня меню.
    Локаль выбирается middleware-ом; здесь добавлена «страховка» из БД.
    """
    # ✅ Приоритет: user_salon_id → salon_id
    if not salon_id:
        if user_salon_id:
            user_salon = await session.get(UserSalon, user_salon_id)
            if user_salon:
                salon_id = user_salon.salon_id
            else:
                raise ValueError("UserSalon not found for given user_salon_id")
        else:
            raise ValueError("salon_id or user_salon_id is required")

    # 🔒 Страховка локали (важно для callback-ов)
    await _ensure_locale_from_user_salon(session, user_salon_id)

    # 🔀 Перенаправление по уровням меню
    match level:
        case 0:
            return await main_menu(session, level, menu_name, salon_id)
        case 1:
            return await catalog(session, level, menu_name, salon_id)
        case 2:
            if category is None or page is None:
                raise ValueError("category and page are required for level 2 (products)")
            return await products(
                session,
                level,
                menu_name,
                category,
                page,
                product_id,
                salon_id,
            )
        case 3:
            if page is None:
                raise ValueError("page is required for level 3 (cart)")
            return await carts(
                session, level, menu_name, page, user_salon_id, product_id, salon_id
            )
        case _:
            raise ValueError(f"Unknown menu level: {level}")
