from utils.product_media import select_product_photo


def test_select_product_photo_prefers_file_id() -> None:
    """Возвращает file_id, если он передан."""

    assert select_product_photo("FILE_ID", "https://example.com/image.jpg") == "FILE_ID"


def test_select_product_photo_uses_url_if_no_file_id() -> None:
    """Возвращает ссылку, когда file_id отсутствует."""

    assert select_product_photo(None, "https://example.com/image.jpg") == "https://example.com/image.jpg"


def test_select_product_photo_returns_none_when_empty() -> None:
    """Возвращает None, если нет ни file_id, ни ссылки."""

    assert select_product_photo(None, None) is None
