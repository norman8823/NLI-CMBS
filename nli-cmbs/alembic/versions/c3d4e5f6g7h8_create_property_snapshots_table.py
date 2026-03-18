"""Create property_snapshots table

Revision ID: c3d4e5f6g7h8
Revises: 92f8b9126fff
Create Date: 2026-03-18
"""

from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6g7h8'
down_revision: Union[str, None] = '92f8b9126fff'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        'property_snapshots',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column(
            'property_id', UUID(as_uuid=True),
            sa.ForeignKey('properties.id', ondelete='CASCADE'), nullable=False,
        ),
        sa.Column('filing_id', UUID(as_uuid=True), sa.ForeignKey('filings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reporting_period_end', sa.Date, nullable=False),

        # Financials
        sa.Column('occupancy', sa.Numeric(7, 4), nullable=True),
        sa.Column('noi', sa.Numeric(20, 2), nullable=True),
        sa.Column('ncf', sa.Numeric(20, 2), nullable=True),
        sa.Column('revenue', sa.Numeric(20, 2), nullable=True),
        sa.Column('operating_expenses', sa.Numeric(20, 2), nullable=True),
        sa.Column('dscr_noi', sa.Numeric(10, 4), nullable=True),
        sa.Column('dscr_ncf', sa.Numeric(10, 4), nullable=True),

        # Valuation
        sa.Column('valuation_amount', sa.Numeric(20, 2), nullable=True),
        sa.Column('valuation_date', sa.Date, nullable=True),
        sa.Column('valuation_source', sa.String(50), nullable=True),

        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),

        sa.UniqueConstraint('property_id', 'filing_id', name='uq_property_snapshots_property_filing'),
    )

    op.create_index('idx_property_snapshots_property_id', 'property_snapshots', ['property_id'])
    op.create_index('idx_property_snapshots_filing_id', 'property_snapshots', ['filing_id'])
    op.create_index('idx_property_snapshots_period', 'property_snapshots', ['reporting_period_end'])


def downgrade() -> None:
    op.drop_table('property_snapshots')
