from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nli_cmbs.db.models import Property, PropertySnapshot
from nli_cmbs.db.session import get_session
from nli_cmbs.schemas.property import PropertyHistoryResponse, PropertySnapshotSchema

router = APIRouter()


@router.get("/{property_id}/history", response_model=PropertyHistoryResponse)
async def get_property_history(
    property_id: UUID,
    db: AsyncSession = Depends(get_session),
):
    """Get historical snapshots for a property (for sparkline charts)."""

    # Verify property exists
    prop = await db.get(Property, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    # Get snapshots ordered by date
    query = (
        select(PropertySnapshot)
        .where(PropertySnapshot.property_id == property_id)
        .order_by(PropertySnapshot.reporting_period_end.asc())
    )

    result = await db.execute(query)
    snapshots = result.scalars().all()

    return PropertyHistoryResponse(
        property_id=property_id,
        property_name=prop.property_name,
        snapshot_count=len(snapshots),
        snapshots=[
            PropertySnapshotSchema(
                reporting_period_end=s.reporting_period_end,
                occupancy=float(s.occupancy) if s.occupancy else None,
                noi=float(s.noi) if s.noi else None,
                ncf=float(s.ncf) if s.ncf else None,
                dscr_noi=float(s.dscr_noi) if s.dscr_noi else None,
                dscr_ncf=float(s.dscr_ncf) if s.dscr_ncf else None,
                valuation_amount=float(s.valuation_amount) if s.valuation_amount else None,
            )
            for s in snapshots
        ],
    )
