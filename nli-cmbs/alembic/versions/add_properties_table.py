"""Add properties table for multi-property loans

Revision ID: add_properties_table
Revises: 
Create Date: 2026-03-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_properties_table'
down_revision = '8697a13d425a'  # Update this to your latest migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add property_count to loans table
    op.add_column('loans', sa.Column('property_count', sa.Integer(), nullable=True, server_default='1'))
    
    # Create properties table
    op.create_table(
        'properties',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('loan_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('property_id', sa.String(50), nullable=False),  # e.g., "1-001", "1-002"
        sa.Column('property_name', sa.String(500), nullable=True),
        sa.Column('property_address', sa.String(500), nullable=True),
        sa.Column('property_city', sa.String(200), nullable=True),
        sa.Column('property_state', sa.String(2), nullable=True),
        sa.Column('property_zip', sa.String(20), nullable=True),
        sa.Column('property_type', sa.String(100), nullable=True),
        sa.Column('property_type_code', sa.String(10), nullable=True),
        sa.Column('net_rentable_sq_ft', sa.Numeric(20, 2), nullable=True),
        sa.Column('year_built', sa.Integer(), nullable=True),
        sa.Column('valuation_securitization', sa.Numeric(20, 2), nullable=True),
        sa.Column('valuation_securitization_date', sa.Date(), nullable=True),
        sa.Column('occupancy_securitization', sa.Numeric(5, 4), nullable=True),
        sa.Column('occupancy_most_recent', sa.Numeric(5, 4), nullable=True),
        sa.Column('noi_securitization', sa.Numeric(20, 2), nullable=True),
        sa.Column('noi_most_recent', sa.Numeric(20, 2), nullable=True),
        sa.Column('ncf_securitization', sa.Numeric(20, 2), nullable=True),
        sa.Column('ncf_most_recent', sa.Numeric(20, 2), nullable=True),
        sa.Column('dscr_noi_securitization', sa.Numeric(10, 4), nullable=True),
        sa.Column('dscr_noi_most_recent', sa.Numeric(10, 4), nullable=True),
        sa.Column('dscr_ncf_securitization', sa.Numeric(10, 4), nullable=True),
        sa.Column('dscr_ncf_most_recent', sa.Numeric(10, 4), nullable=True),
        sa.Column('revenue_most_recent', sa.Numeric(20, 2), nullable=True),
        sa.Column('operating_expenses_most_recent', sa.Numeric(20, 2), nullable=True),
        sa.Column('largest_tenant', sa.String(300), nullable=True),
        sa.Column('second_largest_tenant', sa.String(300), nullable=True),
        sa.Column('third_largest_tenant', sa.String(300), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['loan_id'], ['loans.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_properties_loan_id', 'properties', ['loan_id'])
    op.create_index('ix_properties_property_name', 'properties', ['property_name'])
    op.create_index('ix_properties_property_city', 'properties', ['property_city'])
    op.create_index('ix_properties_property_state', 'properties', ['property_state'])
    op.create_index('uq_properties_loan_property_id', 'properties', ['loan_id', 'property_id'], unique=True)


def downgrade() -> None:
    op.drop_index('uq_properties_loan_property_id', table_name='properties')
    op.drop_index('ix_properties_property_state', table_name='properties')
    op.drop_index('ix_properties_property_city', table_name='properties')
    op.drop_index('ix_properties_property_name', table_name='properties')
    op.drop_index('ix_properties_loan_id', table_name='properties')
    op.drop_table('properties')
    op.drop_column('loans', 'property_count')
