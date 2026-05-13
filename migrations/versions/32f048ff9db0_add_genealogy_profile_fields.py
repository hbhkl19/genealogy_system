"""add genealogy profile fields

Revision ID: 32f048ff9db0
Revises: 8ef1ddc6ab24
Create Date: 2026-05-13 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "32f048ff9db0"
down_revision = "8ef1ddc6ab24"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("genealogies", schema=None) as batch_op:
        batch_op.add_column(sa.Column("surname", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("revision_year", sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table("genealogies", schema=None) as batch_op:
        batch_op.drop_column("revision_year")
        batch_op.drop_column("surname")
