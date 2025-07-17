"""Add group_chat_id to Salon

Revision ID: bd1234567891
Revises: bc74b9b64819
Create Date: 2025-07-20 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'bd1234567891'
down_revision: Union[str, Sequence[str], None] = 'bc74b9b64819'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('salon', schema=None) as batch_op:
        batch_op.add_column(sa.Column('group_chat_id', sa.BigInteger(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('salon', schema=None) as batch_op:
        batch_op.drop_column('group_chat_id')
