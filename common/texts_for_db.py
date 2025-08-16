from aiogram.utils.formatting import Bold, as_list, as_marked_section
from aiogram.utils.i18n import gettext as _


description_for_info_pages = {
    "main": _("Добро пожаловать!"),
    "about": _("Описание заведения.\nРежим работы - круглосуточно."),
    "payment": as_marked_section(
        Bold(_("Варианты оплаты:")),
        _("Картой в боте"),
        _("При получении карта/кеш"),
        _("В заведении"),
        marker="✅ ",
    ).as_html(),
    "shipping": as_list(
        as_marked_section(
            Bold(_("Варианты доставки/заказа:")),
            _("Курьер"),
            _("Самовынос (сейчас прибегу заберу)"),
            _("Покушаю у Вас (сейчас прибегу)"),
            marker="✅ ",
        ),
        as_marked_section(Bold(_("Нельзя:")), _("Почта"), marker="❌ "),
        sep="\n----------------------\n",
    ).as_html(),
    "catalog": _("Категории:"),
    "cart": _("В корзине ничего нет!"),
}

images_for_info_pages = {
    "main": "banners/main.jpg",
    "about": "banners/about.jpg",
    "payment": "banners/payment.jpg",
    "shipping": "banners/shipping.jpg",
    "catalog": "banners/catalog.jpg",
    "cart": "banners/cart.jpg",
}