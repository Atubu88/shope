from aiogram import F, types, Router
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from utils.i18n import _, i18n  # ✅ единый i18n и gettext
from common.bot_cmds_list import set_commands
from database.models import User, UserSalon
from database.orm_query import (
    orm_add_to_cart,
    orm_add_user,
    orm_get_user_salons,
    orm_get_product,
    orm_get_products,
    orm_get_user,
    orm_set_user_language,
)
from database.repositories import SalonRepository

from filters.chat_types import ChatTypeFilter
from handlers.invite_creation import InviteFilter
from handlers.menu_processing import get_menu_content, products
from kbds.inline import MenuCallBack, SalonCallBack, get_salon_btns


user_private_router = Router()
user_private_router.message.filter(ChatTypeFilter(["private"]))


def extract_start_param(text: str | None) -> str | None:
    """Извлекает payload из команды ``/start``.

    Поддерживает оба формата Telegram:

    * ``/start payload`` (классический вариант по пробелу)
    * ``/start=payload`` (payload слитно через знак ``=``)
    """

    if not text:
        return None

    stripped = text.strip()
    if not stripped.startswith("/start"):
        return None

    command_part, _space, payload = stripped.partition(" ")
    if payload:
        return payload.strip() or None

    if "=" in command_part:
        _prefix, _eq, inline_payload = command_part.partition("=")
        return inline_payload or None

    return None


@user_private_router.message(Command("language"))
async def cmd_language(message: types.Message, session: AsyncSession):
    """
    Выбор языка. Локаль подтягивается из БД и выставляется на время апдейта,
    чтобы кнопки и текст сразу были на нужном языке.
    """
    # 1) подтянем язык пользователя из БД
    lang = await session.scalar(
        select(User.language).where(User.user_id == message.from_user.id)
    )
    if lang:
        # 2) выставим локаль на этот апдейт
        i18n.ctx_locale.set(lang)

    # 3) теперь строки переведутся правильно
    kb = InlineKeyboardBuilder()
    kb.button(text=_("Русский"), callback_data="setlang_ru")
    kb.button(text=_("English"), callback_data="setlang_en")
    kb.adjust(2)

    await message.answer(_("Выберите язык"), reply_markup=kb.as_markup())


@user_private_router.callback_query(StateFilter(None), F.data.startswith("setlang_"))
async def set_language(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    lang = callback.data.split("_", 1)[1]
    await orm_set_user_language(session, callback.from_user.id, lang)
    i18n.ctx_locale.set(lang)
    await callback.message.edit_text(_("Язык обновлён"))
    await callback.answer()
    start_message = callback.message.model_copy(
        update={"from_user": callback.from_user, "text": "/start"}
    )
    await start_cmd(start_message, state, session)



@user_private_router.message(CommandStart(), ~InviteFilter())
async def start_cmd(message: types.Message, state: FSMContext, session: AsyncSession):
    await state.clear()
    param = extract_start_param(message.text)
    user_id = message.from_user.id

    repo = SalonRepository(session)
    # создаём пользователя, если его ещё нет
    result = await session.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            user_id=user_id,
            language=message.from_user.language_code or "ru",
        )
        session.add(user)
        await session.commit()

    # подтянем запись с правами/языком
    user_record = await orm_get_user(session, user_id)
    if user_record and user_record.user and user_record.user.language:
        i18n.ctx_locale.set(user_record.user.language)

    # команды бота с учётом ролей
    is_admin = bool(user_record and (user_record.is_super_admin or user_record.is_salon_admin))
    await set_commands(message.bot, user_id, is_admin)

    # если салонов нет
    salons = await repo.list()
    if not salons:
        if user.id == 1:
            user.is_super_admin = True
            await session.commit()
            await message.answer(
                _("✅ Вы стали суперадмином.\nСоздайте первый салон командой /create_salon")
            )
        else:
            await message.answer(_("Салонов пока нет. Обратитесь к администратору."))
        return

    # пробуем определить салон по параметру /start
    salon = None
    if param:
        if "-" in param:
            slug, _suffix = param.rsplit("-", 1)
            salon = await repo.get_by_slug(slug)
        elif param.isdigit():
            salon = await repo.get_by_id(int(param))
        else:
            salon = await repo.get_by_slug(param)

    # если салон определён — привяжем пользователя и зайдём в меню
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
            _("Вы находитесь в салоне: <b>{name}</b>").format(name=salon.name),
            parse_mode="HTML",
        )
        media, reply_markup = await get_menu_content(
            session, level=0, menu_name="main", user_salon_id=user_salon.id
        )
        await message.answer_photo(media.media, caption=media.caption, reply_markup=reply_markup)
        return

    # ➜ показываем только те салоны, к которым пользователь уже привязан
    user_salons = await orm_get_user_salons(session, user_id)

    # 0 салонов — сообщаем, что доступа пока нет
    if not user_salons:
        await message.answer(
            _(
                "У вас пока нет салонов. Попросите администратора прислать пригласительную ссылку или создайте собственный салон по инвайту."
            )
        )
        return

    # 1 салон — сразу заходим в него
    if len(user_salons) == 1:
        us = user_salons[0]
        await state.update_data(user_salon_id=us.id)
        await message.answer(
            _("Вы находитесь в салоне: <b>{name}</b>").format(name=us.salon.name),
            parse_mode="HTML",
        )
        media, reply_markup = await get_menu_content(
            session, level=0, menu_name="main", user_salon_id=us.id
        )
        await message.answer_photo(media.media, caption=media.caption, reply_markup=reply_markup)
        return

    # >1 салонов — даём пользователю выбрать среди своих
    await message.answer(
        _("Выберите салон:"),
        reply_markup=get_salon_btns([us.salon for us in user_salons]),
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
        await callback.answer(_("Салон не выбран."))
        return

    await orm_add_to_cart(
        session,
        user_salon_id=user_salon_id,
        product_id=callback_data.product_id,
    )
    await callback.answer(_("Товар добавлен в корзину."))


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

    # выставим язык пользователя, если он есть
    if user_salon.user and user_salon.user.language:
        i18n.ctx_locale.set(user_salon.user.language)

    media, reply_markup = await get_menu_content(
        session,
        level=0,
        menu_name="main",
        user_salon_id=user_salon.id,
    )
    await callback.message.edit_text(_("Салон выбран"))
    await callback.message.answer_photo(media.media, caption=media.caption, reply_markup=reply_markup)

@user_private_router.callback_query(MenuCallBack.filter())
async def user_menu(
    callback: types.CallbackQuery,
    callback_data: MenuCallBack,
    session: AsyncSession,
    state: FSMContext,
):
    # 🧩 Приводим типы
    level = int(callback_data.level) if callback_data.level is not None else None
    menu_name = str(callback_data.menu_name or "")

    # 🛒 Добавление в корзину
    if menu_name == "add_to_cart":
        await add_to_cart(callback, callback_data, session, state)
        return

    # 🔐 Проверяем user_salon_id
    data = await state.get_data()
    user_salon_id = data.get("user_salon_id")
    if not user_salon_id:
        await callback.answer(_("Салон не выбран. Перезапустите бота командой /start."))
        return

    # 📦 Получаем контент
    media, reply_markup = await get_menu_content(
        session,
        level=level,
        menu_name=menu_name,
        category=callback_data.category,
        page=callback_data.page,
        product_id=callback_data.product_id,
        user_salon_id=user_salon_id,
    )

    # 🖼️ Если пришёл объект InputMediaPhoto (карточка или список товаров) → редактируем медиа
    if isinstance(media, InputMediaPhoto):
        try:
            await callback.message.edit_media(media=media, reply_markup=reply_markup)
        except Exception as e:
            print(f"[edit_media error]: {e}")
        await callback.answer()
        return

    # 📝 Иначе (просто текст или подпись) → редактируем подпись/текст
    try:
        await callback.message.edit_caption(caption=media, reply_markup=reply_markup)
    except Exception:
        try:
            await callback.message.edit_text(text=media, reply_markup=reply_markup)
        except Exception as e:
            print(f"[edit_text error]: {e}")

    await callback.answer()

@user_private_router.message(F.text.startswith("/product_"))
async def show_product(message: Message, session: AsyncSession, state: FSMContext):
    try:
        product_id = int(message.text.split("_")[1])

        data = await state.get_data()
        user_salon_id = data.get("user_salon_id")
        if not user_salon_id:
            await message.answer(_("Салон не выбран. Перезапустите /start."))
            return

        user_salon = await session.get(UserSalon, user_salon_id)
        if not user_salon:
            await message.answer(_("Салон не найден. Перезапустите /start."))
            return

        salon_id = user_salon.salon_id

        product = await orm_get_product(session, product_id, salon_id=salon_id)
        if not product:
            await message.answer(_("Товар не найден!"))
            return

        products_in_cat = await orm_get_products(
            session, category_id=product.category_id, salon_id=salon_id
        )
        product_ids = [p.id for p in products_in_cat]
        if product_id not in product_ids:
            await message.answer(_("Товар не найден в этой категории!"))
            return

        idx = product_ids.index(product_id)
        page = idx + 1

        image, kbds = await products(
            session,
            level=2,
            menu_name="product_detail",
            category=product.category_id,
            page=page,
            product_id=product.id,
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
        await message.answer(_("Ошибка при загрузке товара."))