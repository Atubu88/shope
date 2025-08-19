from typing import Dict

from aiogram.types import Message
from aiogram.utils.formatting import Bold, as_list, as_marked_section

from utils.i18n import _, i18n  # ✅ единый gettext


def get_description_for_info_pages(page_key: str):
    if page_key == "main":
        locale = i18n.ctx_locale.get()

        if locale == "en":
            url = "https://telegra.ph/aucacuva-07-18"  # английская версия
        else:
            url = "https://telegra.ph/EHtot-bot--ne-prosto-picceriya-07-18"  # русская версия

        result = (
            "👋 " + _("Добро пожаловать!") + "\n"
            + f'<a href="{url}">' + _("Подробнее о боте") + "</a>"
        )
        print("DEBUG get_description_for_info_pages:", repr(result))
        return result

    elif page_key == "about":
        return _("Информация о компании.\nРежим работы: ежедневно.")
    elif page_key == "payment":
        return as_marked_section(
            Bold(_("Способы оплаты:")),
            _("Онлайн-картой в боте"),
            _("Картой при получении"),
            _("Наличными при получении"),
            marker="✅ ",
        )
    elif page_key == "shipping":
        return as_list(
            as_marked_section(
                Bold(_("Способы получения заказа:")),
                _("Курьерская доставка"),
                _("Самовывоз из точки продаж"),
                marker="✅ ",
            ),
            sep="\n----------------------\n",
        )
    elif page_key == "catalog":
        return _("Каталог товаров и услуг:")
    elif page_key == "cart":
        return _("В корзине пока нет товаров.")
    else:
        return ""


async def show_info(page_key: str, message: Message):
    """
    Отправляет информацию по указанному ключу пользователю.
    Учитывает, что get_description_for_info_pages может вернуть объект форматирования.
    """
    data = get_description_for_info_pages(page_key)
    text = data.as_html() if hasattr(data, "as_html") else str(data)
    await message.answer(text)


def get_default_banner_description(page_key: str) -> str:
    """
    Возвращает описание для баннера с учётом текущей локали (ctx_locale).
    Совместимо и со строками, и с объектами форматирования.
    """
    data = get_description_for_info_pages(page_key)
    if hasattr(data, "as_html"):
        return data.as_html()
    return str(data)


images_for_info_pages: Dict[str, str] = {
    "main": "banners/main.jpg",
    "about": "banners/about.jpg",
    "payment": "banners/payment.jpg",
    "shipping": "banners/shipping.jpg",
    "catalog": "banners/catalog.jpg",
    "cart": "banners/cart.jpg",
}

# Описания баннеров: если None — будет использован get_default_banner_description(page_key).
description_for_info_pages: Dict[str, str | None] = {key: None for key in images_for_info_pages}
