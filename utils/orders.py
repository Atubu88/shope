from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query import orm_get_user_carts, orm_get_salon_by_id
from utils.currency import get_currency_symbol


async def get_order_summary(
    session: AsyncSession,
    user_id: int,
    salon_id: int,
    state_data: dict,
    for_group: bool = False
) -> str:
    cart_items = await orm_get_user_carts(session, user_id, salon_id)
    salon = await orm_get_salon_by_id(session, salon_id)
    currency = get_currency_symbol(salon.currency) if salon else "RUB"

    lines = []
    total = 0
    for item in cart_items:
        item_cost = item.product.price * item.quantity
        total += item_cost
        lines.append(
            f"- 🛒 {item.product.name} — {item.quantity} x {item.product.price:.0f}{currency} = {item_cost:.0f}{currency}"
        )

    delivery_cost = int(state_data.get("delivery_cost") or 0)
    delivery_type = state_data.get("delivery")

    if delivery_type == "delivery_courier":
        delivery_text = f"🚗 Курьер (+{delivery_cost}{currency})"
    elif delivery_type == "delivery_pickup":
        delivery_text = f"🏃 Самовывоз (0{currency})"
    else:
        delivery_text = "❓ Не выбран"

    total_with_delivery = total + delivery_cost

    text = "🆕 <b>Новый заказ!</b>\n\n"
    text += "🛍 <b>Состав:</b>\n" + "\n".join(lines)
    text += f"\n\n🚚 <b>Доставка:</b> {delivery_text}"

    # Для группы — адрес только если курьер
    # Для клиента — адрес всегда если есть
    show_address = (
        (for_group and delivery_type == "delivery_courier")
        or
        (not for_group and state_data.get("address"))
    )
    if show_address and state_data.get("address"):
        text += f"\n📍 <b>Адрес:</b> {state_data['address']}"

    if state_data.get("distance_km") is not None and delivery_type == "delivery_courier":
        text += f"\n📏 <b>Расстояние:</b> {state_data['distance_km']:.2f} км"

    # Телефон только для клиента
    if not for_group and state_data.get("phone"):
        text += f"\n☎️ <b>Телефон:</b> {state_data['phone']}"

    text += f"\n\n💰 <b>Итого:</b> {total_with_delivery:.2f}{currency}"

    return text
