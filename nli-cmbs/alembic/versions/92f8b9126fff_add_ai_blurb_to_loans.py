"""add ai_blurb to loans

Revision ID: 92f8b9126fff
Revises: b2c3d4e5f6g7
Create Date: 2026-03-17 17:15:02.845045

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '92f8b9126fff'
down_revision: Union[str, None] = 'b2c3d4e5f6g7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("loans", sa.Column("ai_blurb", sa.Text(), nullable=True))
    op.add_column(
        "loans",
        sa.Column(
            "ai_blurb_generated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("loans", "ai_blurb_generated_at")
    op.drop_column("loans", "ai_blurb")
