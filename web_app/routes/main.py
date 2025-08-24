from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query import (
    orm_add_user,
    orm_get_categories,
    orm_get_last_salon_slug,
    orm_get_salon_by_slug,
    orm_get_salons,
    orm_get_user_salon,
    orm_get_user_salons,
    orm_touch_user_salon,
    orm_get_category,
)

from ..dependencies import (
    get_cart_count,
    get_session,
    templates,
    verify_init_data,
)

router = APIRouter()


@router.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)


@router.get("/", response_class=HTMLResponse)
async def root(request: Request, session: AsyncSession = Depends(get_session)):
    init_data_raw = request.query_params.get("init_data")
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
                }
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
        status_code=307
    )


@router.get("/{salon_slug}/", response_class=HTMLResponse)
async def index(
    request: Request,
    salon_slug: str,
    cat: int | None = None,
    session: AsyncSession = Depends(get_session),
):
    salon = await orm_get_salon_by_slug(session, salon_slug)
    if not salon:
        raise HTTPException(status_code=404, detail="Salon not found")

    init_data = request.headers.get("X-Telegram-Init-Data") or request.query_params.get("init_data")
    user_salon_id_cookie = request.cookies.get("user_salon_id")

    payload = verify_init_data(init_data) if init_data else None
    user_payload = payload.get("user") if payload else None

    user_salon_id: str | None = user_salon_id_cookie
    welcome_name: str | None = None

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
        last  = (user_payload.get("last_name") or "").strip()
        full  = f"{first} {last}".strip()
        if full or first or last:
            welcome_name = full or first or last
        else:
            fn = (getattr(link, "first_name", "") or "").strip()
            ln = (getattr(link, "last_name", "") or "").strip()
            welcome_name = (f"{fn} {ln}".strip()) or fn or ln or None

    categories = await orm_get_categories(session, salon_id=salon.id)
    current_cat_id = cat or (categories[0].id if categories else None)
    current_cat_name = None
    if current_cat_id:
        current_cat = next((c for c in categories if c.id == current_cat_id), None)
        current_cat_name = current_cat.name if current_cat else None

    products = (
        await orm_get_products(session, category_id=current_cat_id, salon_id=salon.id)
        if current_cat_id else []
    )

    cart_count = await get_cart_count(session, user_salon_id)

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
        "last_salon_slug", salon.slug,
        max_age=31536000, samesite="None", secure=True
    )
    if user_salon_id:
        response.set_cookie(
            "user_salon_id", user_salon_id,
            max_age=31536000, samesite="None", secure=True
        )

    return response


@router.get("/{salon_slug}/category/{cat_id}", response_class=HTMLResponse)
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

    context = {
        "request": request,
        "products": products,
        "categories": categories,
        "current_cat": cat_id,
        "current_cat_name": category.name if category else None,
        "salon_slug": salon.slug,
    }
    return templates.TemplateResponse("catalog_content.html", context)
