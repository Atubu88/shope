from aiogram.types import (
    CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from database.orm_query import orm_get_user, orm_get_salon_by_id
from utils.orders import get_order_summary


def get_contact_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="💬 Написать клиенту",
                url=f"tg://user?id={user_id}"
            )
        ]]
    )


# utils/notifications.py
async def notify_salon_about_order(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    data    = await state.get_data()
    user_id = callback.from_user.id
    phone   = data.get("phone") or "Нет номера"

    user = await orm_get_user(session, user_id)
    if not user or not user.salon_id:
        print(f"[notify] salon_id не найден для user_id={user_id}")
        return

    salon = await orm_get_salon_by_id(session, user.salon_id)
    if not salon or not salon.group_chat_id:
        print(f"[notify] group_chat_id не найден для salon_id={user.salon_id}")
        return

    # ---------- чек для группы салона ----------
    group_summary = await get_order_summary(
        session, user_id, user.salon_id, data, for_group=True
    )
    await callback.bot.send_message(
        salon.group_chat_id,
        group_summary,
        parse_mode="HTML",
        reply_markup=get_contact_kb(user_id)
    )

    # ---------- контакт клиента ----------
    if phone and phone != "Нет номера":
        try:
            await callback.bot.send_contact(
                chat_id=salon.group_chat_id,
                phone_number=phone,
                first_name=user.first_name or "Клиент"
            )
        except Exception as e:
            print(f"[notify] Ошибка отправки contact: {e}")

