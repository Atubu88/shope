"""Общие утилиты и вспомогательные обработчики заказа."""

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import UserSalon
from database.orm_query import (
    orm_clear_cart,
    orm_create_order,
    orm_get_orders_count,
    orm_get_user,
    orm_get_user_carts,
    orm_get_user_salons,
)
from database.repositories import SalonRepository
from handlers.menu_processing import get_menu_content
from utils.i18n import _
from utils.notifications import notify_salon_about_order
from utils.orders import get_order_summary

from .keyboards import get_confirm_kb, get_delivery_kb, phone_keyboard
from .states import OrderStates

router = Router(name="order-helpers")


def is_back_button(message: types.Message) -> bool:
    """Проверяет, является ли сообщение кнопкой «Назад»."""

    return (message.text or "") == _("⬅️ Назад")


def get_map_link(lat: float, lon: float) -> str:
    """Возвращает ссылку на карту по координатам."""

    return f"https://maps.google.com/?q={lat},{lon}"


@router.message(OrderStates.entering_phone, is_back_button)
async def phone_back(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    """Обрабатывает возврат со стадии ввода телефона."""

    data = await state.get_data()
    back_where = data.get("phone_back")
    last_msg_id = data.get("last_msg_id")
    phone_msg_id = data.get("phone_msg_id")

    if phone_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, phone_msg_id)
        except Exception:
            pass

    try:
        await message.bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass

    await message.answer("\u2063", reply_markup=types.ReplyKeyboardRemove())

    if back_where == "apartment":
        if last_msg_id:
            try:
                await message.bot.delete_message(message.chat.id, last_msg_id)
            except Exception:
                pass

        await state.set_state(OrderStates.entering_apartment)
        await state.update_data(phone_back=None, phone_msg_id=None)
        await message.answer(_("Пожалуйста, укажите номер квартиры (или подъезда, офиса):"))
        return

    if last_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, last_msg_id)
        except Exception:
            pass

    await state.update_data(
        delivery=None,
        address=None,
        delivery_cost=0,
        distance_km=None,
        phone_back=None,
        phone_msg_id=None,
    )

    data = await state.get_data()
    user_salon_id = data.get("user_salon_id")
    summary = await get_order_summary(session, user_salon_id, data) if user_salon_id else ""

    new_msg = await message.answer(
        summary + "\n\n" + _("Выберите способ доставки:"),
        reply_markup=get_delivery_kb(),
        parse_mode="HTML",
    )

    await state.update_data(last_msg_id=new_msg.message_id)
    await state.set_state(OrderStates.choosing_delivery)


@router.message(OrderStates.entering_phone)
async def enter_phone(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    """Сохраняет телефон и показывает итог заказа для подтверждения."""

    phone = (
        message.contact.phone_number
        if message.contact and message.contact.phone_number
        else (message.text or "").strip()
    )

    data = await state.get_data()
    last_msg_id = data.get("last_msg_id")
    await state.update_data(phone=phone)
    await state.set_state(OrderStates.confirming_order)

    user_salon_id = data.get("user_salon_id")

    if last_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, last_msg_id)
        except Exception:
            pass

    await message.answer(_("Спасибо, номер получен!"), reply_markup=types.ReplyKeyboardRemove())

    summary = (
        await get_order_summary(session, user_salon_id, {**data, "phone": phone})
        if user_salon_id
        else ""
    )

    msg = await message.answer(
        summary + "\n\n" + _("Проверьте все данные и подтвердите заказ!"),
        reply_markup=get_confirm_kb(),
        parse_mode="HTML",
    )
    await state.update_data(last_msg_id=msg.message_id)


@router.callback_query(OrderStates.confirming_order, F.data == "confirm_order")
async def confirm_order(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Финализирует заказ и очищает корзину пользователя."""

    repo = SalonRepository(session)
    data = await state.get_data()
    user_salon_id = data.get("user_salon_id")

    cart_items = await orm_get_user_carts(session, user_salon_id) if user_salon_id else []

    if user_salon_id and cart_items:
        user_salon = await session.get(UserSalon, user_salon_id)
        salon = await repo.get_by_id(user_salon.salon_id) if user_salon else None
        if salon and salon.free_plan:
            orders_count = await orm_get_orders_count(session, salon.id)
            if orders_count >= salon.order_limit:
                await callback.message.answer(
                    _(
                        "Вы достигли лимита бесплатного тарифа ({limit} заказов). Чтобы продолжить приём заказов, продлите подписку."
                    ).format(limit=salon.order_limit)
                )
                await state.clear()
                return

        name = " ".join(
            filter(
                None,
                [user_salon.first_name if user_salon else None, user_salon.last_name if user_salon else None],
            )
        ) or callback.from_user.full_name or ""

        delivery_type = data.get("delivery") or ""
        payment_method = data.get("payment_method")

        if not payment_method:
            if delivery_type in {"samovyvoz", "pickup"}:
                payment_method = "pickup"
            elif delivery_type == "delivery_courier":
                payment_method = "cash"

        email = data.get("email") or ""
        comment = data.get("comment") or ""

        await orm_create_order(
            session,
            user_salon_id=user_salon_id,
            name=name,
            address=data.get("address"),
            phone=data.get("phone"),
            email=email,
            delivery_type=delivery_type,
            payment_method=payment_method,
            comment=comment,
            cart_items=cart_items,
        )
        await notify_salon_about_order(callback, state, session, user_salon_id)
        await orm_clear_cart(session, user_salon_id)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await callback.message.answer(_("Спасибо! Ваш заказ принят 👍"))
        await state.clear()
    else:
        await callback.message.answer(_("Ваша корзина пуста или не выбран салон. Заказ не оформлен."))
        await state.clear()

    await callback.answer()


@router.callback_query(F.data == "back_to_cart")
async def back_to_cart(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Возвращает пользователя в корзину, очищая состояние заказа."""

    data = await state.get_data()
    user_salon_id = data.get("user_salon_id")

    if not user_salon_id:
        user_id = callback.from_user.id
        user_salons = await orm_get_user_salons(session, user_id)
        if len(user_salons) != 1:
            await callback.message.answer(_("Не удалось определить салон. Пожалуйста, выберите салон."))
            await callback.answer()
            return
        user_salon_id = user_salons[0].id

    await state.clear()
    await state.update_data(user_salon_id=user_salon_id)

    image, kbds = await get_menu_content(
        session=session,
        level=3,
        menu_name="main",
        page=1,
        user_salon_id=user_salon_id,
    )

    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer_photo(
        photo=image.media,
        caption=image.caption,
        reply_markup=kbds,
        parse_mode="HTML",
    )

    await callback.answer()


@router.callback_query(OrderStates.confirming_order, F.data == "back_to_phone")
async def back_to_phone(callback: CallbackQuery, state: FSMContext) -> None:
    """Возвращает на шаг ввода телефона из экрана подтверждения."""

    data = await state.get_data()
    last_msg_id = data.get("last_msg_id")

    if last_msg_id:
        try:
            await callback.bot.delete_message(
                chat_id=callback.message.chat.id,
                message_id=last_msg_id,
            )
        except Exception:
            pass

    await state.set_state(OrderStates.entering_phone)
    await callback.message.answer(
        _("Пожалуйста, введите ваш номер телефона или отправьте контакт кнопкой ниже 👇"),
        reply_markup=phone_keyboard(),
    )

    await callback.answer()
