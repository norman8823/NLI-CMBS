from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class PropertySnapshotSchema(BaseModel):
    reporting_period_end: date
    occupancy: Optional[float] = None
    noi: Optional[float] = None
    ncf: Optional[float] = None
    dscr_noi: Optional[float] = None
    dscr_ncf: Optional[float] = None
    valuation_amount: Optional[float] = None


class PropertyHistoryResponse(BaseModel):
    property_id: UUID
    property_name: Optional[str]
    snapshot_count: int
    snapshots: list[PropertySnapshotSchema]
