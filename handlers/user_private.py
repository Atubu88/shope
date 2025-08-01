from aiogram import F, types, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Salon
from database.orm_query import (
    orm_add_to_cart,
    orm_add_user,
    orm_get_salons,
    orm_get_user,
    orm_get_salon_by_slug, orm_get_product, orm_get_products,
)

from filters.chat_types import ChatTypeFilter
from handlers.menu_processing import get_menu_content, products
from kbds.inline import MenuCallBack, get_callback_btns, SalonCallBack, get_salon_btns



user_private_router = Router()
user_private_router.message.filter(ChatTypeFilter(["private"]))


@user_private_router.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext, session: AsyncSession):
    await state.clear()

    args = message.text.split()
    param = args[1] if len(args) > 1 else None
    salon_id = None
    salon_name = None

    # 1. Получаем салон из параметра, если есть
    if param:
        if "-" in param:
            slug, _ = param.rsplit("-", 1)
            salon = await orm_get_salon_by_slug(session, slug)
        elif param.isdigit():
            salon = await session.get(Salon, int(param))
        else:
            salon = await orm_get_salon_by_slug(session, param)

        if salon:
            salon_id = salon.id
            salon_name = salon.name

    # 2. Проверяем пользователя
    user = await orm_get_user(session, message.from_user.id)
    if not user:
        user = await orm_add_user(
            session,
            user_id=message.from_user.id,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )

    # 3. Если салонов нет
    salons = await orm_get_salons(session)
    if not salons:
        if user.id == 1:
            await orm_add_user(session, user_id=user.user_id, is_super_admin=True)
            await message.answer(
                "✅ Вы стали суперадмином.\nСоздайте первый салон командой /create_salon"
            )
        else:
            await message.answer("Салонов пока нет. Обратитесь к администратору.")
        return

    # 4. Если салон не выбран и не закреплён
    if salon_id is None:
        if user.salon_id:
            salon_id = user.salon_id
            salon = await session.get(Salon, salon_id)
            if salon:
                salon_name = salon.name
        else:
            await message.answer("Выберите салон:", reply_markup=get_salon_btns(salons))
            return

    # 5. Обновляем пользователя (привязываем к салону)
    await orm_add_user(
        session,
        user_id=user.user_id,
        salon_id=salon_id,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
    )

    # 6. Сообщаем выбранный салон
    if salon_name:
        await message.answer(f"Вы находитесь в салоне: <b>{salon_name}</b>", parse_mode="HTML")

    media, reply_markup = await get_menu_content(session, level=0, menu_name="main", user_id=user.user_id)
    await message.answer_photo(media.media, caption=media.caption, reply_markup=reply_markup)


async def add_to_cart(callback: types.CallbackQuery, callback_data: MenuCallBack, session: AsyncSession):
    user = callback.from_user
    await orm_add_user(
        session,
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=None,
        salon_id=(await orm_get_user(session, user.id)).salon_id if await orm_get_user(session, user.id) else None,
    )
    user_db = await orm_get_user(session, user.id)
    salon_id = user_db.salon_id if user_db else None
    await orm_add_to_cart(session, user_id=user.id, product_id=callback_data.product_id, salon_id=salon_id)
    await callback.answer("Товар добавлен в корзину.")


@user_private_router.callback_query(SalonCallBack.filter())
async def choose_salon(callback: types.CallbackQuery, callback_data: SalonCallBack, session: AsyncSession):
    await orm_add_user(
        session,
        user_id=callback.from_user.id,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name,
        phone=None,
        salon_id=callback_data.salon_id,
    )
    media, reply_markup = await get_menu_content(
        session,
        level=0,
        menu_name="main",
        user_id=callback.from_user.id,
    )
    await callback.message.edit_text("Салон выбран")
    await callback.message.answer_photo(media.media, caption=media.caption, reply_markup=reply_markup)


@user_private_router.callback_query(MenuCallBack.filter())
async def user_menu(callback: types.CallbackQuery, callback_data: MenuCallBack, session: AsyncSession):

    if callback_data.menu_name == "add_to_cart":
        await add_to_cart(callback, callback_data, session)
        return

    media, reply_markup = await get_menu_content(
        session,
        level=callback_data.level,
        menu_name=callback_data.menu_name,
        category=callback_data.category,
        page=callback_data.page,
        product_id=callback_data.product_id,
        user_id=callback.from_user.id,
    )

    await callback.message.edit_media(media=media, reply_markup=reply_markup)
    await callback.answer()


@user_private_router.message(F.text.startswith("/product_"))
async def show_product(message: Message, session: AsyncSession):
    try:
        product_id = int(message.text.split("_")[1])
        user = await orm_get_user(session, message.from_user.id)
        salon_id = user.salon_id if user else None

        if not salon_id:
            await message.answer("Салон не выбран. Перезапустите /start.")
            return

        # Получаем сам товар
        product = await orm_get_product(session, product_id, salon_id=salon_id)
        if not product:
            await message.answer("Товар не найден!")
            return

        # Получаем все товары в категории для этого салона
        products_in_cat = await orm_get_products(session, category_id=product.category_id, salon_id=salon_id)
        # Находим индекс выбранного товара
        product_ids = [p.id for p in products_in_cat]
        if product_id not in product_ids:
            await message.answer("Товар не найден в этой категории!")
            return

        idx = product_ids.index(product_id)
        # Определяем номер страницы, где находится этот товар (если у тебя на странице 1 товар)
        page = idx + 1  # если один товар на страницу (иначе дели на размер страницы и округляй вверх)

        # Показываем страницу с нужным товаром и актуальной пагинацией
        image, kbds = await products(
            session,
            level=2,
            category=product.category_id,
            page=page,
            salon_id=salon_id,
        )

        await message.answer_photo(
            image.media,
            caption=image.caption,
            reply_markup=kbds,
            parse_mode="HTML"
        )

    except Exception as e:
        print(f"[show_product] Ошибка: {e}")
        await message.answer("Ошибка при загрузке товара.")


