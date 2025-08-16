from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from aiogram.utils.i18n import I18n
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Callable, Dict, Any, Awaitable

from database.orm_query import orm_get_user
from database.models import User  # 👈 нужно импортировать

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

        # Смотри, есть ли salon_id в state
        state_data = data.get("state")
        salon_id = None
        if state_data:
            salon_id_data = await state_data.get_data()
            salon_id = salon_id_data.get("salon_id") or salon_id_data.get("user_salon_id")

        lang = None

        if salon_id:
            user_salon = await orm_get_user(session, user_id, salon_id=salon_id)
            if user_salon and user_salon.user and user_salon.user.language:
                lang = user_salon.user.language

        # ✅ Если язык не удалось получить — попробуем достать напрямую из таблицы User
        if not lang:
            result = await session.execute(select(User.language).where(User.user_id == user_id))
            lang = result.scalar_one_or_none()

        # Если всё ещё нет — ставим язык по умолчанию
        if not lang:
            lang = self.i18n.default_locale

        self.i18n.ctx_locale.set(lang)
        return await handler(event, data)
