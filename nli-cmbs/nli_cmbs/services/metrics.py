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


async def compute_deal_metrics(session: AsyncSession, deal_id: uuid.UUID) -> DealMetrics:
    """Compute metrics for a deal from its latest filing's snapshots."""
    latest_filing_stmt = (
        select(Filing.id, Filing.filing_date)
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

    filing_id, filing_date = filing_row

    snap_stmt = (
        select(
            LoanSnapshot.ending_balance,
            LoanSnapshot.current_interest_rate,
            LoanSnapshot.delinquency_status,
            Loan.original_term_months,
        )
        .join(Loan, LoanSnapshot.loan_id == Loan.id)
        .where(LoanSnapshot.filing_id == filing_id)
    )
    rows = (await session.execute(snap_stmt)).all()

    if not rows:
        return DealMetrics(
            total_upb=0, wa_coupon=0, wa_remaining_term=None,
            delinquency_rate=0, delinquency_by_status={}, loan_count=0,
            last_filing_date=str(filing_date),
        )

    total_upb = Decimal(0)
    weighted_rate = Decimal(0)
    weighted_term = Decimal(0)
    term_balance = Decimal(0)
    delinquent_balance = Decimal(0)
    delinq_counts: dict[str, int] = {}
    loan_count = len(rows)

    for ending_balance, rate, delinq_status, orig_term in rows:
        bal = Decimal(str(ending_balance or 0))
        total_upb += bal
        weighted_rate += bal * Decimal(str(rate or 0))

        if orig_term is not None:
            weighted_term += bal * Decimal(str(orig_term))
            term_balance += bal

        status = delinq_status or "Unknown"
        delinq_counts[status] = delinq_counts.get(status, 0) + 1

        if status not in ("0", "Unknown", ""):
            delinquent_balance += bal

    wa_coupon = float(weighted_rate / total_upb * 100) if total_upb else 0.0
    wa_remaining_term = float(weighted_term / term_balance) if term_balance else None
    delinquency_rate = float(delinquent_balance / total_upb * 100) if total_upb else 0.0

    return DealMetrics(
        total_upb=float(total_upb),
        wa_coupon=round(wa_coupon, 4),
        wa_remaining_term=round(wa_remaining_term, 1) if wa_remaining_term else None,
        delinquency_rate=round(delinquency_rate, 4),
        delinquency_by_status=delinq_counts,
        loan_count=loan_count,
        last_filing_date=str(filing_date),
    )
