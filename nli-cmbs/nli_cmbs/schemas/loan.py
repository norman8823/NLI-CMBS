from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class SnapshotOut(BaseModel):
    ending_balance: float | None = None
    beginning_balance: float | None = None
    current_interest_rate: float | None = None
    delinquency_status: str | None = None
    scheduled_interest_amount: float | None = None
    scheduled_principal_amount: float | None = None
    actual_interest_collected: float | None = None
    actual_principal_collected: float | None = None
    reporting_period_end_date: date | None = None
    # Credit metrics — current/mostRecent
    dscr_noi: float | None = None
    dscr_ncf: float | None = None
    noi: float | None = None
    ncf: float | None = None
    occupancy: float | None = None
    revenue: float | None = None
    operating_expenses: float | None = None
    debt_service: float | None = None
    appraised_value: float | None = None
    # Credit metrics — securitization-time
    dscr_noi_at_securitization: float | None = None
    dscr_ncf_at_securitization: float | None = None
    noi_at_securitization: float | None = None
    ncf_at_securitization: float | None = None
    occupancy_at_securitization: float | None = None
    appraised_value_at_securitization: float | None = None

    model_config = {"from_attributes": True}


class LoanOut(BaseModel):
    id: UUID
    deal_id: UUID
    prospectus_loan_id: str
    asset_number: int
    originator_name: str | None = None
    original_loan_amount: float
    origination_date: date | None = None
    maturity_date: date | None = None
    original_term_months: int | None = None
    original_amortization_term_months: int | None = None
    original_interest_rate: float | None = None
    property_type: str | None = None
    property_name: str | None = None
    property_city: str | None = None
    property_state: str | None = None
    borrower_name: str | None = None
    interest_only_indicator: bool | None = None
    balloon_indicator: bool | None = None
    lien_position: str | None = None
    created_at: datetime
    latest_snapshot: SnapshotOut | None = None

    model_config = {"from_attributes": True}


class LoanSearchOut(BaseModel):
    id: UUID
    deal_id: UUID
    deal_ticker: str | None = None
    prospectus_loan_id: str
    asset_number: int
    original_loan_amount: float
    property_type: str | None = None
    property_name: str | None = None
    property_city: str | None = None
    property_state: str | None = None
    borrower_name: str | None = None

    model_config = {"from_attributes": True}
