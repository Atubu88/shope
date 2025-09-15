from types import SimpleNamespace
import sys
from pathlib import Path
import asyncio
import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from handlers.invite_creation import (
    InviteFilter,
    get_currency_kb,
    get_tz_fixed_kb,
    contact_keyboard,
    TIMEZONES,
    start_via_invite,
    invite_set_language,
    salon_name,
    salon_slug,
    salon_currency,
    tz_pick,
    salon_phone,
    AddSalon,
)

import handlers.invite_creation as invite_module


def test_invite_filter_accepts_valid_payload():
    flt = InviteFilter()
    message = SimpleNamespace(text="/start invite_abc")
    assert asyncio.run(flt(message))


def test_invite_filter_rejects_invalid_payload():
    flt = InviteFilter()
    message = SimpleNamespace(text="/start something")
    assert not asyncio.run(flt(message))
    message_no_payload = SimpleNamespace(text="/start")
    assert not asyncio.run(flt(message_no_payload))


def test_currency_keyboard_layout():
    kb = get_currency_kb()
    assert len(kb.inline_keyboard) == 3
    assert all(len(row) == 3 for row in kb.inline_keyboard)
    assert kb.inline_keyboard[0][0].callback_data == "currency_RUB"


def test_timezone_keyboard_contains_all_timezones():
    kb = get_tz_fixed_kb()
    assert len(kb.inline_keyboard) == len(TIMEZONES)
    for row, (tz, label) in zip(kb.inline_keyboard, TIMEZONES):
        button = row[0]
        assert button.callback_data == f"tz_pick:{tz}"
        assert button.text == label


def test_contact_keyboard_requests_contact():
    kb = contact_keyboard()
    assert len(kb.keyboard) == 1
    button = kb.keyboard[0][0]
    assert button.request_contact is True


@pytest.mark.asyncio
async def test_full_invite_creation_flow(monkeypatch):
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
            self.users = {}

        async def get(self, model, user_id):
            return self.users.get(user_id)

        def add(self, obj):
            self.users[getattr(obj, "user_id", 0)] = obj

        async def commit(self):
            pass

    class I18nStub:
        def __init__(self):
            self.locale = None
            self.ctx_locale = SimpleNamespace(set=lambda lang: setattr(self, "locale", lang))

    class Bot:
        async def get_me(self):
            return SimpleNamespace(username="bot")

    class Msg:
        def __init__(self, text="", user_id=1, contact=None):
            self.text = text
            self.contact = contact
            self.from_user = SimpleNamespace(id=user_id)
            self.bot = Bot()
            self.answers = []
            self.edits = []
            self.photos = []

        async def answer(self, text, reply_markup=None):
            self.answers.append((text, reply_markup))

        async def answer_photo(self, photo, caption, reply_markup=None):
            self.photos.append((caption, reply_markup))

        async def edit_text(self, text, reply_markup=None):
            self.edits.append((text, reply_markup))

        async def delete(self):
            pass

    class Cb:
        def __init__(self, data, message, user_id=1):
            self.data = data
            self.message = message
            self.from_user = SimpleNamespace(id=user_id)
            self.answered = []

        async def answer(self, text=None, show_alert=False):
            self.answered.append((text, show_alert))

    async def fake_generate_unique_slug(session, source):
        return "slug1"

    class FakeSalonRepository:
        def __init__(self, session):
            self.session = session

        async def create_salon(self, name, slug, currency, timezone_name):
            self.session.created = SimpleNamespace(
                id=1, name=name, slug=slug, timezone=timezone_name
            )
            return self.session.created

    async def fake_init_default_salon_content(session, salon_id):
        session.init_called = salon_id

    async def fake_orm_add_user(session, **kwargs):
        session.added_user = kwargs

    def fake_make(link):
        class Img:
            def save(self, buf, format):
                buf.write(b"img")

        return Img()

    monkeypatch.setattr(invite_module, "generate_unique_slug", fake_generate_unique_slug)
    monkeypatch.setattr(invite_module, "SalonRepository", FakeSalonRepository)
    monkeypatch.setattr(invite_module, "init_default_salon_content", fake_init_default_salon_content)
    monkeypatch.setattr(invite_module, "orm_add_user", fake_orm_add_user)
    monkeypatch.setattr(invite_module, "qrcode", SimpleNamespace(make=fake_make))
    monkeypatch.setattr(invite_module, "_", lambda s: s)

    state = FSM()
    session = Session()
    i18n = I18nStub()

    start_msg = Msg("/start invite_code", user_id=1)
    await start_via_invite(start_msg, state, session, i18n)
    assert state.state == AddSalon.language

    lang_cb = Cb("setlang_ru", Msg(), user_id=1)
    await invite_set_language(lang_cb, state, session, i18n)
    assert state.state == AddSalon.name
    assert session.users[1].language == "ru"

    name_msg = Msg("Test", user_id=1)
    await salon_name(name_msg, state)
    assert state.state == AddSalon.slug

    slug_msg = Msg("-", user_id=1)
    await salon_slug(slug_msg, state, session)
    assert state.state == AddSalon.currency
    assert state.data["slug"] == "slug1"

    curr_cb = Cb("currency_USD", Msg(), user_id=1)
    await salon_currency(curr_cb, state)
    assert state.state == AddSalon.timezone

    tz_cb = Cb("tz_pick:Europe/Moscow", Msg(), user_id=1)
    await tz_pick(tz_cb, state)
    assert state.state == AddSalon.phone

    contact = SimpleNamespace(phone_number="+1", first_name="A", last_name="B")
    contact_msg = Msg("", user_id=1, contact=contact)
    await salon_phone(contact_msg, state, session)
    assert state.state is None
    assert session.added_user["phone"] == "+1"
    assert contact_msg.photos
