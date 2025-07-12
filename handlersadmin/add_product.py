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

from database.orm_query import orm_add_product, orm_get_categories
from .menu import show_admin_menu

add_product_router = Router()


class AddProductFSM(StatesGroup):
    category = State()
    name = State()
    description = State()
    price = State()
    photo = State()  # deprecated name kept for state logic
    # store photo file_id under "image" key in FSM data
    confirm = State()


def exit_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Выйти", callback_data="add_prod_exit")]]
    )


def back_exit_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="add_prod_back")],
            [InlineKeyboardButton(text="Выйти", callback_data="add_prod_exit")],
        ]
    )


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Подтвердить", callback_data="add_prod_confirm")],
            [InlineKeyboardButton(text="Назад", callback_data="add_prod_back")],
            [InlineKeyboardButton(text="Выйти", callback_data="add_prod_exit")],
        ]
    )


def category_kb(categories) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=c.name, callback_data=f"add_cat_{c.id}")]
               for c in categories]
    buttons.append([InlineKeyboardButton(text="Выйти", callback_data="add_prod_exit")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@add_product_router.callback_query(F.data == "admin_add_product")
async def start_add(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    data = await state.get_data()
    message_id = data.get("main_message_id") or callback.message.message_id
    await state.update_data(main_message_id=message_id)
    categories = await orm_get_categories(session, 1)
    await state.set_state(AddProductFSM.category)
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=message_id,
        text="Выберите категорию:",
        reply_markup=category_kb(categories),
    )
    await callback.answer()


@add_product_router.callback_query(AddProductFSM.category, F.data.startswith("add_cat_"))
async def choose_category(callback: CallbackQuery, state: FSMContext) -> None:
    category_id = int(callback.data.split("_")[-1])
    await state.update_data(category=category_id)
    data = await state.get_data()
    await state.set_state(AddProductFSM.name)
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=data["main_message_id"],
        text="Введите название товара:",
        reply_markup=back_exit_kb(),
    )
    await callback.answer()


@add_product_router.message(AddProductFSM.category)
async def invalid_category(message: Message) -> None:
    await message.answer("Выберите категорию кнопкой ниже.")


@add_product_router.message(AddProductFSM.name, F.text)
async def process_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not name:
        await message.answer("Название не может быть пустым.")
        return
    await state.update_data(name=name)
    data = await state.get_data()
    await state.set_state(AddProductFSM.description)
    await message.bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=data["main_message_id"],
        text="Введите описание товара:",
        reply_markup=back_exit_kb(),
    )
    await message.delete()


@add_product_router.message(AddProductFSM.name)
async def invalid_name(message: Message) -> None:
    await message.answer("Отправьте название текстом.")


@add_product_router.message(AddProductFSM.description, F.text)
async def process_description(message: Message, state: FSMContext) -> None:
    desc = message.text.strip()
    if not desc:
        await message.answer("Описание не может быть пустым.")
        return
    await state.update_data(description=desc)
    data = await state.get_data()
    await state.set_state(AddProductFSM.price)
    await message.bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=data["main_message_id"],
        text="Введите цену товара:",
        reply_markup=back_exit_kb(),
    )
    await message.delete()


@add_product_router.message(AddProductFSM.description)
async def invalid_description(message: Message) -> None:
    await message.answer("Отправьте описание текстом.")


@add_product_router.message(AddProductFSM.price, F.text)
async def process_price(message: Message, state: FSMContext) -> None:
    text = message.text.replace(",", ".").strip()
    try:
        price = float(text)
    except ValueError:
        await message.answer("Введите корректную цену.")
        return
    await state.update_data(price=price)
    data = await state.get_data()
    await state.set_state(AddProductFSM.photo)
    await message.bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=data["main_message_id"],
        text="Отправьте фото товара:",
        reply_markup=back_exit_kb(),
    )
    await message.delete()


@add_product_router.message(AddProductFSM.price)
async def invalid_price(message: Message) -> None:
    await message.answer("Введите цену числом.")


@add_product_router.message(AddProductFSM.photo, F.photo)
async def process_photo(message: Message, state: FSMContext) -> None:
    photo_id = message.photo[-1].file_id
    await state.update_data(image=photo_id)
    data = await state.get_data()
    caption = (
        f"<b>{data['name']}</b>\n{data['description']}\nЦена: {data['price']}"
    )
    await state.set_state(AddProductFSM.confirm)
    await message.bot.edit_message_media(
        chat_id=message.chat.id,
        message_id=data["main_message_id"],
        media=InputMediaPhoto(media=photo_id, caption=caption),
        reply_markup=confirm_kb(),
    )
    await message.delete()


@add_product_router.message(AddProductFSM.photo)
async def invalid_photo(message: Message) -> None:
    await message.answer("Пришлите фотографию товара.")


@add_product_router.callback_query(AddProductFSM.confirm, F.data == "add_prod_confirm")
async def confirm_product(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    data = await state.get_data()
    message_id = data["main_message_id"]
    await orm_add_product(session, data, 1)
    await state.clear()
    await state.update_data(main_message_id=message_id)
    await callback.bot.edit_message_caption(
        chat_id=callback.message.chat.id,
        message_id=message_id,
        caption="Товар добавлен",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="В меню", callback_data="admin_menu")]]
        ),
    )
    await callback.answer()


@add_product_router.callback_query(F.data == "add_prod_exit")
async def exit_to_menu(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    message_id = data.get("main_message_id") or callback.message.message_id
    await state.clear()
    await state.update_data(main_message_id=message_id)
    await show_admin_menu(state, callback.message.chat.id, callback.bot)
    await callback.answer()


@add_product_router.callback_query(F.data == "add_prod_back")
async def go_back(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    data = await state.get_data()
    current = await state.get_state()
    message_id = data["main_message_id"]

    if current == AddProductFSM.name.state:
        await state.set_state(AddProductFSM.category)
        categories = await orm_get_categories(session, 1)
        await callback.bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=message_id,
            text="Выберите категорию:",
            reply_markup=category_kb(categories),
        )
    elif current == AddProductFSM.description.state:
        await state.set_state(AddProductFSM.name)
        text = "Введите название товара:"
        if data.get("name"):
            text += f"\nТекущее значение: {data['name']}"
        kb = back_exit_kb()
        await callback.bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=message_id,
            text=text,
            reply_markup=kb,
        )
    elif current == AddProductFSM.price.state:
        await state.set_state(AddProductFSM.description)
        text = "Введите описание товара:"
        if data.get("description"):
            text += f"\nТекущее значение: {data['description']}"
        await callback.bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=message_id,
            text=text,
            reply_markup=back_exit_kb(),
        )
    elif current == AddProductFSM.photo.state:
        await state.set_state(AddProductFSM.price)
        text = "Введите цену товара:"
        if data.get("price"):
            text += f"\nТекущее значение: {data['price']}"
        await callback.bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=message_id,
            text=text,
            reply_markup=back_exit_kb(),
        )
    elif current == AddProductFSM.confirm.state:
        await state.set_state(AddProductFSM.photo)
        caption = "Отправьте фото товара:"
        if data.get("image"):
            await callback.bot.edit_message_media(
                chat_id=callback.message.chat.id,
                message_id=message_id,
                media=InputMediaPhoto(media=data["image"], caption=caption),
                reply_markup=back_exit_kb(),
            )
        else:
            await callback.bot.edit_message_text(
                chat_id=callback.message.chat.id,
                message_id=message_id,
                text=caption,
                reply_markup=back_exit_kb(),
            )
    await callback.answer()
