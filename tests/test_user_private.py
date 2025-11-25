"""Тесты для пользовательских хендлеров."""

from handlers.user_private import extract_start_param


def test_extract_start_param_with_space_payload():
    """Парсер должен вытаскивать payload, переданный через пробел."""

    assert extract_start_param("/start beauty-salon-abc") == "beauty-salon-abc"


def test_extract_start_param_with_equals_payload():
    """Парсер должен поддерживать формат ``/start=payload`` без пробела."""

    assert extract_start_param("/start=beauty-salon-abc") == "beauty-salon-abc"


def test_extract_start_param_unknown_format():
    """Неверные строки не должны возвращать payload."""

    assert extract_start_param("/help") is None
    assert extract_start_param("just text") is None
