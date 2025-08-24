from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import Cart, UserSalon
from database.orm_query import (
    orm_add_user,
    orm_get_product,
    orm_get_salon_by_slug,
    orm_get_user_salon,
)

from ..web_main import get_session, templates, verify_init_data

router = APIRouter()


@router.get("/{salon_slug}/cart", response_class=HTMLResponse)
async def view_cart(
    request: Request,
    salon_slug: str,
    session: AsyncSession = Depends(get_session),
):
    user_salon_id = request.cookies.get("user_salon_id")
    if not user_salon_id:
        raise HTTPException(401, "User not identified")

    salon = await orm_get_salon_by_slug(session, salon_slug)
    if not salon:
        raise HTTPException(status_code=404, detail="Salon not found")

    link = await session.get(UserSalon, int(user_salon_id))
    if not link or link.salon_id != salon.id:
        raise HTTPException(403, "Access forbidden")

    first = (link.first_name or "").strip()
    last = (link.last_name or "").strip()
    full = f"{first} {last}".strip()
    welcome_name = full or first or last or None

    result = await session.execute(
        select(Cart).where(Cart.user_salon_id == link.id).options(
            selectinload(Cart.product)
        )
    )
    items = result.scalars().all()

    total = sum(i.product.price * i.quantity for i in items)

    cart_count = sum(i.quantity for i in items)

    return templates.TemplateResponse(
        "cart.html",
        {
            "request": request,
            "items": items,
            "total": total,
            "salon_slug": salon_slug,
            "salon_name": salon.name,
            "welcome_name": welcome_name,
            "cart_count": cart_count,
        },
    )


@router.post("/{salon_slug}/cart/add/{product_id}")
async def add_to_cart(
    request: Request,
    salon_slug: str,
    product_id: int,
    session: AsyncSession = Depends(get_session),
):
    salon = await orm_get_salon_by_slug(session, salon_slug)
    if not salon:
        raise HTTPException(status_code=404, detail="Salon not found")

    product = await orm_get_product(session, product_id, salon.id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    init_data = request.headers.get("X-Telegram-Init-Data") or request.query_params.get("init_data")
    payload = verify_init_data(init_data) if init_data else None
    user_payload = payload.get("user") if payload else None
    if not user_payload:
        raise HTTPException(status_code=401, detail="Unauthorized")

    link = await orm_get_user_salon(session, user_payload["id"], salon.id)
    if not link:
        link = await orm_add_user(
            session,
            user_id=user_payload["id"],
            salon_id=salon.id,
            first_name=user_payload.get("first_name"),
            last_name=user_payload.get("last_name"),
        )

    cart_item = await session.execute(
        select(Cart).where(Cart.user_salon_id == link.id, Cart.product_id == product_id)
    )
    cart_item = cart_item.scalars().first()
    if cart_item:
        cart_item.quantity += 1
    else:
        cart_item = Cart(user_salon_id=link.id, product_id=product_id, quantity=1)
        session.add(cart_item)
    await session.commit()

    total = await session.execute(
        select(func.sum(Cart.quantity)).where(Cart.user_salon_id == link.id)
    )
    count = total.scalar() or 0

    return templates.TemplateResponse(
        "_cart_counts_oob.htm",
        {
            "request": request,
            "cart_count": count,
        },
    )


@router.post("/{salon_slug}/cart/increase/{product_id}")
async def increase_cart_item(
    request: Request,
    salon_slug: str,
    product_id: int,
    session: AsyncSession = Depends(get_session),
):
    user_salon_id = request.cookies.get("user_salon_id")
    if not user_salon_id:
        raise HTTPException(401, "User not identified")

    salon = await orm_get_salon_by_slug(session, salon_slug)
    if not salon:
        raise HTTPException(status_code=404, detail="Salon not found")

    link = await session.get(UserSalon, int(user_salon_id))
    if not link or link.salon_id != salon.id:
        raise HTTPException(403, "Access forbidden")

    product = await orm_get_product(session, product_id, salon.id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    cart_item = await session.execute(
        select(Cart).where(Cart.user_salon_id == link.id, Cart.product_id == product_id)
    )
    cart_item = cart_item.scalars().first()
    if cart_item:
        cart_item.quantity += 1
    else:
        cart_item = Cart(user_salon_id=link.id, product_id=product_id, quantity=1)
        session.add(cart_item)
    await session.commit()

    result = await session.execute(
        select(Cart)
        .where(Cart.user_salon_id == link.id)
        .options(selectinload(Cart.product))
    )
    items = result.scalars().all()
    total = sum(i.product.price * i.quantity for i in items)
    count = sum(i.quantity for i in items)

    return templates.TemplateResponse(
        "_cart_body.html",
        {
            "request": request,
            "items": items,
            "total": total,
            "salon_slug": salon_slug,
            "cart_count": count,
        },
    )


@router.post("/{salon_slug}/cart/decrease/{product_id}")
async def decrease_cart_item(
    request: Request,
    salon_slug: str,
    product_id: int,
    session: AsyncSession = Depends(get_session),
):
    user_salon_id = request.cookies.get("user_salon_id")
    if not user_salon_id:
        raise HTTPException(401, "User not identified")

    salon = await orm_get_salon_by_slug(session, salon_slug)
    if not salon:
        raise HTTPException(status_code=404, detail="Salon not found")

    link = await session.get(UserSalon, int(user_salon_id))
    if not link or link.salon_id != salon.id:
        raise HTTPException(403, "Access forbidden")

    product = await orm_get_product(session, product_id, salon.id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    cart_item = await session.execute(
        select(Cart).where(Cart.user_salon_id == link.id, Cart.product_id == product_id)
    )
    cart_item = cart_item.scalars().first()
    if cart_item:
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
        else:
            await session.delete(cart_item)
        await session.commit()

    result = await session.execute(
        select(Cart)
        .where(Cart.user_salon_id == link.id)
        .options(selectinload(Cart.product))
    )
    items = result.scalars().all()
    total = sum(i.product.price * i.quantity for i in items)
    count = sum(i.quantity for i in items)

    return templates.TemplateResponse(
        "_cart_body.html",
        {
            "request": request,
            "items": items,
            "total": total,
            "salon_slug": salon_slug,
            "cart_count": count,
        },
    )




