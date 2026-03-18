"""Service to backfill historical filings and create time-series snapshots."""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nli_cmbs.db.models import (
    Deal,
    Filing,
    Loan,
    LoanSnapshot,
    Property,
    PropertySnapshot,
)
from nli_cmbs.edgar.client import EdgarClient
from nli_cmbs.edgar.filing_fetcher import FilingFetcher
from nli_cmbs.edgar.xml_parser import Ex102Parser
from nli_cmbs.schemas.parsed_loan import ParsedFiling

logger = logging.getLogger(__name__)


@dataclass
class BackfillStats:
    deal_ticker: str
    filings_found: int = 0
    filings_processed: int = 0
    filings_skipped: int = 0  # already parsed
    loan_snapshots_created: int = 0
    property_snapshots_created: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class BackfillResult:
    deals_processed: int = 0
    total_filings: int = 0
    total_loan_snapshots: int = 0
    total_property_snapshots: int = 0
    errors: list[str] = field(default_factory=list)
    stats_by_deal: list[BackfillStats] = field(default_factory=list)


class BackfillService:
    def __init__(
        self,
        db: AsyncSession,
        edgar_client: EdgarClient,
        filing_fetcher: FilingFetcher,
        parser: Ex102Parser,
        years_back: int = 3,
        rate_limit_delay: float = 2.0,
        batch_size: int = 5,
        batch_pause: float = 15.0,
    ):
        self.db = db
        self.edgar = edgar_client
        self.filing_fetcher = filing_fetcher
        self.parser = parser
        self.years_back = years_back
        self.rate_limit_delay = rate_limit_delay
        self.batch_size = batch_size
        self.batch_pause = batch_pause

    async def backfill_all_deals(self, limit: int | None = None) -> BackfillResult:
        """Backfill historical data for all deals in the database."""
        query = select(Deal).order_by(Deal.ticker)
        if limit:
            query = query.limit(limit)
        result = await self.db.execute(query)
        deals = result.scalars().all()

        total_result = BackfillResult()

        for deal in deals:
            try:
                stats = await self.backfill_deal(deal)
                total_result.stats_by_deal.append(stats)
                total_result.deals_processed += 1
                total_result.total_filings += stats.filings_processed
                total_result.total_loan_snapshots += stats.loan_snapshots_created
                total_result.total_property_snapshots += stats.property_snapshots_created
                total_result.errors.extend(stats.errors)

                logger.info(
                    "Completed %s: %d filings, %d loan snapshots, %d property snapshots",
                    deal.ticker,
                    stats.filings_processed,
                    stats.loan_snapshots_created,
                    stats.property_snapshots_created,
                )
            except Exception as e:
                error_msg = f"Failed to backfill {deal.ticker}: {e}"
                logger.error(error_msg)
                total_result.errors.append(error_msg)

        return total_result

    async def backfill_deal(self, deal: Deal) -> BackfillStats:
        """Backfill historical filings for a single deal."""
        stats = BackfillStats(deal_ticker=deal.ticker)

        # Get CIK (prefer trust_cik, fall back to depositor_cik)
        cik = deal.trust_cik or deal.depositor_cik
        if not cik:
            stats.errors.append(f"No CIK found for {deal.ticker}")
            return stats

        # ~12 filings/year * years_back
        filing_limit = 12 * self.years_back

        # Fetch historical ABS-EE filings (creates Filing records in DB)
        try:
            filings = await self.filing_fetcher.get_filings_history(
                cik=cik,
                deal_ticker=deal.ticker,
                limit=filing_limit,
            )
            stats.filings_found = len(filings)
        except Exception as e:
            stats.errors.append(f"Failed to fetch filing history: {e}")
            return stats

        # Process filings in batches with pauses between batches
        consecutive_failures = 0
        processed_in_batch = 0

        for filing in filings:
            accession = filing.accession_number

            # Jittered delay between individual requests
            jittered = self.rate_limit_delay * (0.75 + random.random() * 0.5)
            await asyncio.sleep(jittered)

            try:
                if filing.parsed:
                    stats.filings_skipped += 1
                    continue

                # Download and parse XML
                xml_bytes = await self.edgar.download_filing_document(filing.exhibit_url)
                parsed = self.parser.parse(xml_bytes)

                # Update filing with reporting period
                filing.reporting_period_start = parsed.reporting_period_start
                filing.reporting_period_end = parsed.reporting_period_end

                # Create snapshots
                loan_count, prop_count = await self._create_snapshots(
                    deal, filing, parsed
                )
                stats.loan_snapshots_created += loan_count
                stats.property_snapshots_created += prop_count

                # Mark filing as parsed
                filing.parsed = True
                await self.db.commit()

                stats.filings_processed += 1
                consecutive_failures = 0
                processed_in_batch += 1

                # Batch pause: after N filings, take a longer break
                if processed_in_batch >= self.batch_size:
                    batch_jittered = self.batch_pause * (0.75 + random.random() * 0.5)
                    logger.info(
                        "Batch of %d complete for %s — pausing %.0fs",
                        processed_in_batch, deal.ticker, batch_jittered,
                    )
                    await asyncio.sleep(batch_jittered)
                    processed_in_batch = 0

            except Exception as e:
                stats.errors.append(f"Filing {accession}: {e}")
                await self.db.rollback()
                consecutive_failures += 1

                if consecutive_failures >= 2:
                    cooldown = 60 * (0.75 + random.random() * 0.5)
                    logger.warning(
                        "%d consecutive failures for %s — cooling down %.0fs",
                        consecutive_failures, deal.ticker, cooldown,
                    )
                    await asyncio.sleep(cooldown)

        return stats

    async def _create_snapshots(
        self, deal: Deal, filing: Filing, parsed: ParsedFiling
    ) -> tuple[int, int]:
        """Create loan and property snapshots from parsed data.

        Returns (loan_snapshot_count, property_snapshot_count).
        """
        loan_count = 0
        prop_count = 0

        for parsed_loan in parsed.loans:
            lid = parsed_loan.prospectus_loan_id
            snapshot_data = parsed.snapshots.get(lid)
            property_list = parsed.properties.get(lid, [])

            # Find existing loan
            loan_result = await self.db.execute(
                select(Loan).where(
                    Loan.deal_id == deal.id,
                    Loan.prospectus_loan_id == lid,
                )
            )
            loan = loan_result.scalar_one_or_none()

            if not loan:
                # Loan doesn't exist yet — skip (we only snapshot known loans)
                continue

            # Create loan snapshot if we have snapshot data
            if snapshot_data:
                existing_snap = await self.db.execute(
                    select(LoanSnapshot).where(
                        LoanSnapshot.loan_id == loan.id,
                        LoanSnapshot.filing_id == filing.id,
                    )
                )
                if not existing_snap.scalar_one_or_none():
                    snap = LoanSnapshot(
                        loan_id=loan.id,
                        filing_id=filing.id,
                        reporting_period_begin_date=snapshot_data.reporting_period_begin_date or date.min,
                        reporting_period_end_date=snapshot_data.reporting_period_end_date or date.min,
                        beginning_balance=float(snapshot_data.beginning_balance or 0),
                        ending_balance=float(snapshot_data.ending_balance or 0),
                        current_interest_rate=float(snapshot_data.current_interest_rate or 0),
                        scheduled_interest_amount=_to_float(snapshot_data.scheduled_interest_amount),
                        scheduled_principal_amount=_to_float(snapshot_data.scheduled_principal_amount),
                        actual_interest_collected=_to_float(snapshot_data.actual_interest_collected),
                        actual_principal_collected=_to_float(snapshot_data.actual_principal_collected),
                        actual_other_collected=_to_float(snapshot_data.actual_other_collected),
                        servicer_advanced_amount=_to_float(snapshot_data.servicer_advanced_amount),
                        delinquency_status=snapshot_data.delinquency_status,
                        interest_paid_through_date=snapshot_data.interest_paid_through_date,
                        next_payment_amount_due=_to_float(snapshot_data.next_payment_amount_due),
                        dscr_noi=_to_float(snapshot_data.dscr_noi),
                        dscr_ncf=_to_float(snapshot_data.dscr_ncf),
                        noi=_to_float(snapshot_data.noi),
                        ncf=_to_float(snapshot_data.ncf),
                        occupancy=_to_float(snapshot_data.occupancy),
                        revenue=_to_float(snapshot_data.revenue),
                        operating_expenses=_to_float(snapshot_data.operating_expenses),
                        debt_service=_to_float(snapshot_data.debt_service),
                        appraised_value=_to_float(snapshot_data.appraised_value),
                        dscr_noi_at_securitization=_to_float(snapshot_data.dscr_noi_at_securitization),
                        dscr_ncf_at_securitization=_to_float(snapshot_data.dscr_ncf_at_securitization),
                        noi_at_securitization=_to_float(snapshot_data.noi_at_securitization),
                        ncf_at_securitization=_to_float(snapshot_data.ncf_at_securitization),
                        occupancy_at_securitization=_to_float(snapshot_data.occupancy_at_securitization),
                        appraised_value_at_securitization=_to_float(
                            snapshot_data.appraised_value_at_securitization
                        ),
                    )
                    self.db.add(snap)
                    loan_count += 1

            # Create property snapshots
            for parsed_prop in property_list:
                prop_result = await self.db.execute(
                    select(Property).where(
                        Property.loan_id == loan.id,
                        Property.property_id == parsed_prop.property_id,
                    )
                )
                prop = prop_result.scalar_one_or_none()

                if not prop:
                    continue

                existing_prop_snap = await self.db.execute(
                    select(PropertySnapshot).where(
                        PropertySnapshot.property_id == prop.id,
                        PropertySnapshot.filing_id == filing.id,
                    )
                )
                if existing_prop_snap.scalar_one_or_none():
                    continue

                prop_snapshot = PropertySnapshot(
                    property_id=prop.id,
                    filing_id=filing.id,
                    reporting_period_end=parsed.reporting_period_end or date.min,
                    occupancy=_to_float(parsed_prop.occupancy_most_recent or parsed_prop.occupancy_securitization),
                    noi=_to_float(parsed_prop.noi_most_recent or parsed_prop.noi_securitization),
                    ncf=_to_float(parsed_prop.ncf_most_recent or parsed_prop.ncf_securitization),
                    revenue=_to_float(parsed_prop.revenue_most_recent),
                    operating_expenses=_to_float(parsed_prop.operating_expenses_most_recent),
                    dscr_noi=_to_float(parsed_prop.dscr_noi_most_recent or parsed_prop.dscr_noi_securitization),
                    dscr_ncf=_to_float(parsed_prop.dscr_ncf_most_recent or parsed_prop.dscr_ncf_securitization),
                    valuation_amount=_to_float(parsed_prop.valuation_securitization),
                    valuation_date=parsed_prop.valuation_securitization_date,
                )
                self.db.add(prop_snapshot)
                prop_count += 1

        return loan_count, prop_count


def _to_float(value: Decimal | None) -> float | None:
    """Convert Decimal to float, returning None if input is None."""
    return float(value) if value is not None else None
