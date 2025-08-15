from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    InputMediaPhoto,
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query import orm_change_banner_image, orm_get_info_pages, init_default_salon_content
from .menu import show_admin_menu

banner_router = Router()


class BannerFSM(StatesGroup):
    page = State()
    photo = State()


def banner_kb(pages) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=p.name, callback_data=f"banner_page_{p.name}")]
        for p in pages
    ]
    buttons.append([InlineKeyboardButton(text="Выйти", callback_data="banner_exit")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@banner_router.callback_query(F.data == "admin_banners")
async def start_banner(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    old_data = await state.get_data()
    salon_id = old_data.get("salon_id")
    message_id = old_data.get("main_message_id") or callback.message.message_id
    await state.clear()

    # Если salon_id отсутствует, сообщаем об ошибке и возвращаем в меню
    if salon_id is None:
        await state.update_data(main_message_id=message_id)
        await callback.answer("Не указан салон", show_alert=True)
        await show_admin_menu(state, callback.message.chat.id, callback.bot, session)
        return

    await state.update_data(main_message_id=message_id, salon_id=salon_id)

    pages = await orm_get_info_pages(session, salon_id)
    if not pages:
        await init_default_salon_content(session, salon_id)
        pages = await orm_get_info_pages(session, salon_id)

    await state.set_state(BannerFSM.page)
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=message_id,
        text="Выберите страницу баннера:",
        reply_markup=banner_kb(pages),
    )
    await callback.answer()


@banner_router.callback_query(BannerFSM.page, F.data.startswith("banner_page_"))
async def choose_page(callback: CallbackQuery, state: FSMContext) -> None:
    page = callback.data.split("_")[-1]
    await state.update_data(page=page)
    data = await state.get_data()
    await state.set_state(BannerFSM.photo)
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=data["main_message_id"],
        text="Загрузите фото баннера:",
    )
    await callback.answer()


@banner_router.message(BannerFSM.page)
async def invalid_page(message: Message) -> None:
    await message.answer("Выберите страницу кнопкой ниже.")


from utils.supabase_storage import upload_photo_from_telegram

@banner_router.message(BannerFSM.photo, F.photo)
async def process_photo(message: Message, state: FSMContext, session: AsyncSession) -> None:
    photo_id = message.photo[-1].file_id
    # 1. Скачай и загрузи фото в Supabase, получи public_url
    photo_url = await upload_photo_from_telegram(message.bot, photo_id)
    # 2. Сохрани ссылку в БД
    data = await state.get_data()
    salon_id = data.get("salon_id")
    page = data.get("page")
    await orm_change_banner_image(session, page, photo_url, salon_id)
    await state.clear()
    await state.update_data(main_message_id=data["main_message_id"])
    await message.bot.edit_message_media(
        chat_id=message.chat.id,
        message_id=data["main_message_id"],
        media=InputMediaPhoto(media=photo_url, caption="Баннер обновлён."),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="В меню", callback_data="admin_menu")]]
        ),
    )
    await message.delete()


@banner_router.message(BannerFSM.photo)
async def invalid_photo(message: Message) -> None:
    await message.answer("Пришлите фотографию баннера.")


@banner_router.callback_query(F.data == "banner_exit")
async def exit_to_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    message_id = data.get("main_message_id") or callback.message.message_id
    await state.clear()
    await state.update_data(main_message_id=message_id)
    await show_admin_menu(state, callback.message.chat.id, callback.bot, session)
    await callback.answer()


@banner_router.callback_query(BannerFSM.page, F.data == "banner_exit")
async def exit_from_page(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    message_id = data.get("main_message_id") or callback.message.message_id
    await state.clear()
    await state.update_data(main_message_id=message_id)
    await show_admin_menu(state, callback.message.chat.id, callback.bot, session)
    await callback.answer()