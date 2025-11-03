from typing import Sequence

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.i18n import _




class MenuCallBack(CallbackData, prefix="menu"):
    level: int
    menu_name: str
    category: int | None = None
    page: int = 1
    product_id: int | None = None


class SalonCallBack(CallbackData, prefix="salon"):
    salon_id: int


def get_user_main_btns(*, level: int, sizes: tuple[int] = (2,)):
    keyboard = InlineKeyboardBuilder()
    btns = {
        _("Товары 🛍️"): "catalog",
        _("Корзина 🛒"): "cart",
        _("О нас ℹ️"): "about",
        _("Оплата 💰"): "payment",
        _("Доставка ⛵"): "shipping",
    }
    for text, menu_name in btns.items():
        if menu_name == 'catalog':
            keyboard.add(InlineKeyboardButton(text=text,
                                              callback_data=MenuCallBack(level=level + 1, menu_name=menu_name).pack()))
        elif menu_name == 'cart':
            keyboard.add(InlineKeyboardButton(text=text,
                                              callback_data=MenuCallBack(level=3, menu_name=menu_name).pack()))
        else:
            keyboard.add(InlineKeyboardButton(text=text,
                                              callback_data=MenuCallBack(level=level, menu_name=menu_name).pack()))

    return keyboard.adjust(*sizes).as_markup()


def get_salon_btns(salons):
    keyboard = InlineKeyboardBuilder()
    for salon in salons:
        keyboard.add(
            InlineKeyboardButton(
                text=salon.name,
                callback_data=SalonCallBack(salon_id=salon.id).pack(),
            )
        )
    return keyboard.as_markup()


def get_user_catalog_btns(*, level: int, categories: list, sizes: tuple[int] = (2,)):
    keyboard = InlineKeyboardBuilder()

    keyboard.add(
        InlineKeyboardButton(
            text=_('Назад'),
            callback_data=MenuCallBack(level=level - 1, menu_name='main').pack()
        )
    )
    keyboard.add(
        InlineKeyboardButton(
            text=_('Корзина 🛒'),
            callback_data=MenuCallBack(level=3, menu_name='cart').pack()
        )
    )

    for c in categories:
        keyboard.add(InlineKeyboardButton(text=c.name,
                                          callback_data=MenuCallBack(level=level + 1, menu_name=c.name,
                                                                     category=c.id).pack()))
        #keyboard.add(
            #InlineKeyboardButton(
                #text=c.name,
                #switch_inline_query_current_chat=f"cat_{c.id}"
            #)
        #)
    return keyboard.adjust(*sizes).as_markup()


def get_product_detail_btns(
        *,
        level: int,
        category: int,
        page: int,
        pagination_btns: Sequence[tuple[str, str]],
        product_id: int,
        list_page: int,
        category_menu_name: str,
        sizes: tuple[int, ...] = (2, 2)
):
    """Кнопки для карточки товара с переходами и возвратом к списку."""

    keyboard = InlineKeyboardBuilder()

    keyboard.add(
        InlineKeyboardButton(
            text=_('🔙 В категории'),
            callback_data=MenuCallBack(level=level - 1, menu_name='catalog').pack()
        )
    )
    keyboard.add(
        InlineKeyboardButton(
            text=_('📋 Список товаров'),
            callback_data=MenuCallBack(
                level=level,
                menu_name=category_menu_name,
                category=category,
                page=list_page,
            ).pack()
        )
    )
    keyboard.add(
        InlineKeyboardButton(
            text=_('Корзина 🛒'),
            callback_data=MenuCallBack(level=3, menu_name='cart').pack()
        )
    )
    keyboard.add(
        InlineKeyboardButton(
            text=_('Добавить в 🛒'),
            callback_data=MenuCallBack(level=level, menu_name='add_to_cart', product_id=product_id).pack()
        )
    )

    keyboard.adjust(*sizes)

    row = []
    for text, action in pagination_btns:
        if action == "next":
            row.append(
                InlineKeyboardButton(
                    text=text,
                    callback_data=MenuCallBack(
                        level=level,
                        menu_name='product_detail',
                        category=category,
                        page=page + 1,
                    ).pack(),
                )
            )
        elif action == "previous":
            row.append(
                InlineKeyboardButton(
                    text=text,
                    callback_data=MenuCallBack(
                        level=level,
                        menu_name='product_detail',
                        category=category,
                        page=page - 1,
                    ).pack(),
                )
            )

    if row:
        keyboard.row(*row)

    return keyboard.as_markup()


def get_product_list_btns(
        *,
        level: int,
        category: int,
        page: int,
        pagination_btns: Sequence[tuple[str, str]],
        products: list,
        category_menu_name: str,
        start_index: int,
):
    """Формирует клавиатуру для списка товаров с пагинацией."""

    keyboard = InlineKeyboardBuilder()

    for offset, product in enumerate(products):
        keyboard.add(
            InlineKeyboardButton(
                text=f"{product.name}",
                callback_data=MenuCallBack(
                    level=level,
                    menu_name='product_detail',
                    category=category,
                    page=start_index + offset,
                    product_id=product.id,
                ).pack(),
            )
        )

    keyboard.adjust(1)

    keyboard.row(
        InlineKeyboardButton(
            text=_('🔙 В категории'),
            callback_data=MenuCallBack(level=level - 1, menu_name='catalog').pack()
        )
    )
    pagination_row: list[InlineKeyboardButton] = []
    for text, action in pagination_btns:
        if action == "next":
            pagination_row.append(
                InlineKeyboardButton(
                    text=text,
                    callback_data=MenuCallBack(
                        level=level,
                        menu_name=category_menu_name,
                        category=category,
                        page=page + 1,
                    ).pack(),
                )
            )
        elif action == "previous":
            pagination_row.append(
                InlineKeyboardButton(
                    text=text,
                    callback_data=MenuCallBack(
                        level=level,
                        menu_name=category_menu_name,
                        category=category,
                        page=page - 1,
                    ).pack(),
                )
            )

    if pagination_row:
        keyboard.row(*pagination_row)

    return keyboard.as_markup()


def get_user_cart(
        *,
        level: int,
        page: int | None,
        pagination_btns: Sequence[tuple[str, str]] | None,
        product_id: int | None,
        sizes: tuple[int] = (3,)
):
    keyboard = InlineKeyboardBuilder()
    if page:
        keyboard.add(
            InlineKeyboardButton(
                text=_('Удалить'),
                callback_data=MenuCallBack(
                    level=level, menu_name='delete', product_id=product_id, page=page
                ).pack()
            )
        )
        keyboard.add(
            InlineKeyboardButton(
                text="-1",
                callback_data=MenuCallBack(level=level, menu_name="decrement", product_id=product_id, page=page).pack(),

            )
        )
        keyboard.add(
            InlineKeyboardButton(
                text="+1",
                callback_data=MenuCallBack(level=level, menu_name="increment", product_id=product_id, page=page).pack(),
            )

        )

        keyboard.adjust(*sizes)

        row: list[InlineKeyboardButton] = []
        for text, menu_name in (pagination_btns or []):
            if menu_name == "next":
                row.append(InlineKeyboardButton(text=text,
                                                callback_data=MenuCallBack(level=level, menu_name=menu_name,
                                                                           page=page + 1).pack()))
            elif menu_name == "previous":
                row.append(InlineKeyboardButton(text=text,
                                                callback_data=MenuCallBack(level=level, menu_name=menu_name,
                                                                           page=page - 1).pack()))

        keyboard.row(*row)

        row2 = [
            InlineKeyboardButton(
                text=_('На главную 🏠'),
                callback_data=MenuCallBack(level=0, menu_name='main').pack()
            ),
            InlineKeyboardButton(
                text=_('Заказать'),
                callback_data='start_order'  # Изменено на отдельный callback_data
            )
        ]
        return keyboard.row(*row2).as_markup()
    else:
        keyboard.add(
            InlineKeyboardButton(
                text=_('На главную 🏠'),
                callback_data=MenuCallBack(level=0, menu_name='main').pack()
            )
        )

        return keyboard.adjust(*sizes).as_markup()


def get_callback_btns(*, btns: dict[str, str], sizes: tuple[int] = (2,)) -> InlineKeyboardMarkup:
    """
    Создаёт inline-клавиатуру с кнопками из словаря `btns`.

    :param btns: Словарь вида {'Текст кнопки': 'callback_data'}
    :param sizes: Кортеж, определяющий количество кнопок в строках
    :return: Объект InlineKeyboardMarkup
    """
    keyboard = InlineKeyboardBuilder()

    for text, data in btns.items():
        keyboard.add(InlineKeyboardButton(text=text, callback_data=data))

    return keyboard.adjust(*sizes).as_markup()


def get_admin_main_kb() -> InlineKeyboardMarkup:
    btns = {
        _("Добавить товар"): "admin_add_product",
        _("Ассортимент"): "admin_products",
        _("Добавить/Изменить баннер"): "admin_banners",
         ("Создать салон"): "admin_create_salon",
    }
    return get_callback_btns(btns=btns, sizes=(2,))





def get_currency_kb() -> InlineKeyboardMarkup:
    btns = {
        "USD": "currency_USD",
        "EUR": "currency_EUR",
        "RUB": "currency_RUB",
        "UAH": "currency_UAH",
        "KZT": "currency_KZT",
        "KGS": "currency_KGS",
        "AED": "currency_AED",
    }
    return get_callback_btns(btns=btns, sizes=(2, 2, 2, 1))