"""Add slug column to Salon

Revision ID: d1b27b34b7aa
Revises: 5d334f0f1eee
Create Date: 2025-07-10 15:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd1b27b34b7aa'
down_revision: Union[str, Sequence[str], None] = '5d334f0f1eee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('salon', schema=None) as batch_op:
        batch_op.add_column(sa.Column('slug', sa.String(length=50), nullable=True))
        batch_op.create_unique_constraint('uq_salon_slug', ['slug'])
    op.execute("UPDATE salon SET slug='default' WHERE slug IS NULL")
    with op.batch_alter_table('salon', schema=None) as batch_op:
        batch_op.alter_column('slug', nullable=False)

def downgrade() -> None:
    with op.batch_alter_table('salon', schema=None) as batch_op:
        batch_op.drop_constraint('uq_salon_slug', type_='unique')
        batch_op.drop_column('slug')
