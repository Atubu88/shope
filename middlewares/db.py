from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from sqlalchemy.ext.asyncio import async_sessionmaker


# middlewares/db.py
from sqlalchemy import text as sa_text

class DataBaseSession(BaseMiddleware):
    def __init__(self, session_pool: async_sessionmaker):
        self.session_pool = session_pool
        try:
            bind = getattr(session_pool, "kw", {}).get("bind")
            if bind is not None:
                u = bind.url
                print("[MW] Engine URL:", str(u).replace(u.password or "", "***"))
        except Exception as e:
            print("[MW] inspect engine failed:", e)

    async def __call__(self, handler, event, data):
        async with self.session_pool() as session:
            # Разовая проверка, куда реально коннектимся
            try:
                res = await session.execute(sa_text(
                    "select current_database(), inet_server_addr(), inet_server_port()"
                ))
                row = res.fetchone()
                print("[MW] Connected to:", row)
            except Exception as e:
                print("[MW] session test FAIL:", e)
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