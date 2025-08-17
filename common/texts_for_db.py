from aiogram.types import Message
from aiogram.utils.formatting import Bold, as_list, as_marked_section
from aiogram.utils.i18n import gettext as _  # Используем обычный gettext


def get_description_for_info_pages(page_key: str):
    """Возвращает переведённый текст по ключу страницы."""
    mapping = {
        "main": _("Добро пожаловать!"),
        "about": _("Информация о компании.\nРежим работы: ежедневно."),
        "payment": as_marked_section(
            Bold(_("Способы оплаты:")),
            _("Онлайн-картой в боте"),
            _("Картой при получении"),
            _("Наличными при получении"),
            marker="✅ ",
        ),
        "shipping": as_list(
            as_marked_section(
                Bold(_("Способы получения заказа:")),
                _("Курьерская доставка"),
                _("Самовывоз из точки продаж"),
                marker="✅ ",
            ),
            sep="\n----------------------\n",
        ),
        "catalog": _("Каталог товаров и услуг:"),
        "cart": _("В корзине пока нет товаров."),
    }

    return mapping.get(page_key, "")


async def show_info(page_key: str, message: Message):
    """Отправляет информацию по указанному ключу пользователю."""
    data = get_description_for_info_pages(page_key)
    if hasattr(data, "as_html"):
        text = data.as_html()
    else:
        text = str(data)
    await message.answer(text)


def get_default_banner_description(page_key: str) -> str:
    """Возвращает описание для баннера с учётом i18n."""
    data = get_description_for_info_pages(page_key)
    if hasattr(data, "as_html"):
        return data.as_html()
    return str(data)


images_for_info_pages = {
    "main": "banners/main.jpg",
    "about": "banners/about.jpg",
    "payment": "banners/payment.jpg",
    "shipping": "banners/shipping.jpg",
    "catalog": "banners/catalog.jpg",
    "cart": "banners/cart.jpg",
}
