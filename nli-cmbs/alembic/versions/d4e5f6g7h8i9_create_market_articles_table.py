"""Create market_articles table

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-03-18
"""

from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6g7h8i9'
down_revision: Union[str, None] = 'c3d4e5f6g7h8'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        'market_articles',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('url', sa.String(2000), unique=True, nullable=False),
        sa.Column('title', sa.String(1000), nullable=False),
        sa.Column('author', sa.String(300), nullable=True),
        sa.Column('published_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('excerpt', sa.Text, nullable=True),
        sa.Column('body_text', sa.Text, nullable=True),
        sa.Column('source', sa.String(50), nullable=False, server_default='Trepp'),
        sa.Column('summary', sa.Text, nullable=True),
        sa.Column('key_themes', JSONB, nullable=True),
        sa.Column('ingested_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    op.create_index('ix_market_articles_url', 'market_articles', ['url'], unique=True)
    op.create_index('ix_market_articles_published_date', 'market_articles', ['published_date'])
    op.create_index('ix_market_articles_source', 'market_articles', ['source'])


def downgrade() -> None:
    op.drop_table('market_articles')
