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
    property_name: str | None = None
    property_city: str | None = None
    property_state: str | None = None
    property_type: str | None = None
    borrower_name: str | None = None
    maturity_date: date | None = None
    original_term_months: int | None = None
    original_amortization_term_months: int | None = None
    original_interest_rate: Decimal | None = None


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


class ParsedFiling(BaseModel):
    """Complete parsed result from an EX-102 XML file."""

    loans: list[ParsedLoan] = []
    snapshots: dict[str, ParsedLoanSnapshot] = {}
    reporting_period_start: date | None = None
    reporting_period_end: date | None = None
    total_loan_count: int = 0
    parse_errors: list[str] = []
