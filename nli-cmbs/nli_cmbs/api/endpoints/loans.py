from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nli_cmbs.db.models import Deal, Filing, Loan, LoanSnapshot
from nli_cmbs.db.session import get_session
from nli_cmbs.schemas.loan import LoanOut, LoanSearchOut, SnapshotOut

router = APIRouter()


def _to_float(val) -> float | None:
    return float(val) if val is not None else None


def _latest_snapshot(loan: Loan) -> SnapshotOut | None:
    """Get the most recent snapshot for a loan."""
    if not loan.snapshots:
        return None
    latest = max(loan.snapshots, key=lambda s: s.reporting_period_end_date)
    return SnapshotOut(
        ending_balance=_to_float(latest.ending_balance),
        beginning_balance=_to_float(latest.beginning_balance),
        current_interest_rate=_to_float(latest.current_interest_rate),
        delinquency_status=latest.delinquency_status,
        scheduled_interest_amount=_to_float(latest.scheduled_interest_amount),
        scheduled_principal_amount=_to_float(latest.scheduled_principal_amount),
        actual_interest_collected=_to_float(latest.actual_interest_collected),
        actual_principal_collected=_to_float(latest.actual_principal_collected),
        reporting_period_end_date=latest.reporting_period_end_date,
        dscr_noi=_to_float(latest.dscr_noi),
        dscr_ncf=_to_float(latest.dscr_ncf),
        noi=_to_float(latest.noi),
        ncf=_to_float(latest.ncf),
        occupancy=_to_float(latest.occupancy),
        revenue=_to_float(latest.revenue),
        operating_expenses=_to_float(latest.operating_expenses),
        debt_service=_to_float(latest.debt_service),
        appraised_value=_to_float(latest.appraised_value),
        dscr_noi_at_securitization=_to_float(latest.dscr_noi_at_securitization),
        dscr_ncf_at_securitization=_to_float(latest.dscr_ncf_at_securitization),
        noi_at_securitization=_to_float(latest.noi_at_securitization),
        ncf_at_securitization=_to_float(latest.ncf_at_securitization),
        occupancy_at_securitization=_to_float(latest.occupancy_at_securitization),
        appraised_value_at_securitization=_to_float(latest.appraised_value_at_securitization),
    )


def _loan_to_out(loan: Loan) -> LoanOut:
    return LoanOut(
        id=loan.id,
        deal_id=loan.deal_id,
        prospectus_loan_id=loan.prospectus_loan_id,
        asset_number=loan.asset_number,
        originator_name=loan.originator_name,
        original_loan_amount=float(loan.original_loan_amount),
        origination_date=loan.origination_date,
        maturity_date=loan.maturity_date,
        original_term_months=loan.original_term_months,
        original_amortization_term_months=loan.original_amortization_term_months,
        original_interest_rate=float(loan.original_interest_rate) if loan.original_interest_rate else None,
        property_type=loan.property_type,
        property_name=loan.property_name,
        property_city=loan.property_city,
        property_state=loan.property_state,
        borrower_name=loan.borrower_name,
        interest_only_indicator=loan.interest_only_indicator,
        balloon_indicator=loan.balloon_indicator,
        lien_position=loan.lien_position,
        created_at=loan.created_at,
        latest_snapshot=_latest_snapshot(loan),
    )


@router.get("/search", response_model=list[LoanSearchOut])
async def search_loans(
    property_name: str | None = Query(None, description="Partial property name (case-insensitive)"),
    property_city: str | None = Query(None, description="Partial city name (case-insensitive)"),
    state: str | None = Query(None, description="Two-letter state code, e.g. TX"),
    borrower_name: str | None = Query(None, description="Partial borrower name (case-insensitive)"),
    limit: int = Query(50, ge=1, le=500),
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

    stmt = stmt.limit(limit)
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
async def list_loans_by_ticker(
    ticker: str,
    delinquent: bool | None = Query(None, description="Filter to delinquent loans only"),
    maturing_within: int | None = Query(None, description="Filter to loans maturing within N months"),
    sort_by: str | None = Query(None, description="Sort field: ending_balance, original_loan_amount, asset_number"),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Deal).where(Deal.ticker == ticker))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    stmt = (
        select(Loan)
        .options(selectinload(Loan.snapshots))
        .where(Loan.deal_id == deal.id)
    )

    if delinquent:
        # Filter loans that have a snapshot with delinquency_status != "0"
        latest_filing_stmt = (
            select(Filing.id)
            .where(Filing.deal_id == deal.id, Filing.parsed.is_(True))
            .order_by(Filing.filing_date.desc())
            .limit(1)
        )
        latest_filing = (await session.execute(latest_filing_stmt)).scalar()
        if latest_filing:
            delinquent_loan_ids = (
                select(LoanSnapshot.loan_id)
                .where(
                    LoanSnapshot.filing_id == latest_filing,
                    LoanSnapshot.delinquency_status.isnot(None),
                    LoanSnapshot.delinquency_status != "0",
                    LoanSnapshot.delinquency_status != "",
                )
            )
            stmt = stmt.where(Loan.id.in_(delinquent_loan_ids))

    if maturing_within is not None:
        cutoff = date.today() + timedelta(days=maturing_within * 30)
        stmt = stmt.where(Loan.maturity_date.isnot(None), Loan.maturity_date <= cutoff)

    # Sorting
    if sort_by == "ending_balance":
        # Sort by snapshot balance - fall back to original amount
        stmt = stmt.order_by(Loan.original_loan_amount.desc())
    elif sort_by == "original_loan_amount":
        stmt = stmt.order_by(Loan.original_loan_amount.desc())
    else:
        stmt = stmt.order_by(Loan.asset_number)

    stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    loans = result.scalars().all()

    return [_loan_to_out(loan) for loan in loans]
