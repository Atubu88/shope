import os
from typing import Tuple, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from aiogram.types import InputMediaPhoto, FSInputFile

from database.orm_query import (
    orm_add_to_cart,
    orm_delete_from_cart,
    orm_get_banner,
    orm_get_categories,
    orm_get_products,
    orm_get_user_carts,
    orm_reduce_product_in_cart,
)
from database.repositories.salon_repository import SalonRepository
from kbds.inline import (
    get_products_btns,
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
) -> InputMediaPhoto:
    """
    Готовит InputMediaPhoto из разных источников картинки (file_id, URL, локальный путь).
    Если путь не существует — берём дефолтную картинку. К описанию можно добавить extra_description.
    """
    caption = description.rstrip()
    if extra_description:
        caption = f"{caption}\n{extra_description}"

    if image and image.startswith("AgACAg"):
        # Telegram file_id
        return InputMediaPhoto(media=image, caption=caption)
    elif image and (image.startswith("http://") or image.startswith("https://")):
        # Внешний URL
        return InputMediaPhoto(media=image, caption=caption)
    elif image and os.path.exists(image):
        # Локальный файл
        return InputMediaPhoto(media=FSInputFile(image), caption=caption)
    else:
        # Фолбэк на дефолтный баннер
        return InputMediaPhoto(media=FSInputFile("banners/default.jpg"), caption=caption)


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


def pages(paginator: Paginator) -> Dict[str, str]:
    """
    Возвращает словарь {текст_кнопки: действие} для пагинации.
    Тексты локализованы.
    """
    btns: Dict[str, str] = {}
    if paginator.has_previous():
        btns[_("◀ Пред.")] = "previous"
    if paginator.has_next():
        btns[_("След. ▶")] = "next"
    return btns


async def products(
    session: AsyncSession,
    level: int,
    category: int,
    page: int,
    salon_id: int,
):
    try:
        items = await orm_get_products(session, category_id=category, salon_id=salon_id)
        paginator = Paginator(items, page=page)
        page_items = paginator.get_page()

        if not page_items:
            # Нет товаров в категории — сообщаем и показываем каталог
            return (
                get_image_banner(
                    None,
                    _("В этой категории пока нет товаров. Попробуйте позже или выберите другую категорию."),
                ),
                get_user_catalog_btns(level=1, categories=await orm_get_categories(session, salon_id)),
            )

        product = page_items[0]
        salon = await SalonRepository(session).get_salon_by_id(salon_id)
        currency = get_currency_symbol(salon.currency) if salon else get_currency_symbol("RUB")

        image = get_image_banner(
            product.image,
            _("<strong>{name}</strong>\n{description}\nСтоимость: {price}{currency}\n").format(
                name=product.name,
                description=product.description or "",
                price=round(product.price, 2),
                currency=currency,
            ),
            _("<strong>Товар {page} из {pages}</strong>").format(
                page=paginator.page, pages=paginator.pages
            ),
        )

        pagination_btns = pages(paginator)
        kbds = get_products_btns(
            level=level,
            category=category,
            page=page,
            pagination_btns=pagination_btns,
            product_id=product.id,
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

    salon = await SalonRepository(session).get_salon_by_id(salon_id)
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
            return await products(session, level, category, page, salon_id)
        case 3:
            if page is None:
                raise ValueError("page is required for level 3 (cart)")
            return await carts(
                session, level, menu_name, page, user_salon_id, product_id, salon_id
            )
        case _:
            raise ValueError(f"Unknown menu level: {level}")
