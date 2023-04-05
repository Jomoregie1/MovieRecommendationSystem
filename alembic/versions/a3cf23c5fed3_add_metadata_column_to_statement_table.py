"""Add metadata column to Statement table

Revision ID: a3cf23c5fed3
Revises: 
Create Date: 2023-04-04 21:59:22.265877

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import JSON


# revision identifiers, used by Alembic.
revision = 'a3cf23c5fed3'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('statement', sa.Column('metadata', JSON, nullable=True))


def downgrade() -> None:
    op.drop_column('statement', 'metadata')
