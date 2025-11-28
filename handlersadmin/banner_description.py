from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query import orm_change_banner_description, orm_get_info_pages
from .menu import show_admin_menu

banner_text_router = Router()


class BannerTextFSM(StatesGroup):
    page = State()
    text = State()


def banner_text_kb(pages) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=p.name, callback_data=f"banner_text_page_{p.name}")]
        for p in pages
    ]
    buttons.append([InlineKeyboardButton(text="Выйти", callback_data="banner_text_exit")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@banner_text_router.callback_query(F.data == "admin_banner_text")
async def start_banner_text(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    old_data = await state.get_data()
    salon_id = old_data.get("salon_id")
    message_id = old_data.get("main_message_id") or callback.message.message_id
    await state.clear()
    await state.update_data(main_message_id=message_id, salon_id=salon_id)
    pages = await orm_get_info_pages(session, salon_id)
    await state.set_state(BannerTextFSM.page)
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=message_id,
        text="Выберите страницу баннера:",
        reply_markup=banner_text_kb(pages),
    )
    await callback.answer()


@banner_text_router.callback_query(BannerTextFSM.page, F.data.startswith("banner_text_page_"))
async def choose_page(callback: CallbackQuery, state: FSMContext) -> None:
    page = callback.data.split("_")[-1]
    await state.update_data(page=page)
    data = await state.get_data()
    await state.set_state(BannerTextFSM.text)
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=data["main_message_id"],
        text="Введите описание баннера:",
        parse_mode="HTML"
    )
    await callback.answer()


@banner_text_router.message(BannerTextFSM.page)
async def invalid_page(message: Message) -> None:
    await message.answer("Выберите страницу кнопкой ниже.")


@banner_text_router.message(BannerTextFSM.text, F.text)
async def process_text(message: Message, state: FSMContext, session: AsyncSession) -> None:
    desc = message.text.strip()
    data = await state.get_data()
    salon_id = data.get("salon_id")
    page = data.get("page")
    await orm_change_banner_description(session, page, desc, salon_id)
    await state.clear()
    await state.update_data(main_message_id=data["main_message_id"])
    await message.bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=data["main_message_id"],
        text="Описание обновлено.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="В меню", callback_data="admin_menu")]]
        ),
    )
    await message.delete()


@banner_text_router.message(BannerTextFSM.text)
async def invalid_text(message: Message) -> None:
    await message.answer("Введите описание текстом.")


@banner_text_router.callback_query(F.data == "banner_text_exit")
async def exit_to_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    message_id = data.get("main_message_id") or callback.message.message_id
    await state.clear()
    await state.update_data(main_message_id=message_id)
    await show_admin_menu(state, callback.message.chat.id, callback.bot, session)
    await callback.answer()


@banner_text_router.callback_query(BannerTextFSM.page, F.data == "banner_text_exit")
async def exit_from_page(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    message_id = data.get("main_message_id") or callback.message.message_id
    await state.clear()
    await state.update_data(main_message_id=message_id)
    await show_admin_menu(state, callback.message.chat.id, callback.bot, session)
    await callback.answer()