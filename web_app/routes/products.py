from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query import orm_get_category, orm_get_product, orm_get_salon_by_slug

from ..web_main import get_cart_count, get_session, templates

router = APIRouter()


@router.get("/{salon_slug}/product/{product_id}", response_class=HTMLResponse)
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

    cart_count = await get_cart_count(session, request.cookies.get("user_salon_id"))

    context = {
        "request": request,
        "product": product,
        "category": category,
        "salon_slug": salon.slug,
        "cart_count": cart_count,
    }
    return templates.TemplateResponse("product_detail.html", context)
