from aiogram import Router, types, F
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from utils.notifications import notify_salon_about_order
from utils.orders import get_order_summary
from handlers.menu_processing import get_menu_content
from utils.geo import haversine, calc_delivery_cost, get_address_from_coords
from database.orm_query import (
    orm_get_user_carts,
    orm_get_user,
    orm_get_salon_by_id,
    orm_clear_cart,
    orm_create_order,
    orm_get_user_salons,
)
from database.models import UserSalon

order_router = Router()

class OrderStates(StatesGroup):
    choosing_delivery = State()
    entering_address = State()
    confirming_address = State()
    entering_apartment = State()
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

def geo_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Отправить геолокацию", request_location=True)],
            [KeyboardButton(text="⬅️ Назад")],    # ← обычный текст, без константы
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def confirm_address_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data="address_ok")],
        [InlineKeyboardButton(text="✏️ Ввести вручную", callback_data="address_manual")]
    ])

BACK_PHONE_TXT = "⬅️ Назад"

def phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📞 Отправить номер телефона",
                            request_contact=True)],
            [KeyboardButton(text=BACK_PHONE_TXT)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


# --- Старт оформления ---
@order_router.callback_query(F.data == "start_order")
async def start_order(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await callback.message.delete()
    user_id = callback.from_user.id
    user = await orm_get_user(session, user_id)
    user_salon_id = user.id if user else None

    state_data = {"delivery": None, "address": None, "delivery_cost": 0, "distance_km": None}
    summary = await get_order_summary(session, user_salon_id, state_data)
    msg = await callback.message.answer(
        summary + "\n\nВыберите способ доставки:",
        reply_markup=get_delivery_kb(),
        parse_mode="HTML"
    )
    await state.set_state(OrderStates.choosing_delivery)
    await state.update_data(
        last_msg_id=msg.message_id,
        user_salon_id=user_salon_id,
        delivery=None, address=None, delivery_cost=0, distance_km=None
    )

# --- Доставка: Курьер ---
@order_router.callback_query(OrderStates.choosing_delivery,
                             F.data == "delivery_courier")
async def choose_delivery_courier(callback: CallbackQuery,
                                  state: FSMContext,
                                  session: AsyncSession):

    data = await state.get_data()
    await state.update_data(delivery="delivery_courier",
                            address=None, delivery_cost=0, distance_km=None)
    last_msg_id = data["last_msg_id"]

    # редактируем старое сообщение без inline‑клавиатуры
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=last_msg_id,
        text="Пожалуйста, отправьте геолокацию для расчёта стоимости доставки.",
        reply_markup=None
    )

    # ⬇️ оставляем пузырёк с Reply‑клавиатурой — НЕ удаляем!
    geo_msg = await callback.message.answer(
        "Отправьте геолокацию кнопкой ниже ⬇️",
        reply_markup=geo_keyboard()
    )

    # сохраняем ID, чтобы потом убрать, когда локация придёт или нажмут «Назад»
    await state.update_data(geo_msg_id=geo_msg.message_id)
    await state.set_state(OrderStates.entering_address)
    await callback.answer()



# --- Получение геолокации пользователя и подтверждение ---
@order_router.message(OrderStates.entering_address, F.location)
async def receive_location(message: types.Message, state: FSMContext, session: AsyncSession):
    user_lat = message.location.latitude
    user_lon = message.location.longitude

    data = await state.get_data()
    geo_msg_id  = data.get("geo_msg_id")      # 📍‑сообщение с reply‑клавиатурой
    last_msg_id = data.get("last_msg_id")     # «Пожалуйста, отправьте геолокацию…» + «⬅️ Назад»

    # --- расчёт доставки ------------------------------------------------
    user_salon_id = data.get("user_salon_id")
    user = await session.get(UserSalon, user_salon_id) if user_salon_id else await orm_get_user(session, message.from_user.id)
    salon    = await orm_get_salon_by_id(session, user.salon_id) if user else None

    if not salon.latitude or not salon.longitude:
        await message.answer("Ошибка: координаты салона не заданы.")
        return

    salon_lat = float(salon.latitude)
    salon_lon = float(salon.longitude)
    distance_km   = haversine(salon_lat, salon_lon, user_lat, user_lon)
    delivery_cost = calc_delivery_cost(distance_km)

    address_str = (
        get_address_from_coords(user_lat, user_lon)
        or f"Геолокация ({user_lat:.5f}, {user_lon:.5f})"
    )

    await state.update_data(
        address=address_str,
        delivery_cost=delivery_cost,
        distance_km=distance_km,
        geo_lat=user_lat,
        geo_lon=user_lon
    )

    # --- чистим старые сообщения ----------------------------------------
    if geo_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, geo_msg_id)
        except Exception:
            pass

    if last_msg_id:
        try:
            # скрываем inline‑кнопку «Назад»
            await message.bot.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=last_msg_id,
                reply_markup=None
            )
        except Exception:
            pass

    # --- спрашиваем подтверждение адреса --------------------------------
    confirm_msg = await message.answer(
        f"Вы находитесь по адресу:\n<b>{address_str}</b>\nВсё верно?",
        reply_markup=confirm_address_kb(),
        parse_mode="HTML"
    )
    await state.update_data(confirm_addr_msg_id=confirm_msg.message_id)
    await state.set_state(OrderStates.confirming_address)

@order_router.message(OrderStates.entering_address, F.text == "⬅️ Назад")
async def back_to_delivery_msg(message: types.Message,
                               state: FSMContext,
                               session: AsyncSession):

    data = await state.get_data()
    geo_msg_id  = data.get("geo_msg_id")   # 📍‑сообщение
    last_msg_id = data.get("last_msg_id")  # «Отправьте геолокацию…»
    apt_msg_id  = data.get("apt_msg_id")   # ← добавили

    # удаляем ВСЕ временные сообщения
    for mid in (geo_msg_id, last_msg_id, apt_msg_id):
        if mid:
            try:
                await message.bot.delete_message(message.chat.id, mid)
            except Exception:
                pass

    # сбрасываем apt_msg_id, чтобы не «тащить» его дальше
    await state.update_data(apt_msg_id=None)

    # показываем выбор доставки заново
    user_salon_id = data.get("user_salon_id")
    summary  = await get_order_summary(session, user_salon_id, data) if user_salon_id else ""

    new_msg = await message.answer(
        summary + "\n\nВыберите способ доставки:",
        reply_markup=get_delivery_kb(),
        parse_mode="HTML"
    )
    await state.update_data(last_msg_id=new_msg.message_id)
    await state.set_state(OrderStates.choosing_delivery)

    # убираем Reply‑клавиатуру
    await message.answer("\u2063", reply_markup=ReplyKeyboardRemove())

# --- Получение ручного адреса пользователя ---
@order_router.message(OrderStates.entering_address, F.text)
async def receive_address_text(message: types.Message, state: FSMContext):
    address_str = message.text.strip()
    if not address_str:
        await message.answer("Пожалуйста, введите корректный адрес.")
        return

    await state.update_data(address=address_str)
    # Просим ввести номер квартиры/офиса
    await state.set_state(OrderStates.entering_apartment)
    await message.answer(
        "Пожалуйста, укажите номер квартиры (или подъезда, офиса):",
        reply_markup=ReplyKeyboardRemove()
    )


# --- Обработка подтверждения адреса ---
# ─────────────────────────────────────────────────────────────
# 1. Кнопка «✅ Да» → спрашиваем номер квартиры и сохраняем apt_msg_id
# ─────────────────────────────────────────────────────────────
@order_router.callback_query(OrderStates.confirming_address,
                             F.data == "address_ok")
async def address_ok(callback: CallbackQuery,
                     state: FSMContext,
                     session: AsyncSession):

    data = await state.get_data()
    last_msg_id = data.get("confirm_addr_msg_id")   # сообщение «Всё верно?»

    # удаляем его, чтобы не мешалось
    if last_msg_id:
        try:
            await callback.bot.delete_message(callback.message.chat.id, last_msg_id)
        except Exception:
            pass

    # спрашиваем номер квартиры
    ask_msg = await callback.message.answer(
        "Пожалуйста, укажите номер квартиры (или подъезда, офиса):",
        reply_markup=ReplyKeyboardRemove()
    )

    # сохраняем ID этого вопроса → потом удалим
    await state.update_data(apt_msg_id=ask_msg.message_id)
    await state.set_state(OrderStates.entering_apartment)
    await callback.answer()           # закрываем «часики» на кнопке


# ─────────────────────────────────────────────────────────────
# 2. Пользователь ответил → удаляем вопрос, добавляем квартиру
# ─────────────────────────────────────────────────────────────
# --- Получение номера квартиры / подъезда --------------------------------
@order_router.message(OrderStates.entering_apartment)
async def receive_apartment(message: types.Message, state: FSMContext):

    apartment = message.text.strip()

    data        = await state.get_data()
    full_addr   = data["address"]
    apt_msg_id  = data.get("apt_msg_id")        # ID вопроса «Укажите номер квартиры»

    # дописываем квартиру к адресу
    if apartment:
        full_addr += f", кв./офис {apartment}"
    await state.update_data(address=full_addr)

    # удаляем подсказку «Укажите номер квартиры»
    if apt_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, apt_msg_id)
        except Exception:
            pass

    # переходим к шагу ввода телефона
    await state.set_state(OrderStates.entering_phone)

    phone_msg = await message.answer(
        "Пожалуйста, введите ваш номер телефона или отправьте контакт кнопкой ниже 👇",
        reply_markup=phone_keyboard()
    )

    # сохраняем, чтобы «⬅️ Назад» знал откуда вернуться и что удалить
    await state.update_data(
        phone_back="apartment",            # вернёмся к этому шагу
        phone_msg_id=phone_msg.message_id  # чтобы потом удалить
    )


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

# ─── «⬅️ Назад» со стадии ввода телефона ──────────────────────────────
@order_router.message(OrderStates.entering_phone, F.text == BACK_PHONE_TXT)
async def phone_back(message: types.Message,
                     state: FSMContext,
                     session: AsyncSession):

    data          = await state.get_data()
    back_where    = data.get("phone_back")          # "apartment" | "delivery" | None
    last_msg_id   = data.get("last_msg_id")         # карточка заказа
    phone_msg_id  = data.get("phone_msg_id")        # «Введите номер…»

    # 1. Удаляем пузырёк «Введите номер…»
    if phone_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, phone_msg_id)
        except Exception:
            pass

    # 2. Удаляем сообщение пользователя «⬅️ Назад»
    try:
        await message.bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass

    # 3. Прячем клавиатуру (невидимый символ)
    await message.answer("\u2063", reply_markup=ReplyKeyboardRemove())

    # ============= ВОЗВРАТ К ШАГУ «КВАРТИРА» ============================
    if back_where == "apartment":
        # старую карточку заказа удаляем, если была
        if last_msg_id:
            try:
                await message.bot.delete_message(message.chat.id, last_msg_id)
            except Exception:
                pass

        await state.set_state(OrderStates.entering_apartment)
        await state.update_data(phone_back=None, phone_msg_id=None)
        await message.answer("Пожалуйста, укажите номер квартиры (или подъезда, офиса):")
        return

    # ============= ВОЗВРАТ К ВЫБОРУ ДОСТАВКИ ===========================
    # 4. Сносим карточку «Самовывоз/Курьер», если она была
    if last_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, last_msg_id)
        except Exception:
            pass

    # 5. Сбрасываем поля доставки — делаем summary «чистым»
    await state.update_data(
        delivery=None,
        address=None,
        delivery_cost=0,
        distance_km=None,
        phone_back=None,
        phone_msg_id=None
    )

    # 6. Формируем новую карточку без выбранной доставки
    data = await state.get_data()
    user_salon_id = data.get("user_salon_id")
    summary = await get_order_summary(session, user_salon_id, data) if user_salon_id else ""

    new_msg = await message.answer(
        summary + "\n\nВыберите способ доставки:",
        reply_markup=get_delivery_kb(),
        parse_mode="HTML"
    )

    # 7. Запоминаем ID новой карточки и переходим к выбору доставки
    await state.update_data(last_msg_id=new_msg.message_id)
    await state.set_state(OrderStates.choosing_delivery)




# --- Ввод телефона: и контакт, и текст ---
@order_router.message(OrderStates.entering_phone)
async def enter_phone(message: types.Message, state: FSMContext, session: AsyncSession):
    # --- определяем phone ---
    phone = message.contact.phone_number if (message.contact and message.contact.phone_number) \
            else message.text.strip()

    data        = await state.get_data()
    last_msg_id = data.get("last_msg_id")
    await state.update_data(phone=phone)
    await state.set_state(OrderStates.confirming_order)

    user_salon_id = data.get("user_salon_id")

    # удаляем предыдущий итог, если был
    if last_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, last_msg_id)
        except Exception:
            pass

    # ❶ сначала «спасибо» + убираем Reply‑клавиатуру
    await message.answer(
        "Спасибо, номер получен!",
        reply_markup=ReplyKeyboardRemove()
    )

    # ❷ потом формируем обзор заказа + inline‑кнопки
    summary = await get_order_summary(session, user_salon_id, {**data, "phone": phone}) if user_salon_id else ""

    msg = await message.answer(
        summary + "\n\nПроверьте все данные и подтвердите заказ!",
        reply_markup=get_confirm_kb(),
        parse_mode="HTML"
    )
    await state.update_data(last_msg_id=msg.message_id)


@order_router.callback_query(OrderStates.confirming_order, F.data == "confirm_order")
async def confirm_order(callback: CallbackQuery,
                        state: FSMContext,
                        session: AsyncSession):

    # 1. Получаем все данные
    data = await state.get_data()
    user_salon_id = data.get("user_salon_id")

    # 2. Получаем корзину пользователя
    cart_items = await orm_get_user_carts(session, user_salon_id) if user_salon_id else []

    # 3. Если корзина не пуста и есть salon — оформляем заказ
    if user_salon_id and cart_items:
        order = await orm_create_order(
            session,
            user_salon_id=user_salon_id,
            address=data.get("address"),
            phone=data.get("phone"),
            payment_method=data.get("payment_method"),
            cart_items=cart_items,
        )
        # 4. Уведомляем салон ДО очистки FSM и корзины!
        await notify_salon_about_order(callback, state, session, user_salon_id)
        # 5. Очищаем корзину
        await orm_clear_cart(session, user_salon_id)
        # 6. Убираем inline-кнопки
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        # 7. Благодарим клиента
        await callback.message.answer("Спасибо! Ваш заказ принят 👍")
        await state.clear()
    else:
        await callback.message.answer("Ваша корзина пуста или не выбран салон. Заказ не оформлен.")
        await state.clear()

    await callback.answer()




@order_router.callback_query(F.data == "back_to_cart")
async def back_to_cart(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await state.clear()                     # ① очистили сразу

    user_id = callback.from_user.id
    user_salons = await orm_get_user_salons(session, user_id)
    if len(user_salons) != 1:
        await callback.message.answer("Не удалось определить салон. Пожалуйста, выберите салон.")
        await callback.answer()
        return

    user_salon_id = user_salons[0].id
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
        parse_mode="HTML"
    )



def get_map_link(lat, lon):
    return f"https://maps.google.com/?q={lat},{lon}"


# --- Доставка: Самовывоз ---
@order_router.callback_query(OrderStates.choosing_delivery, F.data == "delivery_pickup")
async def choose_delivery_pickup(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    last_msg_id = data["last_msg_id"]

    user_salon_id = data.get("user_salon_id")
    user = await session.get(UserSalon, user_salon_id) if user_salon_id else await orm_get_user(session, callback.from_user.id)
    if user and not user_salon_id:
        user_salon_id = user.id
        await state.update_data(user_salon_id=user_salon_id)
    salon = await orm_get_salon_by_id(session, user.salon_id) if user else None

    # --- Генерируем ссылку на карту, если есть координаты ---
    if salon.latitude and salon.longitude:
        address = f'<a href="https://maps.google.com/?q={salon.latitude},{salon.longitude}">Открыть на карте</a>'
    else:
        address = "Адрес салона не указан"

    await state.update_data(
        delivery="delivery_pickup",
        delivery_cost=0,
        address=address,
        distance_km=None
    )

    summary = await get_order_summary(session, user_salon_id, {
        **data,
        "delivery": "delivery_pickup",
        "delivery_cost": 0,
        "address": address,
        "distance_km": None
    }) if user_salon_id else ""

    # Показываем только сумму заказа, без кнопок подтверждения!
    try:
        await callback.bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=last_msg_id,
            text=summary,
            reply_markup=None,
            parse_mode="HTML",
            disable_web_page_preview=True   # не обязательно, но чтобы не было лишней "карточки" в сообщении
        )
    except Exception:
        await callback.message.answer(
            summary,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    # Сразу просим номер телефона!
    await state.set_state(OrderStates.entering_phone)

    phone_msg = await callback.message.answer(
        "Пожалуйста, введите ваш номер телефона или отправьте контакт кнопкой ниже 👇",
        reply_markup=phone_keyboard()
    )

    # ⬇️ одним вызовом кладём оба поля
    await state.update_data(
        phone_back="delivery",  # ← куда возвращаться при «Назад»
        phone_msg_id=phone_msg.message_id
    )

# --- «Назад» с экрана подтверждения (возврат к вводу телефона) ---
@order_router.callback_query(OrderStates.confirming_order, F.data == "back_to_phone")
async def back_to_phone(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_msg_id = data.get("last_msg_id")

    # Удаляем сообщение с итогом заказа, чтобы не плодить дубликаты
    if last_msg_id:
        try:
            await callback.bot.delete_message(
                chat_id=callback.message.chat.id,
                message_id=last_msg_id
            )
        except Exception:
            pass

    # Возвращаемся к стадии ввода телефона
    await state.set_state(OrderStates.entering_phone)
    await callback.message.answer(
        "Пожалуйста, введите ваш номер телефона или отправьте контакт кнопкой ниже 👇",
        reply_markup=phone_keyboard()
    )

    # Закрываем «часики» на кнопке
    await callback.answer()



