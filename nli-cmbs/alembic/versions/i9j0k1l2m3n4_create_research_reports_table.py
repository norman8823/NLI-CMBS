"""create research_reports table

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-03-20 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'i9j0k1l2m3n4'
down_revision: Union[str, None] = 'h8i9j0k1l2m3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('research_reports',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('filename', sa.String(length=500), nullable=False),
        sa.Column('title', sa.String(length=1000), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('published_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('full_text', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('key_themes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ingested_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_research_reports_filename', 'research_reports', ['filename'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_research_reports_filename', table_name='research_reports')
    op.drop_table('research_reports')
