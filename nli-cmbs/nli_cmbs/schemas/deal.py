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
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
