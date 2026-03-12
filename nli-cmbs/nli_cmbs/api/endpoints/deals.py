from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nli_cmbs.db.models import Deal
from nli_cmbs.db.session import get_session
from nli_cmbs.schemas.deal import DealOut

router = APIRouter()


@router.get("/", response_model=list[DealOut])
async def list_deals(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Deal).order_by(Deal.created_at.desc()))
    return result.scalars().all()


@router.get("/{deal_id}", response_model=DealOut)
async def get_deal(deal_id: UUID, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Deal not found")
    return deal
