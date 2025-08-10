"""add free plan fields to salon

Revision ID: eacb5304a640
Revises: 2b1ff0126b4b
Create Date: 2025-02-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eacb5304a640'
down_revision: Union[str, Sequence[str], None] = '2b1ff0126b4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('salon', sa.Column('free_plan', sa.Boolean(), server_default=sa.true(), nullable=False))
    op.add_column('salon', sa.Column('order_limit', sa.Integer(), server_default='30', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('salon', 'order_limit')
    op.drop_column('salon', 'free_plan')

