import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

logging.basicConfig(level=logging.DEBUG)

app = FastAPI()


@app.middleware("http")
async def log_exceptions(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        logging.error("🔥 Ошибка при обработке запроса", exc_info=True)
        return PlainTextResponse(
            content=f"Ошибка: {str(e)}\n\n{traceback.format_exc()}",
            status_code=500,
        )


from .routes.main import router as main_router
from .routes.products import router as products_router
from .routes.cart import router as cart_router

app.include_router(main_router)
app.include_router(products_router)
app.include_router(cart_router)
