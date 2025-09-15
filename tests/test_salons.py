"""
Создание салона: уникальность имени/slug и значения по умолчанию.
"""

import pytest
from database.repositories.salon_repository import SalonRepository


@pytest.mark.asyncio
async def test_create_salon_uniqueness_and_defaults(session):
    repo = SalonRepository(session)
    s1 = await repo.create_salon("Name1", "slug1", "USD", None)
    assert s1.timezone == "UTC"
    assert s1.free_plan is True
    assert s1.order_limit == 30

    with pytest.raises(ValueError):
        await repo.create_salon("Name1", "slugX", "USD", None)
    with pytest.raises(ValueError):
        await repo.create_salon("NameX", "slug1", "USD", None)


@pytest.mark.asyncio
async def test_get_salon_by_slug(session):
    repo = SalonRepository(session)
    await repo.create_salon("Name2", "slug2", "USD")
    salon = await repo.get_salon_by_slug("slug2")
    assert salon is not None
    assert salon.name == "Name2"


@pytest.mark.asyncio
async def test_update_salon_location(session):
    repo = SalonRepository(session)
    salon = await repo.create_salon("Name3", "slug3", "USD")
    await repo.update_salon_location(salon.id, 10.0, 20.0)
    updated = await repo.get_salon_by_id(salon.id)
    assert updated.latitude == 10.0
    assert updated.longitude == 20.0

