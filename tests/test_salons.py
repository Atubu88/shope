"""
Создание салона: уникальность имени/slug и значения по умолчанию.
"""

import pytest
from database.orm_query import orm_create_salon


@pytest.mark.asyncio
async def test_create_salon_uniqueness_and_defaults(session):
    s1 = await orm_create_salon(session, "Name1", "slug1", "USD", None)
    assert s1.timezone == "UTC"
    assert s1.free_plan is True
    assert s1.order_limit == 30

    with pytest.raises(ValueError):
        await orm_create_salon(session, "Name1", "slugX", "USD", None)
    with pytest.raises(ValueError):
        await orm_create_salon(session, "NameX", "slug1", "USD", None)

