"""Generate invite links for salon creation."""
from __future__ import annotations

from uuid import uuid4
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from filters.chat_types import ChatTypeFilter, IsAdmin

invite_link_router = Router()
invite_link_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())


@invite_link_router.message(Command("invite"))
async def generate_invite(message: types.Message) -> None:
    token = uuid4().hex[:10]
    bot_username = (await message.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start=invite_{token}"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Скопировать ссылку", switch_inline_query=link)]]
    )
    await message.answer(f"Инвайт для создания салона:\n{link}", reply_markup=kb)

