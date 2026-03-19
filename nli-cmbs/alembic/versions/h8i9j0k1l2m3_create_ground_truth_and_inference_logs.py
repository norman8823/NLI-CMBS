"""Create ground_truth_entries and inference_logs tables

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-03-18
"""

from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = 'h8i9j0k1l2m3'
down_revision: Union[str, None] = 'g7h8i9j0k1l2'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # ground_truth_entries table
    op.create_table(
        'ground_truth_entries',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('deal_id', UUID(as_uuid=True), sa.ForeignKey('deals.id'), nullable=False),
        sa.Column('loan_id', UUID(as_uuid=True), sa.ForeignKey('loans.id'), nullable=False),
        sa.Column('filing_id', UUID(as_uuid=True), sa.ForeignKey('filings.id'), nullable=False),
        sa.Column('field_name', sa.String(100), nullable=False),
        sa.Column('field_value', sa.Text, nullable=False),
        sa.Column('field_type', sa.String(20), nullable=False),
        sa.Column('tier', sa.Integer, nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )
    op.create_index('ix_gt_deal_loan_field', 'ground_truth_entries', ['deal_id', 'loan_id', 'field_name'])
    op.create_index('ix_gt_filing', 'ground_truth_entries', ['filing_id'])
    op.create_index('ix_gt_tier', 'ground_truth_entries', ['tier'])

    # inference_logs table
    op.create_table(
        'inference_logs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('task_type', sa.String(50), nullable=False),
        sa.Column('deal_id', UUID(as_uuid=True), sa.ForeignKey('deals.id'), nullable=True),
        sa.Column('loan_id', UUID(as_uuid=True), sa.ForeignKey('loans.id'), nullable=True),
        sa.Column('filing_id', UUID(as_uuid=True), sa.ForeignKey('filings.id'), nullable=True),
        sa.Column('model_id', sa.String(100), nullable=False),
        sa.Column('system_prompt', sa.Text, nullable=False),
        sa.Column('user_prompt', sa.Text, nullable=False),
        sa.Column('raw_response', sa.Text, nullable=False),
        sa.Column('prompt_tokens', sa.Integer, nullable=True),
        sa.Column('completion_tokens', sa.Integer, nullable=True),
        sa.Column('latency_ms', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )
    op.create_index('ix_inference_logs_model', 'inference_logs', ['model_id'])
    op.create_index('ix_inference_logs_task', 'inference_logs', ['task_type'])
    op.create_index('ix_inference_logs_deal', 'inference_logs', ['deal_id'])
    op.create_index('ix_inference_logs_created', 'inference_logs', ['created_at'])


def downgrade() -> None:
    op.drop_table('inference_logs')
    op.drop_table('ground_truth_entries')
