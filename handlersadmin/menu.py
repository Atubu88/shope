from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message
from aiogram.client.bot import Bot

admin_menu_router = Router()


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Добавить товар", callback_data="admin_add_product")],
            [InlineKeyboardButton(text="Ассортимент", callback_data="admin_products")],
            [InlineKeyboardButton(text="Добавить/Изменить баннер", callback_data="admin_banners")],
            [InlineKeyboardButton(text="Создать салон", callback_data="admin_create_salon")],
        ]
    )


async def show_admin_menu(state: FSMContext, chat_id: int, bot: Bot):
    data = await state.get_data()
    message_id = data.get("main_message_id")
    text = "Что хотите сделать?"
    kb = admin_keyboard()
    if message_id:
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=kb)
    else:
        msg = await bot.send_message(chat_id, text, reply_markup=kb)
        await state.update_data(main_message_id=msg.message_id)


@admin_menu_router.message(Command("admin"))
async def open_admin(message: Message, state: FSMContext):
    await show_admin_menu(state, message.chat.id, message.bot)


@admin_menu_router.callback_query(F.data == "admin_menu")
async def cb_admin_menu(callback: CallbackQuery, state: FSMContext):
    await show_admin_menu(state, callback.message.chat.id, callback.bot)
    await callback.answer()