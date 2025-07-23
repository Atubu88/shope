import os
from sqlalchemy.ext.asyncio import AsyncSession
from database.orm_query import (
    orm_add_to_cart,
    orm_delete_from_cart,
    orm_get_banner,
    orm_get_categories,
    orm_get_products,
    orm_get_user_carts,
    orm_reduce_product_in_cart,
    orm_get_user,
    orm_get_salons,
    orm_get_salon_by_id,
)
from kbds.inline import (
    get_products_btns,
    get_user_cart,
    get_user_catalog_btns,
    get_user_main_btns,
)
from utils.paginator import Paginator
from utils.currency import get_currency_symbol
from aiogram.types import InputMediaPhoto, FSInputFile


from aiogram.types import InputMediaPhoto

from aiogram.types import InputMediaPhoto, FSInputFile
import os


def get_image_banner(
    image: str | None,
    description: str,
    extra_description: str | None = None,
) -> InputMediaPhoto:
    """Return an ``InputMediaPhoto`` prepared from different image sources.

    ``image`` can be a Telegram ``file_id`` or a local path. If the path does
    not exist, a default banner image is used. ``extra_description`` is
    optional and appended below ``description`` when provided.
    """

    caption = description.rstrip()
    if extra_description:
        caption = f"{caption}\n{extra_description}"

    if image and image.startswith("AgACAg"):
        return InputMediaPhoto(media=image, caption=caption)
    elif image and os.path.exists(image):
        return InputMediaPhoto(media=FSInputFile(image), caption=caption)
    else:
        return InputMediaPhoto(
            media=FSInputFile("banners/default.jpg"), caption=caption
        )




async def main_menu(session, level, menu_name, salon_id):
    banner = await orm_get_banner(session, menu_name, salon_id)
    image = get_image_banner(banner.image if banner else None, banner.description if banner else "")
    kbds = get_user_main_btns(level=level)
    return image, kbds


async def catalog(session, level, menu_name, salon_id):
    banner = await orm_get_banner(session, menu_name, salon_id)
    image = get_image_banner(banner.image if banner else None, banner.description if banner else "")
    categories = await orm_get_categories(session, salon_id)
    kbds = get_user_catalog_btns(level=level, categories=categories)
    return image, kbds


def pages(paginator: Paginator):
    btns = {}
    if paginator.has_previous():
        btns["◀ Пред."] = "previous"
    if paginator.has_next():
        btns["След. ▶"] = "next"
    return btns


async def products(session, level, category, page, salon_id):
    try:
        products = await orm_get_products(session, category_id=category, salon_id=salon_id)
        paginator = Paginator(products, page=page)
        page_items = paginator.get_page()

        if not page_items:
            # Если товаров нет — показываем сообщение и кнопки (например, назад/главное меню)
            return (
                get_image_banner(None, "В этой категории пока нет товаров. Попробуйте позже или выберите другую категорию."),
                get_user_catalog_btns(level=1, categories=await orm_get_categories(session, salon_id))
            )

        product = page_items[0]
        salon = await orm_get_salon_by_id(session, salon_id)
        currency = get_currency_symbol(salon.currency) if salon else "RUB"
        image = get_image_banner(
            product.image,
            f"<strong>{product.name}</strong>\n{product.description}\nСтоимость: {round(product.price, 2)}{currency}\n",
            f"<strong>Товар {paginator.page} из {paginator.pages}</strong>",
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
        # Логируем ошибку (или можешь отправить дефолтную картинку с текстом)
        print(f"[products] Ошибка: {e}")
        return (
            get_image_banner(None, "Произошла непредвиденная ошибка при загрузке товаров. Попробуйте позже."),
            get_user_catalog_btns(level=1, categories=[])
        )


async def carts(session, level, menu_name, page, user_id, product_id, salon_id):
    if menu_name == "delete":
        await orm_delete_from_cart(session, user_id, product_id, salon_id)
        if page > 1:
            page -= 1
    elif menu_name == "decrement":
        is_cart = await orm_reduce_product_in_cart(session, user_id, product_id, salon_id)
        if page > 1 and not is_cart:
            page -= 1
    elif menu_name == "increment":
        await orm_add_to_cart(session, user_id, product_id, salon_id)

    carts = await orm_get_user_carts(session, user_id, salon_id)

    if not carts:
        banner = await orm_get_banner(session, "cart", salon_id)
        image = get_image_banner(banner.image if banner else None, f"<strong>{banner.description}</strong>" if banner else "Корзина пуста")
        kbds = get_user_cart(level=level, page=None, pagination_btns=None, product_id=None)
    else:
        paginator = Paginator(carts, page=page)
        cart = paginator.get_page()[0]
        salon = await orm_get_salon_by_id(session, salon_id)
        currency = get_currency_symbol(salon.currency) if salon else "RUB"
        cart_price = round(cart.quantity * cart.product.price, 2)
        total_price = round(sum(c.quantity * c.product.price for c in carts), 2)

        image = get_image_banner(
            cart.product.image,
            f"<strong>{cart.product.name}</strong>\n{cart.product.price}{currency} x {cart.quantity} = {cart_price}{currency}\n",
            f"Товар {paginator.page} из {paginator.pages} в корзине.\nОбщая стоимость: {total_price}{currency}",
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
    category: int | None = None,
    page: int | None = None,
    product_id: int | None = None,
    user_id: int | None = None,
):
    salon_id = None
    if user_id:
        user = await orm_get_user(session, user_id)
        salon_id = user.salon_id if user else None
    if salon_id is None:
        salons = await orm_get_salons(session)
        if salons:
            salon_id = salons[0].id

    if level == 0:
        return await main_menu(session, level, menu_name, salon_id)
    elif level == 1:
        return await catalog(session, level, menu_name, salon_id)
    elif level == 2:
        return await products(session, level, category, page, salon_id)
    elif level == 3:
        return await carts(session, level, menu_name, page, user_id, product_id, salon_id)