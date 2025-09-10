"""
Фикстуры для асинхронных тестов с чистой SQLite (aiosqlite).
Создаёт таблицы один раз и выдаёт новую сессию на каждый тест.
"""

import asyncio
import sys
from pathlib import Path
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Добавляем корень проекта в sys.path для импортов пакета database и прочих модулей
sys.path.append(str(Path(__file__).resolve().parents[1]))

from database.models import Base, Salon, Category, Product, User, UserSalon


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def session(engine):
    maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        yield s


@pytest_asyncio.fixture
async def sample_data(session: AsyncSession):
    """Создаёт минимальный набор: салон, категорию, товар, пользователя и связь UserSalon."""
    import time
    timestamp = int(time.time() * 1000)  # уникальный timestamp
    
    salon = Salon(
        name=f"Salon1_{timestamp}", 
        slug=f"salon1_{timestamp}", 
        currency="USD", 
        timezone="UTC"
    )
    session.add(salon)
    await session.flush()

    category = Category(name=f"Pizza_{timestamp}", salon_id=salon.id)
    session.add(category)
    await session.flush()

    product = Product(
        name=f"Pepperoni_{timestamp}",
        description="tasty",
        price=10,
        image="pep.jpg",
        category_id=category.id,
        salon_id=salon.id,
    )
    session.add(product)
    await session.flush()

    user = User(user_id=timestamp, is_super_admin=False, language="ru")
    session.add(user)
    await session.flush()

    user_salon = UserSalon(
        user_id=user.user_id,
        salon_id=salon.id,
        first_name="Ivan",
        last_name="Petrov",
        phone=f"+1000{timestamp}",
    )
    session.add(user_salon)
    await session.commit()

    return salon, user_salon, product
