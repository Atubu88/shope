import pytest
import sys
from pathlib import Path

# Добавляем корень проекта (pizza_bot) в sys.path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from database.orm_query import (
    orm_add_to_cart,
    orm_get_user_carts,
    orm_delete_from_cart,
    orm_create_order,
    orm_update_order_status,
)


@pytest.mark.asyncio
async def test_add_to_cart_increments_quantity(session, sample_data):
    _, user_salon, product = sample_data
    await orm_add_to_cart(session, user_salon.id, product.id)
    await orm_add_to_cart(session, user_salon.id, product.id)
    carts = await orm_get_user_carts(session, user_salon.id)
    assert len(carts) == 1
    assert carts[0].quantity == 2


@pytest.mark.asyncio
async def test_delete_from_cart(session, sample_data):
    _, user_salon, product = sample_data
    await orm_add_to_cart(session, user_salon.id, product.id)
    await orm_delete_from_cart(session, user_salon.id, product.id)
    carts = await orm_get_user_carts(session, user_salon.id)
    assert carts == []


@pytest.mark.asyncio
async def test_order_total_and_status_update(session, sample_data):
    salon, user_salon, product = sample_data
    await orm_add_to_cart(session, user_salon.id, product.id)
    await orm_add_to_cart(session, user_salon.id, product.id)
    carts = await orm_get_user_carts(session, user_salon.id)
    order = await orm_create_order(
        session, user_salon.id, "addr", "123", "cash", carts
    )
    assert float(order.total) == pytest.approx(20.0)
    updated = await orm_update_order_status(session, order.id, salon.id, "DONE")
    assert updated.status == "DONE"