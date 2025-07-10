"""Change unique banner.name to banner.name+salon_id

Revision ID: 713516ad44ca
Revises: d1b27b34b7aa
Create Date: 2025-07-10 16:40:09.744627

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '713516ad44ca'
down_revision: Union[str, Sequence[str], None] = 'd1b27b34b7aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('banner', schema=None) as batch_op:
        # Просто убираем unique у name (Alembic поймёт, что он есть)
        batch_op.alter_column('name', existing_type=sa.String(length=15), unique=False)
        # Добавляем новый composite-constraint
        batch_op.create_unique_constraint('uq_banner_name_salon', ['name', 'salon_id'])

def downgrade() -> None:
    with op.batch_alter_table('banner', schema=None) as batch_op:
        batch_op.drop_constraint('uq_banner_name_salon', type_='unique')
        batch_op.alter_column('name', existing_type=sa.String(length=15), unique=True)


