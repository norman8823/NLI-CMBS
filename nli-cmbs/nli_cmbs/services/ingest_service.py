"""Service to persist parsed EX-102 XML data into PostgreSQL."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nli_cmbs.db.models import Deal, Filing, Loan, LoanSnapshot
from nli_cmbs.edgar.xml_parser import Ex102Parser
from nli_cmbs.schemas.parsed_loan import ParsedFiling

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    deal_ticker: str
    filing_accession: str
    reporting_period: str | None = None
    loans_created: int = 0
    loans_updated: int = 0
    snapshots_created: int = 0
    parse_errors: int = 0
    errors: list[str] = field(default_factory=list)
    already_parsed: bool = False


class IngestService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ingest_filing(
        self, deal: Deal, filing: Filing, xml_bytes: bytes
    ) -> IngestResult:
        result = IngestResult(
            deal_ticker=deal.ticker,
            filing_accession=filing.accession_number,
        )

        # Idempotency: skip if already parsed
        if filing.parsed:
            result.already_parsed = True
            result.reporting_period = (
                f"{filing.reporting_period_start} to {filing.reporting_period_end}"
                if filing.reporting_period_start
                else None
            )
            return result

        # Parse XML
        parser = Ex102Parser()
        parsed = parser.parse(xml_bytes)
        result.parse_errors = len(parsed.parse_errors)
        if parsed.parse_errors:
            result.errors.extend(parsed.parse_errors)

        if parsed.reporting_period_start:
            result.reporting_period = (
                f"{parsed.reporting_period_start} to {parsed.reporting_period_end}"
            )

        # Upsert loans and create snapshots
        await self._persist_loans(deal, filing, parsed, result)

        # Update filing
        filing.reporting_period_start = parsed.reporting_period_start
        filing.reporting_period_end = parsed.reporting_period_end
        filing.parsed = True

        # Update deal stats
        total_balance = Decimal(0)
        for loan_data in parsed.loans:
            if loan_data.original_loan_amount:
                total_balance += loan_data.original_loan_amount
        deal.loan_count = parsed.total_loan_count
        deal.original_balance = float(total_balance)

        await self._session.commit()
        return result

    async def _persist_loans(
        self,
        deal: Deal,
        filing: Filing,
        parsed: ParsedFiling,
        result: IngestResult,
    ) -> None:
        # Load existing loans for this deal keyed by prospectus_loan_id
        stmt = select(Loan).where(Loan.deal_id == deal.id)
        existing = await self._session.execute(stmt)
        loan_map: dict[str, Loan] = {
            loan.prospectus_loan_id: loan for loan in existing.scalars().all()
        }

        for loan_data in parsed.loans:
            lid = loan_data.prospectus_loan_id
            snapshot_data = parsed.snapshots.get(lid)

            if lid in loan_map:
                # Update existing loan
                db_loan = loan_map[lid]
                self._update_loan(db_loan, loan_data)
                result.loans_updated += 1
            else:
                # Create new loan
                db_loan = Loan(
                    deal_id=deal.id,
                    prospectus_loan_id=lid,
                    asset_number=loan_data.asset_number or 0,
                    originator_name=loan_data.originator_name,
                    original_loan_amount=float(loan_data.original_loan_amount or 0),
                    origination_date=loan_data.origination_date,
                    maturity_date=loan_data.maturity_date,
                    original_term_months=loan_data.original_term_months,
                    original_amortization_term_months=loan_data.original_amortization_term_months,
                    original_interest_rate=(
                        float(loan_data.original_interest_rate)
                        if loan_data.original_interest_rate
                        else None
                    ),
                    property_type=loan_data.property_type,
                    property_name=loan_data.property_name,
                    property_city=loan_data.property_city,
                    property_state=loan_data.property_state,
                    borrower_name=loan_data.borrower_name,
                )
                self._session.add(db_loan)
                loan_map[lid] = db_loan
                result.loans_created += 1

            # Flush to get loan IDs for new loans
            await self._session.flush()

            # Create snapshot if we have snapshot data
            if snapshot_data:
                # Check if snapshot already exists for this loan+filing
                snap_stmt = select(LoanSnapshot).where(
                    LoanSnapshot.loan_id == db_loan.id,
                    LoanSnapshot.filing_id == filing.id,
                )
                existing_snap = await self._session.execute(snap_stmt)
                if existing_snap.scalar_one_or_none():
                    continue

                snap = LoanSnapshot(
                    loan_id=db_loan.id,
                    filing_id=filing.id,
                    reporting_period_begin_date=snapshot_data.reporting_period_begin_date or date.min,
                    reporting_period_end_date=snapshot_data.reporting_period_end_date or date.min,
                    beginning_balance=float(snapshot_data.beginning_balance or 0),
                    ending_balance=float(snapshot_data.ending_balance or 0),
                    current_interest_rate=float(snapshot_data.current_interest_rate or 0),
                    scheduled_interest_amount=(
                        float(snapshot_data.scheduled_interest_amount)
                        if snapshot_data.scheduled_interest_amount
                        else None
                    ),
                    scheduled_principal_amount=(
                        float(snapshot_data.scheduled_principal_amount)
                        if snapshot_data.scheduled_principal_amount
                        else None
                    ),
                    actual_interest_collected=(
                        float(snapshot_data.actual_interest_collected)
                        if snapshot_data.actual_interest_collected
                        else None
                    ),
                    actual_principal_collected=(
                        float(snapshot_data.actual_principal_collected)
                        if snapshot_data.actual_principal_collected
                        else None
                    ),
                    actual_other_collected=(
                        float(snapshot_data.actual_other_collected)
                        if snapshot_data.actual_other_collected
                        else None
                    ),
                    servicer_advanced_amount=(
                        float(snapshot_data.servicer_advanced_amount)
                        if snapshot_data.servicer_advanced_amount
                        else None
                    ),
                    delinquency_status=snapshot_data.delinquency_status,
                    interest_paid_through_date=snapshot_data.interest_paid_through_date,
                    next_payment_amount_due=(
                        float(snapshot_data.next_payment_amount_due)
                        if snapshot_data.next_payment_amount_due
                        else None
                    ),
                )
                self._session.add(snap)
                result.snapshots_created += 1

    @staticmethod
    def _update_loan(db_loan: Loan, loan_data) -> None:
        """Update loan fields from parsed data if they have new values."""
        if loan_data.property_name and not db_loan.property_name:
            db_loan.property_name = loan_data.property_name
        if loan_data.property_city and not db_loan.property_city:
            db_loan.property_city = loan_data.property_city
        if loan_data.property_state and not db_loan.property_state:
            db_loan.property_state = loan_data.property_state
        if loan_data.borrower_name and not db_loan.borrower_name:
            db_loan.borrower_name = loan_data.borrower_name
        if loan_data.originator_name and not db_loan.originator_name:
            db_loan.originator_name = loan_data.originator_name
