"""fix occupancy column precision

Revision ID: 0073a4de655f
Revises: add_properties_table
Create Date: 2026-03-13 17:10:25.530135

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0073a4de655f'
down_revision: Union[str, None] = 'add_properties_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # loan_snapshots: occupancy reported as percentage (e.g. 95.5), not decimal
    op.alter_column(
        "loan_snapshots", "occupancy",
        type_=sa.Numeric(7, 4),
        existing_type=sa.Numeric(5, 4),
    )
    op.alter_column(
        "loan_snapshots", "occupancy_at_securitization",
        type_=sa.Numeric(7, 4),
        existing_type=sa.Numeric(5, 4),
    )
    # properties table has the same issue
    op.alter_column(
        "properties", "occupancy_securitization",
        type_=sa.Numeric(7, 4),
        existing_type=sa.Numeric(5, 4),
    )
    op.alter_column(
        "properties", "occupancy_most_recent",
        type_=sa.Numeric(7, 4),
        existing_type=sa.Numeric(5, 4),
    )


def downgrade() -> None:
    op.alter_column(
        "loan_snapshots", "occupancy",
        type_=sa.Numeric(5, 4),
        existing_type=sa.Numeric(7, 4),
    )
    op.alter_column(
        "loan_snapshots", "occupancy_at_securitization",
        type_=sa.Numeric(5, 4),
        existing_type=sa.Numeric(7, 4),
    )
    op.alter_column(
        "properties", "occupancy_securitization",
        type_=sa.Numeric(5, 4),
        existing_type=sa.Numeric(7, 4),
    )
    op.alter_column(
        "properties", "occupancy_most_recent",
        type_=sa.Numeric(5, 4),
        existing_type=sa.Numeric(7, 4),
    )
