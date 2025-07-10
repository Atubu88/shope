from aiogram.filters import Filter
from aiogram import Bot, types
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query import orm_get_user


class ChatTypeFilter(Filter):
    def __init__(self, chat_types: list[str]) -> None:
        self.chat_types = chat_types

    async def __call__(self, message: types.Message) -> bool:
        return message.chat.type in self.chat_types


class IsAdmin(Filter):
    def __init__(self) -> None:
        pass

    async def __call__(self, message: types.Message, bot: Bot, session: AsyncSession) -> bool:
        if message.from_user.id in bot.my_admins_list:
            return True
        user = await orm_get_user(session, message.from_user.id)
        return bool(user and (user.is_super_admin or user.is_salon_admin))


class IsSuperAdmin(Filter):
    async def __call__(self, message: types.Message, session: AsyncSession) -> bool:
        user = await orm_get_user(session, message.from_user.id)
        return bool(user and user.is_super_admin)