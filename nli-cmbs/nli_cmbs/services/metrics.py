"""Deal-level metrics computed from loan snapshots."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nli_cmbs.db.models import Filing, Loan, LoanSnapshot


@dataclass
class DealMetrics:
    total_upb: float
    wa_coupon: float
    wa_remaining_term: float | None
    delinquency_rate: float
    delinquency_by_status: dict[str, int]
    loan_count: int
    last_filing_date: str | None
    last_filing_accession: str | None = None
    wa_dscr: float | None = None
    wa_occupancy: float | None = None
    wa_ltv: float | None = None
    pct_interest_only: float | None = None
    pct_balloon: float | None = None
    has_current_financials: bool = False


async def compute_deal_metrics(session: AsyncSession, deal_id: uuid.UUID) -> DealMetrics:
    """Compute metrics for a deal from its latest filing's snapshots."""
    latest_filing_stmt = (
        select(Filing.id, Filing.filing_date, Filing.accession_number)
        .where(Filing.deal_id == deal_id, Filing.parsed.is_(True))
        .order_by(Filing.filing_date.desc())
        .limit(1)
    )
    filing_row = (await session.execute(latest_filing_stmt)).first()
    if not filing_row:
        return DealMetrics(
            total_upb=0, wa_coupon=0, wa_remaining_term=None,
            delinquency_rate=0, delinquency_by_status={}, loan_count=0,
            last_filing_date=None,
        )

    filing_id, filing_date, accession_number = filing_row

    snap_stmt = (
        select(
            LoanSnapshot.ending_balance,
            LoanSnapshot.current_interest_rate,
            LoanSnapshot.delinquency_status,
            LoanSnapshot.dscr_noi,
            LoanSnapshot.occupancy,
            LoanSnapshot.appraised_value,
            LoanSnapshot.noi,
            Loan.original_term_months,
            Loan.interest_only_indicator,
            Loan.balloon_indicator,
        )
        .join(Loan, LoanSnapshot.loan_id == Loan.id)
        .where(LoanSnapshot.filing_id == filing_id)
    )
    rows = (await session.execute(snap_stmt)).all()

    if not rows:
        return DealMetrics(
            total_upb=0, wa_coupon=0, wa_remaining_term=None,
            delinquency_rate=0, delinquency_by_status={}, loan_count=0,
            last_filing_date=str(filing_date), last_filing_accession=accession_number,
        )

    total_upb = Decimal(0)
    weighted_rate = Decimal(0)
    weighted_term = Decimal(0)
    term_balance = Decimal(0)
    delinquent_balance = Decimal(0)
    delinq_counts: dict[str, int] = {}
    loan_count = len(rows)

    # Credit metric accumulators
    weighted_dscr = Decimal(0)
    dscr_balance = Decimal(0)
    weighted_occupancy = Decimal(0)
    occupancy_balance = Decimal(0)
    weighted_ltv = Decimal(0)
    ltv_balance = Decimal(0)
    io_count = 0
    balloon_count = 0
    has_financials = False

    for (
        ending_balance, rate, delinq_status, dscr_noi, occupancy,
        appraised_value, noi, orig_term, is_io, is_balloon,
    ) in rows:
        bal = Decimal(str(ending_balance or 0))
        total_upb += bal
        weighted_rate += bal * Decimal(str(rate or 0))

        if orig_term is not None:
            weighted_term += bal * Decimal(str(orig_term))
            term_balance += bal

        status = delinq_status or "Unknown"
        delinq_counts[status] = delinq_counts.get(status, 0) + 1

        if status not in ("0", "B", "Unknown", ""):
            delinquent_balance += bal

        # DSCR (weighted average by balance)
        if dscr_noi is not None and bal:
            weighted_dscr += bal * Decimal(str(dscr_noi))
            dscr_balance += bal

        # Occupancy (weighted average by balance)
        if occupancy is not None and bal:
            weighted_occupancy += bal * Decimal(str(occupancy))
            occupancy_balance += bal

        # LTV = ending_balance / appraised_value (weighted average by balance)
        if appraised_value and float(appraised_value) > 0 and bal:
            ltv = bal / Decimal(str(appraised_value))
            weighted_ltv += bal * ltv
            ltv_balance += bal

        # Track if any loan has current financial data
        if noi is not None or dscr_noi is not None:
            has_financials = True

        if is_io:
            io_count += 1
        if is_balloon:
            balloon_count += 1

    wa_coupon = float(weighted_rate / total_upb * 100) if total_upb else 0.0
    wa_remaining_term = float(weighted_term / term_balance) if term_balance else None
    delinquency_rate = float(delinquent_balance / total_upb * 100) if total_upb else 0.0
    wa_dscr = float(weighted_dscr / dscr_balance) if dscr_balance else None
    wa_occupancy = float(weighted_occupancy / occupancy_balance * 100) if occupancy_balance else None
    wa_ltv = float(weighted_ltv / ltv_balance * 100) if ltv_balance else None

    return DealMetrics(
        total_upb=float(total_upb),
        wa_coupon=round(wa_coupon, 4),
        wa_remaining_term=round(wa_remaining_term, 1) if wa_remaining_term else None,
        delinquency_rate=round(delinquency_rate, 4),
        delinquency_by_status=delinq_counts,
        loan_count=loan_count,
        last_filing_date=str(filing_date),
        last_filing_accession=accession_number,
        wa_dscr=round(wa_dscr, 4) if wa_dscr else None,
        wa_occupancy=round(wa_occupancy, 2) if wa_occupancy else None,
        wa_ltv=round(wa_ltv, 2) if wa_ltv else None,
        pct_interest_only=round(io_count / loan_count * 100, 2) if loan_count else None,
        pct_balloon=round(balloon_count / loan_count * 100, 2) if loan_count else None,
        has_current_financials=has_financials,
    )
