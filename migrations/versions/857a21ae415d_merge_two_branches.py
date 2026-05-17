"""merge two branches

Revision ID: 857a21ae415d
Revises: a7c9d2f4b601, c4d2f8305a00
Create Date: 2026-05-18 02:00:39.820492

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '857a21ae415d'
down_revision = ('a7c9d2f4b601', 'c4d2f8305a00')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
