"""FastAPI application serving the Telegram mini-app storefront.

Supports selecting a salon by its slug (``/{salon_slug}/``) and authenticates
Telegram MiniApp requests via ``initData``. On first visit a ``User`` and
``UserSalon`` record are created (если их нет), их ``user_salon_id`` кладётся в cookie.
"""

import hashlib
import hmac
import json
import os
import logging
import traceback
from urllib.parse import parse_qsl, quote

from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database.engine import session_maker
from database.orm_query import (
    orm_get_categories,
    orm_get_products,
    orm_get_product,
    orm_get_category,
    orm_get_salon_by_slug,
    orm_add_user,
    orm_get_user_salon,
    orm_get_salons,
    orm_get_user_salons,
    orm_get_last_salon_slug,
    orm_touch_user_salon,
)

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)

app = FastAPI()

# middleware, чтобы ошибки точно печатались
@app.middleware("http")
async def log_exceptions(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logging.error("🔥 Ошибка при обработке запроса", exc_info=True)
        return PlainTextResponse(
            content=f"Ошибка: {str(e)}\n\n{traceback.format_exc()}",
            status_code=500,
        )

templates = Jinja2Templates(directory="web_app/templates")


async def get_session() -> AsyncSession:
    async with session_maker() as session:
        yield session


def _verify_init_data(init_data: str) -> dict | None:
    """Validate Telegram WebApp ``initData`` signature."""
    token = os.getenv("TOKEN")
    if not token:
        logging.error("❌ Нет TOKEN в переменных окружения")
        return None

    data = dict(parse_qsl(init_data, strict_parsing=True))
    received_hash = data.pop("hash", None)
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))

    # ⚡ важно: без .digest()
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256)
    computed_hash = hmac.new(secret.digest(), data_check_string.encode(), hashlib.sha256).hexdigest()

    if computed_hash != received_hash:
        logging.warning("⚠️ Подпись initData не совпала")
        return None

    if "user" in data:
        data["user"] = json.loads(data["user"])
    return data


@app.get("/", response_class=HTMLResponse)
async def root(request: Request, session: AsyncSession = Depends(get_session)):
    init_data_raw = request.query_params.get("init_data")
    if not init_data_raw:
        content = """
        <html><body>
        <script>
        const initData = window.Telegram?.WebApp?.initData || '';
        if (initData) {
            const url = new URL(window.location.href);
            url.searchParams.set('init_data', initData);
            window.location.replace(url.toString());
        }
        </script>
        Загрузка...
        </body></html>
        """
        return HTMLResponse(content)

    payload = _verify_init_data(init_data_raw)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid init_data")

    user = payload.get("user", {})
    user_id = user.get("id")
    slug = payload.get("start_param")

    if not slug:
        slug = request.cookies.get("last_salon_slug")

    if not slug and user_id:
        slug = await orm_get_last_salon_slug(session, user_id)

    if not slug and user_id:
        user_salons = await orm_get_user_salons(session, user_id)
        if len(user_salons) == 1:
            slug = user_salons[0].salon.slug

    if not slug:
        salons = await orm_get_salons(session)
        if not salons:
            raise HTTPException(status_code=404, detail="No salons configured")
        slug = salons[0].slug

    return RedirectResponse(
        url=f"/{slug}/?init_data={quote(init_data_raw, safe='')}")


@app.get("/{salon_slug}/", response_class=HTMLResponse)
async def index(
    request: Request,
    salon_slug: str,
    cat: int | None = None,
    session: AsyncSession = Depends(get_session),
):
    salon = await orm_get_salon_by_slug(session, salon_slug)
    if not salon:
        raise HTTPException(status_code=404, detail="Salon not found")

    user_salon_id = request.cookies.get("user_salon_id")
    init_data = request.headers.get("X-Telegram-Init-Data") or request.query_params.get("init_data")

    payload = _verify_init_data(init_data) if init_data else None
    user_payload = payload.get("user") if payload else None

    if user_payload:
        user_salon = await orm_get_user_salon(session, user_payload["id"], salon.id)
        if not user_salon:
            user_salon = await orm_add_user(
                session,
                user_id=user_payload["id"],
                salon_id=salon.id,
                first_name=user_payload.get("first_name"),
                last_name=user_payload.get("last_name"),
            )
        else:
            await orm_touch_user_salon(session, user_payload["id"], salon.id)
        user_salon_id = str(user_salon.id)

    categories = await orm_get_categories(session, salon_id=salon.id)
    current_cat_id = cat or (categories[0].id if categories else None)
    current_cat_name = None
    if current_cat_id:
        current_cat = next((c for c in categories if c.id == current_cat_id), None)
        current_cat_name = current_cat.name if current_cat else None

    products = (
        await orm_get_products(session, category_id=current_cat_id, salon_id=salon.id)
        if current_cat_id
        else []
    )

    context = {
        "request": request,
        "categories": categories,
        "products": products,
        "current_cat": current_cat_id,
        "current_cat_name": current_cat_name,
        "salon_slug": salon.slug,
        "salon_name": salon.name,
        "init_data": init_data or "",
        "user_payload": user_payload or {},  # ⚡ всегда dict, чтобы не ломать шаблон
    }

    response = templates.TemplateResponse("index.html", context)
    if user_salon_id:
        response.set_cookie("user_salon_id", user_salon_id)
    response.set_cookie("last_salon_slug", salon.slug)
    return response


@app.get("/{salon_slug}/category/{cat_id}", response_class=HTMLResponse)
async def load_category(
    request: Request,
    salon_slug: str,
    cat_id: int,
    session: AsyncSession = Depends(get_session),
):
    salon = await orm_get_salon_by_slug(session, salon_slug)
    if not salon:
        raise HTTPException(status_code=404, detail="Salon not found")

    products = await orm_get_products(session, category_id=cat_id, salon_id=salon.id)
    categories = await orm_get_categories(session, salon_id=salon.id)
    category = await orm_get_category(session, category_id=cat_id, salon_id=salon.id)

    context = {
        "request": request,
        "products": products,
        "categories": categories,
        "current_cat": cat_id,
        "current_cat_name": category.name if category else None,
        "salon_slug": salon.slug,
    }
    return templates.TemplateResponse("catalog_content.html", context)


@app.get("/{salon_slug}/product/{product_id}", response_class=HTMLResponse)
async def product_detail(
    request: Request,
    salon_slug: str,
    product_id: int,
    session: AsyncSession = Depends(get_session),
):
    salon = await orm_get_salon_by_slug(session, salon_slug)
    if not salon:
        raise HTTPException(status_code=404, detail="Salon not found")

    product = await orm_get_product(session, product_id=product_id, salon_id=salon.id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    category = await orm_get_category(session, category_id=product.category_id, salon_id=salon.id)

    context = {
        "request": request,
        "product": product,
        "category": category,
        "salon_slug": salon.slug,
    }
    return templates.TemplateResponse("product_detail.html", context)