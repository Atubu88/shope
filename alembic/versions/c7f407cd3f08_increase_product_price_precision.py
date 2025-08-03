"""increase product price precision

Revision ID: c7f407cd3f08
Revises: 8d94c90d94b5
Create Date: 2025-08-03 10:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c7f407cd3f08'
down_revision: Union[str, Sequence[str], None] = '8d94c90d94b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('product', 'price',
               type_=sa.Numeric(10, 2),
               existing_type=sa.Numeric(5, 2),
               existing_nullable=False)


def downgrade() -> None:
    op.alter_column('product', 'price',
               type_=sa.Numeric(5, 2),
               existing_type=sa.Numeric(10, 2),
               existing_nullable=False)