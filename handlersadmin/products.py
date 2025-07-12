from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query import (
    orm_get_categories,
    orm_get_products,
    orm_delete_product,
    orm_change_product_image,
)
from .menu import show_admin_menu

products_router = Router()


class EditPhotoFSM(StatesGroup):
    waiting_for_photo = State()

# --- Клавиатуры ---

def product_category_kb(categories) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=c.name, callback_data=f"prod_cat_{c.id}")]
               for c in categories]
    buttons.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="admin_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def product_action_kb(product_id) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Изменить", callback_data=f"edit_prod_{product_id}"),
                InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_prod_{product_id}")
            ]
        ]
    )

# --- Хендлеры ---

# 1. Открытие меню ассортимента
@products_router.callback_query(F.data == "admin_products")
async def show_categories(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    salon_id = data.get("salon_id")
    if not salon_id:
        await callback.message.answer("Ошибка: не выбран салон.")
        await callback.answer()
        return

    categories = await orm_get_categories(session, salon_id)
    if not categories:
        await callback.message.answer("В этом салоне пока нет категорий.")
        await callback.answer()
        return

    message_id = data.get("main_message_id") or callback.message.message_id
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=message_id,
        text="Выберите категорию ассортимента:",
        reply_markup=product_category_kb(categories)
    )
    await state.update_data(main_message_id=message_id)
    await callback.answer()

# 2. Показ товаров выбранной категории
@products_router.callback_query(F.data.startswith("prod_cat_"))
async def show_products(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    salon_id = data.get("salon_id")
    category_id = int(callback.data.split("_")[-1])
    message_id = data.get("main_message_id") or callback.message.message_id

    # ПЕРЕД отправкой новых товаров УДАЛЯЕМ прошлые сообщения с товарами
    old_product_msg_ids = data.get("product_msg_ids", [])
    if old_product_msg_ids:
        try:
            await callback.bot.delete_messages(callback.message.chat.id, old_product_msg_ids)
        except Exception as e:
            print(f"Bulk delete failed: {e}")
            for msg_id in old_product_msg_ids:
                try:
                    await callback.bot.delete_message(callback.message.chat.id, msg_id)
                except Exception as e:
                    print(f"Ошибка удаления старого сообщения с товаром {msg_id}: {e}")

    # Потом очищаем список
    await state.update_data(product_msg_ids=[])

    # Удаляем главное сообщение с категориями
    try:
        await callback.bot.delete_message(chat_id=callback.message.chat.id, message_id=message_id)
    except Exception:
        pass

    products = await orm_get_products(session, category_id, salon_id)
    product_msg_ids = []
    if products:
        for product in products:
            caption = (
                f"<b>{product.name}</b>\n"
                f"{product.description}\n"
                f"Цена: <b>{product.price:.2f}</b>"
            )
            msg = await callback.bot.send_photo(
                chat_id=callback.message.chat.id,
                photo=product.image,
                caption=caption,
                reply_markup=product_action_kb(product.id),
                parse_mode="HTML"
            )
            product_msg_ids.append(msg.message_id)
        await state.update_data(product_msg_ids=product_msg_ids)
    else:
        await callback.message.answer("В этой категории пока нет товаров.")
        await state.update_data(product_msg_ids=[])

    # Кнопка "В меню" — новое главное сообщение
    msg = await callback.message.answer(
        "Товары этой категории выше ⏫",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅️ В меню", callback_data="admin_menu")]]
        )
    )
    await state.update_data(main_message_id=msg.message_id)
    await callback.answer()





# 3. Удаление товара
@products_router.callback_query(F.data.startswith("delete_prod_"))
async def delete_product(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    salon_id = data.get("salon_id")
    if not salon_id:
        await callback.message.answer("Ошибка: не выбран салон.")
        await callback.answer()
        return

    product_id = int(callback.data.split("_")[-1])
    await orm_delete_product(session, product_id, salon_id)
    await callback.answer("Товар удалён ✅", show_alert=True)
    try:
        await callback.message.delete()
    except Exception:
        pass

# 4. Изменение товара — FSM сценарий реализуй в другом файле (или подключи сюда)
@products_router.callback_query(F.data.startswith("edit_prod_"))
async def edit_product(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[-1])
    await state.set_state(EditPhotoFSM.waiting_for_photo)
    await state.update_data(edit_product_id=product_id)
    await callback.message.answer("Отправьте новое фото товара или отмените командой /cancel")
    await callback.answer()


@products_router.message(EditPhotoFSM.waiting_for_photo, F.photo)
async def save_new_photo(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    salon_id = data.get("salon_id")
    product_id = data.get("edit_product_id")
    photo_id = message.photo[-1].file_id
    await orm_change_product_image(session, product_id, photo_id, salon_id)
    msg_id = data.get("main_message_id") or message.message_id
    await state.clear()
    await state.update_data(main_message_id=msg_id, salon_id=salon_id, product_msg_ids=[])
    await message.answer("Фото товара обновлено ✅")
    await show_admin_menu(state, message.chat.id, message.bot, session)


@products_router.message(EditPhotoFSM.waiting_for_photo)
async def cancel_edit(message: Message, state: FSMContext, session: AsyncSession):
    if message.text and message.text.lower() in {"/cancel", "отмена"}:
        data = await state.get_data()
        msg_id = data.get("main_message_id") or message.message_id
        salon_id = data.get("salon_id")
        await state.clear()
        await state.update_data(main_message_id=msg_id, salon_id=salon_id)
        await message.answer("Отменено")
        await show_admin_menu(state, message.chat.id, message.bot, session)
    else:
        await message.answer("Пришлите фотографию или отправьте /cancel")

# 5. Вернуться в меню
@products_router.callback_query(F.data == "admin_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    product_msg_ids = data.get("product_msg_ids", [])
    print("Удаляем сообщения:", product_msg_ids)

    if product_msg_ids:
        try:
            await callback.bot.delete_messages(callback.message.chat.id, product_msg_ids)
        except Exception as e:
            print(f"Bulk delete failed: {e}")
            for msg_id in product_msg_ids:
                try:
                    await callback.bot.delete_message(callback.message.chat.id, msg_id)
                except Exception as e:
                    print(f"Ошибка удаления {msg_id}: {e}")

    await state.update_data(product_msg_ids=[])
    await show_admin_menu(state, callback.message.chat.id, callback.bot, session)
    await callback.answer()
