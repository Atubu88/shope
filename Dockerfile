FROM python:3.11-slim

ARG BUILD_TIME
LABEL build_time=$BUILD_TIME

# Без буферизации вывода
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Нужные системные либы (для psycopg2 или asyncpg + alembic). tzdata — чтобы TZ работали.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev tzdata \
    && rm -rf /var/lib/apt/lists/*

# Зависимости
COPY requirements.txt .
# Если у тебя alembic + asyncpg — psycopg2-binary можно НЕ ставить.
# Если alembic у тебя на psycopg2 — оставь строку установки psycopg2-binary и
# используй в alembic.ini DSN на psycopg2.
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir alembic

# Код
COPY . .

# ► При старте: (опционально) миграции, затем бот
# Установи RUN_MIGRATIONS=1 в docker-compose, если хочешь прогонять миграции.
ENTRYPOINT ["sh", "-c", "if [ \"$RUN_MIGRATIONS\" = \"1\" ]; then alembic upgrade head; fi && python -m main"]
