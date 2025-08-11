# database/engine.py
import os
import asyncio
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# 1) Читаем DSN из окружения (и прибираем пробелы по краям)
raw = (os.getenv("DB_CORE") or "")
print("[DB RAW]", repr(raw))  # <-- смотрим, нет ли лишних \r/\n/пробелов
if not raw.strip():
    raise RuntimeError("DB_CORE is not set")

# 2) Готовим URL под asyncpg
url = make_url(raw.strip()).set(drivername="postgresql+asyncpg")

# 3) Логи по паролю (без раскрытия) — проверяем длину и коды символов
pwd = url.password or ""
print("[DB PWD LEN]", len(pwd), "CHARS:", [ord(c) for c in pwd])  # ищем лишние символы
masked = str(url).replace(pwd, "***")
print("[DB ENGINE] USING:", masked)

# 4) (опционально) Пробный коннект asyncpg — включается только если DB_PROBE=1
async def _probe(u):
    import asyncpg
    try:
        conn = await asyncpg.connect(
            user=u.username, password=u.password,
            host=u.host, port=u.port, database=u.database
        )
        print("[DB PROBE] asyncpg OK")
        await conn.close()
    except Exception as e:
        print("[DB PROBE] asyncpg FAIL:", e)

if os.getenv("DB_PROBE") == "1":
    asyncio.run(_probe(url))

# 5) Единый engine и sessionmaker
engine = create_async_engine(str(url), pool_pre_ping=True)
session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
