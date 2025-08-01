import os
import uuid
import asyncio
from io import BytesIO
from typing import Optional

from supabase import create_client
from aiogram import Bot

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET")

_client = create_client(SUPABASE_URL, SUPABASE_API_KEY) if SUPABASE_URL and SUPABASE_API_KEY else None

async def upload_photo_from_telegram(bot: Bot, file_id: str, filename: Optional[str] = None) -> str:
    """Download file from Telegram and upload it to Supabase. Return public URL."""
    if _client is None:
        raise RuntimeError("Supabase client is not configured")

    if not filename:
        filename = f"{uuid.uuid4()}.jpg"

    file_io = await bot.download(file_id)
    data = file_io.read()

    # Передаём опции как словарь, строки!
    options = {
        "content-type": "image/jpeg",
        "x-upsert": "true"
    }

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: _client.storage.from_(SUPABASE_BUCKET).upload(filename, data, options)
    )

    return _client.storage.from_(SUPABASE_BUCKET).get_public_url(filename)


async def delete_photo_from_supabase(filename: str):
    if _client is None:
        raise RuntimeError("Supabase client is not configured")

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: _client.storage.from_(SUPABASE_BUCKET).remove([filename])
    )

def get_path_from_url(url: str) -> str:
    return url.split("/")[-1]

