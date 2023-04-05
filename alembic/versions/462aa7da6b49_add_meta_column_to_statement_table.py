"""Add meta column to Statement table

Revision ID: 462aa7da6b49
Revises: a3cf23c5fed3
Create Date: 2023-04-04 22:05:12.990162

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import JSON


# revision identifiers, used by Alembic.
revision = '462aa7da6b49'
down_revision = 'a3cf23c5fed3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('statement', sa.Column('meta', JSON, nullable=True))


def downgrade() -> None:
    op.drop_column('statement', 'meta')
