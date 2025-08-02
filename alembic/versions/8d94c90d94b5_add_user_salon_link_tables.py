"""add user_salon link tables

Revision ID: 8d94c90d94b5
Revises: b99bca9922b3
Create Date: 2025-08-02 10:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '8d94c90d94b5'
down_revision: Union[str, Sequence[str], None] = 'b99bca9922b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'user_salon',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('salon_id', sa.Integer(), nullable=False),
        sa.Column('first_name', sa.String(length=150), nullable=True),
        sa.Column('last_name', sa.String(length=150), nullable=True),
        sa.Column('phone', sa.String(length=13), nullable=True),
        sa.Column('is_salon_admin', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['user.user_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['salon_id'], ['salon.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'salon_id', name='uq_user_salon')
    )

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_constraint('user_salon_id_fkey', type_='foreignkey')
        batch_op.drop_column('first_name')
        batch_op.drop_column('last_name')
        batch_op.drop_column('phone')
        batch_op.drop_column('salon_id')
        batch_op.drop_column('is_salon_admin')

    with op.batch_alter_table('cart', schema=None) as batch_op:
        batch_op.drop_constraint('cart_user_id_fkey', type_='foreignkey')
        batch_op.drop_column('user_id')
        batch_op.add_column(sa.Column('user_salon_id', sa.Integer(), nullable=False))
        batch_op.create_foreign_key(
            'cart_user_salon_id_fkey', 'user_salon', ['user_salon_id'], ['id'], ondelete='CASCADE'
        )

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_constraint('orders_user_id_fkey', type_='foreignkey')
        batch_op.drop_constraint('orders_salon_id_fkey', type_='foreignkey')
        batch_op.drop_column('user_id')
        batch_op.drop_column('salon_id')
        batch_op.add_column(sa.Column('user_salon_id', sa.Integer(), nullable=False))
        batch_op.create_foreign_key(
            'orders_user_salon_id_fkey', 'user_salon', ['user_salon_id'], ['id']
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('salon_id', sa.Integer(), nullable=False))
        batch_op.add_column(sa.Column('user_id', sa.BigInteger(), nullable=False))
        batch_op.create_foreign_key('orders_salon_id_fkey', 'salon', ['salon_id'], ['id'])
        batch_op.create_foreign_key('orders_user_id_fkey', 'user', ['user_id'], ['user_id'])
        batch_op.drop_constraint('orders_user_salon_id_fkey', type_='foreignkey')
        batch_op.drop_column('user_salon_id')

    with op.batch_alter_table('cart', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.BigInteger(), nullable=False))
        batch_op.create_foreign_key('cart_user_id_fkey', 'user', ['user_id'], ['user_id'], ondelete='CASCADE')
        batch_op.drop_constraint('cart_user_salon_id_fkey', type_='foreignkey')
        batch_op.drop_column('user_salon_id')

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_salon_admin', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('salon_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('phone', sa.String(length=13), nullable=True))
        batch_op.add_column(sa.Column('last_name', sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column('first_name', sa.String(length=150), nullable=True))
        batch_op.create_foreign_key('user_salon_id_fkey', 'salon', ['salon_id'], ['id'])

    op.drop_table('user_salon')
