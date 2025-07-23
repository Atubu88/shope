from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardRemove

from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.filters import Command
from database.orm_query import orm_create_salon, init_default_salon_content
from kbds.inline import get_currency_kb
from filters.chat_types import ChatTypeFilter, IsSuperAdmin
from utils.slug import generate_unique_slug

salon_creation_router = Router()
salon_creation_router.message.filter(ChatTypeFilter(["private"]), IsSuperAdmin())


class AddSalon(StatesGroup):
    name = State()
    slug = State()
    currency = State()


@salon_creation_router.message(StateFilter(None), Command("create_salon"))
async def start_create_salon(message: types.Message, state: FSMContext) -> None:
    await message.answer('Введите название салона:', reply_markup=ReplyKeyboardRemove())
    await state.set_state(AddSalon.name)

@salon_creation_router.message(AddSalon.name, F.text)
async def salon_name(message: types.Message, state: FSMContext) -> None:
    if len(message.text.strip()) < 2:
        await message.answer('Название слишком короткое, попробуйте ещё раз')
        return
    await state.update_data(name=message.text.strip())
    await message.answer('Введите slug или "-" для автоматического создания')
    await state.set_state(AddSalon.slug)


@salon_creation_router.message(AddSalon.name)
async def salon_name_invalid(message: types.Message) -> None:
    await message.answer('Отправьте текстовое название или "отмена"')


@salon_creation_router.message(AddSalon.slug, F.text)
async def salon_slug(message: types.Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    name = data['name']
    slug_raw = message.text.strip()
    slug_source = slug_raw if slug_raw and slug_raw != '-' else name
    slug = await generate_unique_slug(session, slug_source)
    await state.update_data(slug=slug)
    await message.answer('Выберите валюту салона:', reply_markup=get_currency_kb())
    await state.set_state(AddSalon.currency)


@salon_creation_router.message(AddSalon.slug)
async def salon_slug_invalid(message: types.Message) -> None:
    await message.answer('Введите slug текстом или "-" для авто')


@salon_creation_router.callback_query(AddSalon.currency, F.data.startswith("currency_"))
async def salon_currency(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    currency = callback.data.split("_")[-1]
    data = await state.get_data()
    name = data['name']
    slug = data['slug']
    try:
        salon = await orm_create_salon(session, name, slug, currency)
    except ValueError:
        await callback.message.answer('Салон с таким названием или слагом уже существует.')
        await state.clear()
        await callback.answer()
        return
    await init_default_salon_content(session, salon.id)
    bot_username = (await callback.bot.get_me()).username
    link = f'https://t.me/{bot_username}?start={salon.slug}'
    import qrcode
    from io import BytesIO
    img = qrcode.make(link)
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    await callback.message.answer_photo(
        types.BufferedInputFile(buf.getvalue(), filename='qr.png'),
        caption=f"Салон '{salon.name}' создан!\n{link}"
    )
    await state.clear()
    await callback.answer()