"""Тесты для вспомогательных функций меню каталога."""

from types import SimpleNamespace

from handlers.menu_processing import _number_to_emoji, format_product_list,  format_product_list_caption


def test_number_to_emoji_known_values() -> None:
    """Проверяет корректное отображение чисел эмодзи и fallback."""

    assert _number_to_emoji(1) == "1️⃣"
    assert _number_to_emoji(10) == "🔟"
    assert _number_to_emoji(12) == "12."


def test_format_product_list_creates_expected_text() -> None:
    """Проверяет формирование текста списка товаров с ценами."""

    products = [
        SimpleNamespace(name="Шампунь «Мята»", price=250),
        SimpleNamespace(name="Маска для волос", price=390),
        SimpleNamespace(name="Кондиционер", price=300),
    ]

    text = format_product_list(
        category_name="Товары для ухода",
        products=products,
        currency="₽",
        start_index=1,
    )

    assert "🏷️ **Категория:** Товары для ухода" in text
    assert "1️⃣ Шампунь «Мята» — 250 ₽" in text
    assert "2️⃣ Маска для волос — 390 ₽" in text
    assert "3️⃣ Кондиционер — 300 ₽" in text



def test_format_product_list_caption_contains_page_info() -> None:
    """Проверяет, что подпись включает название категории и номер страницы."""

    caption = format_product_list_caption(
        category_name="Уход",
        current_page=1,
        total_pages=2,
    )

    assert "🏷️ **Категория:** Уход" in caption
    assert "📋 **Список товаров:** 1 из 2" in caption
