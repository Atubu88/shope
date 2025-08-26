"""add checkout fields

Revision ID: 7cdb2b3c0a5d
Revises: a552f6302e19
Create Date: 2024-02-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "7cdb2b3c0a5d"
down_revision: Union[str, Sequence[str], None] = "a552f6302e19"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("name", sa.String(length=150), nullable=False))
    op.add_column("orders", sa.Column("email", sa.String(length=150), nullable=True))
    op.add_column("orders", sa.Column("delivery_type", sa.String(length=20), nullable=False))
    op.add_column("orders", sa.Column("comment", sa.Text(), nullable=True))
    op.alter_column("orders", "phone", existing_type=sa.String(length=20), nullable=False)
    op.alter_column(
        "orders", "payment_method", existing_type=sa.String(length=20), nullable=False
    )
    op.add_column("order_item", sa.Column("product_name", sa.String(length=150), nullable=False))


def downgrade() -> None:
    op.drop_column("order_item", "product_name")
    op.alter_column(
        "orders", "payment_method", existing_type=sa.String(length=20), nullable=True
    )
    op.alter_column("orders", "phone", existing_type=sa.String(length=20), nullable=True)
    op.drop_column("orders", "comment")
    op.drop_column("orders", "delivery_type")
    op.drop_column("orders", "email")
    op.drop_column("orders", "name")
