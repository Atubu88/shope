"""Tests for custom filters."""

from __future__ import annotations

from datetime import datetime

import pytest
from aiogram import types

from database.models import User
from filters.chat_types import IsAdmin


@pytest.mark.asyncio
async def test_is_admin_allows_superadmin_without_salon(session):
    """Super admin without salon binding should pass the IsAdmin filter."""

    user = User(user_id=987654321, is_super_admin=True, language="ru")
    session.add(user)
    await session.commit()

    message = types.Message.model_validate(
        {
            "message_id": 1,
            "date": int(datetime.now().timestamp()),
            "chat": {"id": 1, "type": "private"},
            "from": {"id": user.user_id, "is_bot": False, "first_name": "Admin"},
            "text": "/invite",
        }
    )

    is_admin = await IsAdmin()(message, session)

    assert is_admin is True


@pytest.mark.asyncio
async def test_is_admin_denies_regular_user_without_salon(session):
    """Regular user without salon binding should not pass the IsAdmin filter."""

    user = User(user_id=123456789, is_super_admin=False, language="ru")
    session.add(user)
    await session.commit()

    message = types.Message.model_validate(
        {
            "message_id": 2,
            "date": int(datetime.now().timestamp()),
            "chat": {"id": 2, "type": "private"},
            "from": {"id": user.user_id, "is_bot": False, "first_name": "User"},
            "text": "/invite",
        }
    )

    is_admin = await IsAdmin()(message, session)

    assert is_admin is False
