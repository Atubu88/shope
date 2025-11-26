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
from utils.supabase_storage import upload_photo_from_telegram
from database.orm_query import orm_add_product, orm_get_categories
from database.repositories import SalonRepository
from utils.currency import get_currency_symbol
from .menu import show_admin_menu

add_product_router = Router()

class AddProductFSM(StatesGroup):
    category = State()
    name = State()
    description = State()
    price = State()
    photo = State()

def category_kb(categories) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=c.name, callback_data=f"add_cat_{c.id}")]
               for c in categories]
    buttons.append([InlineKeyboardButton(text="Выйти", callback_data="add_prod_exit")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@add_product_router.callback_query(F.data == "admin_add_product")
async def start_add(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    # 1. Сначала достаём salon_id, чтобы не потерять его!
    old_data = await state.get_data()
    salon_id = old_data.get("salon_id")
    message_id = old_data.get("main_message_id") or callback.message.message_id

    # 2. Очищаем состояние
    await state.clear()

    # 3. Восстанавливаем важные данные!
    await state.update_data(main_message_id=message_id, salon_id=salon_id)

    # 4. Дальше всё как раньше
    categories = await orm_get_categories(session, salon_id)
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
        text="Введите название товара:"
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
        text="Введите описание товара:"
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
        text="Введите цену товара:"
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
        text="Отправьте фото товара:"
    )
    await message.delete()

@add_product_router.message(AddProductFSM.price)
async def invalid_price(message: Message) -> None:
    await message.answer("Введите цену числом.")

@add_product_router.message(AddProductFSM.photo, F.photo)
async def process_photo(message: Message, state: FSMContext, session: AsyncSession) -> None:
    photo_id = message.photo[-1].file_id
    photo_url = await upload_photo_from_telegram(message.bot, photo_id)
    await state.update_data(image_file_id=photo_id, image=photo_url)
    data = await state.get_data()
    salon_id = data.get("salon_id")  # <-- снова достаем актуальный salon_id
    repo = SalonRepository(session)
    salon = await repo.get_by_id(salon_id) if salon_id else None
    currency = get_currency_symbol(salon.currency) if salon else "RUB"
    caption = (
        f"<b>{data['name']}</b>\n{data['description']}\nЦена: {data['price']}{currency}"
    )
    await orm_add_product(session, data, salon_id)  # <-- используем правильный salon_id!
    await state.clear()
    await state.update_data(main_message_id=data["main_message_id"])
    await message.bot.edit_message_media(
        chat_id=message.chat.id,
        message_id=data["main_message_id"],
        media=InputMediaPhoto(media=photo_id, caption=caption + "\n\nТовар добавлен."),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="В меню", callback_data="admin_menu")]]
        ),
    )
    await message.delete()

@add_product_router.message(AddProductFSM.photo)
async def invalid_photo(message: Message) -> None:
    await message.answer("Пришлите фотографию товара.")

@add_product_router.callback_query(F.data == "add_prod_exit")
async def exit_to_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    message_id = data.get("main_message_id") or callback.message.message_id
    await state.clear()
    await state.update_data(main_message_id=message_id)
    await show_admin_menu(state, callback.message.chat.id, callback.bot, session)
    await callback.answer()

@add_product_router.callback_query(AddProductFSM.category, F.data == "add_prod_exit")
async def exit_from_category(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    message_id = data.get("main_message_id") or callback.message.message_id
    await state.clear()
    await state.update_data(main_message_id=message_id)
    await show_admin_menu(state, callback.message.chat.id, callback.bot, session)
    await callback.answer()

