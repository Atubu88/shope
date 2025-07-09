from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'salon',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(length=100), nullable=False, unique=True),
    )
    op.add_column('banner', sa.Column('salon_id', sa.Integer, sa.ForeignKey('salon.id'), nullable=False, server_default='1'))
    op.add_column('category', sa.Column('salon_id', sa.Integer, sa.ForeignKey('salon.id'), nullable=False, server_default='1'))
    op.add_column('product', sa.Column('salon_id', sa.Integer, sa.ForeignKey('salon.id'), nullable=False, server_default='1'))
    op.add_column('user', sa.Column('salon_id', sa.Integer, sa.ForeignKey('salon.id'), nullable=True))


def downgrade():
    op.drop_column('user', 'salon_id')
    op.drop_column('product', 'salon_id')
    op.drop_column('category', 'salon_id')
    op.drop_column('banner', 'salon_id')
    op.drop_table('salon')
