"""Add latitude and longitude to Salon

Revision ID: bb1234567890
Revises: d1b27b34b7aa
Create Date: 2025-07-10 16:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'bb1234567890'
down_revision: Union[str, Sequence[str], None] = 'd1b27b34b7aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('salon', schema=None) as batch_op:
        batch_op.add_column(sa.Column('latitude', sa.Numeric(9, 6), nullable=True))
        batch_op.add_column(sa.Column('longitude', sa.Numeric(9, 6), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('salon', schema=None) as batch_op:
        batch_op.drop_column('longitude')
        batch_op.drop_column('latitude')