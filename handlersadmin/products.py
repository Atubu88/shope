from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query import orm_get_categories, orm_get_products, orm_delete_product
from .menu import show_admin_menu

admin_products_router = Router()


def products_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="\ud83d\udccb \u0410\u0441\u0441\u043e\u0440\u0442\u0438\u043c\u0435\u043d\u0442", callback_data="admin_products")]
        ]
    )


class AdminProductsFSM(StatesGroup):
    category = State()


def category_kb(categories) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=c.name, callback_data=f"prod_cat_{c.id}")]
               for c in categories]
    buttons.append([InlineKeyboardButton(text="Выйти", callback_data="prod_exit")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@admin_products_router.callback_query(F.data == "admin_products")
async def start_show_products(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    old_data = await state.get_data()
    salon_id = old_data.get("salon_id")
    message_id = old_data.get("main_message_id") or callback.message.message_id

    await state.clear()
    await state.update_data(main_message_id=message_id, salon_id=salon_id)

    categories = await orm_get_categories(session, salon_id)
    await state.set_state(AdminProductsFSM.category)
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=message_id,
        text="Выберите категорию:",
        reply_markup=category_kb(categories),
    )
    await callback.answer()


@admin_products_router.callback_query(AdminProductsFSM.category, F.data.startswith("prod_cat_"))
async def show_category(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    category_id = int(callback.data.split("_")[-1])
    await state.update_data(category=category_id)
    data = await state.get_data()
    salon_id = data.get("salon_id")
    products = await orm_get_products(session, category_id, salon_id)
    if not products:
        await callback.message.answer("В этой категории нет товаров.")
    else:
        for product in products:
            caption = (
                f"<b>{product.name}</b>\n{product.description}\nЦена: {product.price}"
            )
            await callback.message.answer_photo(
                product.image,
                caption=caption,
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="Удалить",
                                callback_data=f"prod_del_{product.id}",
                            ),
                            InlineKeyboardButton(
                                text="Изменить",
                                callback_data=f"prod_edit_{product.id}",
                            ),
                        ]
                    ]
                ),
            )
    await callback.answer()


@admin_products_router.callback_query(F.data.startswith("prod_del_"))
async def delete_product(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    product_id = int(callback.data.split("_")[-1])
    data = await state.get_data()
    salon_id = data.get("salon_id")
    if salon_id:
        await orm_delete_product(session, product_id, salon_id)
        await callback.answer("Товар удален")
        await callback.message.delete()
    else:
        await callback.answer("Ошибка удаления", show_alert=True)


@admin_products_router.callback_query(F.data.startswith("prod_edit_"))
async def edit_product(callback: CallbackQuery) -> None:
    await callback.answer("Функция редактирования не реализована", show_alert=True)


@admin_products_router.callback_query(AdminProductsFSM.category, F.data == "prod_exit")
async def exit_from_products(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    message_id = data.get("main_message_id") or callback.message.message_id
    await state.clear()
    await state.update_data(main_message_id=message_id)
    await show_admin_menu(state, callback.message.chat.id, callback.bot, session)
    await callback.answer()
