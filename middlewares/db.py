from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from sqlalchemy.ext.asyncio import async_sessionmaker


# middlewares/db.py
from sqlalchemy import text as sa_text
import logging
import os

logger = logging.getLogger("db_middleware")
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logger.setLevel(getattr(logging, log_level, logging.INFO))

class DataBaseSession(BaseMiddleware):
    def __init__(self, session_pool: async_sessionmaker):
        self.session_pool = session_pool
        try:
            bind = getattr(session_pool, "kw", {}).get("bind")
            if bind is not None:
                u = bind.url
                logger.info("Engine URL: %s", str(u).replace(u.password or "", "***"))
        except Exception as e:
            logger.warning("inspect engine failed: %s", e)

    async def __call__(self, handler, event, data):
        async with self.session_pool() as session:
            # Разовая проверка, куда реально коннектимся
            try:
                res = await session.execute(sa_text(
                    "select current_database(), inet_server_addr(), inet_server_port()"
                ))
                row = res.fetchone()
                logger.debug("Connected to: %s", row)
            except Exception as e:
                logger.error("session test FAIL: %s", e)
            data['session'] = session
            return await handler(event, data)

# class CounterMiddleware(BaseMiddleware):
#     def __init__(self) -> None:
#         self.counter = 0

#     async def __call__(
#         self,
#         handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
#         event: TelegramObject,
#         data: Dict[str, Any]
#     ) -> Any:
#         self.counter += 1
#         data['counter'] = self.counter
#         return await handler(event, data)