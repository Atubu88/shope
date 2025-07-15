from aiogram import Router, types, F
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from handlers.menu_processing import get_menu_content
from utils.geo import haversine, calc_delivery_cost, get_address_from_coords
from database.orm_query import orm_get_user_carts, orm_get_user, orm_get_salon_by_id

order_router = Router()

class OrderStates(StatesGroup):
    choosing_delivery = State()
    entering_address = State()
    confirming_address = State()
    entering_apartment = State()     # <---- Новый шаг!
    entering_phone = State()
    confirming_order = State()

def get_delivery_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Курьер", callback_data="delivery_courier")],
        [InlineKeyboardButton(text="Самовывоз", callback_data="delivery_pickup")],
        [InlineKeyboardButton(text="⬅️ Назад в корзину", callback_data="back_to_cart")],
    ])

def get_confirm_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить заказ", callback_data="confirm_order")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_phone")],
    ])

def geo_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Отправить геолокацию", request_location=True)],
            [KeyboardButton(text="Назад")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def confirm_address_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data="address_ok")],
        [InlineKeyboardButton(text="✏️ Ввести вручную", callback_data="address_manual")]
    ])

async def get_order_summary(session: AsyncSession, user_id: int, salon_id: int, state_data: dict) -> str:
    cart_items = await orm_get_user_carts(session, user_id, salon_id)
    lines = []
    total = 0
    for item in cart_items:
        item_cost = item.product.price * item.quantity
        total += item_cost
        lines.append(f"- {item.product.name} {item.quantity} x {item.product.price}₽ = {item_cost}₽")
    delivery_cost = int(state_data.get("delivery_cost") or 0)
    delivery_text = ""
    if state_data.get("delivery") == "delivery_courier":
        delivery_text = f"Курьер (+{delivery_cost}₽)"
    elif state_data.get("delivery") == "delivery_pickup":
        delivery_text = "Самовывоз (0₽)"
    else:
        delivery_text = "Не выбран"

    total_with_delivery = total + delivery_cost

    text = "Ваш заказ:\n" + "\n".join(lines)
    text += f"\n\nДоставка: {delivery_text}"
    if state_data.get("address"):
        text += f"\nАдрес: {state_data['address']}"
    if state_data.get("distance_km") is not None:
        text += f"\nРасстояние: {state_data['distance_km']:.2f} км"
    text += f"\n\n<b>Итого: {total_with_delivery}₽</b>"
    return text

# --- Старт оформления ---
@order_router.callback_query(F.data == "start_order")
async def start_order(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await callback.message.delete()
    user_id = callback.from_user.id
    user = await orm_get_user(session, user_id)
    salon_id = user.salon_id if user else None

    state_data = {"delivery": None, "address": None, "delivery_cost": 0, "distance_km": None}
    summary = await get_order_summary(session, user_id, salon_id, state_data)
    msg = await callback.message.answer(
        summary + "\n\nВыберите способ доставки:",
        reply_markup=get_delivery_kb(),
        parse_mode="HTML"
    )
    await state.set_state(OrderStates.choosing_delivery)
    await state.update_data(
        last_msg_id=msg.message_id,
        delivery=None, address=None, delivery_cost=0, distance_km=None
    )

# --- Доставка: Курьер ---
@order_router.callback_query(OrderStates.choosing_delivery, F.data == "delivery_courier")
async def choose_delivery_courier(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    await state.update_data(delivery="delivery_courier", address=None, delivery_cost=0, distance_km=None)
    last_msg_id = data["last_msg_id"]

    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=last_msg_id,
        text="Пожалуйста, отправьте геолокацию для расчёта стоимости доставки.",
        reply_markup=None
    )
    geo_keyboard_msg = await callback.message.answer(
        "Отправьте геолокацию кнопкой ниже ⬇️",
        reply_markup=geo_keyboard()
    )
    await state.update_data(geo_msg_id=geo_keyboard_msg.message_id)
    await state.set_state(OrderStates.entering_address)

# --- Получение геолокации пользователя и подтверждение ---
@order_router.message(OrderStates.entering_address, F.location)
async def receive_location(message: types.Message, state: FSMContext, session: AsyncSession):
    user_lat = message.location.latitude
    user_lon = message.location.longitude

    data = await state.get_data()
    geo_msg_id = data.get("geo_msg_id")
    user_id = message.from_user.id
    user = await orm_get_user(session, user_id)
    salon_id = user.salon_id if user else None
    salon = await orm_get_salon_by_id(session, salon_id)
    if not salon.latitude or not salon.longitude:
        await message.answer("Ошибка: координаты салона не заданы.")
        return

    salon_lat = float(salon.latitude)
    salon_lon = float(salon.longitude)
    distance_km = haversine(salon_lat, salon_lon, user_lat, user_lon)
    delivery_cost = calc_delivery_cost(distance_km)

    # --- Получаем строку-адрес
    address_str = get_address_from_coords(user_lat, user_lon) or f"Геолокация ({user_lat:.5f}, {user_lon:.5f})"
    await state.update_data(address=address_str, delivery_cost=delivery_cost, distance_km=distance_km,
                            geo_lat=user_lat, geo_lon=user_lon)
    # Удаляем сообщение с клавиатурой геолокации
    if geo_msg_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=geo_msg_id)
        except Exception:
            pass

    # Отправляем подтверждение адреса!
    text = f"Вы находитесь по адресу:\n<b>{address_str}</b>\nВсё верно?"
    msg = await message.answer(
        text,
        reply_markup=confirm_address_kb(),
        parse_mode="HTML"
    )
    await state.set_state(OrderStates.confirming_address)
    await state.update_data(confirm_addr_msg_id=msg.message_id)

# --- Обработка подтверждения адреса ---
@order_router.callback_query(OrderStates.confirming_address, F.data == "address_ok")
async def address_ok(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    last_msg_id = data.get("confirm_addr_msg_id")
    # Удалить сообщение с подтверждением адреса
    try:
        await callback.bot.delete_message(chat_id=callback.message.chat.id, message_id=last_msg_id)
    except Exception:
        pass
    await state.set_state(OrderStates.entering_apartment)  # <--- Новый шаг!
    await callback.message.answer(
        "Пожалуйста, укажите номер квартиры (или подъезда, офиса):",
        reply_markup=ReplyKeyboardRemove()
    )

# --- Получение номера квартиры ---
@order_router.message(OrderStates.entering_apartment)
async def receive_apartment(message: types.Message, state: FSMContext):
    apartment = message.text.strip()
    data = await state.get_data()
    # Добавляем к адресу
    full_address = data["address"]
    if apartment:
        full_address += f", кв./офис {apartment}"
    await state.update_data(address=full_address)
    await state.set_state(OrderStates.entering_phone)
    await message.answer("Введите ваш номер телефона:")

# --- Обработка ручного ввода адреса ---
@order_router.callback_query(OrderStates.confirming_address, F.data == "address_manual")
async def address_manual(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_msg_id = data.get("confirm_addr_msg_id")
    try:
        await callback.bot.delete_message(chat_id=callback.message.chat.id, message_id=last_msg_id)
    except Exception:
        pass
    await state.set_state(OrderStates.entering_address)
    await callback.message.answer("Пожалуйста, введите адрес вручную:")

# --- Ввод телефона ---
@order_router.message(OrderStates.entering_phone)
async def enter_phone(message: types.Message, state: FSMContext, session: AsyncSession):
    phone = message.text.strip()
    data = await state.get_data()
    last_msg_id = data.get("last_msg_id")
    await state.update_data(phone=phone)
    await state.set_state(OrderStates.confirming_order)

    user_id = message.from_user.id
    user = await orm_get_user(session, user_id)
    salon_id = user.salon_id if user else None

    summary = await get_order_summary(session, user_id, salon_id, {**data, "phone": phone})

    # Удалить старое сообщение, если есть
    if last_msg_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=last_msg_id)
        except Exception:
            pass

    msg = await message.answer(
        summary + "\n\nПроверьте все данные и подтвердите заказ!",
        reply_markup=get_confirm_kb(),
        parse_mode="HTML"
    )
    await state.update_data(last_msg_id=msg.message_id)

# --- Подтверждение ---
@order_router.callback_query(OrderStates.confirming_order, F.data == "confirm_order")
async def confirm_order(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await callback.answer("Заказ подтверждён и отправлен!")
    await callback.message.edit_text("Спасибо! Ваш заказ принят 👍")
    await state.clear()



@order_router.callback_query(F.data == "back_to_cart")
async def back_to_cart(callback: CallbackQuery, state: FSMContext, session):
    user_id = callback.from_user.id

    # Получаем содержимое корзины через твой универсальный get_menu_content
    # Если уровень меню для корзины = 3 (или у тебя другое значение — подставь своё)
    image, kbds = await get_menu_content(
        session=session,
        level=3,           # Обычно 3 — это корзина, но проверь свою логику уровней!
        menu_name="main",  # Или "cart", если так у тебя называется корзина
        page=1,
        user_id=user_id,
        product_id=None,
    )

    # Удаляем сообщение, из которого пришёл callback (если нужно)
    try:
        await callback.message.delete()
    except Exception:
        pass

    # Отправляем пользователю корзину (фото + подпись + кнопки)
    # image — это InputMediaPhoto
    await callback.message.answer_photo(
        photo=image.media,          # file_id, FSInputFile или ссылка
        caption=image.caption,      # Описание, смотри get_image_banner
        reply_markup=kbds,
        parse_mode="HTML"
    )

    # Сбрасываем состояние, если нужно
    await state.clear()


# --- Доставка: Самовывоз ---
@order_router.callback_query(OrderStates.choosing_delivery, F.data == "delivery_pickup")
async def choose_delivery_pickup(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    last_msg_id = data["last_msg_id"]

    # Обновляем данные заказа: тип доставки, стоимость = 0, адрес = адрес салона
    user_id = callback.from_user.id
    user = await orm_get_user(session, user_id)
    salon_id = user.salon_id if user else None
    salon = await orm_get_salon_by_id(session, salon_id)
    address = f"{salon.name}, {salon.address}" if hasattr(salon, "address") and salon.address else "Адрес салона уточните у администратора"

    await state.update_data(
        delivery="delivery_pickup",
        delivery_cost=0,
        address=address,
        distance_km=None
    )

    # Формируем итоговый текст заказа
    summary = await get_order_summary(session, user_id, salon_id, {
        **data,
        "delivery": "delivery_pickup",
        "delivery_cost": 0,
        "address": address,
        "distance_km": None
    })

    # Обновляем сообщение
    try:
        await callback.bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=last_msg_id,
            text=summary + "\n\nПроверьте данные и подтвердите заказ!",
            reply_markup=get_confirm_kb(),
            parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            summary + "\n\nПроверьте данные и подтвердите заказ!",
            reply_markup=get_confirm_kb(),
            parse_mode="HTML"
        )

    await state.set_state(OrderStates.confirming_order)
