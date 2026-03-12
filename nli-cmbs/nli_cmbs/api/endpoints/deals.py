from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nli_cmbs.db.models import Deal
from nli_cmbs.db.session import get_session
from nli_cmbs.schemas.deal import DealDetailOut, DealOut
from nli_cmbs.services.metrics import compute_deal_metrics

router = APIRouter()


@router.get("/", response_model=list[DealOut])
async def list_deals(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Deal).order_by(Deal.created_at.desc()))
    deals = result.scalars().all()
    out = []
    for deal in deals:
        metrics = await compute_deal_metrics(session, deal.id)
        out.append(DealOut(
            id=deal.id,
            ticker=deal.ticker,
            trust_name=deal.trust_name,
            depositor_cik=deal.depositor_cik,
            trust_cik=deal.trust_cik,
            issuer_shelf=deal.issuer_shelf,
            issuance_year=deal.issuance_year,
            original_balance=float(deal.original_balance) if deal.original_balance else None,
            loan_count=metrics.loan_count or deal.loan_count,
            total_upb=metrics.total_upb or None,
            delinquency_rate=metrics.delinquency_rate,
            last_filing_date=metrics.last_filing_date,
            created_at=deal.created_at,
            updated_at=deal.updated_at,
        ))
    return out


@router.get("/{ticker}", response_model=DealDetailOut)
async def get_deal_by_ticker(ticker: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Deal).where(Deal.ticker == ticker))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    metrics = await compute_deal_metrics(session, deal.id)
    return DealDetailOut(
        id=deal.id,
        ticker=deal.ticker,
        trust_name=deal.trust_name,
        depositor_cik=deal.depositor_cik,
        trust_cik=deal.trust_cik,
        issuer_shelf=deal.issuer_shelf,
        issuance_year=deal.issuance_year,
        original_balance=float(deal.original_balance) if deal.original_balance else None,
        loan_count=metrics.loan_count or deal.loan_count,
        total_upb=metrics.total_upb or None,
        wa_coupon=metrics.wa_coupon or None,
        wa_remaining_term=metrics.wa_remaining_term,
        delinquency_rate=metrics.delinquency_rate,
        delinquency_by_status=metrics.delinquency_by_status or None,
        last_filing_date=metrics.last_filing_date,
        created_at=deal.created_at,
        updated_at=deal.updated_at,
    )
