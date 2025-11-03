"""Тесты для inline-клавиатур пользователя."""

from types import SimpleNamespace

from kbds.inline import get_product_list_btns
from utils.i18n import _


def test_product_list_paginator_is_last_row() -> None:
    """Убеждаемся, что пагинатор расположен в самом низу списка товаров."""

    products = [
        SimpleNamespace(id=1, name="Шампунь"),
        SimpleNamespace(id=2, name="Маска"),
    ]
    pagination_btns = {_("◀ Пред."): "previous", _("След. ▶"): "next"}

    markup = get_product_list_btns(
        level=2,
        category=10,
        page=1,
        pagination_btns=pagination_btns,
        products=products,
        category_menu_name="hair",
        start_index=1,
    )

    last_row_texts = [button.text for button in markup.inline_keyboard[-1]]

    assert last_row_texts == [_("◀ Пред."), _("След. ▶")]
