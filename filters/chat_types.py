from aiogram import types
from aiogram.filters import Filter
from sqlalchemy.ext.asyncio import AsyncSession
from database.orm_query import orm_get_user


class ChatTypeFilter(Filter):
    def __init__(self, chat_types: list[str]) -> None:
        self.chat_types = chat_types

    async def __call__(self, message: types.Message) -> bool:
        return message.chat.type in self.chat_types


class IsAdmin(Filter):
    async def __call__(self, obj: types.Update, session: AsyncSession) -> bool:
        # поддержка и Message, и CallbackQuery
        if isinstance(obj, types.CallbackQuery):
            user_id = obj.from_user.id
        elif isinstance(obj, types.Message):
            user_id = obj.from_user.id
        else:
            return False

        user = await orm_get_user(session, user_id)
        return bool(user and (user.is_super_admin or user.is_salon_admin))


class IsSuperAdmin(Filter):
    async def __call__(self, obj: types.Update, session: AsyncSession) -> bool:
        if isinstance(obj, types.CallbackQuery):
            user_id = obj.from_user.id
        elif isinstance(obj, types.Message):
            user_id = obj.from_user.id
        else:
            return False

        user = await orm_get_user(session, user_id)
        return bool(user and user.is_super_admin)
