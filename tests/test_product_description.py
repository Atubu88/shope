import pytest

from utils import product_description


@pytest.mark.asyncio
async def test_prepare_description_short_text_returns_original():
    original = "Короткое описание"

    description, details_url = await product_description.prepare_description_with_details(
        "Товар",
        original,
        description_limit=len(original) + 1,
    )

    assert description == original
    assert details_url is None


@pytest.mark.asyncio
async def test_prepare_description_long_text_creates_link(monkeypatch):
    full_text = "Очень длинное описание " * 5
    expected_url = "https://telegra.ph/example"

    async def fake_create_page(title: str, content: str) -> str:
        assert title == "Товар"
        assert content == full_text.strip()
        return expected_url

    monkeypatch.setattr(product_description, "create_telegraph_page", fake_create_page)

    description, details_url = await product_description.prepare_description_with_details(
        "Товар",
        full_text,
        description_limit=20,
    )

    assert description.startswith(full_text.strip()[:20].rstrip())
    assert expected_url in description
    assert description.endswith(f'"{expected_url}">Читать далее</a>')
    assert details_url == expected_url
