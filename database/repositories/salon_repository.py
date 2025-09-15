from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Salon


class SalonRepository:
    """Repository for operations with :class:`Salon` model."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with session."""
        self.session = session

    async def get_salon_name_by_id(self, salon_id: int) -> str | None:
        """Return name of salon by its ID or ``None`` if not found."""
        salon = await self.session.get(Salon, salon_id)
        return salon.name if salon else None

    async def get_salons(self) -> list[Salon]:
        """Return all salons."""
        result = await self.session.execute(select(Salon))
        return result.scalars().all()

    async def create_salon(
        self,
        name: str,
        slug: str,
        currency: str,
        timezone: str | None = "UTC",
    ) -> Salon:
        """Create new salon ensuring unique name and slug."""
        stmt = select(Salon).where((Salon.name == name) | (Salon.slug == slug))
        result = await self.session.execute(stmt)
        salon = result.scalar_one_or_none()
        if salon:
            raise ValueError("Salon with this name or slug already exists")
        new_salon = Salon(
            name=name,
            slug=slug,
            currency=currency,
            timezone=timezone or "UTC",
            free_plan=True,
            order_limit=30,
        )
        self.session.add(new_salon)
        await self.session.commit()
        await self.session.refresh(new_salon)
        return new_salon

    async def set_salon_timezone(self, salon_id: int, tz_name: str) -> None:
        """Update timezone for the given salon."""
        await self.session.execute(
            update(Salon).where(Salon.id == salon_id).values(timezone=tz_name)
        )
        await self.session.commit()

    async def get_salon_by_slug(self, slug: str) -> Salon | None:
        """Return salon by slug or ``None`` if missing."""
        result = await self.session.execute(select(Salon).where(Salon.slug == slug))
        return result.scalar_one_or_none()

    async def update_salon_location(
        self, salon_id: int, latitude: float, longitude: float
    ) -> None:
        """Update geographic coordinates of a salon."""
        await self.session.execute(
            update(Salon)
            .where(Salon.id == salon_id)
            .values(latitude=latitude, longitude=longitude)
        )
        await self.session.commit()

    async def update_salon_group_chat(self, salon_id: int, group_chat_id: int) -> None:
        """Set group chat identifier for a salon."""
        await self.session.execute(
            update(Salon)
            .where(Salon.id == salon_id)
            .values(group_chat_id=group_chat_id)
        )
        await self.session.commit()

    async def get_salon_by_id(self, salon_id: int) -> Salon | None:
        """Return salon by its database ID."""
        result = await self.session.execute(
            select(Salon).where(Salon.id == salon_id)
        )
        return result.scalars().first()
