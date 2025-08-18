from typing import Callable, Awaitable, Dict, Any, Optional

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from database.models import User
from utils.i18n import i18n  # единый экземпляр I18n

# Отладка: покажем, что модуль точно загрузился
print("[i18n] UserLocaleMiddleware imported")

# Логгер для i18n
logger = logging.getLogger("i18n")
logger.setLevel(logging.INFO)

SUPPORTED_LOCALES = {"ru", "en"}


def _normalize(code: Optional[str]) -> Optional[str]:
    """
    'en-US' -> 'en', 'ru' -> 'ru'. None, если пусто/неподдерживаемо.
    """
    if not code:
        return None
    base = code.split("-")[0].lower()
    return base if base in SUPPORTED_LOCALES else None


class UserLocaleMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        tg_user = getattr(event, "from_user", None)
        if tg_user is None:
            return await handler(event, data)

        # Отладка: факт входа в миддлварь
        print("[i18n] middleware called for user:", tg_user.id)

        locale: Optional[str] = None

        # 1) FSM (кладём туда 'locale' в хендлерах при выборе языка)
        state = data.get("state")
        if state:
            stored = await state.get_data()
            locale = stored.get("locale")

        # 2) БД
        if not locale:
            session: Optional[AsyncSession] = data.get("session")
            if session:
                q = select(User.language).where(User.user_id == tg_user.id)
                res = await session.execute(q)
                lang = res.scalar_one_or_none()
                if lang:
                    locale = _normalize(lang) or lang

        # 3) Язык клиента Telegram
        if not locale:
            locale = _normalize(getattr(tg_user, "language_code", None))

        # 4) Дефолт
        if not locale:
            locale = "ru"

        # Установим локаль
        i18n.ctx_locale.set(locale)

        # Двойная отладка — и print, и logging
        print("[i18n] locale set ->", i18n.ctx_locale.get())
        logger.info("locale=%s", i18n.ctx_locale.get())

        # (опционально) положим gettext в data
        data["i18n"] = i18n
        data["_"] = i18n.gettext

        return await handler(event, data)
