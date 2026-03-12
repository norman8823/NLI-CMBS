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
                    interest_only_indicator=loan_data.interest_only_indicator,
                    balloon_indicator=loan_data.balloon_indicator,
                    lien_position=loan_data.lien_position,
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
                    scheduled_interest_amount=self._to_float(snapshot_data.scheduled_interest_amount),
                    scheduled_principal_amount=self._to_float(snapshot_data.scheduled_principal_amount),
                    actual_interest_collected=self._to_float(snapshot_data.actual_interest_collected),
                    actual_principal_collected=self._to_float(snapshot_data.actual_principal_collected),
                    actual_other_collected=self._to_float(snapshot_data.actual_other_collected),
                    servicer_advanced_amount=self._to_float(snapshot_data.servicer_advanced_amount),
                    delinquency_status=snapshot_data.delinquency_status,
                    interest_paid_through_date=snapshot_data.interest_paid_through_date,
                    next_payment_amount_due=self._to_float(snapshot_data.next_payment_amount_due),
                    # Credit metrics — current/mostRecent
                    dscr_noi=self._to_float(snapshot_data.dscr_noi),
                    dscr_ncf=self._to_float(snapshot_data.dscr_ncf),
                    noi=self._to_float(snapshot_data.noi),
                    ncf=self._to_float(snapshot_data.ncf),
                    occupancy=self._to_float(snapshot_data.occupancy),
                    revenue=self._to_float(snapshot_data.revenue),
                    operating_expenses=self._to_float(snapshot_data.operating_expenses),
                    debt_service=self._to_float(snapshot_data.debt_service),
                    appraised_value=self._to_float(snapshot_data.appraised_value),
                    # Credit metrics — securitization-time
                    dscr_noi_at_securitization=self._to_float(
                        snapshot_data.dscr_noi_at_securitization
                    ),
                    dscr_ncf_at_securitization=self._to_float(
                        snapshot_data.dscr_ncf_at_securitization
                    ),
                    noi_at_securitization=self._to_float(snapshot_data.noi_at_securitization),
                    ncf_at_securitization=self._to_float(snapshot_data.ncf_at_securitization),
                    occupancy_at_securitization=self._to_float(
                        snapshot_data.occupancy_at_securitization
                    ),
                    appraised_value_at_securitization=self._to_float(
                        snapshot_data.appraised_value_at_securitization
                    ),
                )
                self._session.add(snap)
                result.snapshots_created += 1

    @staticmethod
    def _to_float(value: Decimal | None) -> float | None:
        """Convert Decimal to float, returning None if input is None."""
        return float(value) if value is not None else None

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
        if loan_data.interest_only_indicator is not None and db_loan.interest_only_indicator is None:
            db_loan.interest_only_indicator = loan_data.interest_only_indicator
        if loan_data.balloon_indicator is not None and db_loan.balloon_indicator is None:
            db_loan.balloon_indicator = loan_data.balloon_indicator
        if loan_data.lien_position and not db_loan.lien_position:
            db_loan.lien_position = loan_data.lien_position
