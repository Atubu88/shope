"""add product image_file_id

Revision ID: b8898d269157
Revises: 7cdb2b3c0a5d
Create Date: 2025-08-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b8898d269157"
down_revision: Union[str, Sequence[str], None] = "7cdb2b3c0a5d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "product",
        sa.Column("image_file_id", sa.String(length=150), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("product", "image_file_id")
