"""Обработчики сценария самовывоза."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import UserSalon
from database.orm_query import orm_get_user
from database.repositories import SalonRepository
from utils.i18n import _
from utils.orders import get_order_summary

from .keyboards import get_pickup_time_kb, phone_keyboard
from .states import OrderStates

router = Router(name="order-pickup")


@router.callback_query(OrderStates.choosing_delivery, F.data == "delivery_pickup")
async def choose_delivery_pickup(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Выбирает самовывоз и предлагает выбрать время готовности."""

    repo = SalonRepository(session)
    data = await state.get_data()
    last_msg_id = data["last_msg_id"]

    user_salon_id = data.get("user_salon_id")
    user = (
        await session.get(UserSalon, user_salon_id)
        if user_salon_id
        else await orm_get_user(session, callback.from_user.id)
    )
    if user and not user_salon_id:
        user_salon_id = user.id
        await state.update_data(user_salon_id=user_salon_id)
    salon = await repo.get_by_id(user.salon_id) if user else None

    if salon and salon.latitude and salon.longitude:
        address = (
            f'<a href="https://maps.google.com/?q={salon.latitude},{salon.longitude}">'
            + _("Открыть на карте")
            + "</a>"
        )
    else:
        address = _("Адрес салона не указан")

    await state.update_data(
        delivery="delivery_pickup",
        delivery_cost=0,
        address=address,
        distance_km=None,
    )

    summary = (
        await get_order_summary(
            session,
            user_salon_id,
            {
                **data,
                "delivery": "delivery_pickup",
                "delivery_cost": 0,
                "address": address,
                "distance_km": None,
            },
        )
        if user_salon_id
        else ""
    )

    prompt_text = summary + "\n\n" + _("Когда вы будете в салоне?")
    prompt_message_id = last_msg_id
    try:
        await callback.bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=last_msg_id,
            text=prompt_text,
            reply_markup=get_pickup_time_kb(),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception:
        prompt_msg = await callback.message.answer(
            prompt_text,
            reply_markup=get_pickup_time_kb(),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        prompt_message_id = prompt_msg.message_id

    await state.set_state(OrderStates.choosing_pickup_time)
    await state.update_data(
        phone_back="delivery", phone_msg_id=None, last_msg_id=prompt_message_id
    )
    await callback.answer()


@router.callback_query(OrderStates.choosing_pickup_time, F.data.startswith("pickup_time:"))
async def set_pickup_time(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Сохраняет выбранное время самовывоза и запрашивает телефон."""

    minutes = int((callback.data or "").split(":", maxsplit=1)[1])

    repo = SalonRepository(session)
    data = await state.get_data()
    user_salon_id = data.get("user_salon_id")
    user = (
        await session.get(UserSalon, user_salon_id)
        if user_salon_id
        else await orm_get_user(session, callback.from_user.id)
    )
    salon = await repo.get_by_id(user.salon_id) if user else None
    tz_name = salon.timezone or "UTC" if salon else "UTC"

    # DEBUG
    print("\n\n===== DEBUG TIMEZONE =====")
    print("salon.timezone =", salon.timezone)
    print("tz_name =", tz_name)
    try:
        print("ZoneInfo =", ZoneInfo(tz_name))
    except Exception as e:
        print("ZoneInfo ERROR:", e)
    print("=================================\n\n")

    # КОРРЕКТНЫЙ РАСЧЁТ ВРЕМЕНИ
    utc_now = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC"))
    local_now = utc_now.astimezone(ZoneInfo(tz_name))

    pickup_dt = local_now + timedelta(minutes=minutes)
    pickup_time = pickup_dt.strftime("%H:%M")

    await state.update_data(pickup_time=pickup_time)

    summary = (
        await get_order_summary(session, user_salon_id, {**data, "pickup_time": pickup_time})
        if user_salon_id
        else ""
    )

    last_msg_id = data.get("last_msg_id")
    try:
        await callback.bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=last_msg_id,
            text=summary,
            reply_markup=None,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception:
        prompt_msg = await callback.message.answer(
            summary,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        last_msg_id = prompt_msg.message_id

    await state.set_state(OrderStates.entering_phone)

    phone_msg = await callback.message.answer(
        _("Пожалуйста, введите ваш номер телефона или отправьте контакт кнопкой ниже 👇"),
        reply_markup=phone_keyboard(),
    )
    await state.update_data(
        phone_back="delivery", last_msg_id=last_msg_id, phone_msg_id=phone_msg.message_id
    )
    await callback.answer()

