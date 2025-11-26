"""add product details url

Revision ID: 0b53f85ddf3f
Revises: b8898d269157
Create Date: 2025-08-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0b53f85ddf3f"
down_revision: Union[str, Sequence[str], None] = "b8898d269157"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "product",
        sa.Column("details_url", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("product", "details_url")
