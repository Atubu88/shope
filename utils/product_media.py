"""Утилиты для выбора изображений товаров."""

from typing import Optional


def select_product_photo(image_file_id: Optional[str], image_url: Optional[str]) -> Optional[str]:
    """Возвращает приоритетный источник фото товара.

    Сначала используется Telegram ``file_id`` (не тратится трафик на загрузку),
    при его отсутствии — ссылка на изображение в облаке.
    """

    return image_file_id or image_url
