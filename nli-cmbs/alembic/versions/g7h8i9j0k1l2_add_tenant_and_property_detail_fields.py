"""Add tenant and property detail fields

Revision ID: g7h8i9j0k1l2
Revises: f6g7h8i9j0k1
Create Date: 2026-03-18
"""

from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = 'g7h8i9j0k1l2'
down_revision: Union[str, None] = 'f6g7h8i9j0k1'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Tenant detail fields
    op.add_column('properties', sa.Column('largest_tenant_sf', sa.Integer(), nullable=True))
    op.add_column('properties', sa.Column('largest_tenant_lease_expiration', sa.Date(), nullable=True))
    op.add_column('properties', sa.Column('largest_tenant_pct_nra', sa.Numeric(5, 2), nullable=True))

    op.add_column('properties', sa.Column('second_largest_tenant_sf', sa.Integer(), nullable=True))
    op.add_column('properties', sa.Column('second_largest_tenant_lease_expiration', sa.Date(), nullable=True))
    op.add_column('properties', sa.Column('second_largest_tenant_pct_nra', sa.Numeric(5, 2), nullable=True))

    op.add_column('properties', sa.Column('third_largest_tenant_sf', sa.Integer(), nullable=True))
    op.add_column('properties', sa.Column('third_largest_tenant_lease_expiration', sa.Date(), nullable=True))
    op.add_column('properties', sa.Column('third_largest_tenant_pct_nra', sa.Numeric(5, 2), nullable=True))

    # Additional property details
    op.add_column('properties', sa.Column('year_renovated', sa.Integer(), nullable=True))
    op.add_column('properties', sa.Column('number_of_units', sa.Integer(), nullable=True))
    op.add_column('properties', sa.Column('appraised_value', sa.Numeric(20, 2), nullable=True))
    op.add_column('properties', sa.Column('appraisal_date', sa.Date(), nullable=True))
    op.add_column('properties', sa.Column('noi_date', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('properties', 'noi_date')
    op.drop_column('properties', 'appraisal_date')
    op.drop_column('properties', 'appraised_value')
    op.drop_column('properties', 'number_of_units')
    op.drop_column('properties', 'year_renovated')
    op.drop_column('properties', 'third_largest_tenant_pct_nra')
    op.drop_column('properties', 'third_largest_tenant_lease_expiration')
    op.drop_column('properties', 'third_largest_tenant_sf')
    op.drop_column('properties', 'second_largest_tenant_pct_nra')
    op.drop_column('properties', 'second_largest_tenant_lease_expiration')
    op.drop_column('properties', 'second_largest_tenant_sf')
    op.drop_column('properties', 'largest_tenant_pct_nra')
    op.drop_column('properties', 'largest_tenant_lease_expiration')
    op.drop_column('properties', 'largest_tenant_sf')
