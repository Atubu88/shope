"""Add currency field to Salon

Revision ID: be1234567892
Revises: bd1234567891
Create Date: 2025-07-30 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'be1234567892'
down_revision: Union[str, Sequence[str], None] = 'bd1234567891'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('salon', schema=None) as batch_op:
        batch_op.add_column(sa.Column('currency', sa.String(length=3), nullable=True))
    op.execute("UPDATE salon SET currency='RUB' WHERE currency IS NULL")
    with op.batch_alter_table('salon', schema=None) as batch_op:
        batch_op.alter_column('currency', nullable=False)


def downgrade() -> None:
    with op.batch_alter_table('salon', schema=None) as batch_op:
        batch_op.drop_column('currency')
