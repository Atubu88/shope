"""create schema

Revision ID: 233c2ac1834c
Revises: 46276c8ae992
Create Date: 2025-08-11 21:15:13.236293

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '233c2ac1834c'
down_revision: Union[str, Sequence[str], None] = '46276c8ae992'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # salon
    op.create_table(
        "salon",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("slug", sa.String(50), nullable=False, unique=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default=sa.text("'RUB'")),
        sa.Column("timezone", sa.String(50), nullable=True),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("group_chat_id", sa.BigInteger, nullable=True),
        sa.Column("free_plan", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("order_limit", sa.Integer, nullable=False, server_default=sa.text("30")),
        sa.Column("created", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )

    # users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, nullable=False, unique=True),
        sa.Column("is_super_admin", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )

    # banner
    op.create_table(
        "banner",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(15), nullable=False),
        sa.Column("image", sa.String(150), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("salon_id", sa.Integer, sa.ForeignKey("salon.id"), nullable=False),
        sa.Column("created", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("name", "salon_id", name="unique_banner_name_per_salon"),
    )

    # category
    op.create_table(
        "category",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("salon_id", sa.Integer, sa.ForeignKey("salon.id"), nullable=False),
        sa.Column("created", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )

    # product
    op.create_table(
        "product",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("image", sa.String(150), nullable=True),
        sa.Column("category_id", sa.Integer, sa.ForeignKey("category.id", ondelete="CASCADE"), nullable=False),
        sa.Column("salon_id", sa.Integer, sa.ForeignKey("salon.id"), nullable=False),
        sa.Column("created", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )

    # user_salon
    op.create_table(
        "user_salon",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("salon_id", sa.Integer, sa.ForeignKey("salon.id", ondelete="CASCADE"), nullable=False),
        sa.Column("first_name", sa.String(150), nullable=True),
        sa.Column("last_name", sa.String(150), nullable=True),
        sa.Column("phone", sa.String(13), nullable=True),
        sa.Column("is_salon_admin", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "salon_id", name="uq_user_salon"),
    )

    # cart
    op.create_table(
        "cart",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_salon_id", sa.Integer, sa.ForeignKey("user_salon.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("product.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("created", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )

    # orders
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_salon_id", sa.Integer, sa.ForeignKey("user_salon.id"), nullable=False),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("payment_method", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'NEW'")),
        sa.Column("total", sa.Numeric(10, 2), nullable=False),
        sa.Column("created", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )

    # order_item
    op.create_table(
        "order_item",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("product.id"), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("created", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("order_item")
    op.drop_table("orders")
    op.drop_table("cart")
    op.drop_table("user_salon")
    op.drop_table("product")
    op.drop_table("category")
    op.drop_table("banner")
    op.drop_table("users")
    op.drop_table("salon")
