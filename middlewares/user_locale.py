from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from aiogram.utils.i18n import I18n
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Callable, Dict, Any, Awaitable

from database.orm_query import orm_get_user  # важно!
from database.models import User

class UserLocaleMiddleware(BaseMiddleware):
    def __init__(self, i18n: I18n):
        super().__init__()
        self.i18n = i18n

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        session: AsyncSession = data.get("session")
        if not session:
            return await handler(event, data)

        user_id = (
            getattr(event.from_user, "id", None)
            if hasattr(event, "from_user")
            else None
        )
        if not user_id:
            return await handler(event, data)

        user = await orm_get_user(session, user_id)
        if user:
            lang = user.language or self.i18n.default_locale
            self.i18n.ctx_locale.set(lang)
        else:
            self.i18n.ctx_locale.set(self.i18n.default_locale)

        return await handler(event, data)
