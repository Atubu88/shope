"""Стартовые шаги оформления заказа."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query import orm_get_user
from utils.i18n import _
from utils.orders import get_order_summary

from .keyboards import get_delivery_kb
from .states import OrderStates

router = Router(name="order-start")


@router.callback_query(F.data == "start_order")
async def start_order(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Запускает оформление заказа и предлагает выбрать способ доставки."""

    await callback.message.delete()
    user_id = callback.from_user.id
    data = await state.get_data()
    user_salon_id = data.get("user_salon_id")
    if not user_salon_id:
        user = await orm_get_user(session, user_id)
        user_salon_id = user.id if user else None

    state_data = {
        "delivery": None,
        "address": None,
        "delivery_cost": 0,
        "distance_km": None,
    }
    summary = await get_order_summary(session, user_salon_id, state_data)
    msg = await callback.message.answer(
        summary + "\n\n" + _("Выберите способ доставки:"),
        reply_markup=get_delivery_kb(),
        parse_mode="HTML",
    )
    await state.set_state(OrderStates.choosing_delivery)
    await state.update_data(
        last_msg_id=msg.message_id,
        user_salon_id=user_salon_id,
        delivery=None,
        address=None,
        delivery_cost=0,
        distance_km=None,
    )
