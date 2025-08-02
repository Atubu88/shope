"""add user_salon link tables

Revision ID: 8d94c90d94b5
Revises:     b99bca9922b3
Create Date: 2025-08-02 10:15:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision: str = "8d94c90d94b5"
down_revision: Union[str, Sequence[str], None] = "b99bca9922b3"
branch_labels = depends_on = None


# ───────────────────────── upgrade ──────────────────────────
def upgrade() -> None:
    conn = op.get_bind()

    # 0. ── таблица-связка user_salon ────────────────────────────────────────
    op.create_table(
        "user_salon",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("salon_id", sa.Integer(),  nullable=False),
        sa.Column("first_name", sa.String(150)),
        sa.Column("last_name",  sa.String(150)),
        sa.Column("phone",      sa.String(13)),
        sa.Column("is_salon_admin", sa.Boolean(),
                  server_default=sa.false(), nullable=False),
        sa.Column("created", sa.DateTime(),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated", sa.DateTime(),
                  server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"],  ["user.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["salon_id"], ["salon.id"],     ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "salon_id", name="uq_user_salon"),
    )

    # 1. ── чистим user ───────────────────────────────────────────────────────
    with op.batch_alter_table("user") as b:
        b.drop_constraint("user_salon_id_fkey", type_="foreignkey")
        b.drop_column("first_name")
        b.drop_column("last_name")
        b.drop_column("phone")
        b.drop_column("salon_id")
        b.drop_column("is_salon_admin")

    # 2. ── добавляем user_salon_id в cart / orders (пока NULL) ──────────────
    with op.batch_alter_table("cart") as b:
        b.add_column(sa.Column("user_salon_id", sa.Integer()))
    with op.batch_alter_table("orders") as b:
        b.add_column(sa.Column("user_salon_id", sa.Integer()))

    # 3-A. ── создаём отсутствующие пары (user_id, salon_id) по cart ---------
    conn.execute(text("""
        INSERT INTO user_salon (user_id, salon_id)
        SELECT DISTINCT c.user_id, p.salon_id
        FROM cart c
        JOIN product p ON p.id = c.product_id
        LEFT JOIN user_salon us
               ON us.user_id = c.user_id AND us.salon_id = p.salon_id
        WHERE us.id IS NULL
    """))

    # 3-B. ── … и по orders ---------------------------------------------------
    conn.execute(text("""
        INSERT INTO user_salon (user_id, salon_id)
        SELECT DISTINCT o.user_id, o.salon_id
        FROM orders o
        LEFT JOIN user_salon us
               ON us.user_id = o.user_id AND us.salon_id = o.salon_id
        WHERE us.id IS NULL
    """))

    # 3-C. ── заполняем cart.user_salon_id -----------------------------------
    conn.execute(text("""
        UPDATE cart
        SET    user_salon_id = us.id
        FROM   user_salon us, product p
        WHERE  cart.product_id = p.id
          AND  cart.user_id    = us.user_id
          AND  p.salon_id      = us.salon_id
          AND  cart.user_salon_id IS NULL
    """))

    # 3-D. ── заполняем orders.user_salon_id ---------------------------------
    conn.execute(text("""
        UPDATE orders
        SET    user_salon_id = us.id
        FROM   user_salon us
        WHERE  orders.user_id  = us.user_id
          AND  orders.salon_id = us.salon_id
          AND  orders.user_salon_id IS NULL
    """))

    # 3-E. ── удаляем «висящие» записи без ссылки ----------------------------
    conn.execute(text("DELETE FROM cart   WHERE user_salon_id IS NULL"))
    conn.execute(text("DELETE FROM orders WHERE user_salon_id IS NULL"))

    # 4. ── cart: ставим NOT NULL, убираем старые поля, новый FK --------------
    with op.batch_alter_table("cart") as b:
        b.alter_column("user_salon_id", existing_type=sa.Integer(), nullable=False)
        b.drop_constraint("cart_user_id_fkey",  type_="foreignkey")
        # cart_product_id_fkey остаётся, потому что колонка product_id нужная
        b.drop_column("user_id")
        # столбца salon_id в cart уже нет — пропускаем
        b.create_foreign_key(
            "cart_user_salon_id_fkey",
            "user_salon",
            ["user_salon_id"], ["id"],
            ondelete="CASCADE",
        )

    # 5. ── orders: то же самое ---------------------------------------------
    with op.batch_alter_table("orders") as b:
        b.alter_column("user_salon_id", existing_type=sa.Integer(), nullable=False)
        b.drop_constraint("orders_user_id_fkey",  type_="foreignkey")
        b.drop_constraint("orders_salon_id_fkey", type_="foreignkey")
        b.drop_column("user_id")
        b.drop_column("salon_id")
        b.create_foreign_key(
            "orders_user_salon_id_fkey",
            "user_salon",
            ["user_salon_id"], ["id"],
        )


# ──────────────────────── downgrade ────────────────────────
def downgrade() -> None:
    # обратные действия (снятие NOT NULL, возврат столбцов и FK) —
    # оставьте без изменений, либо скопируйте логику из прошлой версии.
    ...
