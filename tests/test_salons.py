"""
Создание салона: уникальность имени/slug и значения по умолчанию.
"""

import pytest
from database.repositories import SalonRepository


@pytest.mark.asyncio
async def test_create_salon_uniqueness_and_defaults(session):
    repo = SalonRepository(session)
    s1 = await repo.create("Name1", "slug1", "USD", None)
    assert s1.timezone == "UTC"
    assert s1.free_plan is True
    assert s1.order_limit == 30

    with pytest.raises(ValueError):
        await repo.create("Name1", "slugX", "USD", None)
    with pytest.raises(ValueError):
        await repo.create("NameX", "slug1", "USD", None)



@pytest.mark.asyncio
async def test_get_by_slug(session):
    repo = SalonRepository(session)
    created = await repo.create("SalonSlug", "slug-123", "USD")

    found = await repo.get_by_slug(created.slug)
    assert found is not None
    assert found.id == created.id

    assert await repo.get_by_slug("missing") is None


@pytest.mark.asyncio
async def test_update_location(session):
    repo = SalonRepository(session)
    salon = await repo.create("SalonLocation", "location-slug", "EUR")

    await repo.update_location(salon.id, 55.7558, 37.6176)
    updated = await repo.get_by_id(salon.id)
    assert updated is not None
    assert pytest.approx(float(updated.latitude), rel=1e-6) == 55.7558
    assert pytest.approx(float(updated.longitude), rel=1e-6) == 37.6176
