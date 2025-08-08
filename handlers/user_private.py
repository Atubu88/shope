from aiogram import F, types, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Salon, User, UserSalon
from database.orm_query import (
    orm_add_to_cart,
    orm_add_user,
    orm_get_salons,
    orm_get_user_salons,
    orm_get_salon_by_slug,
    orm_get_product,
    orm_get_products,
)

from filters.chat_types import ChatTypeFilter
from handlers.invite_creation import InviteFilter
from handlers.menu_processing import get_menu_content, products
from kbds.inline import MenuCallBack, get_callback_btns, SalonCallBack, get_salon_btns



user_private_router = Router()
user_private_router.message.filter(ChatTypeFilter(["private"]))


@user_private_router.message(CommandStart())
@user_private_router.message(CommandStart(), ~InviteFilter())
async def start_cmd(message: types.Message, state: FSMContext, session: AsyncSession):
    await state.clear()

    args = message.text.split()
    param = args[1] if len(args) > 1 else None
    user_id = message.from_user.id

    result = await session.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(user_id=user_id)
        session.add(user)
        await session.commit()

    salons = await orm_get_salons(session)
    if not salons:
        if user.id == 1:
            user.is_super_admin = True
            await session.commit()
            await message.answer(
                "✅ Вы стали суперадмином.\nСоздайте первый салон командой /create_salon"
            )
        else:
            await message.answer("Салонов пока нет. Обратитесь к администратору.")
        return

    salon = None
    if param:
        if "-" in param:
            slug, _ = param.rsplit("-", 1)
            salon = await orm_get_salon_by_slug(session, slug)
        elif param.isdigit():
            salon = await session.get(Salon, int(param))
        else:
            salon = await orm_get_salon_by_slug(session, param)

    if salon:
        user_salon = await orm_add_user(
            session,
            user_id=user_id,
            salon_id=salon.id,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )
        await state.update_data(user_salon_id=user_salon.id)
        await message.answer(
            f"Вы находитесь в салоне: <b>{salon.name}</b>", parse_mode="HTML"
        )
        media, reply_markup = await get_menu_content(
            session, level=0, menu_name="main", user_salon_id=user_salon.id
        )
        await message.answer_photo(media.media, caption=media.caption, reply_markup=reply_markup)
        return

    # ➜ Показываем только те салоны, к которым пользователь уже привязан
    user_salons = await orm_get_user_salons(session, user_id)

    # --- 0 салонов — сообщаем, что доступа пока нет ---------------------------
    if not user_salons:
        await message.answer(
            "У вас пока нет салонов. "
            "Попросите администратора прислать пригласительную ссылку "
            "или создайте собственный салон по инвайту."
        )
        return

    # --- 1 салон — сразу заходим в него ---------------------------------------
    if len(user_salons) == 1:
        us = user_salons[0]
        await state.update_data(user_salon_id=us.id)
        await message.answer(
            f"Вы находитесь в салоне: <b>{us.salon.name}</b>", parse_mode="HTML"
        )
        media, reply_markup = await get_menu_content(
            session, level=0, menu_name="main", user_salon_id=us.id
        )
        await message.answer_photo(media.media, caption=media.caption, reply_markup=reply_markup)
        return

    # --- >1 салонов — даём пользователю выбрать среди своих -------------------
    await message.answer(
        "Выберите салон:",
        reply_markup=get_salon_btns([us.salon for us in user_salons])
    )


async def add_to_cart(
    callback: types.CallbackQuery,
    callback_data: MenuCallBack,
    session: AsyncSession,
    state: FSMContext,
):
    data = await state.get_data()
    user_salon_id = data.get("user_salon_id")
    if not user_salon_id:
        await callback.answer("Салон не выбран.")
        return
    await orm_add_to_cart(
        session,
        user_salon_id=user_salon_id,
        product_id=callback_data.product_id,
    )
    await callback.answer("Товар добавлен в корзину.")


@user_private_router.callback_query(SalonCallBack.filter())
async def choose_salon(
    callback: types.CallbackQuery,
    callback_data: SalonCallBack,
    session: AsyncSession,
    state: FSMContext,
):
    user_salon = await orm_add_user(
        session,
        user_id=callback.from_user.id,
        salon_id=callback_data.salon_id,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name,
    )
    await state.update_data(user_salon_id=user_salon.id)
    media, reply_markup = await get_menu_content(
        session,
        level=0,
        menu_name="main",
        user_salon_id=user_salon.id,
    )
    await callback.message.edit_text("Салон выбран")
    await callback.message.answer_photo(media.media, caption=media.caption, reply_markup=reply_markup)


@user_private_router.callback_query(MenuCallBack.filter())
async def user_menu(
    callback: types.CallbackQuery,
    callback_data: MenuCallBack,
    session: AsyncSession,
    state: FSMContext,
):

    if callback_data.menu_name == "add_to_cart":
        await add_to_cart(callback, callback_data, session, state)
        return

    data = await state.get_data()
    user_salon_id = data.get("user_salon_id")

    media, reply_markup = await get_menu_content(
        session,
        level=callback_data.level,
        menu_name=callback_data.menu_name,
        category=callback_data.category,
        page=callback_data.page,
        product_id=callback_data.product_id,
        user_salon_id=user_salon_id,
    )

    await callback.message.edit_media(media=media, reply_markup=reply_markup)
    await callback.answer()


@user_private_router.message(F.text.startswith("/product_"))
async def show_product(message: Message, session: AsyncSession, state: FSMContext):
    try:
        product_id = int(message.text.split("_")[1])
        data = await state.get_data()
        user_salon_id = data.get("user_salon_id")
        if not user_salon_id:
            await message.answer("Салон не выбран. Перезапустите /start.")
            return

        user_salon = await session.get(UserSalon, user_salon_id)
        if not user_salon:
            await message.answer("Салон не найден. Перезапустите /start.")
            return

        salon_id = user_salon.salon_id

        product = await orm_get_product(session, product_id, salon_id=salon_id)
        if not product:
            await message.answer("Товар не найден!")
            return

        products_in_cat = await orm_get_products(
            session, category_id=product.category_id, salon_id=salon_id
        )
        product_ids = [p.id for p in products_in_cat]
        if product_id not in product_ids:
            await message.answer("Товар не найден в этой категории!")
            return

        idx = product_ids.index(product_id)
        page = idx + 1

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
            parse_mode="HTML",
        )

    except Exception as e:
        print(f"[show_product] Ошибка: {e}")
        await message.answer("Ошибка при загрузке товара.")

