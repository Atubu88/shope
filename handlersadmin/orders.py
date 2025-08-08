from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from database.orm_query import orm_get_orders, orm_get_order, orm_update_order_status
from utils.currency import get_currency_symbol
from utils.timezone import to_timezone

orders_router = Router()

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
        buttons.append([
            InlineKeyboardButton(
                text=f"#{o.id} • {time} • {o.status} • {int(o.total)}{currency}",
                callback_data=f"order_{o.id}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="admin_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)



@orders_router.callback_query(F.data == "admin_orders")
async def show_orders(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    message_id = data.get("main_message_id") or callback.message.message_id
    salon_id = data.get("salon_id")
    await state.clear()
    await state.update_data(main_message_id=message_id, salon_id=salon_id)

    orders = await orm_get_orders(session, salon_id)
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=message_id,
        text="Список заказов:",
        reply_markup=orders_kb(orders),
    )
    await callback.answer()


def order_detail_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_orders")],
        ]
    )


@orders_router.callback_query(F.data.startswith("order_"))
async def show_order_detail(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    order_id = int(callback.data.split("_")[-1])
    order = await orm_get_order(session, order_id)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    # ... формирование текста заказа ...
    # пример:
    salon_obj = getattr(order.user_salon, "salon", None)
    currency_code = getattr(salon_obj, "currency", "RUB")
    local_dt = to_timezone(order.created, getattr(salon_obj, "timezone", None))
    text = (
        f"Заказ #{order.id}\n"
        f"{local_dt:%d.%m %H:%M}\n"
        f"{getattr(order.user_salon, 'first_name', '')} / {order.phone or '-'}\n"
        f"🍕 {order.items[0].product.name} × {order.items[0].quantity}\n"
        f"{order.address or ''}\n"
        f"Статус: {order.status}\n"
        f"Итого: {order.total:.0f}{get_currency_symbol(currency_code)}"
    )

    message_id = (await state.get_data()).get("main_message_id") or callback.message.message_id
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=message_id,
        text=text,
        reply_markup=order_action_kb(order.id, order.status),
        parse_mode="HTML",
    )
    await callback.answer()


@orders_router.callback_query(F.data.regexp(r"^(accept|done|cancel)_(\d+)$"))
async def change_order_status(callback: CallbackQuery, session: AsyncSession, state):
    action, order_id = callback.data.split("_")
    order_id = int(order_id)

    # Статусы для каждой кнопки
    status_map = {
        "accept": "IN_PROGRESS",
        "done": "DONE",
        "cancel": "CANCELLED",
    }
    new_status = status_map.get(action)
    if not new_status:
        await callback.answer("Неизвестное действие", show_alert=True)
        return

    # Получаем salon_id из состояния или иным способом
    data = await state.get_data()
    salon_id = data.get("salon_id")

    await orm_update_order_status(session, order_id, salon_id, new_status)
    await show_order_detail(callback, state, session)
    await callback.answer("Статус обновлён!")
