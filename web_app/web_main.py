import logging
import traceback
import hashlib
import hmac
import json
import os
from urllib.parse import parse_qsl, urlencode
import uuid

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.engine import session_maker
from database.models import Cart, UserSalon
from database.orm_query import (
    orm_add_user,
    orm_get_categories,
    orm_get_last_salon_slug,
    orm_get_products,
    orm_get_salon_by_slug,
    orm_get_salons,
    orm_get_user_salon,
    orm_get_user_salons,
    orm_touch_user_salon,
    orm_get_category,
)


DEBUG = os.getenv("DEBUG", "").lower() in {"1", "true", "yes"}
logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO)

templates = Jinja2Templates(directory="web_app/templates")
templates.env.globals["BOT_USERNAME"] = os.getenv("BOT_USERNAME", "")


async def get_session() -> AsyncSession:
    async with session_maker() as session:
        yield session


async def get_cart_count(
    session: AsyncSession, user_salon_id: str | None, salon_id: int | None = None
) -> int:
    if not user_salon_id:
        return 0
    if salon_id is not None:
        link = await session.get(UserSalon, int(user_salon_id))
        if not link or link.salon_id != salon_id:
            return 0
    total = await session.execute(
        select(func.sum(Cart.quantity)).where(Cart.user_salon_id == int(user_salon_id))
    )
    return total.scalar() or 0


def verify_init_data(init_data: str) -> dict | None:
    """Проверка подписи init_data из Mini App или Login Widget."""
    token = os.getenv("TOKEN")
    if not token:
        logging.error("❌ Нет TOKEN в переменных окружения")
        return None

    data = dict(parse_qsl(init_data, strict_parsing=True))
    received_hash = data.pop("hash", None)
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))

    secret_webapp = hmac.new(b"WebAppData", token.encode(), hashlib.sha256)
    hash_webapp = hmac.new(
        secret_webapp.digest(), data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    secret_login = hashlib.sha256(token.encode()).digest()
    hash_login = hmac.new(
        secret_login, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if received_hash not in {hash_webapp, hash_login}:
        logging.warning("⚠️ Подпись initData не совпала")
        return None

    if "user" in data:
        data["user"] = json.loads(data["user"])
    return data


app = FastAPI()


@app.middleware("http")
async def log_exceptions(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        logging.error("🔥 Ошибка при обработке запроса", exc_info=True)
        if DEBUG:
            content = f"Ошибка: {str(e)}\n\n{traceback.format_exc()}"
        else:
            content = "Внутренняя ошибка сервера"
        return PlainTextResponse(content=content, status_code=500)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)


@app.get("/", response_class=HTMLResponse)
async def root(request: Request, session: AsyncSession = Depends(get_session)):
    """Точка входа: принимает init_data или переводит гостя в первый салон."""
    init_data_raw = request.query_params.get("init_data")
    user_agent = request.headers.get("User-Agent", "")
    if not init_data_raw and "Telegram" not in user_agent:
        guest_id = request.cookies.get("guest_id") or uuid.uuid4().hex
        salons = await orm_get_salons(session)
        if not salons:
            raise HTTPException(status_code=404, detail="No salons configured")
        response = RedirectResponse(url=f"/{salons[0].slug}/", status_code=307)
        response.set_cookie(
            "guest_id", guest_id, max_age=31536000, samesite="None", secure=True
        )
        return response
    if not init_data_raw:
        content = """
        <html><body>
        <div id="status">Загрузка...</div>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <script>
        (function () {
            const status = document.getElementById('status');
            let attempts = 0;
            function check() {
                const tg = window.Telegram?.WebApp;
                const initData = tg?.initData;
                if (initData) {
                    tg.ready?.();
                    const url = new URL(window.location.href);
                    url.searchParams.set('init_data', initData);
                    window.location.replace(url.toString());
                } else if (attempts++ < 50) {
                    setTimeout(check, 100);
                } else {
                    status.textContent = 'Это окно нужно открывать внутри Telegram';
                }
            }
            check();
        })();
        </script>
        </body></html>
        """
        return HTMLResponse(content)

    payload = verify_init_data(init_data_raw)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid init_data")

    user = payload.get("user", {})
    user_id = user.get("id")
    slug = payload.get("start_param")

    if user_id:
        user_salons = await orm_get_user_salons(session, user_id)
        cart_count = await get_cart_count(session, request.cookies.get("user_salon_id"))
        if len(user_salons) == 1:
            slug = user_salons[0].salon.slug
        elif len(user_salons) > 1 and not slug:
            return templates.TemplateResponse(
                "choose_salon.html",
                {
                    "request": request,
                    "salons": [link.salon for link in user_salons],
                    "init_data": init_data_raw,
                    "cart_count": cart_count,
                },
            )

    if not slug:
        slug = request.cookies.get("last_salon_slug")

    if not slug and user_id:
        slug = await orm_get_last_salon_slug(session, user_id)

    if not slug:
        salons = await orm_get_salons(session)
        if not salons:
            raise HTTPException(status_code=404, detail="No salons configured")
        slug = salons[0].slug

    return RedirectResponse(
        url=f"/{slug}/?{urlencode({'init_data': init_data_raw})}",
        status_code=307,
    )


@app.get("/{salon_slug}/", response_class=HTMLResponse)
async def index(
    request: Request,
    salon_slug: str,
    cat: int | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Главная страница салона или гостевого режима."""
    init_data = request.headers.get("X-Telegram-Init-Data") or request.query_params.get("init_data")
    user_agent = request.headers.get("User-Agent", "")
    if not init_data and "Telegram" not in user_agent:
        guest_id = request.cookies.get("guest_id") or uuid.uuid4().hex
        salons = await orm_get_salons(session)
        if not salons:
            raise HTTPException(status_code=404, detail="No salons configured")
        first_slug = salons[0].slug
        response = RedirectResponse(url=f"/{first_slug}/", status_code=307)
        response.set_cookie(
            "guest_id", guest_id, max_age=31536000, samesite="None", secure=True
        )
        if salon_slug != first_slug:
            return response
        guest_cookie = guest_id
    else:
        guest_cookie = request.cookies.get("guest_id")

    salon = await orm_get_salon_by_slug(session, salon_slug)
    if not salon:
        raise HTTPException(status_code=404, detail="Salon not found")

    user_salon_id_cookie = request.cookies.get("user_salon_id")

    payload = verify_init_data(init_data) if init_data else None
    user_payload = payload.get("user") if payload else None

    user_salon_id: str | None = None
    welcome_name: str | None = None

    if user_salon_id_cookie:
        link_cookie = await session.get(UserSalon, int(user_salon_id_cookie))
        if link_cookie and link_cookie.salon_id == salon.id:
            user_salon_id = str(link_cookie.id)
            fn = (getattr(link_cookie, "first_name", "") or "").strip()
            ln = (getattr(link_cookie, "last_name", "") or "").strip()
            welcome_name = (f"{fn} {ln}".strip()) or fn or ln or None

    if user_payload:
        link = await orm_get_user_salon(session, user_payload["id"], salon.id)
        if not link:
            link = await orm_add_user(
                session,
                user_id=user_payload["id"],
                salon_id=salon.id,
                first_name=user_payload.get("first_name"),
                last_name=user_payload.get("last_name"),
            )
        else:
            await orm_touch_user_salon(session, user_payload["id"], salon.id)

        user_salon_id = str(link.id)

        first = (user_payload.get("first_name") or "").strip()
        last = (user_payload.get("last_name") or "").strip()
        full = f"{first} {last}".strip()
        if full or first or last:
            welcome_name = full or first or last
        else:
            fn = (getattr(link, "first_name", "") or "").strip()
            ln = (getattr(link, "last_name", "") or "").strip()
            welcome_name = (f"{fn} {ln}".strip()) or fn or ln or None
    else:
        welcome_name = "Гость"
        if not guest_cookie:
            guest_cookie = uuid.uuid4().hex

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

    cart_count = await get_cart_count(session, user_salon_id, salon.id)

    context = {
        "request": request,
        "categories": categories,
        "products": products,
        "current_cat": current_cat_id,
        "current_cat_name": current_cat_name,
        "salon_slug": salon.slug,
        "salon_name": salon.name,
        "init_data": init_data or "",
        "user_payload": user_payload or {},
        "welcome_name": welcome_name,
        "cart_count": cart_count,
    }

    response = templates.TemplateResponse("index.html", context)
    response.set_cookie(
        "last_salon_slug",
        salon.slug,
        max_age=31536000,
        samesite="None",
        secure=True,
    )
    if user_salon_id:
        response.set_cookie(
            "user_salon_id",
            user_salon_id,
            max_age=31536000,
            samesite="None",
            secure=True,
        )
    elif guest_cookie:
        response.set_cookie(
            "guest_id",
            guest_cookie,
            max_age=31536000,
            samesite="None",
            secure=True,
        )

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

    categories = await orm_get_categories(session, salon_id=salon.id)
    category = await orm_get_category(session, category_id=cat_id, salon_id=salon.id)
    products = await orm_get_products(session, category_id=cat_id, salon_id=salon.id)

    context = {
        "request": request,
        "products": products,
        "categories": categories,
        "current_cat": cat_id,
        "current_cat_name": category.name if category else None,
        "salon_slug": salon.slug,
    }
    return templates.TemplateResponse("catalog_content.html", context)


from .routes.products import router as products_router
from .routes.cart import router as cart_router
from .routes.orders import router as orders_router

app.include_router(products_router)
app.include_router(cart_router)
app.include_router(orders_router)