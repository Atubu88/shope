from aiogram import F, Router, types
from aiogram.filters import Command, StateFilter, or_f
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardRemove

from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query import (
    orm_change_banner_image,
    orm_get_categories,
    orm_add_product,
    orm_delete_product,
    orm_get_info_pages,
    orm_get_product,
    orm_get_products,
    orm_update_product,
    orm_get_salons, orm_get_user,
)
from utils.access import check_salon_access

from filters.chat_types import ChatTypeFilter, IsAdmin, IsSuperAdmin

from kbds.inline import get_callback_btns, get_admin_main_kb
from handlers.salon_creation import start_create_salon, AddSalon


admin_router = Router()
admin_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())
ADMIN_SALON: dict[int, int] = {}


ADMIN_KB = get_admin_main_kb()

# Хендлер для выхода из админ-панели
@admin_router.message(Command("exit_admin"), IsAdmin())
async def exit_admin_mode(message: types.Message, state: FSMContext):
    await state.clear()  # Сброс состояния
    await message.answer("Вы вышли из админ-панели.", reply_markup=ReplyKeyboardRemove())

@admin_router.message(Command("admin"))
async def admin_features(message: types.Message, session: AsyncSession):
    args = message.text.split()
    user_id = message.from_user.id
    user = await orm_get_user(session, user_id)

    if len(args) > 1:
        salon_id = int(args[1])
        if not await check_salon_access(session, user_id, salon_id):
            await message.answer("Нет доступа к этому салону")
            return
        ADMIN_SALON[user_id] = salon_id

    if user_id not in ADMIN_SALON:
        salons = await orm_get_salons(session)
        if not (user and user.is_super_admin):
            salons = [s for s in salons if user and s.id == user.salon_id]
        btns = {s.name: f"set_salon_{s.id}" for s in salons}
        await message.answer("Выберите салон", reply_markup=get_callback_btns(btns=btns))
        return

    salon_id = ADMIN_SALON.get(user_id)
    if not await check_salon_access(session, user_id, salon_id):
        await message.answer("Нет доступа к этому салону")
        ADMIN_SALON.pop(user_id, None)
        return

    await message.answer("Что хотите сделать?", reply_markup=ADMIN_KB)


@admin_router.callback_query(F.data.startswith('set_salon_'))
async def set_salon(callback: types.CallbackQuery, session: AsyncSession):
    salon_id = int(callback.data.split('_')[-1])
    if not await check_salon_access(session, callback.from_user.id, salon_id):
        await callback.message.answer("Нет доступа к этому салону")
        await callback.answer()
        return
    ADMIN_SALON[callback.from_user.id] = salon_id
    await callback.message.answer("Салон выбран")
    await callback.answer()


@admin_router.callback_query(IsSuperAdmin(), F.data == 'admin_create_salon')
async def create_salon_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()  # <<< Добавить сюда!
    await start_create_salon(callback.message, state)
    await callback.answer()


@admin_router.callback_query(F.data == 'admin_products')
async def admin_features(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    await state.clear()  # Сброс состояния, чтобы не было конфликтов FSM
    salon_id = ADMIN_SALON.get(callback.from_user.id)
    if not await check_salon_access(session, callback.from_user.id, salon_id):
        await callback.message.answer("Нет доступа к этому салону")
        await callback.answer()
        return
    categories = await orm_get_categories(session, salon_id)
    btns = {category.name: f'category_{category.id}' for category in categories}
    await callback.message.answer(
        "Выберите категорию", reply_markup=get_callback_btns(btns=btns)
    )
    await callback.answer()



@admin_router.callback_query(F.data.startswith('category_'))
async def starring_at_product(callback: types.CallbackQuery, session: AsyncSession):
    category_id = callback.data.split('_')[-1]
    salon_id = ADMIN_SALON.get(callback.from_user.id)
    if not await check_salon_access(session, callback.from_user.id, salon_id):
        await callback.message.answer("Нет доступа к этому салону")
        await callback.answer()
        return
    for product in await orm_get_products(session, int(category_id), salon_id):
        await callback.message.answer_photo(
            product.image,
            caption=f"<strong>{product.name}\
                    </strong>\n{product.description}\nСтоимость: {round(product.price, 2)}",
            reply_markup=get_callback_btns(
                btns={
                    "Удалить": f"delete_{product.id}",
                    "Изменить": f"change_{product.id}",
                },
                sizes=(2,)
            ),
        )
    await callback.answer()
    await callback.message.answer("ОК, вот список товаров ⏫")


@admin_router.callback_query(F.data.startswith("delete_"))
async def delete_product_callback(callback: types.CallbackQuery, session: AsyncSession):
    product_id = callback.data.split("_")[-1]
    salon_id = ADMIN_SALON.get(callback.from_user.id)
    if not await check_salon_access(session, callback.from_user.id, salon_id):
        await callback.message.answer("Нет доступа к этому салону")
        await callback.answer()
        return
    await orm_delete_product(session, int(product_id), salon_id)

    await callback.answer("Товар удален")
    await callback.message.answer("Товар удален!")


################# Микро FSM для загрузки/изменения баннеров ############################

class AddBanner(StatesGroup):
    image = State()

# Отправляем перечень информационных страниц бота и становимся в состояние отправки photo
@admin_router.callback_query(StateFilter("*"), F.data == 'admin_banners')
async def add_image2(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    await state.clear()  # Очистить старое состояние, если пользователь бросил другой процесс

    salon_id = ADMIN_SALON.get(callback.from_user.id)
    if not await check_salon_access(session, callback.from_user.id, salon_id):
        await callback.message.answer("Нет доступа к этому салону")
        await callback.answer()
        return
    pages_names = [page.name for page in await orm_get_info_pages(session, salon_id)]
    await callback.message.answer(
        f"Отправьте фото баннера.\nВ описании укажите для какой страницы:\n{', '.join(pages_names)}"
    )
    await state.set_state(AddBanner.image)
    await callback.answer()

# Добавляем/изменяем изображение в таблице (там уже есть записанные страницы по именам:
# main, catalog, cart(для пустой корзины), about, payment, shipping
@admin_router.message(AddBanner.image, F.photo)
async def add_banner(message: types.Message, state: FSMContext, session: AsyncSession):
    image_id = message.photo[-1].file_id
    for_page = message.caption.strip()
    salon_id = ADMIN_SALON.get(message.from_user.id)
    if not await check_salon_access(session, message.from_user.id, salon_id):
        await message.answer("Нет доступа к этому салону")
        return
    pages_names = [page.name for page in await orm_get_info_pages(session, salon_id)]
    if for_page not in pages_names:
        await message.answer(f"Введите нормальное название страницы, например:\
                         \n{', '.join(pages_names)}")
        return
    await orm_change_banner_image(session, for_page, image_id, salon_id)
    await message.answer("Баннер добавлен/изменен.")
    await state.clear()

@admin_router.message(StateFilter("*"), Command("отмена"))
@admin_router.message(StateFilter("*"), F.text.casefold() == "отмена")
async def cancel_handler(message: types.Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        return
    if AddProduct.product_for_change:
        AddProduct.product_for_change = None
    await state.clear()
    await message.answer("Действия отменены", reply_markup=ADMIN_KB)

# ловим некоррекный ввод
@admin_router.message(AddBanner.image)
async def add_banner2(message: types.Message, state: FSMContext):
    await message.answer("Отправьте фото баннера или отмена")

#########################################################################################



######################### FSM для дабавления/изменения товаров админом ###################

class AddProduct(StatesGroup):
    # Шаги состояний
    name = State()
    description = State()
    category = State()
    price = State()
    image = State()

    product_for_change = None

    texts = {
        "AddProduct:name": "Введите название заново:",
        "AddProduct:description": "Введите описание заново:",
        "AddProduct:category": "Выберите категорию  заново ⬆️",
        "AddProduct:price": "Введите стоимость заново:",
        "AddProduct:image": "Этот стейт последний, поэтому...",
    }


# Становимся в состояние ожидания ввода name
@admin_router.callback_query(StateFilter(None), F.data.startswith("change_"))
async def change_product_callback(
    callback: types.CallbackQuery, state: FSMContext, session: AsyncSession
):
    product_id = callback.data.split("_")[-1]
    salon_id = ADMIN_SALON.get(callback.from_user.id)
    if not await check_salon_access(session, callback.from_user.id, salon_id):
        await callback.message.answer("Нет доступа к этому салону")
        await callback.answer()
        return

    product_for_change = await orm_get_product(session, int(product_id), salon_id)

    AddProduct.product_for_change = product_for_change

    await callback.answer()
    await callback.message.answer(
        "Введите название товара", reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(AddProduct.name)


# Становимся в состояние ожидания ввода name
@admin_router.callback_query(StateFilter(None), F.data == "admin_add_product")
async def add_product(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    await state.clear()  # <--- сбрасываем состояние перед началом нового процесса
    salon_id = ADMIN_SALON.get(callback.from_user.id)
    if not await check_salon_access(session, callback.from_user.id, salon_id):
        await callback.message.answer("Нет доступа к этому салону")
        await callback.answer()
        return
    await callback.message.answer(
        "Введите название товара", reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(AddProduct.name)
    await callback.answer()



# Хендлер отмены и сброса состояния должен быть всегда именно здесь,
# после того, как только встали в состояние номер 1 (элементарная очередность фильтров)



# Вернутся на шаг назад (на прошлое состояние)
@admin_router.message(StateFilter("*"), Command("назад"))
@admin_router.message(StateFilter("*"), F.text.casefold() == "назад")
async def back_step_handler(message: types.Message, state: FSMContext) -> None:
    current_state = await state.get_state()

    if current_state == AddProduct.name:
        await message.answer(
            'Предидущего шага нет, или введите название товара или напишите "отмена"'
        )
        return

    previous = None
    for step in AddProduct.__all_states__:
        if step.state == current_state:
            await state.set_state(previous)
            await message.answer(
                f"Ок, вы вернулись к прошлому шагу \n {AddProduct.texts[previous.state]}"
            )
            return
        previous = step


# Ловим данные для состояние name и потом меняем состояние на description
@admin_router.message(AddProduct.name, F.text)
async def add_name(message: types.Message, state: FSMContext):
    if message.text == "." and AddProduct.product_for_change:
        await state.update_data(name=AddProduct.product_for_change.name)
    else:
        # Здесь можно сделать какую либо дополнительную проверку
        # и выйти из хендлера не меняя состояние с отправкой соответствующего сообщения
        # например:
        if 4 >= len(message.text) >= 150:
            await message.answer(
                "Название товара не должно превышать 150 символов\nили быть менее 5ти символов. \n Введите заново"
            )
            return

        await state.update_data(name=message.text)
    await message.answer("Введите описание товара")
    await state.set_state(AddProduct.description)

# Хендлер для отлова некорректных вводов для состояния name
@admin_router.message(AddProduct.name)
async def add_name2(message: types.Message, state: FSMContext):
    await message.answer("Вы ввели не допустимые данные, введите текст названия товара")


# Ловим данные для состояние description и потом меняем состояние на price
@admin_router.message(AddProduct.description, F.text)
async def add_description(message: types.Message, state: FSMContext, session: AsyncSession):
    if message.text == "." and AddProduct.product_for_change:
        await state.update_data(description=AddProduct.product_for_change.description)
    else:
        if 4 >= len(message.text):
            await message.answer(
                "Слишком короткое описание. \n Введите заново"
            )
            return
        await state.update_data(description=message.text)

    salon_id = ADMIN_SALON.get(message.from_user.id)
    if not await check_salon_access(session, message.from_user.id, salon_id):
        await message.answer("Нет доступа к этому салону")
        return
    categories = await orm_get_categories(session, salon_id)
    btns = {category.name : str(category.id) for category in categories}
    await message.answer("Выберите категорию", reply_markup=get_callback_btns(btns=btns))
    await state.set_state(AddProduct.category)

# Хендлер для отлова некорректных вводов для состояния description
@admin_router.message(AddProduct.description)
async def add_description2(message: types.Message, state: FSMContext):
    await message.answer("Вы ввели не допустимые данные, введите текст описания товара")


# Ловим callback выбора категории
@admin_router.callback_query(AddProduct.category)
async def category_choice(callback: types.CallbackQuery, state: FSMContext , session: AsyncSession):
    salon_id = ADMIN_SALON.get(callback.from_user.id)
    if not await check_salon_access(session, callback.from_user.id, salon_id):
        await callback.message.answer("Нет доступа к этому салону")
        await callback.answer()
        return
    if int(callback.data) in [category.id for category in await orm_get_categories(session, salon_id)]:
        await callback.answer()
        await state.update_data(category=callback.data)
        await callback.message.answer('Теперь введите цену товара.')
        await state.set_state(AddProduct.price)
    else:
        await callback.message.answer('Выберите катеорию из кнопок.')
        await callback.answer()

#Ловим любые некорректные действия, кроме нажатия на кнопку выбора категории
@admin_router.message(AddProduct.category)
async def category_choice2(message: types.Message, state: FSMContext):
    await message.answer("'Выберите катеорию из кнопок.'")


# Ловим данные для состояние price и потом меняем состояние на image
@admin_router.message(AddProduct.price, F.text)
async def add_price(message: types.Message, state: FSMContext, session: AsyncSession):
    if message.text == "." and AddProduct.product_for_change:
        await state.update_data(price=AddProduct.product_for_change.price)
    else:
        try:
            float(message.text)
        except ValueError:
            await message.answer("Введите корректное значение цены")
            return

        await state.update_data(price=message.text)
    salon_id = ADMIN_SALON.get(message.from_user.id)
    if not await check_salon_access(session, message.from_user.id, salon_id):
        await message.answer("Нет доступа к этому салону")
        return
    await message.answer("Загрузите изображение товара")
    await state.set_state(AddProduct.image)

# Хендлер для отлова некорректных ввода для состояния price
@admin_router.message(AddProduct.price)
async def add_price2(message: types.Message, state: FSMContext):
    await message.answer("Вы ввели не допустимые данные, введите стоимость товара")


# Ловим данные для состояние image и потом выходим из состояний
@admin_router.message(AddProduct.image, or_f(F.photo, F.text == "."))
async def add_image(message: types.Message, state: FSMContext, session: AsyncSession):
    if message.text and message.text == "." and AddProduct.product_for_change:
        await state.update_data(image=AddProduct.product_for_change.image)

    elif message.photo:
        await state.update_data(image=message.photo[-1].file_id)
    else:
        await message.answer("Отправьте фото пищи")
        return
    data = await state.get_data()
    salon_id = ADMIN_SALON.get(message.from_user.id)
    if not await check_salon_access(session, message.from_user.id, salon_id):
        await message.answer("Нет доступа к этому салону")
        return
    try:
        if AddProduct.product_for_change:
            await orm_update_product(session, AddProduct.product_for_change.id, data, salon_id)
        else:
            await orm_add_product(session, data, salon_id)
        await message.answer("Товар добавлен/изменен", reply_markup=ADMIN_KB)
        await state.clear()

    except Exception as e:
        await message.answer(
            f"Ошибка: \n{str(e)}\nОбратись к программеру, он опять денег хочет",
            reply_markup=ADMIN_KB,
        )
        await state.clear()

    AddProduct.product_for_change = None

# Ловим все прочее некорректное поведение для этого состояния
@admin_router.message(AddProduct.image)
async def add_image2(message: types.Message, state: FSMContext):
    await message.answer("Отправьте фото пищи")