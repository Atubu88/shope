"""FastAPI application serving the Telegram mini‑app storefront.

The original version was hard‑coded to work only with salon ``id=1`` and did
not provide any user authentication.  This module now supports selecting a
salon by its slug (``/{salon_slug}/``) and authenticates Telegram MiniApp
requests via ``initData``.  On first visit a ``User`` and ``UserSalon`` record
are created and their ``user_salon_id`` is stored in a cookie so that
subsequent requests may reuse it.
"""

from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

import hashlib
import hmac
import json
import os
from urllib.parse import parse_qsl

from database.engine import session_maker  # общий async sessionmaker
from database.orm_query import (
    orm_get_categories,
    orm_get_products,
    orm_get_product,
    orm_get_category,
    orm_get_salon_by_slug,
    orm_add_user,
)

app = FastAPI()
templates = Jinja2Templates(directory="web_app/templates")

async def get_session() -> AsyncSession:
    async with session_maker() as session:
        yield session

def _verify_init_data(init_data: str) -> dict | None:
    """Validate Telegram WebApp ``initData`` signature.

    Returns decoded payload on success, otherwise ``None``.
    """

    token = os.getenv("TOKEN")
    if not token:
        return None

    data = dict(parse_qsl(init_data, strict_parsing=True))
    received_hash = data.pop("hash", None)
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    if computed_hash != received_hash:
        return None

    if "user" in data:
        return json.loads(data["user"])
    return None


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
    if not user_salon_id and init_data:
        user_payload = _verify_init_data(init_data)
        if user_payload:
            user_salon = await orm_add_user(
                session,
                user_id=user_payload["id"],
                salon_id=salon.id,
                first_name=user_payload.get("first_name"),
                last_name=user_payload.get("last_name"),
            )
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
    }
    response = templates.TemplateResponse("index.html", context)
    if user_salon_id:
        response.set_cookie("user_salon_id", user_salon_id)
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
    response = templates.TemplateResponse("catalog_content.html", context)
    return response

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

    category = await orm_get_category(
        session, category_id=product.category_id, salon_id=salon.id
    )

    context = {
        "request": request,
        "product": product,
        "category": category,
        "salon_slug": salon.slug,
    }
    response = templates.TemplateResponse("product_detail.html", context)
    return response

