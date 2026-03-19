"""Service to hydrate ground truth entries from existing LoanSnapshot data."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nli_cmbs.db.models import Deal, Filing, GroundTruthEntry, LoanSnapshot

logger = logging.getLogger(__name__)

# Field → (field_type, tier)
# Tier 1: direct extraction from XML
# Tier 2: derived/calculated metrics
FIELD_CONFIG: dict[str, tuple[str, int]] = {
    # Tier 1 — direct extraction
    "ending_balance": ("numeric", 1),
    "beginning_balance": ("numeric", 1),
    "current_interest_rate": ("numeric", 1),
    "delinquency_status": ("text", 1),
    "reporting_period_begin_date": ("date", 1),
    "reporting_period_end_date": ("date", 1),
    "scheduled_interest_amount": ("numeric", 1),
    "scheduled_principal_amount": ("numeric", 1),
    "actual_interest_collected": ("numeric", 1),
    "actual_principal_collected": ("numeric", 1),
    "actual_other_collected": ("numeric", 1),
    "servicer_advanced_amount": ("numeric", 1),
    "next_payment_amount_due": ("numeric", 1),
    # Tier 2 — derived metrics
    "dscr_noi": ("numeric", 2),
    "dscr_ncf": ("numeric", 2),
    "occupancy": ("numeric", 2),
    "noi": ("numeric", 2),
    "ncf": ("numeric", 2),
    "revenue": ("numeric", 2),
    "operating_expenses": ("numeric", 2),
    "debt_service": ("numeric", 2),
    "appraised_value": ("numeric", 2),
    "dscr_noi_at_securitization": ("numeric", 2),
    "dscr_ncf_at_securitization": ("numeric", 2),
    "noi_at_securitization": ("numeric", 2),
    "ncf_at_securitization": ("numeric", 2),
    "occupancy_at_securitization": ("numeric", 2),
    "appraised_value_at_securitization": ("numeric", 2),
}


async def hydrate_ground_truth(
    db: AsyncSession,
    deal: Deal,
    filing_id: str | None = None,
) -> int:
    """Hydrate ground_truth_entries from LoanSnapshot data.

    Args:
        db: Database session
        deal: The deal to hydrate
        filing_id: Optional specific filing ID. If None, uses latest parsed filing.

    Returns:
        Number of entries created.
    """
    # Resolve filing
    if filing_id:
        filing_result = await db.execute(
            select(Filing).where(Filing.id == filing_id, Filing.deal_id == deal.id)
        )
        filing = filing_result.scalar_one_or_none()
    else:
        filing_result = await db.execute(
            select(Filing)
            .where(Filing.deal_id == deal.id, Filing.parsed.is_(True))
            .order_by(Filing.filing_date.desc())
            .limit(1)
        )
        filing = filing_result.scalar_one_or_none()

    if not filing:
        logger.warning("No parsed filing found for %s", deal.ticker)
        return 0

    # Get all snapshots for this filing
    snap_result = await db.execute(
        select(LoanSnapshot).where(LoanSnapshot.filing_id == filing.id)
    )
    snapshots = list(snap_result.scalars().all())

    if not snapshots:
        logger.warning("No snapshots found for filing %s", filing.accession_number)
        return 0

    # Check existing entries to avoid duplicates
    existing_result = await db.execute(
        select(
            GroundTruthEntry.loan_id,
            GroundTruthEntry.field_name,
        ).where(GroundTruthEntry.filing_id == filing.id)
    )
    existing_keys: set[tuple] = {(row[0], row[1]) for row in existing_result.all()}

    created = 0
    for snap in snapshots:
        for field_name, (field_type, tier) in FIELD_CONFIG.items():
            value = getattr(snap, field_name, None)
            if value is None:
                continue

            key = (snap.loan_id, field_name)
            if key in existing_keys:
                continue

            entry = GroundTruthEntry(
                deal_id=deal.id,
                loan_id=snap.loan_id,
                filing_id=filing.id,
                field_name=field_name,
                field_value=str(value),
                field_type=field_type,
                tier=tier,
            )
            db.add(entry)
            created += 1

    if created:
        await db.commit()

    logger.info(
        "Hydrated %d ground truth entries for %s (filing %s)",
        created, deal.ticker, filing.accession_number,
    )
    return created
