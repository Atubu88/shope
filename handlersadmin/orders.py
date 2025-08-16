from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from database.orm_query import orm_get_orders, orm_get_order, orm_update_order_status, orm_get_user_salons
from utils.currency import get_currency_symbol
from utils.timezone import to_timezone
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from filters.chat_types import ChatTypeFilter, IsAdmin

orders_router = Router()
orders_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())
orders_router.callback_query.filter(IsAdmin())

CUSTOMER_STATUS_MSGS = {
    "IN_PROGRESS": "Ваш заказ #{} принят и готовится. 🧑‍🍳",
    "DONE": "Ваш заказ #{} выполнен. Приятного аппетита! 😋",
    "CANCELLED": "Ваш заказ #{} отменён. Если это ошибка — напишите нам, поможем! ",
}

def build_customer_message(order, new_status: str) -> str:
    # Заголовок по новому статусу
    header = CUSTOMER_STATUS_MSGS.get(new_status, "Статус заказа #{} обновлён.").format(order.id)

    # Время и сумма
    salon_obj = getattr(order.user_salon, "salon", None)
    currency_code = getattr(salon_obj, "currency", "RUB")
    local_dt = to_timezone(order.created, getattr(salon_obj, "timezone", None))
    total_text = f"{order.total:.0f}{get_currency_symbol(currency_code)}"

    # Все позиции заказа
    items = getattr(order, "items", []) or []
    lines = []
    for it in items:
        product = getattr(it, "product", None)
        name = getattr(product, "name", f"Товар #{getattr(it, 'product_id', '?')}")
        qty = getattr(it, "quantity", 1)
        lines.append(f"🍕 {name} × {qty}")

    items_block = ("\n" + "\n".join(lines)) if lines else ""

    # Итоговый текст
    details = (
        f"\n\n⏰ {local_dt:%d.%m %H:%M}"
        f"\n🧾 Сумма: {total_text}"
        f"{items_block}"
    )
    return header + details


async def notify_customer_status_change(bot, order, new_status: str):
    chat_id = getattr(getattr(order.user_salon, "user", None), "user_id", None)
    if not chat_id:
        return

    text = build_customer_message(order, new_status)

    try:
        # просто сообщение, без inline-кнопок
        await bot.send_message(chat_id=chat_id, text=text)
    except TelegramForbiddenError:
        # пользователь заблокировал бота
        pass
    except TelegramBadRequest:
        # например, неверный chat_id и т.п.
        pass


# Русские названия статусов
STATUS_LABELS_RU = {
    "NEW": "Новый",
    "IN_PROGRESS": "В работе",
    "DONE": "Завершён",
    "CANCELLED": "Отменён",
}

def order_action_kb(order_id: int, status: str) -> InlineKeyboardMarkup:
    buttons: list[InlineKeyboardButton] = []

    if status == "NEW":
        buttons.append(
            InlineKeyboardButton(
                text="✅ Принять",
                callback_data=f"accept_{order_id}"
            )
        )

    if status == "IN_PROGRESS":
        buttons.append(
            InlineKeyboardButton(
                text="🏁 Выполнено",
                callback_data=f"done_{order_id}"
            )
        )

    if status in ("NEW", "IN_PROGRESS"):
        buttons.append(
            InlineKeyboardButton(
                text="❌ Отменить",
                callback_data=f"cancel_{order_id}"
            )
        )

    # «Назад»
    buttons.append(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_orders")
    )

    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def orders_kb(orders):
    buttons = []
    for o in orders:
        salon_rel = getattr(o, "user_salon", None)
        salon_obj = getattr(salon_rel, "salon", None)
        local_dt = to_timezone(o.created, getattr(salon_obj, "timezone", None))
        time = local_dt.strftime("%H:%M")
        currency_code = getattr(salon_obj, "currency", "RUB")
        currency = get_currency_symbol(currency_code)
        status_ru = STATUS_LABELS_RU.get(o.status, o.status)
        buttons.append([
            InlineKeyboardButton(
                text=f"#{o.id} • {time} • {status_ru} • {int(o.total)}{currency}",
                callback_data=f"order_{o.id}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="admin_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _show_orders(bot, chat_id: int, message_id: int, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    salon_id = data.get("salon_id")
    if salon_id is None:
        await bot.send_message(chat_id, "Салон не определён")
        return

    await state.clear()
    await state.update_data(main_message_id=message_id, salon_id=salon_id)

    orders = await orm_get_orders(session, salon_id)
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="Список заказов:",
            reply_markup=orders_kb(orders),
        )
    except TelegramBadRequest:
        msg = await bot.send_message(
            chat_id=chat_id,
            text="Список заказов:",
            reply_markup=orders_kb(orders),
        )
        await state.update_data(main_message_id=msg.message_id, salon_id=salon_id)


@orders_router.callback_query(F.data == "admin_orders")
async def show_orders(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    message_id = data.get("main_message_id") or callback.message.message_id
    await _show_orders(callback.bot, callback.message.chat.id, message_id, state, session)
    await callback.answer()


@orders_router.message(Command("orders"))
async def orders_cmd(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    salon_id = data.get("salon_id")

    if salon_id is None:
        # пробуем найти первый салон пользователя
        user_salons = await orm_get_user_salons(session, message.from_user.id)
        if not user_salons:
            await message.answer("У вас нет доступных салонов.")
            return
        salon_id = user_salons[0].salon_id
        await state.update_data(salon_id=salon_id)

    # показываем заказы
    message_id = data.get("main_message_id") or message.message_id
    await _show_orders(message.bot, message.chat.id, message_id, state, session)



def order_detail_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_orders")],
        ]
    )


@orders_router.callback_query(F.data.regexp(r"^order_(\d+)$"))
async def show_order_detail(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
):
    # 1) извлекаем id заказа и salon_id из состояния
    order_id = int(callback.data.split("_")[-1])
    data = await state.get_data()
    salon_id = data.get("salon_id")
    if salon_id is None:
        return await callback.answer("Салон не определён", show_alert=True)

    # 2) берём заказ строго в рамках салона
    order = await orm_get_order(session, order_id, salon_id)
    if not order:
        return await callback.answer("Заказ не найден", show_alert=True)

    # 3) вычисляем служебные поля
    salon_obj = getattr(order.user_salon, "salon", None)
    currency_code = getattr(salon_obj, "currency", "RUB")
    local_dt = to_timezone(order.created, getattr(salon_obj, "timezone", None))
    status_label = STATUS_LABELS_RU.get(order.status, order.status)

    # 4) собираем блок со всеми позициями заказа
    items = getattr(order, "items", []) or []
    lines = []
    for it in items:
        product = getattr(it, "product", None)
        name = getattr(product, "name", f"Товар #{getattr(it, 'product_id', '?')}")
        qty = getattr(it, "quantity", 1)

        # цена позиции: сначала из item (если хранится снапшот), иначе из продукта
        price = getattr(it, "price", None)
        if price is None and product is not None:
            price = getattr(product, "price", None)

        if price is not None:
            try:
                line_total = float(price) * float(qty)
                lines.append(f"• {name} × {qty} = {line_total:.0f}{get_currency_symbol(currency_code)}")
            except Exception:
                lines.append(f"• {name} × {qty}")
        else:
            lines.append(f"• {name} × {qty}")

    items_block = ("\n".join(lines) + "\n") if lines else ""

    # 5) формируем текст
    customer_name = getattr(order.user_salon, "first_name", "") or ""
    phone = order.phone or "-"
    address = (order.address or "").strip()

    address_line = f"{address}\n" if address else ""

    text = (
        f"Заказ #{order.id}\n"
        f"{local_dt:%d.%m %H:%M}\n"
        f"{customer_name} / {phone}\n"
        f"{items_block}"
        f"{address_line}"
        f"Статус: {status_label}\n"
        f"Итого: {order.total:.0f}{get_currency_symbol(currency_code)}"
    )

    # 6) редактируем «главное» админское сообщение
    message_id = data.get("main_message_id") or callback.message.message_id
    try:
        await callback.bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=message_id,
            text=text,
            reply_markup=order_action_kb(order.id, order.status),
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer("Без изменений")
        else:
            raise

    await callback.answer()


@orders_router.callback_query(F.data.regexp(r"^(accept|done|cancel)_(\d+)$"))
async def change_order_status(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    action, order_id_str = callback.data.split("_", 1)
    order_id = int(order_id_str)

    status_map = {
        "accept": "IN_PROGRESS",
        "done": "DONE",
        "cancel": "CANCELLED",
    }
    new_status = status_map.get(action)
    if not new_status:
        return await callback.answer("Неизвестное действие", show_alert=True)

    data = await state.get_data()
    salon_id = data.get("salon_id")
    if salon_id is None:
        return await callback.answer("Салон не определён", show_alert=True)

    # 1) Обновляем статус строго в рамках салона
    await orm_update_order_status(session, order_id, salon_id, new_status)

    # 2) Берём обновлённый заказ уже с фильтром по салону
    order = await orm_get_order(session, order_id, salon_id)
    if not order:
        return await callback.answer("Заказ не найден", show_alert=True)

    # 3) Готовим текст (безопасно к пустым позициям)
    salon_obj = getattr(order.user_salon, "salon", None)
    currency_code = getattr(salon_obj, "currency", "RUB")
    local_dt = to_timezone(order.created, getattr(salon_obj, "timezone", None))
    status_ru = STATUS_LABELS_RU.get(order.status, order.status)

    first_item = order.items[0] if getattr(order, "items", None) else None
    item_line = (
        f"🍕 {first_item.product.name} × {first_item.quantity}\n" if first_item else ""
    )

    text = (
        f"Заказ #{order.id}\n"
        f"{local_dt:%d.%m %H:%M}\n"
        f"{getattr(order.user_salon, 'first_name', '')} / {order.phone or '-'}\n"
        f"{item_line}"
        f"{order.address or ''}\n"
        f"Статус: {status_ru}\n"
        f"Итого: {order.total:.0f}{get_currency_symbol(currency_code)}"
    )

    # 4) Переотрисовываем главное админское сообщение
    message_id = data.get("main_message_id") or callback.message.message_id
    try:
        await callback.bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=message_id,
            text=text,
            reply_markup=order_action_kb(order.id, order.status),
            parse_mode="HTML",
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise

    # 5) Уведомляем клиента о смене статуса
    await notify_customer_status_change(callback.bot, order, new_status)

    await callback.answer(f"Статус изменён на: {status_ru}")