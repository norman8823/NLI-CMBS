"""add parent loan linking for pari passu / A-B note structures

Revision ID: a1b2c3d4e5f6
Revises: 0073a4de655f
Create Date: 2026-03-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '0073a4de655f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add parent_loan_id column
    op.add_column(
        "loans",
        sa.Column("parent_loan_id", UUID(as_uuid=True), sa.ForeignKey("loans.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_loans_parent_loan_id", "loans", ["parent_loan_id"])

    # 2. Populate parent_loan_id by matching "1A"→"1", "22B"→"22", etc.
    op.execute("""
        UPDATE loans child
        SET parent_loan_id = parent.id
        FROM loans parent
        WHERE child.deal_id = parent.deal_id
          AND child.prospectus_loan_id ~ '^\\d+[A-Za-z]+'
          AND parent.prospectus_loan_id = REGEXP_REPLACE(child.prospectus_loan_id, '[A-Za-z]+', '')
    """)

    # 3. Delete junk property records (NA / empty names from pari passu notes)
    op.execute("""
        DELETE FROM properties
        WHERE property_name IS NULL
           OR property_name = 'NA'
           OR TRIM(property_name) = ''
    """)


def downgrade() -> None:
    # Remove junk cleanup is not reversible (data already deleted),
    # but we can reverse the schema change
    op.drop_index("ix_loans_parent_loan_id", table_name="loans")
    op.drop_column("loans", "parent_loan_id")
