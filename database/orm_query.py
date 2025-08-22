import math
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from common.texts_for_db import  description_for_info_pages, images_for_info_pages
from database.models import Banner, Cart, Category, Product, User, Salon, UserSalon



############################ Салоны ###########################################
# database/orm_query.py
async def get_salon_name_by_id(session, salon_id):
    from database.models import Salon
    salon = await session.get(Salon, salon_id)
    return salon.name if salon else None


async def orm_get_salons(session: AsyncSession):
    result = await session.execute(select(Salon))
    return result.scalars().all()


async def orm_create_salon(
    session: AsyncSession,
    name: str,
    slug: str,
    currency: str,
    timezone: str | None = "UTC",
) -> Salon:
    stmt = select(Salon).where((Salon.name == name) | (Salon.slug == slug))
    result = await session.execute(stmt)
    salon = result.scalar_one_or_none()

    if salon:
        raise ValueError("Salon with this name or slug already exists")
    new_salon = Salon(
        name=name,
        slug=slug,
        currency=currency,
        timezone=timezone or "UTC",
        free_plan=True,
        order_limit=30,
    )
    session.add(new_salon)
    await session.commit()
    await session.refresh(new_salon)
    return new_salon


async def orm_set_salon_timezone(
    session: AsyncSession, salon_id: int, tz_name: str
) -> None:
    await session.execute(
        update(Salon).where(Salon.id == salon_id).values(timezone=tz_name)
    )
    await session.commit()


async def orm_get_salon_by_slug(session: AsyncSession, slug: str) -> Salon | None:
    result = await session.execute(select(Salon).where(Salon.slug == slug))
    return result.scalar_one_or_none()

async def orm_update_salon_location(
    session: AsyncSession, salon_id: int, latitude: float, longitude: float
) -> None:
    await session.execute(
        update(Salon)
        .where(Salon.id == salon_id)
        .values(latitude=latitude, longitude=longitude)
    )
    await session.commit()

async def orm_update_salon_group_chat(
    session: AsyncSession, salon_id: int, group_chat_id: int
) -> None:
    await session.execute(
        update(Salon)
        .where(Salon.id == salon_id)
        .values(group_chat_id=group_chat_id)
    )
    await session.commit()


async def orm_get_salon_by_id(session, salon_id: int):
    """
    Получить салон по его ID (асинхронно для SQLAlchemy 2.x).
    """
    result = await session.execute(
        select(Salon).where(Salon.id == salon_id)
    )
    return result.scalars().first()

############### Работа с баннерами (информационными страницами) ###############

async def orm_add_banner_description(
    session: AsyncSession,
    data: dict,
    salon_id: int,
    images: dict | None = None,
):
    """Create or update banner records with optional descriptions and images.

    ``data`` maps page names to descriptions. Passing ``None`` as a description
    means that the banner should rely on ``get_default_banner_description``
    until an admin provides custom text. Existing descriptions are preserved
    when ``None`` is supplied so that manual edits are not overwritten. The
    ``images`` mapping allows providing default images for new salons.
    """

    for name, description in data.items():
        query = select(Banner).where(Banner.name == name, Banner.salon_id == salon_id)
        result = await session.execute(query)
        banner = result.scalar()

        image = images.get(name) if images else None

        if banner:
            values = {}
            if description is not None:
                values["description"] = description
            if image is not None:
                values["image"] = image
            if values:
                await session.execute(
                    update(Banner)
                    .where(Banner.name == name, Banner.salon_id == salon_id)
                    .values(**values)
                )
        else:
            session.add(
                Banner(
                    name=name,
                    description=description,
                    image=image,
                    salon_id=salon_id,
                )
            )

    await session.commit()


async def orm_change_banner_image(session: AsyncSession, name: str, image: str, salon_id: int):
    query = (
        update(Banner)
        .where(Banner.name == name, Banner.salon_id == salon_id)
        .values(image=image)
    )
    await session.execute(query)
    await session.commit()


async def orm_change_banner_description(session: AsyncSession, name: str, description: str, salon_id: int):
    query = (
        update(Banner)
        .where(Banner.name == name, Banner.salon_id == salon_id)
        .values(description=description)
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

async def orm_get_category(session: AsyncSession, category_id: int, salon_id: int):
    query = select(Category).where(Category.id == category_id, Category.salon_id == salon_id)
    result = await session.execute(query)
    return result.scalar()


async def orm_create_categories(session: AsyncSession, categories: list, salon_id: int):
    query = select(Category).where(Category.salon_id == salon_id)
    result = await session.execute(query)
    if result.first():
        return
    session.add_all([Category(name=name, salon_id=salon_id) for name in categories])
    await session.commit()


async def orm_add_category(session: AsyncSession, name: str, salon_id: int):
    """Create a single category for the salon."""
    session.add(Category(name=name, salon_id=salon_id))
    await session.commit()

async def orm_delete_category(session: AsyncSession, category_id: int, salon_id: int) -> None:
    """Delete category by id belonging to a salon."""
    query = delete(Category).where(Category.id == category_id, Category.salon_id == salon_id)
    await session.execute(query)
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


async def orm_get_products(session: AsyncSession, category_id=None, salon_id: int = None):
    query = select(Product)
    if salon_id is not None:
        query = query.where(Product.salon_id == salon_id)
    if category_id is not None:
        query = query.where(Product.category_id == int(category_id))
    result = await session.execute(query)
    return result.scalars().all()


async def orm_get_product(session: AsyncSession, product_id: int, salon_id: int):
    query = select(Product).where(Product.id == product_id, Product.salon_id == salon_id)
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

async def orm_change_product_image(session: AsyncSession, product_id: int, image: str, salon_id: int):
    query = (
        update(Product)
        .where(Product.id == product_id, Product.salon_id == salon_id)
        .values(image=image)
    )
    await session.execute(query)
    await session.commit()

async def orm_change_product_field(
    session: AsyncSession,
    product_id: int,
    salon_id: int,
    **fields,
):
    """Update specific fields of a product.

    Parameters are passed as keyword arguments, e.g. ``name="New name"``.
    """
    query = (
        update(Product)
        .where(Product.id == product_id, Product.salon_id == salon_id)
        .values(**fields)
    )
    await session.execute(query)
    await session.commit()


async def orm_delete_product(session: AsyncSession, product_id: int, salon_id: int):
    query = delete(Product).where(Product.id == product_id, Product.salon_id == salon_id)
    await session.execute(query)
    await session.commit()

async def init_default_salon_content(session: AsyncSession, salon_id: int):
    """Fill newly created salon with default categories and banners."""
    await orm_add_banner_description(
        session,
        description_for_info_pages,
        salon_id,
        images_for_info_pages,
    )



##################### Добавляем юзера в БД #####################################

async def orm_add_user(
    session: AsyncSession,
    user_id: int,
    salon_id: int,
    first_name: str | None = None,
    last_name: str | None = None,
    phone: str | None = None,
    is_super_admin: bool = False,
    is_salon_admin: bool = False,
) -> UserSalon:
    """Create or update a user and bind him to a salon."""
    user = (
        await session.execute(select(User).where(User.user_id == user_id))
    ).scalar_one_or_none()

    if user is None:
        user = User(user_id=user_id, is_super_admin=is_super_admin)
        session.add(user)
    else:
        if is_super_admin:
            user.is_super_admin = True

    user_salon = (
        await session.execute(
            select(UserSalon).where(
                UserSalon.user_id == user_id,
                UserSalon.salon_id == salon_id,
            )
        )
    ).scalar_one_or_none()

    if user_salon is None:
        user_salon = UserSalon(
            user_id=user_id,
            salon_id=salon_id,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            is_salon_admin=is_salon_admin,
        )
        session.add(user_salon)
    else:
        if first_name is not None:
            user_salon.first_name = first_name
        if last_name is not None:
            user_salon.last_name = last_name
        if phone is not None:
            user_salon.phone = phone
        if is_salon_admin:
            user_salon.is_salon_admin = True

    await session.commit()

    # 👉 Повторно получаем user_salon с подгруженным user
    result = await session.execute(
        select(UserSalon)
        .options(selectinload(UserSalon.user))
        .where(UserSalon.id == user_salon.id)
    )
    return result.scalar_one()


async def orm_get_user(
    session: AsyncSession, user_id: int, salon_id: int | None = None
) -> UserSalon | None:
    stmt = (
        select(UserSalon)
        .where(UserSalon.user_id == user_id)
        .options(joinedload(UserSalon.user))
    )
    if salon_id is not None:
        stmt = stmt.where(UserSalon.salon_id == salon_id)
    result = await session.execute(stmt)
    return result.scalars().first()


async def orm_set_user_language(
    session: AsyncSession, user_id: int, language: str
) -> None:
    await session.execute(
        update(User).where(User.user_id == user_id).values(language=language)
    )
    await session.commit()


async def orm_get_user_salons(session: AsyncSession, user_id: int) -> list[UserSalon]:
    stmt = (
        select(UserSalon)
        .where(UserSalon.user_id == user_id)
        .options(joinedload(UserSalon.salon))
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def orm_get_user_salon(session: AsyncSession, user_id: int, salon_id: int) -> UserSalon | None:
    stmt = (
        select(UserSalon)
        .where(UserSalon.user_id == user_id, UserSalon.salon_id == salon_id)
        .options(joinedload(UserSalon.salon))
    )
    result = await session.execute(stmt)
    return result.scalar()


######################## Работа с корзинами #######################################

async def orm_add_to_cart(
    session: AsyncSession, user_salon_id: int, product_id: int
):
    user_salon = await session.get(UserSalon, user_salon_id)
    if not user_salon:
        return

    product_check = await session.execute(
        select(Product.id).where(
            Product.id == product_id, Product.salon_id == user_salon.salon_id
        )
    )
    if not product_check.scalar():
        return

    query = select(Cart).where(
        Cart.user_salon_id == user_salon_id,
        Cart.product_id == product_id,
    ).options(joinedload(Cart.product))
    cart = (await session.execute(query)).scalar()
    if cart:
        cart.quantity += 1
        await session.commit()
        return cart
    else:
        session.add(Cart(user_salon_id=user_salon_id, product_id=product_id, quantity=1))
        await session.commit()


async def orm_get_user_carts(session: AsyncSession, user_salon_id: int):
    query = (
        select(Cart)
        .where(Cart.user_salon_id == user_salon_id)
        .options(joinedload(Cart.product))
    )
    result = await session.execute(query)
    return result.scalars().all()


async def orm_delete_from_cart(session: AsyncSession, user_salon_id: int, product_id: int):
    query = delete(Cart).where(
        Cart.user_salon_id == user_salon_id, Cart.product_id == product_id
    )
    await session.execute(query)
    await session.commit()


async def orm_reduce_product_in_cart(
    session: AsyncSession, user_salon_id: int, product_id: int
):
    query = select(Cart).where(
        Cart.user_salon_id == user_salon_id, Cart.product_id == product_id
    ).options(joinedload(Cart.product))
    cart = await session.execute(query)
    cart = cart.scalar()

    if not cart:
        return
    if cart.quantity > 1:
        cart.quantity -= 1
        await session.commit()
        return True
    else:
        await orm_delete_from_cart(session, user_salon_id, product_id)
        await session.commit()
        return False


async def orm_clear_cart(session: AsyncSession, user_salon_id: int) -> None:
    query = delete(Cart).where(Cart.user_salon_id == user_salon_id)
    await session.execute(query)
    await session.commit()


async def orm_create_order(
    session: AsyncSession,
    user_salon_id: int,
    address: str | None,
    phone: str | None,
    payment_method: str | None,
    cart_items: list,
    status: str = "NEW",
) -> "Order":
    from database.models import Order, OrderItem

    total = sum(item.product.price * item.quantity for item in cart_items)

    order = Order(
        user_salon_id=user_salon_id,
        address=address,
        phone=phone,
        payment_method=payment_method,
        status=status,
        total=total,
    )
    session.add(order)
    await session.flush()

    session.add_all(
        [
            OrderItem(
                order_id=order.id,
                product_id=item.product_id,
                quantity=item.quantity,
                price=item.product.price,
            )
            for item in cart_items
        ]
    )
    await session.commit()
    await session.refresh(order)
    return order

async def orm_get_orders_count(session: AsyncSession, salon_id: int) -> int:
    from database.models import Order, UserSalon
    return await session.scalar(
        select(func.count())
        .select_from(Order)
        .join(UserSalon, Order.user_salon_id == UserSalon.id)
        .where(UserSalon.salon_id == salon_id)
    ) or 0



async def orm_get_orders(session: AsyncSession, salon_id: int):
    from database.models import Order, UserSalon
    result = await session.execute(
        select(Order)
        .join(UserSalon)
        .where(UserSalon.salon_id == salon_id)
        .options(joinedload(Order.user_salon).joinedload(UserSalon.salon))
        .order_by(Order.created.desc())
    )
    return result.scalars().all()


async def orm_get_order(session: AsyncSession, order_id: int, salon_id: int):
    from database.models import Order, OrderItem, Product, UserSalon
    result = await session.execute(
        select(Order)
        .join(UserSalon)  # связываем с владельцем заказа
        .where(
            Order.id == order_id,
            UserSalon.salon_id == salon_id,  # ← ключевая проверка
        )
        .options(
            joinedload(Order.items).joinedload(OrderItem.product),
            joinedload(Order.user_salon).joinedload(UserSalon.user),
            joinedload(Order.user_salon).joinedload(UserSalon.salon),
        )
    )
    return result.unique().scalar_one_or_none()


async def orm_update_order_status(
    session: AsyncSession, order_id: int, salon_id: int, new_status: str
):
    from database.models import Order, UserSalon
    result = await session.execute(
        select(Order)
        .join(UserSalon)
        .where(Order.id == order_id, UserSalon.salon_id == salon_id)
    )
    order = result.scalar_one_or_none()
    if order:
        order.status = new_status
        await session.commit()
        await session.refresh(order)
        return order
    return None



async def orm_get_user_by_tg_and_salon(session, user_id: int, salon_id: int):
    stmt = select(UserSalon).where(
        UserSalon.user_id == user_id,
        UserSalon.salon_id == salon_id,
    )
    res = await session.execute(stmt)
    return res.scalars().first()


async def orm_get_user_salon(session, user_id: int, salon_id: int):
    stmt = select(UserSalon).where(
        UserSalon.user_id == user_id,
        UserSalon.salon_id == salon_id
    )
    result = await session.execute(stmt)
    return result.scalars().first()