"""
Заказы: доступ строго в рамках салона и подсчёт.
"""

import pytest
from database.models import Salon, Category, Product, User, UserSalon
from database.orm_query import (
    orm_add_to_cart,
    orm_get_user_carts,
    orm_create_order,
    orm_get_order,
    orm_get_orders,
    orm_get_orders_count,
)


@pytest.mark.asyncio
async def test_order_visibility_by_salon(session, sample_data):
    salon1, user_salon1, product1 = sample_data
    import time
    timestamp = int(time.time() * 1000)

    salon2 = Salon(name=f"Salon2_{timestamp}", slug=f"salon2_{timestamp}", currency="USD", timezone="UTC")
    session.add(salon2)
    await session.flush()
    cat2 = Category(name=f"Drinks_{timestamp}", salon_id=salon2.id)
    session.add(cat2)
    await session.flush()
    user2 = User(user_id=2 + timestamp, is_super_admin=False, language="ru")
    session.add(user2)
    await session.flush()
    user_salon2 = UserSalon(user_id=user2.user_id, salon_id=salon2.id)
    session.add(user_salon2)
    await session.commit()

    await orm_add_to_cart(session, user_salon1.id, product1.id)
    carts = await orm_get_user_carts(session, user_salon1.id)
    order = await orm_create_order(
        session,
        user_salon1.id,
        "John",
        "+123",
        None,
        "addr",
        "delivery",
        "cash",
        None,
        carts,
    )

    assert await orm_get_order(session, order.id, salon1.id) is not None
    assert await orm_get_order(session, order.id, salon2.id) is None

    orders_s2 = await orm_get_orders(session, salon2.id)
    assert orders_s2 == []


@pytest.mark.asyncio
async def test_orders_count(session, sample_data):
    salon1, user_salon1, product1 = sample_data
    await orm_add_to_cart(session, user_salon1.id, product1.id)
    carts = await orm_get_user_carts(session, user_salon1.id)
    await orm_create_order(
        session,
        user_salon1.id,
        "John",
        "+123",
        None,
        "addr",
        "delivery",
        "cash",
        None,
        carts,
    )

    count1 = await orm_get_orders_count(session, salon1.id)
    assert count1 == 1
