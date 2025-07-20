from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query import (
    orm_get_categories,
    orm_add_category,
    orm_delete_category,
)


categories_router = Router()

class NewCategoryFSM(StatesGroup):
    name = State()


def categories_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Создать", callback_data="cat_create")],
            [InlineKeyboardButton(text="Удалить", callback_data="cat_delete")],
            [InlineKeyboardButton(text="В меню", callback_data="admin_menu")],
        ]
    )


def del_category_kb(categories) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=c.name, callback_data=f"cat_del_{c.id}")]
        for c in categories
    ]
    buttons.append([InlineKeyboardButton(text="Назад", callback_data="cat_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@categories_router.callback_query(F.data == "admin_categories")
async def open_categories(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    message_id = data.get("main_message_id") or callback.message.message_id
    salon_id = data.get("salon_id")
    await state.clear()
    await state.update_data(main_message_id=message_id, salon_id=salon_id)
    categories = await orm_get_categories(session, salon_id)
    names = ", ".join(c.name for c in categories) if categories else "нет"
    text = f"Категории: {names}"
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=message_id,
        text=text,
        reply_markup=categories_kb(),
    )
    await callback.answer()


@categories_router.callback_query(F.data == "cat_create")
async def cat_create(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_state(NewCategoryFSM.name)
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=data["main_message_id"],
        text="Введите название категории:",
    )
    await callback.answer()


@categories_router.message(NewCategoryFSM.name, F.text)
async def save_new_category(message: Message, state: FSMContext, session: AsyncSession) -> None:
    name = message.text.strip()
    if not name:
        await message.answer("Название не может быть пустым.")
        return
    data = await state.get_data()
    salon_id = data.get("salon_id")
    await orm_add_category(session, name, salon_id)
    await state.clear()
    await state.update_data(main_message_id=data["main_message_id"], salon_id=salon_id)
    categories = await orm_get_categories(session, salon_id)
    names = ", ".join(c.name for c in categories) if categories else "нет"
    await message.bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=data["main_message_id"],
        text=f"Категории: {names}",
        reply_markup=categories_kb(),
    )
    await message.delete()


@categories_router.message(NewCategoryFSM.name)
async def invalid_new_category(message: Message) -> None:
    await message.answer("Отправьте название категории текстом.")


@categories_router.callback_query(F.data == "cat_delete")
async def choose_category(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    salon_id = data.get("salon_id")
    categories = await orm_get_categories(session, salon_id)
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=data["main_message_id"],
        text="Выберите категорию для удаления:",
        reply_markup=del_category_kb(categories),
    )
    await callback.answer()


@categories_router.callback_query(F.data.startswith("cat_del_"))
async def delete_category(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    category_id = int(callback.data.split("_")[-1])
    data = await state.get_data()
    salon_id = data.get("salon_id")
    await orm_delete_category(session, category_id, salon_id)
    categories = await orm_get_categories(session, salon_id)
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=data["main_message_id"],
        text="Категория удалена. Выберите ещё:",
        reply_markup=del_category_kb(categories),
    )
    await callback.answer("Категория удалена", show_alert=True)


@categories_router.callback_query(F.data == "cat_back")
async def back_from_delete(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await open_categories(callback, state, session)
    await callback.answer()