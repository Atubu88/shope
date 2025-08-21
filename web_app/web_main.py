# web_app/main.py
from fastapi import FastAPI, Depends, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database.engine import session_maker           # общий async sessionmaker
from database.orm_query import orm_get_categories, orm_get_products  # твои ORM-функции

app = FastAPI()
templates = Jinja2Templates(directory="web_app/templates")

async def get_session() -> AsyncSession:
    async with session_maker() as session:
        yield session

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, session: AsyncSession = Depends(get_session)):
    salon_id = 1
    categories = await orm_get_categories(session, salon_id=salon_id)
    first_cat_id = categories[0].id if categories else None
    products = await orm_get_products(session, category_id=first_cat_id, salon_id=salon_id) if first_cat_id else []
    return templates.TemplateResponse("index.html", {
        "request": request,
        "categories": categories,
        "products": products,
        "current_cat": first_cat_id
    })

@app.get("/category/{cat_id}", response_class=HTMLResponse)
async def load_category(request: Request, cat_id: int, session: AsyncSession = Depends(get_session)):
    salon_id = 1
    products = await orm_get_products(session, category_id=cat_id, salon_id=salon_id)
    return templates.TemplateResponse("products_list.html", {"request": request, "products": products})
