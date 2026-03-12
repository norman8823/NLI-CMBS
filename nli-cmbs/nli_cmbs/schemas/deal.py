from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DealOut(BaseModel):
    id: UUID
    ticker: str
    trust_name: str
    depositor_cik: str
    trust_cik: str | None = None
    issuer_shelf: str
    issuance_year: int
    original_balance: float | None = None
    loan_count: int | None = None
    total_upb: float | None = None
    delinquency_rate: float | None = None
    last_filing_date: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DealDetailOut(BaseModel):
    id: UUID
    ticker: str
    trust_name: str
    depositor_cik: str
    trust_cik: str | None = None
    issuer_shelf: str
    issuance_year: int
    original_balance: float | None = None
    loan_count: int | None = None
    total_upb: float | None = None
    wa_coupon: float | None = None
    wa_remaining_term: float | None = None
    delinquency_rate: float | None = None
    delinquency_by_status: dict[str, int] | None = None
    last_filing_date: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
