"""Merge banner and location branches

Revision ID: bc74b9b64819
Revises: 713516ad44ca, bb1234567890
Create Date: 2025-07-14 01:44:54.832312

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bc74b9b64819'
down_revision: Union[str, Sequence[str], None] = ('713516ad44ca', 'bb1234567890')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
