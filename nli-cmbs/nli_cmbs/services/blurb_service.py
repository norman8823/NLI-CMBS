"""AI-generated loan-level credit blurbs."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nli_cmbs.ai.client import AnthropicClient
from nli_cmbs.db.models import Deal, Loan, LoanSnapshot, Property

logger = logging.getLogger(__name__)

BLURB_SYSTEM_PROMPT = (
    "You are a CMBS credit analyst writing a 2-3 sentence summary for a loan detail view. "
    "Focus on what's notable — do not restate metrics the user already sees on screen."
)

BLURB_CACHE_DAYS = 30


def _fmt_currency(amount: float | None) -> str:
    if amount is None:
        return "N/A"
    if amount >= 1_000_000_000:
        return f"${amount / 1_000_000_000:.2f}B"
    elif amount >= 1_000_000:
        return f"${amount / 1_000_000:.1f}M"
    else:
        return f"${amount:,.0f}"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    # Values stored as decimals (0.73 = 73%)
    pct = value * 100 if value <= 1 else value
    return f"{pct:.1f}"


def _fmt_date(d) -> str:
    if d is None:
        return "N/A"
    if hasattr(d, "strftime"):
        return d.strftime("%B %Y")
    return str(d)


def _build_blurb_prompt(
    loan: Loan,
    snapshot: LoanSnapshot | None,
    properties: list[Property],
    deal: Deal,
) -> str:
    """Build user prompt for loan blurb generation."""
    securitization_date = _fmt_date(
        # Use the first property's valuation date, or fall back to deal issuance year
        next(
            (p.valuation_securitization_date for p in properties if p.valuation_securitization_date),
            None,
        )
    )
    if securitization_date == "N/A" and deal.issuance_year:
        securitization_date = str(deal.issuance_year)

    delinquency = "Current"
    if snapshot and snapshot.delinquency_status:
        from nli_cmbs.ai.prompts import format_delinquency_status

        delinquency = format_delinquency_status(snapshot.delinquency_status)

    lines = [
        "Generate a brief credit note for this loan.",
        "",
        f"LOAN: {loan.prospectus_loan_id}",
        f"DEAL: {deal.ticker}",
        f"SECURITIZATION DATE: {securitization_date}",
        f"PROPERTY COUNT: {loan.property_count}",
        f"BALANCE: {_fmt_currency(float(snapshot.ending_balance) if snapshot and snapshot.ending_balance else float(loan.original_loan_amount))}",
        f"RATE: {float(snapshot.current_interest_rate) * 100:.2f}%" if snapshot and snapshot.current_interest_rate else "RATE: N/A",
        f"MATURITY: {_fmt_date(loan.maturity_date)}",
        f"DSCR: {float(snapshot.dscr_noi):.2f}x" if snapshot and snapshot.dscr_noi else "DSCR: N/A",
        f"DELINQUENCY: {delinquency}",
        "",
        "PROPERTIES:",
    ]

    for prop in properties:
        lines.append(
            f"- {prop.property_name or 'N/A'}, {prop.property_city or 'N/A'}, {prop.property_state or 'N/A'}"
        )
        lines.append(f"  Type: {prop.property_type or 'N/A'}")
        lines.append(f"  Year Built: {prop.year_built or 'N/A'}")
        lines.append(f"  Sq Ft: {float(prop.net_rentable_sq_ft):,.0f}" if prop.net_rentable_sq_ft else "  Sq Ft: N/A")
        lines.append(f"  Occupancy at securitization: {_fmt_pct(float(prop.occupancy_securitization) if prop.occupancy_securitization else None)}%")
        lines.append(f"  Occupancy most recent: {_fmt_pct(float(prop.occupancy_most_recent) if prop.occupancy_most_recent else None)}%")
        lines.append(f"  NOI at securitization: {_fmt_currency(float(prop.noi_securitization) if prop.noi_securitization else None)}")
        lines.append(f"  NOI most recent: {_fmt_currency(float(prop.noi_most_recent) if prop.noi_most_recent else None)}")
        lines.append(f"  Largest Tenant: {prop.largest_tenant or 'N/A'}")

    lines.append("")
    lines.append("GUIDELINES:")
    lines.append("")
    lines.append("1. DO NOT restate balance, rate, maturity, DSCR — the user sees these already.")
    lines.append("")
    lines.append("2. OCCUPANCY/NOI: You have exactly TWO data points — securitization and most recent.")
    lines.append(f"   - Correct: 'Occupancy is 87%, down from 100% at the {securitization_date} securitization'")
    lines.append(f"   - Correct: 'NOI declined 29% since the {securitization_date} securitization, from $21.6M to $15.3M'")
    lines.append("   - Wrong: 'Occupancy has been stable' or 'maintained 100%' or 'NOI declined' (without date context)")
    lines.append(f"   - If both values are the same, say 'unchanged since the {securitization_date} securitization'")
    lines.append("   - ALWAYS include the securitization date when discussing changes")
    lines.append("")
    lines.append(
        "3. SINGLE-TENANT PROPERTIES: 100% occupancy is trivial for single-tenant assets — "
        "the tenant is either there or gone. Note this if relevant: "
        "'As a single-tenant property, occupancy is binary — the tenant remains in place.'"
    )
    lines.append("")
    lines.append("4. DATA ANOMALIES: Flag suspicious patterns that warrant attention:")
    lines.append(
        f"   - If occupancy unchanged but NOI dropped significantly: 'NOI declined 29% since the "
        f"{securitization_date} securitization despite unchanged occupancy — may reflect rent "
        "reductions, concessions, or expense increases'"
    )
    lines.append("   - If NOI is null for some properties: 'NOI unavailable for X of Y properties'")
    lines.append("")
    lines.append(
        "5. TENANT CREDIT: If you recognize a tenant from your training data, note their credit "
        "quality or public status. Only do this for tenants you're confident about."
    )
    lines.append("")
    lines.append(
        "6. MULTI-PROPERTY CONCENTRATION: For portfolio loans, note geographic or property type "
        "concentration if notable: '8 of 12 properties are in Texas, creating geographic concentration risk'"
    )
    lines.append("")
    lines.append(
        "7. MATURITY CONTEXT: If maturity is within 18 months and DSCR is below 1.25x, flag "
        "refinancing risk. If maturity is 5+ years out, note the runway."
    )
    lines.append("")
    lines.append("8. LENGTH: 2-3 sentences maximum. Be direct.")

    return "\n".join(lines)


async def generate_loan_blurb(
    db: AsyncSession,
    ai_client: AnthropicClient,
    loan_id: str,
) -> dict:
    """Generate or return cached AI blurb for a loan.

    Returns dict with 'blurb' and 'generated_at' keys.
    """
    # Fetch loan with properties and snapshots
    stmt = (
        select(Loan)
        .options(
            selectinload(Loan.properties),
            selectinload(Loan.snapshots),
            selectinload(Loan.deal),
            selectinload(Loan.parent_loan).selectinload(Loan.properties),
        )
        .where(Loan.id == loan_id)
    )
    loan = (await db.execute(stmt)).scalar_one_or_none()
    if not loan:
        return None

    # Check cache
    now = datetime.now(timezone.utc)
    if loan.ai_blurb and loan.ai_blurb_generated_at:
        age = now - loan.ai_blurb_generated_at.replace(tzinfo=timezone.utc) if loan.ai_blurb_generated_at.tzinfo is None else now - loan.ai_blurb_generated_at
        if age < timedelta(days=BLURB_CACHE_DAYS):
            return {
                "blurb": loan.ai_blurb,
                "generated_at": loan.ai_blurb_generated_at.isoformat(),
            }

    # Get latest snapshot
    snapshot = None
    if loan.snapshots:
        snapshot = max(loan.snapshots, key=lambda s: s.reporting_period_end_date)

    # Get properties — use parent's for A/B notes
    properties = loan.properties or []
    if loan.parent_loan_id and loan.parent_loan and loan.parent_loan.properties:
        properties = loan.parent_loan.properties

    # Build prompt and generate
    user_prompt = _build_blurb_prompt(loan, snapshot, properties, loan.deal)

    logger.info("Generating blurb for loan %s (%s)", loan.prospectus_loan_id, loan_id)
    blurb_text = await ai_client.generate_report(
        system_prompt=BLURB_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.3,
    )

    # Cache in DB
    loan.ai_blurb = blurb_text
    loan.ai_blurb_generated_at = now
    await db.commit()

    return {
        "blurb": blurb_text,
        "generated_at": now.isoformat(),
    }
