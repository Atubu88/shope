import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from database.models import Base
from database.orm_query import (
    orm_add_banner_description,
    orm_create_categories,
    orm_create_salon,
    orm_get_salon_by_slug,
)

from common.texts_for_db import categories, description_for_info_pages

# from .env file:
# DB_LITE=sqlite+aiosqlite:///my_base.db
# DB_URL=postgresql+asyncpg://login:password@localhost:5432/db_name

db_url = os.getenv("DB_URL")
if not db_url:
    raise RuntimeError("DB_URL environment variable is not set")

# engine = create_async_engine(os.getenv('DB_URL'), echo=True)
engine = create_async_engine(db_url, echo=True)

session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def create_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_maker() as session:
        try:
            salon = await orm_create_salon(session, "Default", "default", currency="RUB")
        except ValueError:
            salon = await orm_get_salon_by_slug(session, "default")
        await orm_create_categories(session, categories, salon.id)
        await orm_add_banner_description(session, description_for_info_pages, salon.id)


async def drop_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)