from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nli_cmbs.db.models import Deal, Loan
from nli_cmbs.db.session import get_session
from nli_cmbs.schemas.loan import LoanOut, LoanSearchOut

router = APIRouter()


@router.get("/search", response_model=list[LoanSearchOut])
async def search_loans(
    property_name: str | None = Query(None, description="Partial property name (case-insensitive)"),
    property_city: str | None = Query(None, description="Partial city name (case-insensitive)"),
    state: str | None = Query(None, description="Two-letter state code, e.g. TX"),
    borrower_name: str | None = Query(None, description="Partial borrower name (case-insensitive)"),
    session: AsyncSession = Depends(get_session),
):
    if not any([property_name, property_city, state, borrower_name]):
        raise HTTPException(status_code=422, detail="At least one search parameter is required")

    stmt = select(Loan, Deal.ticker).join(Deal, Loan.deal_id == Deal.id)

    if property_name:
        stmt = stmt.where(Loan.property_name.ilike(f"%{property_name}%"))
    if property_city:
        stmt = stmt.where(Loan.property_city.ilike(f"%{property_city}%"))
    if state:
        stmt = stmt.where(Loan.property_state.ilike(state))
    if borrower_name:
        stmt = stmt.where(Loan.borrower_name.ilike(f"%{borrower_name}%"))

    result = await session.execute(stmt)
    rows = result.all()

    return [
        LoanSearchOut(
            id=loan.id,
            deal_id=loan.deal_id,
            deal_ticker=ticker,
            prospectus_loan_id=loan.prospectus_loan_id,
            asset_number=loan.asset_number,
            original_loan_amount=float(loan.original_loan_amount),
            property_type=loan.property_type,
            property_name=loan.property_name,
            property_city=loan.property_city,
            property_state=loan.property_state,
            borrower_name=loan.borrower_name,
        )
        for loan, ticker in rows
    ]


@router.get("/{ticker}/loans", response_model=list[LoanOut])
async def list_loans_by_ticker(ticker: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Deal).where(Deal.ticker == ticker))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    result = await session.execute(select(Loan).where(Loan.deal_id == deal.id).order_by(Loan.asset_number))
    return result.scalars().all()
