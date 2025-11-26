from sqlalchemy import (
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    BigInteger,
    func,
    Boolean, Integer,
)
from sqlalchemy import text as sa_text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import UniqueConstraint

class Base(DeclarativeBase):
    created: Mapped[DateTime] = mapped_column(
        DateTime,
        default=func.now(),
        server_default=func.now(),
    )
    updated: Mapped[DateTime] = mapped_column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        server_default=func.now(),
    )



class Salon(Base):
    __tablename__ = "salon"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    timezone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    group_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    free_plan: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_text("true"))
    order_limit: Mapped[int] = mapped_column(Integer, nullable=False, server_default="30")

    user_salons: Mapped[list['UserSalon']] = relationship(back_populates='salon')


class Banner(Base):
    __tablename__ = 'banner'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(15))
    image: Mapped[str] = mapped_column(String(150), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    salon_id: Mapped[int] = mapped_column(ForeignKey('salon.id'), nullable=False)

    salon: Mapped['Salon'] = relationship(backref='banners')

    __table_args__ = (
        UniqueConstraint('name', 'salon_id', name='unique_banner_name_per_salon'),
    )

class Category(Base):
    __tablename__ = 'category'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    salon_id: Mapped[int] = mapped_column(ForeignKey('salon.id'), nullable=False)

    salon: Mapped['Salon'] = relationship(backref='categories')


class Product(Base):
    __tablename__ = 'product'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    image: Mapped[str] = mapped_column(String(150))
    image_file_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    category_id: Mapped[int] = mapped_column(ForeignKey('category.id', ondelete='CASCADE'), nullable=False)
    salon_id: Mapped[int] = mapped_column(ForeignKey('salon.id'), nullable=False)

    category: Mapped['Category'] = relationship(backref='product')
    salon: Mapped['Salon'] = relationship(backref='product')


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    is_super_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str] = mapped_column(String(2), default='ru')

    user_salons: Mapped[list['UserSalon']] = relationship(back_populates='user')


class UserSalon(Base):
    __tablename__ = 'user_salon'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.user_id', ondelete='CASCADE'))
    salon_id: Mapped[int] = mapped_column(ForeignKey('salon.id', ondelete='CASCADE'))
    first_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(13), nullable=True)
    is_salon_admin: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped['User'] = relationship(back_populates='user_salons')
    salon: Mapped['Salon'] = relationship(back_populates='user_salons')

    @property
    def is_super_admin(self) -> bool:
        """Proxy super admin flag from related :class:`User`.

        Returns ``False`` if user relationship is not set.
        """
        return bool(self.user and self.user.is_super_admin)

    __table_args__ = (
        UniqueConstraint('user_id', 'salon_id', name='uq_user_salon'),
    )


class Cart(Base):
    __tablename__ = 'cart'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_salon_id: Mapped[int] = mapped_column(
        ForeignKey('user_salon.id', ondelete='CASCADE'), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey('product.id', ondelete='CASCADE'), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    user_salon: Mapped['UserSalon'] = relationship(backref='cart')
    product: Mapped['Product'] = relationship(backref='cart')


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_salon_id: Mapped[int] = mapped_column(
        ForeignKey('user_salon.id'), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_type: Mapped[str] = mapped_column(String(20))
    payment_method: Mapped[str] = mapped_column(String(20))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="NEW")
    total: Mapped[float] = mapped_column(Numeric(10, 2))

    user_salon: Mapped['UserSalon'] = relationship(backref='orders')


class OrderItem(Base):
    __tablename__ = "order_item"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.id', ondelete='CASCADE'))
    product_id: Mapped[int] = mapped_column(ForeignKey('product.id'))
    product_name: Mapped[str] = mapped_column(String(150))
    quantity: Mapped[int]
    price: Mapped[float] = mapped_column(Numeric(10, 2))

    order: Mapped['Order'] = relationship(backref='items')
    product: Mapped['Product'] = relationship(backref='order_items')