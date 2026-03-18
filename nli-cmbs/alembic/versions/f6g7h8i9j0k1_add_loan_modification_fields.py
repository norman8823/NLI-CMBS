"""Add loan modification fields

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2026-03-18
"""

from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = 'f6g7h8i9j0k1'
down_revision: Union[str, None] = 'e5f6g7h8i9j0'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column('loans', sa.Column('is_modified', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('loans', sa.Column('modification_date', sa.Date(), nullable=True))
    op.add_column('loans', sa.Column('modification_code', sa.String(100), nullable=True))
    op.add_column('loans', sa.Column('modified_interest_rate', sa.Numeric(7, 4), nullable=True))
    op.add_column('loans', sa.Column('modified_maturity_date', sa.Date(), nullable=True))
    op.add_column('loans', sa.Column('modified_payment_amount', sa.Numeric(16, 2), nullable=True))
    op.add_column('loans', sa.Column('principal_forgiveness_amount', sa.Numeric(16, 2), nullable=True))
    op.add_column('loans', sa.Column('principal_deferral_amount', sa.Numeric(16, 2), nullable=True))
    op.add_column('loans', sa.Column('deferred_interest_amount', sa.Numeric(16, 2), nullable=True))

    op.create_index('ix_loans_is_modified', 'loans', ['is_modified'])


def downgrade() -> None:
    op.drop_index('ix_loans_is_modified', table_name='loans')
    op.drop_column('loans', 'deferred_interest_amount')
    op.drop_column('loans', 'principal_deferral_amount')
    op.drop_column('loans', 'principal_forgiveness_amount')
    op.drop_column('loans', 'modified_payment_amount')
    op.drop_column('loans', 'modified_maturity_date')
    op.drop_column('loans', 'modified_interest_rate')
    op.drop_column('loans', 'modification_code')
    op.drop_column('loans', 'modification_date')
    op.drop_column('loans', 'is_modified')
