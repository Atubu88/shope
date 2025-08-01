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
from utils.supabase_storage import upload_photo_from_telegram, get_path_from_url, delete_photo_from_supabase
from database.orm_query import (
    orm_get_categories,
    orm_get_products,
    orm_delete_product,
    orm_change_product_image,
    orm_get_salon_by_id, orm_get_product,
)
from utils.currency import get_currency_symbol
from .menu import show_admin_menu

products_router = Router()


# ---------- FSM ----------
class EditPhotoFSM(StatesGroup):
    waiting_for_photo = State()


# ---------- КЛАВИАТУРЫ ----------
def product_category_kb(categories) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=c.name, callback_data=f"prod_cat_{c.id}")]
               for c in categories]
    # !!! уникальное callback_data
    buttons.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="prod_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def product_action_kb(product_id) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            # !!! та же уникальная «назад»‑кнопка
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="prod_back")],
            [
                InlineKeyboardButton(text="✏️ Изменить",
                                     callback_data=f"edit_prod_{product_id}"),
                InlineKeyboardButton(text="🗑️ Удалить",
                                     callback_data=f"delete_prod_{product_id}")
            ],
        ]
    )


# ---------- ХЕНДЛЕРЫ ----------
@products_router.callback_query(F.data == "admin_products")
async def show_categories(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    # Получить id главного сообщения
    data = await state.get_data()
    message_id = data.get("main_message_id") or callback.message.message_id
    salon_id = data.get("salon_id")

    if not salon_id:
        await callback.answer("Ошибка: не выбран салон.")
        return

    categories = await orm_get_categories(session, salon_id)
    kb = product_category_kb(categories)

    try:
        await callback.bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=message_id,
            text="Выберите категорию ассортимента:",
            reply_markup=kb
        )
    except Exception as e:
        # Если вдруг не удаётся (например, сообщение было удалено),
        # можно создать новое, но обычно лучше обновить main_message_id в FSM
        msg = await callback.message.answer("Выберите категорию ассортимента:", reply_markup=kb)
        await state.update_data(main_message_id=msg.message_id)

    await callback.answer()



@products_router.callback_query(F.data.startswith("prod_cat_"))
async def show_products(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Шаг 2 — показать товары выбранной категории."""
    # чистим старые товары
    for msg_id in (await state.get_data()).get("product_msg_ids", []):
        try:
            await callback.bot.delete_message(callback.message.chat.id, msg_id)
        except Exception:
            pass
    await state.update_data(product_msg_ids=[])

    salon_id = (await state.get_data()).get("salon_id")
    category_id = int(callback.data.split("_")[-1])
    old_main_id = (await state.get_data()).get("main_message_id") or callback.message.message_id

    # удаляем сообщение со списком категорий
    try:
        await callback.bot.delete_message(callback.message.chat.id, old_main_id)
    except Exception:
        pass

    products = await orm_get_products(session, category_id, salon_id)
    product_msg_ids: list[int] = []

    if products:
        salon = await orm_get_salon_by_id(session, salon_id)
        currency = get_currency_symbol(salon.currency) if salon else "RUB"
        for product in products:
            caption = (
                f"<b>{product.name}</b>\n"
                f"{product.description}\n"
                f"Цена: <b>{product.price:.2f}{currency}</b>"
            )
            msg = await callback.bot.send_photo(
                callback.message.chat.id,
                product.image,
                caption=caption,
                reply_markup=product_action_kb(product.id),
                parse_mode="HTML",
            )
            product_msg_ids.append(msg.message_id)
    else:
        msg_empty = await callback.message.answer("В этой категории пока нет товаров.")
        product_msg_ids.append(msg_empty.message_id)

    # подсказка + кнопка «назад»
    msg_hint = await callback.message.answer(
        "Товары этой категории выше ⏫",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅️ В меню", callback_data="prod_back")]]
        ),
    )
    product_msg_ids.append(msg_hint.message_id)

    await state.update_data(
        product_msg_ids=product_msg_ids,
        main_message_id=msg_hint.message_id,
    )
    await callback.answer()


@products_router.callback_query(F.data.startswith("delete_prod_"))
async def delete_product(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    salon_id = (await state.get_data()).get("salon_id")
    if not salon_id:
        await callback.message.answer("Ошибка: не выбран салон.")
        await callback.answer()
        return

    product_id = int(callback.data.split("_")[-1])

    # Получаем продукт (для url картинки)
    product = await orm_get_product(session, product_id, salon_id)
    if product and product.image:
        filename = get_path_from_url(product.image)
        try:
            await delete_photo_from_supabase(filename)
        except Exception as e:
            print(f"Ошибка при удалении фото из Supabase: {e}")

    await orm_delete_product(session, product_id, salon_id)
    await callback.answer("Товар удалён ✅", show_alert=True)
    try:
        await callback.message.delete()
    except Exception:
        pass


@products_router.callback_query(F.data.startswith("edit_prod_"))
async def edit_product(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EditPhotoFSM.waiting_for_photo)
    await state.update_data(edit_product_id=int(callback.data.split("_")[-1]))
    await callback.message.answer("Отправьте новое фото товара или отмените командой /cancel")
    await callback.answer()


@products_router.message(EditPhotoFSM.waiting_for_photo, F.photo)
async def save_new_photo(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    photo_url = await upload_photo_from_telegram(message.bot, message.photo[-1].file_id)
    await orm_change_product_image(
        session,
        data["edit_product_id"],
        photo_url,
        data["salon_id"],
    )

    await state.clear()
    await message.answer("Фото товара обновлено ✅")
    await show_admin_menu(state, message.chat.id, message.bot, session)


@products_router.message(EditPhotoFSM.waiting_for_photo)
async def cancel_edit(message: Message, state: FSMContext, session: AsyncSession):
    if message.text and message.text.lower() in {"/cancel", "отмена"}:
        salon_id = (await state.get_data()).get("salon_id")
        await state.clear()
        await state.update_data(salon_id=salon_id)
        await message.answer("Отменено")
        await show_admin_menu(state, message.chat.id, message.bot, session)
    else:
        await message.answer("Пришлите фотографию или отправьте /cancel")


# ---------- ГЛАВНОЕ: «⬅️ В меню» из ассортимента ----------
@products_router.callback_query(F.data == "prod_back")
async def back_to_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Удаляем все товары и выводим главное админ‑меню."""
    await callback.answer()

    data = await state.get_data()
    for msg_id in data.get("product_msg_ids", []):
        try:
            await callback.bot.delete_message(callback.message.chat.id, msg_id)
        except Exception:
            pass

    try:                                     # удаляем сообщение‑кнопку, из которого пришёл callback
        await callback.message.delete()
    except Exception:
        pass

    await state.update_data(product_msg_ids=[])
    await show_admin_menu(state, callback.message.chat.id, callback.bot, session)