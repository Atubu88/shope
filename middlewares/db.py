from typing import Any, Awaitable, Callable, Dict

import logging
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import text as sa_text

logger = logging.getLogger(__name__)


class DataBaseSession(BaseMiddleware):
    """
    Создаёт AsyncSession на время обработки апдейта и кладёт его в data['session'].
    Подключение к БД проверяется и логируется ОДИН РАЗ при первом апдейте.
    """
    _checked = False  # класс-флаг одноразовой проверки

    def __init__(self, session_pool: async_sessionmaker):
        self.session_pool = session_pool
        # Аккуратно логируем URL движка без пароля, если можем его получить
        try:
            bind = getattr(session_pool, "kw", {}).get("bind")
            if bind is not None and getattr(bind, "url", None) is not None:
                url = bind.url
                # SQLAlchemy URL умеет скрывать пароль
                logger.info("Engine URL: %s", url.render_as_string(hide_password=True))
        except Exception as e:
            logger.warning("inspect engine failed: %s", e)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ):
        async with self.session_pool() as session:
            # Разовая проверка подключения
            if not type(self)._checked:
                try:
                    res = await session.execute(sa_text(
                        "select current_database(), inet_server_addr(), inet_server_port()"
                    ))
                    row = res.fetchone()
                    logger.info("DB connect ok: %s", row)
                except Exception as e:
                    # Не падаем в рантайме, просто логируем проблему
                    logger.error("DB connect check failed: %s", e, exc_info=True)
                finally:
                    type(self)._checked = True

            data["session"] = session
            return await handler(event, data)
