"""Пользователь и MRU-салон: идемпотентность флагов и порядок updated."""

import pytest
import asyncio
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from database.models import Salon, User, UserSalon
from database.orm_query import (
    orm_add_user,
    orm_touch_user_salon,
    orm_get_mru_salon,
    orm_get_any_salon,
    orm_get_last_salon_slug,
)


@pytest.mark.asyncio
async def test_add_user_idempotent_and_flags(session):
    import time
    timestamp = int(time.time() * 1000)
    
    salon = Salon(name=f"U1_{timestamp}", slug=f"u1_{timestamp}", currency="USD", timezone="UTC")
    session.add(salon)
    await session.flush()

    await orm_add_user(
        session,
        user_id=777 + timestamp,
        salon_id=salon.id,
        first_name="A",
        last_name="B",
        phone="+1",
        is_super_admin=True,
        is_salon_admin=True,
    )

    res = await session.execute(
        select(UserSalon)
        .where(UserSalon.user_id == 777 + timestamp, UserSalon.salon_id == salon.id)
        .options(selectinload(UserSalon.user))
    )
    us = res.scalar_one()
    assert us.is_salon_admin is True
    assert us.user.is_super_admin is True

    await orm_add_user(
        session,
        user_id=777 + timestamp,
        salon_id=salon.id,
        phone="+2",
    )
    res2 = await session.execute(
        select(UserSalon)
        .where(UserSalon.id == us.id)
        .options(selectinload(UserSalon.user))
    )
    us2 = res2.scalar_one()
    assert us2.phone == "+2"
    assert us2.is_salon_admin is True
    assert us2.user.is_super_admin is True


@pytest.mark.asyncio
async def test_mru_salon_ordering(session):
    import time
    timestamp = int(time.time() * 1000)
    
    u = User(user_id=1000 + timestamp, is_super_admin=False, language="ru")
    session.add(u)
    await session.flush()

    s1 = Salon(name=f"S-A_{timestamp}", slug=f"sa_{timestamp}", currency="USD", timezone="UTC")
    s2 = Salon(name=f"S-B_{timestamp}", slug=f"sb_{timestamp}", currency="USD", timezone="UTC")
    session.add_all([s1, s2])
    await session.flush()

    us1 = UserSalon(user_id=u.user_id, salon_id=s1.id)
    us2 = UserSalon(user_id=u.user_id, salon_id=s2.id)
    session.add_all([us1, us2])
    await session.commit()

    await orm_touch_user_salon(session, u.user_id, s1.id)
    # SQLite CURRENT_TIMESTAMP имеет точность 1 сек; подождём, чтобы updated отличались
    await asyncio.sleep(1)
    await orm_touch_user_salon(session, u.user_id, s2.id)

    mru = await orm_get_mru_salon(session, u.user_id)
    assert mru and mru.id == s2.id

    any_salon = await orm_get_any_salon(session, u.user_id)
    assert any_salon is not None

    last_slug = await orm_get_last_salon_slug(session, u.user_id)
    assert last_slug == f"sb_{timestamp}"


@pytest.mark.asyncio
async def test_mru_updates_on_reselect(session):
    import time

    timestamp = int(time.time() * 1000)

    user = User(user_id=2000 + timestamp, is_super_admin=False, language="ru")
    session.add(user)
    await session.flush()

    s1 = Salon(name=f"S-C_{timestamp}", slug=f"sc_{timestamp}", currency="USD", timezone="UTC")
    s2 = Salon(name=f"S-D_{timestamp}", slug=f"sd_{timestamp}", currency="USD", timezone="UTC")
    session.add_all([s1, s2])
    await session.flush()

    await orm_add_user(session, user.user_id, s1.id, first_name="A", last_name="B")
    await asyncio.sleep(1)

    await orm_add_user(session, user.user_id, s2.id, first_name="C", last_name="D")
    await asyncio.sleep(1)

    await orm_add_user(session, user.user_id, s1.id)

    mru = await orm_get_mru_salon(session, user.user_id)
    assert mru and mru.id == s1.id
