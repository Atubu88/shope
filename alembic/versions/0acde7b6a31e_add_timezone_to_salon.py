"""add timezone to salon

Revision ID: 0acde7b6a31e
Revises: 8d94c90d94b5
Create Date: 2025-08-03 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0acde7b6a31e"
down_revision: Union[str, Sequence[str], None] = "8d94c90d94b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("salon", sa.Column("timezone", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("salon", "timezone")
