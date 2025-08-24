import hashlib
import hmac
import json
import logging
import os
from urllib.parse import parse_qsl

from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.engine import session_maker
from database.models import Cart


templates = Jinja2Templates(directory="web_app/templates")


async def get_session() -> AsyncSession:
    async with session_maker() as session:
        yield session


async def get_cart_count(session: AsyncSession, user_salon_id: str | None) -> int:
    if not user_salon_id:
        return 0
    total = await session.execute(
        select(func.sum(Cart.quantity)).where(Cart.user_salon_id == int(user_salon_id))
    )
    return total.scalar() or 0


def verify_init_data(init_data: str) -> dict | None:
    token = os.getenv("TOKEN")
    if not token:
        logging.error("❌ Нет TOKEN в переменных окружения")
        return None

    data = dict(parse_qsl(init_data, strict_parsing=True))
    received_hash = data.pop("hash", None)
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))

    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256)
    computed_hash = hmac.new(secret.digest(), data_check_string.encode(), hashlib.sha256).hexdigest()

    if computed_hash != received_hash:
        logging.warning("⚠️ Подпись initData не совпала")
        return None

    if "user" in data:
        data["user"] = json.loads(data["user"])
    return data
