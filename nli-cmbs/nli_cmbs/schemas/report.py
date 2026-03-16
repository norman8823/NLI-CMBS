from datetime import datetime

from pydantic import BaseModel


class ReportResponse(BaseModel):
    deal_ticker: str
    report_text: str
    generated_at: datetime
    model_used: str
    filing_date: str
    accession_number: str
    cached: bool = False
