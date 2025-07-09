import math
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database.models import Banner, Cart, Category, Product, User, Salon

# Простой пагинатор
class Paginator:
    def __init__(self, array: list | tuple, page: int=1, per_page: int=1):
        self.array = array
        self.per_page = per_page
        self.page = page
        self.len = len(self.array)
        # math.ceil - округление в большую сторону до целого числа
        self.pages = math.ceil(self.len / self.per_page)

    def __get_slice(self):
        start = (self.page - 1) * self.per_page
        stop = start + self.per_page
        return self.array[start:stop]

    def get_page(self):
        page_items = self.__get_slice()
        return page_items

    def has_next(self):
        if self.page < self.pages:
            return self.page + 1
        return False

    def has_previous(self):
        if self.page > 1:
            return self.page - 1
        return False

    def get_next(self):
        if self.page < self.pages:
            self.page += 1
            return self.get_page()
        raise IndexError(f'Next page does not exist. Use has_next() to check before.')

    def get_previous(self):
        if self.page > 1:
            self.page -= 1
            return self.__get_slice()
        raise IndexError(f'Previous page does not exist. Use has_previous() to check before.')


############################ Салоны ###########################################

async def orm_get_salons(session: AsyncSession):
    result = await session.execute(select(Salon))
    return result.scalars().all()


async def orm_create_salon(session: AsyncSession, name: str):
    stmt = select(Salon).where(Salon.name == name)
    result = await session.execute(stmt)
    salon = result.scalar_one_or_none()

    if salon:
        return salon  # уже существует — возвращаем
    new_salon = Salon(name=name)
    session.add(new_salon)
    await session.commit()
    await session.refresh(new_salon)
    return new_salon



############### Работа с баннерами (информационными страницами) ###############

async def orm_add_banner_description(session: AsyncSession, data: dict, salon_id: int):
    # Проходим по каждому элементу данных
    for name, description in data.items():
        # Проверяем, существует ли баннер с данным именем
        query = select(Banner).where(Banner.name == name, Banner.salon_id == salon_id)
        result = await session.execute(query)
        banner = result.scalar()

        if banner:
            # Обновляем существующий баннер
            await session.execute(
                update(Banner)
                .where(Banner.name == name, Banner.salon_id == salon_id)
                .values(description=description)
            )
        else:
            # Добавляем новый баннер, если его нет
            session.add(Banner(name=name, description=description, salon_id=salon_id))

    await session.commit()


async def orm_change_banner_image(session: AsyncSession, name: str, image: str, salon_id: int):
    query = (
        update(Banner)
        .where(Banner.name == name, Banner.salon_id == salon_id)
        .values(image=image)
    )
    await session.execute(query)
    await session.commit()


async def orm_get_banner(session: AsyncSession, page: str, salon_id: int):
    query = select(Banner).where(Banner.name == page, Banner.salon_id == salon_id)
    result = await session.execute(query)
    return result.scalar()


async def orm_get_info_pages(session: AsyncSession, salon_id: int):
    query = select(Banner).where(Banner.salon_id == salon_id)
    result = await session.execute(query)
    return result.scalars().all()


############################ Категории ######################################

async def orm_get_categories(session: AsyncSession, salon_id: int):
    query = select(Category).where(Category.salon_id == salon_id)
    result = await session.execute(query)
    return result.scalars().all()

async def orm_create_categories(session: AsyncSession, categories: list, salon_id: int):
    query = select(Category).where(Category.salon_id == salon_id)
    result = await session.execute(query)
    if result.first():
        return
    session.add_all([Category(name=name, salon_id=salon_id) for name in categories])
    await session.commit()

############ Админка: добавить/изменить/удалить товар ########################

async def orm_add_product(session: AsyncSession, data: dict, salon_id: int):
    obj = Product(
        name=data["name"],
        description=data["description"],
        price=float(data["price"]),
        image=data["image"],
        category_id=int(data["category"]),
        salon_id=salon_id,
    )
    session.add(obj)
    await session.commit()


async def orm_get_products(session: AsyncSession, category_id, salon_id: int):
    query = select(Product).where(
        Product.category_id == int(category_id), Product.salon_id == salon_id
    )
    result = await session.execute(query)
    return result.scalars().all()


async def orm_get_product(session: AsyncSession, product_id: int):
    query = select(Product).where(Product.id == product_id)
    result = await session.execute(query)
    return result.scalar()


async def orm_update_product(session: AsyncSession, product_id: int, data, salon_id: int):
    query = (
        update(Product)
        .where(Product.id == product_id, Product.salon_id == salon_id)
        .values(
            name=data["name"],
            description=data["description"],
            price=float(data["price"]),
            image=data["image"],
            category_id=int(data["category"]),
        )
    )
    await session.execute(query)
    await session.commit()


async def orm_delete_product(session: AsyncSession, product_id: int, salon_id: int):
    query = delete(Product).where(Product.id == product_id, Product.salon_id == salon_id)
    await session.execute(query)
    await session.commit()

##################### Добавляем юзера в БД #####################################

async def orm_add_user(
    session: AsyncSession,
    user_id: int,
    first_name: str | None = None,
    last_name: str | None = None,
    phone: str | None = None,
    salon_id: int | None = None,
):
    query = select(User).where(User.user_id == user_id)
    result = await session.execute(query)
    if result.first() is None:
        session.add(
            User(
                user_id=user_id,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                salon_id=salon_id,
            )
        )
        await session.commit()


async def orm_get_user(session: AsyncSession, user_id: int):
    result = await session.execute(select(User).where(User.user_id == user_id))
    return result.scalar()


######################## Работа с корзинами #######################################

async def orm_add_to_cart(session: AsyncSession, user_id: int, product_id: int):
    query = select(Cart).where(Cart.user_id == user_id, Cart.product_id == product_id).options(joinedload(Cart.product))
    cart = await session.execute(query)
    cart = cart.scalar()
    if cart:
        cart.quantity += 1
        await session.commit()
        return cart
    else:
        session.add(Cart(user_id=user_id, product_id=product_id, quantity=1))
        await session.commit()



async def orm_get_user_carts(session: AsyncSession, user_id):
    query = select(Cart).filter(Cart.user_id == user_id).options(joinedload(Cart.product))
    result = await session.execute(query)
    return result.scalars().all()


async def orm_delete_from_cart(session: AsyncSession, user_id: int, product_id: int):
    query = delete(Cart).where(Cart.user_id == user_id, Cart.product_id == product_id)
    await session.execute(query)
    await session.commit()


async def orm_reduce_product_in_cart(session: AsyncSession, user_id: int, product_id: int):
    query = select(Cart).where(Cart.user_id == user_id, Cart.product_id == product_id).options(joinedload(Cart.product))
    cart = await session.execute(query)
    cart = cart.scalar()

    if not cart:
        return
    if cart.quantity > 1:
        cart.quantity -= 1
        await session.commit()
        return True
    else:
        await orm_delete_from_cart(session, user_id, product_id)
        await session.commit()
        return False

