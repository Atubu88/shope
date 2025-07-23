import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

# 🔧 Добавляем путь к проекту
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# 🔻 Импортируем Base и модели
from database.models import Base  # declarative_base()

# Alembic config
config = context.config

# Подключение логгера
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Метаданные для autogenerate
target_metadata = Base.metadata


def get_url():
    # Путь к SQLite-файлу
    # Получаем URL базы данных из переменных окружения
    db_url = os.getenv("DB_URL")
    if not db_url:
        raise RuntimeError("DB_URL environment variable is not set")
    return db_url


def run_migrations_offline():
    """Генерация SQL-файла без подключения к БД"""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    """Асинхронное выполнение миграции в реальной БД"""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=None,
        url=get_url(),
    )

    async with connectable.connect() as connection:
        def do_run_migrations(sync_connection):
            context.configure(
                connection=sync_connection,
                target_metadata=target_metadata,
            )
            with context.begin_transaction():
                context.run_migrations()

        await connection.run_sync(do_run_migrations)


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
