"""Helpers for preparing product descriptions for Telegram."""

from __future__ import annotations

from typing import Tuple

from utils.telegraph import create_telegraph_page

DESCRIPTION_LIMIT = 100


async def prepare_description_with_details(
    title: str, description: str, description_limit: int = DESCRIPTION_LIMIT
) -> Tuple[str, str | None]:
    """Return a shortened description and optional Telegraph URL.

    When the original description exceeds ``description_limit`` characters, a
    Telegraph page is created with the full text and the Telegram description
    is trimmed to the limit with an additional "Читать далее" link.
    """

    normalized_description = description.strip()
    if len(normalized_description) <= description_limit:
        return normalized_description, None

    details_url = await create_telegraph_page(title=title, content=normalized_description)

    shortened = normalized_description[:description_limit].rstrip()
    shortened_with_link = f"{shortened}..."
    if details_url:
        shortened_with_link = f'{shortened_with_link} <a href="{details_url}">Читать далее</a>'

    return shortened_with_link, details_url
