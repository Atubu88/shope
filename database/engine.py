import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from database.models import Base




# from .env file:
# DB_LITE=sqlite+aiosqlite:///my_base.db
# DB_URL=postgresql+asyncpg://login:password@localhost:5432/db_name

db_url = os.getenv("DB_URL")
if not db_url:
    raise RuntimeError("DB_URL environment variable is not set")

# engine = create_async_engine(os.getenv('DB_URL'), echo=True)
engine = create_async_engine(db_url, echo=True)

session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)




async def drop_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)