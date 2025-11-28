"""Определения состояний FSM для оформления заказа."""

from aiogram.fsm.state import State, StatesGroup


class OrderStates(StatesGroup):
    """Список состояний цепочки оформления заказа."""

    choosing_delivery = State()
    entering_address = State()
    confirming_address = State()
    entering_apartment = State()
    entering_phone = State()
    confirming_order = State()
