"""Repositories for working with :class:`~database.models.Salon`."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Salon


class SalonRepository:
    """Асинхронный репозиторий для управления салонами."""

    def __init__(self, session: AsyncSession) -> None:
        """Сохраняет сессию для дальнейших запросов."""
        self._session = session

    @property
    def session(self) -> AsyncSession:
        """Возвращает привязанную сессию."""
        return self._session

    async def list(self) -> list[Salon]:
        """Возвращает список всех салонов."""
        result = await self._session.execute(select(Salon))
        return list(result.scalars().all())

    async def get_name_by_id(self, salon_id: int) -> str | None:
        """Находит название салона по идентификатору."""
        salon = await self._session.get(Salon, salon_id)
        return salon.name if salon else None

    async def create(
        self,
        name: str,
        slug: str,
        currency: str,
        timezone: str | None = "UTC",
    ) -> Salon:
        """Создаёт новый салон, гарантируя уникальность имени и slug."""
        stmt = select(Salon).where((Salon.name == name) | (Salon.slug == slug))
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            raise ValueError("Salon with this name or slug already exists")

        new_salon = Salon(
            name=name,
            slug=slug,
            currency=currency,
            timezone=timezone or "UTC",
            free_plan=True,
            order_limit=30,
        )
        self._session.add(new_salon)
        await self._session.commit()
        await self._session.refresh(new_salon)
        return new_salon

    async def set_timezone(self, salon_id: int, tz_name: str) -> None:
        """Обновляет часовой пояс салона."""
        await self._session.execute(
            update(Salon).where(Salon.id == salon_id).values(timezone=tz_name)
        )
        await self._session.commit()

    async def get_by_slug(self, slug: str) -> Salon | None:
        """Возвращает салон по slug или ``None``."""
        result = await self._session.execute(select(Salon).where(Salon.slug == slug))
        return result.scalar_one_or_none()

    async def update_location(
        self, salon_id: int, latitude: float, longitude: float
    ) -> None:
        """Обновляет координаты салона."""
        await self._session.execute(
            update(Salon)
            .where(Salon.id == salon_id)
            .values(latitude=latitude, longitude=longitude)
        )
        await self._session.commit()

    async def update_group_chat(self, salon_id: int, group_chat_id: int) -> None:
        """Сохраняет идентификатор группового чата салона."""
        await self._session.execute(
            update(Salon)
            .where(Salon.id == salon_id)
            .values(group_chat_id=group_chat_id)
        )
        await self._session.commit()

    async def get_by_id(self, salon_id: int) -> Salon | None:
        """Получает салон по идентификатору."""
        result = await self._session.execute(
            select(Salon).where(Salon.id == salon_id)
        )
        return result.scalars().first()
