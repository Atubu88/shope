"""
Баннеры: не перезаписывать ручные описания и установка изображений.
"""

import pytest
from database.models import Salon
from database.orm_query import orm_add_banner_description, orm_get_banner


@pytest.mark.asyncio
async def test_banner_description_preserve_manual_and_set_images(session):
    salon = Salon(name="Bnnr", slug="bnnr", currency="USD", timezone="UTC")
    session.add(salon)
    await session.flush()
    salon_id = salon.id
    await session.commit()

    await orm_add_banner_description(session, {"about": "manual"}, salon_id, None)
    banner = await orm_get_banner(session, "about", salon_id)
    assert banner and banner.description == "manual"

    await orm_add_banner_description(session, {"about": None}, salon_id, None)
    banner2 = await orm_get_banner(session, "about", salon_id)
    assert banner2 and banner2.description == "manual"

    await orm_add_banner_description(session, {"contact": None}, salon_id, {"contact": "img.png"})
    banner3 = await orm_get_banner(session, "contact", salon_id)
    assert banner3 and banner3.image == "img.png"

