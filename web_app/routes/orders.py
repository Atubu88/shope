from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import Cart, UserSalon
from database.orm_query import orm_create_order, orm_get_salon_by_slug
from ..web_main import get_session, templates


router = APIRouter()


class CheckoutForm(BaseModel):
    name: str
    phone: str
    email: EmailStr | None = None
    address: str | None = None
    delivery_type: str
    payment_method: str
    comment: str | None = None


@router.get("/{salon_slug}/checkout", response_class=HTMLResponse)
async def checkout_page(
    request: Request,
    salon_slug: str,
    delivery_type: str = "delivery",
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

    result = await session.execute(
        select(Cart)
            .where(Cart.user_salon_id == link.id)
            .options(selectinload(Cart.product))
            .order_by(Cart.id)
    )
    items = result.scalars().all()
    total = sum(i.product.price * i.quantity for i in items)
    cart_count = sum(i.quantity for i in items)

    first = (link.first_name or "").strip()
    last = (link.last_name or "").strip()
    full = f"{first} {last}".strip()
    welcome_name = full or first or last or None

    template = "_checkout_cafe.html" if request.headers.get("HX-Request") else "checkout.html"
    return templates.TemplateResponse(
        template,
        {
            "request": request,
            "salon_slug": salon.slug,
            "salon_name": salon.name,
            "welcome_name": welcome_name,
            "cart_count": cart_count,
            "total": total,
            "delivery_type": delivery_type,
        },
    )


@router.post("/{salon_slug}/checkout", response_class=HTMLResponse)
async def checkout_submit(
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

    result = await session.execute(
        select(Cart)
            .where(Cart.user_salon_id == link.id)
            .options(selectinload(Cart.product))
            .order_by(Cart.id)
    )
    cart_items = result.scalars().all()
    if not cart_items:
        raise HTTPException(400, "Cart is empty")

    form = await request.form()
    data = CheckoutForm(**form)

    await orm_create_order(
        session,
        user_salon_id=link.id,
        name=data.name,
        phone=data.phone,
        email=data.email,
        address=data.address,
        delivery_type=data.delivery_type,
        payment_method=data.payment_method,
        comment=data.comment,
        cart_items=cart_items,
    )

    await session.execute(delete(Cart).where(Cart.user_salon_id == link.id))
    await session.commit()

    token = os.getenv("TOKEN")
    if token:
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    data={"chat_id": link.user_id, "text": "Спасибо за заказ"},
                )
        except Exception:
            pass

    # Close the mini app
    return HTMLResponse("<script>Telegram.WebApp.ready();Telegram.WebApp.close();</script>")

