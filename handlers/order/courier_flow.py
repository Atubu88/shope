"""Обработчики шагов для доставки курьером."""

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import UserSalon
from database.orm_query import orm_get_user
from database.repositories import SalonRepository
from utils.geo import calc_delivery_cost, get_address_from_coords, haversine
from utils.i18n import _
from utils.orders import get_order_summary

from .helpers import is_back_button
from .keyboards import confirm_address_kb, geo_keyboard, get_delivery_kb, phone_keyboard
from .states import OrderStates

router = Router(name="order-courier")


@router.callback_query(OrderStates.choosing_delivery, F.data == "delivery_courier")
async def choose_delivery_courier(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Запрашивает геолокацию для расчёта стоимости доставки."""

    data = await state.get_data()
    await state.update_data(
        delivery="delivery_courier",
        address=None,
        delivery_cost=0,
        distance_km=None,
    )
    last_msg_id = data["last_msg_id"]

    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=last_msg_id,
        text=_("Пожалуйста, отправьте геолокацию для расчёта стоимости доставки."),
        reply_markup=None,
    )

    geo_msg = await callback.message.answer(
        _("Отправьте геолокацию кнопкой ниже ⬇️"),
        reply_markup=geo_keyboard(),
    )

    await state.update_data(geo_msg_id=geo_msg.message_id)
    await state.set_state(OrderStates.entering_address)
    await callback.answer()


@router.message(OrderStates.entering_address, F.location)
async def receive_location(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    """Получает геолокацию пользователя и рассчитывает стоимость доставки."""

    user_lat = message.location.latitude
    user_lon = message.location.longitude

    repo = SalonRepository(session)
    data = await state.get_data()
    geo_msg_id = data.get("geo_msg_id")
    last_msg_id = data.get("last_msg_id")

    user_salon_id = data.get("user_salon_id")
    user = (
        await session.get(UserSalon, user_salon_id)
        if user_salon_id
        else await orm_get_user(session, message.from_user.id)
    )
    salon = await repo.get_by_id(user.salon_id) if user else None

    if not salon or not salon.latitude or not salon.longitude:
        await message.answer(_("Ошибка: координаты салона не заданы."))
        return

    distance_km = haversine(float(salon.latitude), float(salon.longitude), user_lat, user_lon)
    delivery_cost = calc_delivery_cost(distance_km)

    address_str = (
        get_address_from_coords(user_lat, user_lon)
        or _("Геолокация ({lat:.5f}, {lon:.5f})").format(lat=user_lat, lon=user_lon)
    )

    await state.update_data(
        address=address_str,
        delivery_cost=delivery_cost,
        distance_km=distance_km,
        geo_lat=user_lat,
        geo_lon=user_lon,
    )

    if geo_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, geo_msg_id)
        except Exception:
            pass

    if last_msg_id:
        try:
            await message.bot.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=last_msg_id,
                reply_markup=None,
            )
        except Exception:
            pass

    confirm_msg = await message.answer(
        _("Вы находитесь по адресу:\n<b>{address}</b>\nВсё верно?").format(address=address_str),
        reply_markup=confirm_address_kb(),
        parse_mode="HTML",
    )
    await state.update_data(confirm_addr_msg_id=confirm_msg.message_id)
    await state.set_state(OrderStates.confirming_address)


@router.message(OrderStates.entering_address, is_back_button)
async def back_to_delivery_msg(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    """Возвращает пользователя к выбору типа доставки."""

    data = await state.get_data()
    geo_msg_id = data.get("geo_msg_id")
    last_msg_id = data.get("last_msg_id")
    apt_msg_id = data.get("apt_msg_id")

    for mid in (geo_msg_id, last_msg_id, apt_msg_id):
        if mid:
            try:
                await message.bot.delete_message(message.chat.id, mid)
            except Exception:
                pass

    await state.update_data(apt_msg_id=None)

    user_salon_id = data.get("user_salon_id")
    summary = await get_order_summary(session, user_salon_id, data) if user_salon_id else ""

    new_msg = await message.answer(
        summary + "\n\n" + _("Выберите способ доставки:"),
        reply_markup=get_delivery_kb(),
        parse_mode="HTML",
    )
    await state.update_data(last_msg_id=new_msg.message_id)
    await state.set_state(OrderStates.choosing_delivery)
    await message.answer("\u2063", reply_markup=types.ReplyKeyboardRemove())


@router.message(OrderStates.entering_address, F.text)
async def receive_address_text(message: types.Message, state: FSMContext) -> None:
    """Сохраняет вручную введённый адрес и запрашивает номер квартиры."""

    address_str = (message.text or "").strip()
    if not address_str:
        await message.answer(_("Пожалуйста, введите корректный адрес."))
        return

    await state.update_data(address=address_str)
    await state.set_state(OrderStates.entering_apartment)
    await message.answer(
        _("Пожалуйста, укажите номер квартиры (или подъезда, офиса):"),
        reply_markup=types.ReplyKeyboardRemove(),
    )


@router.callback_query(OrderStates.confirming_address, F.data == "address_ok")
async def address_ok(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Подтверждает адрес и переводит к вводу квартиры."""

    data = await state.get_data()
    last_msg_id = data.get("confirm_addr_msg_id")

    if last_msg_id:
        try:
            await callback.bot.delete_message(callback.message.chat.id, last_msg_id)
        except Exception:
            pass

    ask_msg = await callback.message.answer(
        _("Пожалуйста, укажите номер квартиры (или подъезда, офиса):"),
        reply_markup=types.ReplyKeyboardRemove(),
    )

    await state.update_data(apt_msg_id=ask_msg.message_id)
    await state.set_state(OrderStates.entering_apartment)
    await callback.answer()


@router.message(OrderStates.entering_apartment)
async def receive_apartment(message: types.Message, state: FSMContext) -> None:
    """Добавляет номер квартиры к адресу и переходит к запросу телефона."""

    apartment = (message.text or "").strip()

    data = await state.get_data()
    full_addr = data["address"]
    apt_msg_id = data.get("apt_msg_id")

    if apartment:
        full_addr += _(", кв./офис {apt}").format(apt=apartment)
    await state.update_data(address=full_addr)

    if apt_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, apt_msg_id)
        except Exception:
            pass

    await state.set_state(OrderStates.entering_phone)

    phone_msg = await message.answer(
        _("Пожалуйста, введите ваш номер телефона или отправьте контакт кнопкой ниже 👇"),
        reply_markup=phone_keyboard(),
    )

    await state.update_data(phone_back="apartment", phone_msg_id=phone_msg.message_id)


@router.callback_query(OrderStates.confirming_address, F.data == "address_manual")
async def address_manual(callback: CallbackQuery, state: FSMContext) -> None:
    """Переключает ввод адреса на ручной режим."""

    data = await state.get_data()
    last_msg_id = data.get("confirm_addr_msg_id")
    try:
        await callback.bot.delete_message(chat_id=callback.message.chat.id, message_id=last_msg_id)
    except Exception:
        pass
    await state.set_state(OrderStates.entering_address)
    await callback.message.answer(_("Пожалуйста, введите адрес вручную:"))
