"""add orders tables

Revision ID: b99bca9922b3
Revises: 0345942b30c1
Create Date: 2025-08-01 09:38:38.653368

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b99bca9922b3'
down_revision: Union[str, Sequence[str], None] = '0345942b30c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'orders',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('salon_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('payment_method', sa.String(length=20), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='NEW', nullable=False),
        sa.Column('total', sa.Numeric(10, 2), nullable=False),
        sa.Column('created', sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated', sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['salon_id'], ['salon.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.user_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'order_item',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('price', sa.Numeric(10, 2), nullable=False),
        sa.Column('created', sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated', sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['product.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('order_item')
    op.drop_table('orders')