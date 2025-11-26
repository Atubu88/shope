"""Utilities for creating Telegraph pages for long texts."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx


async def create_telegraph_page(title: str, content: str) -> str | None:
    """Create a Telegraph page with the given title and HTML content.

    Returns the URL of the created page or ``None`` if the request failed or
    if the Telegraph token is not configured.
    """

    token = os.getenv("TELEGRAPH_ACCESS_TOKEN")
    if not token:
        logging.warning("TELEGRAPH_ACCESS_TOKEN is not configured; skipping Telegraph upload")
        return None

    payload = {
        "access_token": token,
        "title": title,
        "content": json.dumps([{"tag": "p", "children": [content]}]),
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post("https://api.telegra.ph/createPage", data=payload)
            response.raise_for_status()
    except Exception:
        logging.exception("Failed to create Telegraph page")
        return None

    data: dict[str, Any] = response.json()
    if data.get("ok") and isinstance(data.get("result"), dict):
        result = data["result"]
        url = result.get("url")
        if isinstance(url, str):
            return url

    logging.error("Unexpected response from Telegraph: %s", data)
    return None
