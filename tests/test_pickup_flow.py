"""Тесты сценария самовывоза."""

from datetime import datetime
from types import SimpleNamespace

import pytest

from handlers.order import OrderStates, choose_delivery_pickup, set_pickup_time


class FSM:
    def __init__(self) -> None:
        self.data: dict = {}
        self.state = None

    async def set_state(self, state) -> None:
        self.state = state

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def get_data(self) -> dict:
        return self.data

    async def clear(self) -> None:
        self.data = {}
        self.state = None


class Session:
    def __init__(self) -> None:
        self.order_params = None

    async def get(self, model, obj_id):
        return SimpleNamespace(id=obj_id, salon_id=1)


class Bot:
    def __init__(self) -> None:
        self.edited: list = []
        self.sent_messages: list = []

    async def edit_message_text(self, chat_id, message_id, text, reply_markup=None, parse_mode=None, disable_web_page_preview=None):
        self.edited.append(
            SimpleNamespace(chat_id=chat_id, message_id=message_id, text=text, reply_markup=reply_markup)
        )


class Msg:
    _next_id = 1

    def __init__(self, bot, text="", user_id=1):
        self.bot = bot
        self.text = text
        self.from_user = SimpleNamespace(id=user_id, full_name="User")
        self.chat = SimpleNamespace(id=user_id)
        self.message_id = Msg._next_id
        Msg._next_id += 1
        self.answers = []

    async def answer(self, text, reply_markup=None, parse_mode=None, disable_web_page_preview=None):
        msg = Msg(self.bot, text=text, user_id=self.chat.id)
        self.bot.sent_messages.append(msg)
        self.answers.append(SimpleNamespace(text=text, reply_markup=reply_markup))
        return msg


class Cb:
    def __init__(self, data, message, user_id=1):
        self.data = data
        self.message = message
        self.from_user = SimpleNamespace(id=user_id, full_name="User")
        self.bot = message.bot
        self._answered = []

    async def answer(self, text=None, show_alert=False):
        self._answered.append((text, show_alert))


@pytest.mark.asyncio
async def test_pickup_time_flow(monkeypatch):
    async def fake_orm_get_user(session, user_id):
        return SimpleNamespace(id=1, salon_id=1)

    class FakeSalonRepository:
        def __init__(self, session):
            self.session = session

        async def get_by_id(self, salon_id):
            return SimpleNamespace(id=salon_id, latitude=1.0, longitude=1.0, timezone="UTC")

    async def fake_get_order_summary(session, user_salon_id, data):
        return "Summary"

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2024, 1, 1, 10, 0, tzinfo=tz)

    monkeypatch.setattr("handlers.order.pickup_flow.orm_get_user", fake_orm_get_user)
    monkeypatch.setattr("handlers.order.pickup_flow.SalonRepository", FakeSalonRepository)
    monkeypatch.setattr("handlers.order.pickup_flow.get_order_summary", fake_get_order_summary)
    monkeypatch.setattr("handlers.order.pickup_flow._", lambda s: s)
    monkeypatch.setattr("handlers.order.pickup_flow.datetime", FixedDatetime)

    state = FSM()
    session = Session()
    bot = Bot()

    start_msg = Msg(bot)
    start_cb = Cb("delivery_pickup", start_msg)
    await state.update_data(last_msg_id=start_msg.message_id, user_salon_id=1)

    await choose_delivery_pickup(start_cb, state, session)

    assert state.state == OrderStates.choosing_pickup_time
    assert bot.edited[0].reply_markup is not None

    pickup_cb = Cb("pickup_time:20", start_msg)
    await set_pickup_time(pickup_cb, state, session)

    assert state.data["pickup_time"] == "10:20"
    assert state.state == OrderStates.entering_phone
    assert start_msg.answers[-1].text.startswith("Пожалуйста, введите ваш номер телефона")
