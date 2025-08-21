# web_app/main.py
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database.engine import session_maker           # общий async sessionmaker
from database.orm_query import (
    orm_get_categories,
    orm_get_products,
    orm_get_product,
    orm_get_category,
)  # твои ORM-функции

app = FastAPI()
templates = Jinja2Templates(directory="web_app/templates")

async def get_session() -> AsyncSession:
    async with session_maker() as session:
        yield session

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, cat: int | None = None, session: AsyncSession = Depends(get_session)):
    salon_id = 1
    categories = await orm_get_categories(session, salon_id=salon_id)
    current_cat_id = cat or (categories[0].id if categories else None)
    current_cat_name = None
    if current_cat_id:
        current_cat = next((c for c in categories if c.id == current_cat_id), None)
        current_cat_name = current_cat.name if current_cat else None
    products = await orm_get_products(session, category_id=current_cat_id, salon_id=salon_id) if current_cat_id else []
    return templates.TemplateResponse("index.html", {
        "request": request,
        "categories": categories,
        "products": products,
        "current_cat": current_cat_id,
        "current_cat_name": current_cat_name,
    })

@app.get("/category/{cat_id}", response_class=HTMLResponse)
async def load_category(request: Request, cat_id: int, session: AsyncSession = Depends(get_session)):
    salon_id = 1
    products = await orm_get_products(session, category_id=cat_id, salon_id=salon_id)
    categories = await orm_get_categories(session, salon_id=salon_id)
    category = await orm_get_category(session, category_id=cat_id, salon_id=salon_id)
    return templates.TemplateResponse(
        "catalog_content.html",
        {
            "request": request,
            "products": products,
            "categories": categories,
            "current_cat": cat_id,
            "current_cat_name": category.name if category else None,
        },
    )

@app.get("/product/{product_id}", response_class=HTMLResponse)
async def product_detail(request: Request, product_id: int, session: AsyncSession = Depends(get_session)):
    salon_id = 1
    product = await orm_get_product(session, product_id=product_id, salon_id=salon_id)

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    category = await orm_get_category(session, category_id=product.category_id, salon_id=salon_id)

    return templates.TemplateResponse(
        "product_detail.html",
        {"request": request, "product": product, "category": category},
    )