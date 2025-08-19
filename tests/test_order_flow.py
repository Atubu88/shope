import sys
from types import SimpleNamespace
from pathlib import Path
import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from handlers.order_processing import (
    start_order,
    choose_delivery_courier,
    receive_location,
    confirm_address_kb,
    enter_phone,
    confirm_order,
    OrderStates,
)
import handlers.order_processing as order_module


class FSM:
    def __init__(self):
        self.data = {}
        self.state = None

    async def set_state(self, state):
        self.state = state

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def get_data(self):
        return self.data

    async def clear(self):
        self.data = {}
        self.state = None


class Session:
    def __init__(self):
        self.order_params = None

    async def get(self, model, obj_id):
        return SimpleNamespace(salon_id=1)


class Bot:
    def __init__(self):
        self.sent_messages = []
        self.edited = []
        self.deleted = []

    async def edit_message_text(self, chat_id, message_id, text, reply_markup=None):
        self.edited.append((chat_id, message_id, text))

    async def delete_message(self, chat_id, message_id):
        self.deleted.append((chat_id, message_id))

    async def edit_message_reply_markup(self, chat_id, message_id, reply_markup=None):
        pass


class Msg:
    _next_id = 1

    def __init__(self, bot, text="", user_id=1, location=None, contact=None):
        self.bot = bot
        self.text = text
        self.from_user = SimpleNamespace(id=user_id)
        self.chat = SimpleNamespace(id=user_id)
        self.location = location
        self.contact = contact
        self.message_id = Msg._next_id
        Msg._next_id += 1
        self.answers = []
        self.reply_markup = None

    async def answer(self, text, reply_markup=None, parse_mode=None):
        msg = Msg(self.bot, text=text, user_id=self.from_user.id)
        self.bot.sent_messages.append(msg)
        self.answers.append((text, reply_markup))
        return msg

    async def delete(self):
        pass

    async def edit_reply_markup(self, reply_markup=None):
        self.reply_markup = reply_markup


class Cb:
    def __init__(self, data, message, user_id=1):
        self.data = data
        self.message = message
        self.from_user = SimpleNamespace(id=user_id)
        self.bot = message.bot
        self._answered = []

    async def answer(self, text=None, show_alert=False):
        self._answered.append((text, show_alert))


@pytest.mark.asyncio
async def test_full_order_flow(monkeypatch):
    async def fake_orm_get_user(session, user_id):
        return SimpleNamespace(id=1, salon_id=1)

    async def fake_get_order_summary(session, user_salon_id, data):
        return "Summary"

    async def fake_orm_get_salon_by_id(session, salon_id):
        return SimpleNamespace(id=1, latitude=1.0, longitude=1.0, free_plan=False)

    async def fake_orm_get_user_carts(session, user_salon_id):
        return [SimpleNamespace(id=1)]

    async def fake_notify(callback, state, session, user_salon_id):
        session.notified = True

    async def fake_orm_clear_cart(session, user_salon_id):
        session.cleared = True

    async def fake_orm_create_order(session, user_salon_id, address, phone, payment_method, cart_items):
        session.order_params = {
            "user_salon_id": user_salon_id,
            "address": address,
            "phone": phone,
            "payment_method": payment_method,
            "cart_items": cart_items,
        }
        return SimpleNamespace(id=1)

    def fake_haversine(*args, **kwargs):
        return 1.0

    def fake_calc_delivery_cost(*args, **kwargs):
        return 100

    def fake_get_address_from_coords(lat, lon):
        return "Address"

    monkeypatch.setattr(order_module, "orm_get_user", fake_orm_get_user)
    monkeypatch.setattr(order_module, "get_order_summary", fake_get_order_summary)
    monkeypatch.setattr(order_module, "orm_get_salon_by_id", fake_orm_get_salon_by_id)
    monkeypatch.setattr(order_module, "orm_get_user_carts", fake_orm_get_user_carts)
    monkeypatch.setattr(order_module, "notify_salon_about_order", fake_notify)
    monkeypatch.setattr(order_module, "orm_clear_cart", fake_orm_clear_cart)
    monkeypatch.setattr(order_module, "orm_create_order", fake_orm_create_order)
    monkeypatch.setattr(order_module, "haversine", fake_haversine)
    monkeypatch.setattr(order_module, "calc_delivery_cost", fake_calc_delivery_cost)
    monkeypatch.setattr(order_module, "get_address_from_coords", fake_get_address_from_coords)
    monkeypatch.setattr(order_module, "_", lambda s: s)

    state = FSM()
    session = Session()
    bot = Bot()

    start_msg = Msg(bot)
    start_cb = Cb("start_order", start_msg)
    await start_order(start_cb, state, session)

    delivery_msg = bot.sent_messages[0]
    delivery_cb = Cb("delivery_courier", delivery_msg)
    await choose_delivery_courier(delivery_cb, state, session)

    loc_msg = Msg(bot, location=SimpleNamespace(latitude=1.0, longitude=2.0))
    await receive_location(loc_msg, state, session)

    kb = confirm_address_kb()
    assert kb.inline_keyboard[0][0].callback_data == "address_ok"

    await state.set_state(OrderStates.entering_phone)

    phone_msg = Msg(bot, text="+12345")
    await enter_phone(phone_msg, state, session)

    summary_msg = bot.sent_messages[-1]
    confirm_cb = Cb("confirm_order", summary_msg)
    await confirm_order(confirm_cb, state, session)

    assert summary_msg.answers[-1][0] == "Спасибо! Ваш заказ принят 👍"
    assert session.order_params["address"] == "Address"
    assert session.order_params["phone"] == "+12345"