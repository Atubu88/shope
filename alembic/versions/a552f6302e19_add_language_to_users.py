"""add language to users

Revision ID: a552f6302e19
Revises: 233c2ac1834c
Create Date: 2025-08-11 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a552f6302e19'
down_revision: Union[str, Sequence[str], None] = '233c2ac1834c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('language', sa.String(length=2), nullable=False, server_default=sa.text("'ru'")),
    )


def downgrade() -> None:
    op.drop_column('users', 'language')