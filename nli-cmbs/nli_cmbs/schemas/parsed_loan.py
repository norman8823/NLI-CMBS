"""Pydantic models for parsed EX-102 loan data."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class ParsedLoan(BaseModel):
    """Static loan-level data from an EX-102 filing."""

    prospectus_loan_id: str
    asset_number: int | None = None
    originator_name: str | None = None
    original_loan_amount: Decimal | None = None
    origination_date: date | None = None
    # Primary property info (for single-property loans) or portfolio summary (for multi-property)
    property_name: str | None = None
    property_city: str | None = None
    property_state: str | None = None
    property_type: str | None = None
    borrower_name: str | None = None
    maturity_date: date | None = None
    original_term_months: int | None = None
    original_amortization_term_months: int | None = None
    original_interest_rate: Decimal | None = None
    interest_only_indicator: bool | None = None
    balloon_indicator: bool | None = None
    lien_position: str | None = None
    # Multi-property indicator (updated after parsing properties)
    property_count: int = 1

    # Modification fields
    is_modified: bool = False
    modification_date: date | None = None
    modification_code: str | None = None
    modified_interest_rate: Decimal | None = None
    modified_maturity_date: date | None = None
    modified_payment_amount: Decimal | None = None
    principal_forgiveness_amount: Decimal | None = None
    principal_deferral_amount: Decimal | None = None
    deferred_interest_amount: Decimal | None = None


class ParsedProperty(BaseModel):
    """Individual property within a multi-property loan.
    
    For single-property loans, property info is stored directly on ParsedLoan.
    For multi-property loans, each property gets a ParsedProperty record.
    
    Property IDs follow the format "{loan_id}-{property_index}" e.g., "1-001", "1-002".
    """
    parent_loan_id: str  # The loan this property belongs to
    property_id: str  # e.g., "1-001"
    
    # Property identification
    property_name: str | None = None
    property_address: str | None = None
    property_city: str | None = None
    property_state: str | None = None
    property_zip: str | None = None
    property_type: str | None = None
    
    # Physical characteristics
    net_rentable_sq_ft: Decimal | None = None
    year_built: int | None = None
    
    # Valuation
    valuation_securitization: Decimal | None = None
    valuation_securitization_date: date | None = None
    
    # Occupancy
    occupancy_securitization: Decimal | None = None
    occupancy_most_recent: Decimal | None = None
    
    # NOI / NCF
    noi_securitization: Decimal | None = None
    noi_most_recent: Decimal | None = None
    ncf_securitization: Decimal | None = None
    ncf_most_recent: Decimal | None = None
    
    # DSCR (at property level for multi-property loans)
    dscr_noi_securitization: Decimal | None = None
    dscr_noi_most_recent: Decimal | None = None
    dscr_ncf_securitization: Decimal | None = None
    dscr_ncf_most_recent: Decimal | None = None
    
    # Financials
    revenue_most_recent: Decimal | None = None
    operating_expenses_most_recent: Decimal | None = None
    
    # Tenants
    largest_tenant: str | None = None
    largest_tenant_sf: int | None = None
    largest_tenant_lease_expiration: date | None = None
    largest_tenant_pct_nra: Decimal | None = None

    second_largest_tenant: str | None = None
    second_largest_tenant_sf: int | None = None
    second_largest_tenant_lease_expiration: date | None = None
    second_largest_tenant_pct_nra: Decimal | None = None

    third_largest_tenant: str | None = None
    third_largest_tenant_sf: int | None = None
    third_largest_tenant_lease_expiration: date | None = None
    third_largest_tenant_pct_nra: Decimal | None = None

    # Additional property details
    year_renovated: int | None = None
    number_of_units: int | None = None
    appraised_value: Decimal | None = None
    appraisal_date: date | None = None
    noi_date: date | None = None


class ParsedLoanSnapshot(BaseModel):
    """Periodic reporting snapshot for a loan."""

    reporting_period_begin_date: date | None = None
    reporting_period_end_date: date | None = None
    beginning_balance: Decimal | None = None
    ending_balance: Decimal | None = None
    current_interest_rate: Decimal | None = None
    scheduled_interest_amount: Decimal | None = None
    scheduled_principal_amount: Decimal | None = None
    actual_interest_collected: Decimal | None = None
    actual_principal_collected: Decimal | None = None
    actual_other_collected: Decimal | None = None
    servicer_advanced_amount: Decimal | None = None
    delinquency_status: str | None = None
    interest_paid_through_date: date | None = None
    next_payment_amount_due: Decimal | None = None
    # Current/most recent credit metrics
    dscr_noi: Decimal | None = None
    dscr_ncf: Decimal | None = None
    noi: Decimal | None = None
    ncf: Decimal | None = None
    occupancy: Decimal | None = None
    revenue: Decimal | None = None
    operating_expenses: Decimal | None = None
    debt_service: Decimal | None = None
    appraised_value: Decimal | None = None
    # Securitization-time credit metrics
    dscr_noi_at_securitization: Decimal | None = None
    dscr_ncf_at_securitization: Decimal | None = None
    noi_at_securitization: Decimal | None = None
    ncf_at_securitization: Decimal | None = None
    occupancy_at_securitization: Decimal | None = None
    appraised_value_at_securitization: Decimal | None = None


class ParsedFiling(BaseModel):
    """Complete parsed result from an EX-102 XML file."""

    loans: list[ParsedLoan] = []
    snapshots: dict[str, ParsedLoanSnapshot] = {}
    properties: dict[str, list[ParsedProperty]] = {}  # loan_id -> list of properties
    reporting_period_start: date | None = None
    reporting_period_end: date | None = None
    total_loan_count: int = 0
    parse_errors: list[str] = []
