"""init

Revision ID: 8a489756427d
Revises:
Create Date: 2025-08-11 16:07:58.213562
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "8a489756427d"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Переименовать таблицу user → users (без потери данных)
    op.rename_table("user", "users")

    # 2) Обновить внешний ключ user_salon.user_id → users.user_id
    #    (сначала дроп старый FK, потом создать новый на users)
    op.drop_constraint(op.f("user_salon_user_id_fkey"), "user_salon", type_="foreignkey")
    op.create_foreign_key(
        op.f("user_salon_user_id_fkey"),
        source_table="user_salon",
        referent_table="users",
        local_cols=["user_id"],
        remote_cols=["user_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # Откатываем FK обратно на user
    op.drop_constraint(op.f("user_salon_user_id_fkey"), "user_salon", type_="foreignkey")
    op.create_foreign_key(
        op.f("user_salon_user_id_fkey"),
        source_table="user_salon",
        referent_table="user",
        local_cols=["user_id"],
        remote_cols=["user_id"],
        ondelete="CASCADE",
    )

    # Переименовать таблицу обратно users → user
    op.rename_table("users", "user")
