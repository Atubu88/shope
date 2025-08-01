from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from database.orm_query import orm_get_orders, orm_get_order
from utils.currency import get_currency_symbol

orders_router = Router()


def orders_kb(orders):
    buttons = []
    for o in orders:
        time = o.created.strftime("%H:%M")
        buttons.append([
            InlineKeyboardButton(
                text=f"#{o.id} • {time} • {o.status} • {int(o.total)} ₽",
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

    lines = [f"{item.product.name} × {item.quantity}" for item in order.items]
    items = ", ".join(lines)
    currency = get_currency_symbol(order.salon.currency)
    text = (
        f"Заказ \N{NUMBER SIGN}{order.id}\n"
        f"{order.created:%d.%m %H:%M}\n"
        f"{order.user.first_name or ''} / {order.phone or '-'}\n"
        f"{items}\n"
        f"{order.address or ''}\n"
        f"Статус: {order.status}\n"
        f"Итого: {order.total:.0f}{currency}"
    )
    data = await state.get_data()
    message_id = data.get("main_message_id") or callback.message.message_id
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=message_id,
        text=text,
        reply_markup=order_detail_kb(order_id),
        parse_mode="HTML",
    )
    await callback.answer()
