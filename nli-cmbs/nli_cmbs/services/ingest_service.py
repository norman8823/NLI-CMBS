"""Service to persist parsed EX-102 XML data into PostgreSQL."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nli_cmbs.db.models import Deal, Filing, Loan, LoanSnapshot, Property
from nli_cmbs.edgar.xml_parser import Ex102Parser
from nli_cmbs.schemas.parsed_loan import ParsedFiling, ParsedProperty

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    deal_ticker: str
    filing_accession: str
    reporting_period: str | None = None
    loans_created: int = 0
    loans_updated: int = 0
    snapshots_created: int = 0
    properties_created: int = 0
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

        # Idempotency: skip if already fully parsed (loans AND properties exist)
        if filing.parsed:
            # Check if deal's loans are missing properties
            missing_properties = await self._deal_missing_properties(deal)
            if not missing_properties:
                result.already_parsed = True
                result.reporting_period = (
                    f"{filing.reporting_period_start} to {filing.reporting_period_end}"
                    if filing.reporting_period_start
                    else None
                )
                return result
            # Loans exist but properties are missing — continue to backfill
            logger.info(
                "Deal %s has loans but no properties — backfilling properties",
                deal.ticker,
            )

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

        # Upsert loans, create snapshots, and create properties
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
            property_list = parsed.properties.get(lid, [])

            if lid in loan_map:
                # Update existing loan
                db_loan = loan_map[lid]
                self._update_loan(db_loan, loan_data)
                # Update property count if we have properties
                if property_list:
                    db_loan.property_count = len(property_list)
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
                    property_count=len(property_list) if property_list else 1,
                    interest_only_indicator=loan_data.interest_only_indicator,
                    balloon_indicator=loan_data.balloon_indicator,
                    lien_position=loan_data.lien_position,
                    is_modified=loan_data.is_modified,
                    modification_date=loan_data.modification_date,
                    modification_code=loan_data.modification_code,
                    modified_interest_rate=(
                        float(loan_data.modified_interest_rate)
                        if loan_data.modified_interest_rate
                        else None
                    ),
                    modified_maturity_date=loan_data.modified_maturity_date,
                    modified_payment_amount=self._to_float(loan_data.modified_payment_amount),
                    principal_forgiveness_amount=self._to_float(
                        loan_data.principal_forgiveness_amount
                    ),
                    principal_deferral_amount=self._to_float(loan_data.principal_deferral_amount),
                    deferred_interest_amount=self._to_float(loan_data.deferred_interest_amount),
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
                if not existing_snap.scalar_one_or_none():
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

            # Create properties (multi-property from X-NNN assets, or single-property inline)
            if property_list:
                await self._persist_properties(db_loan, property_list, result)

    async def _persist_properties(
        self,
        loan: Loan,
        property_list: list[ParsedProperty],
        result: IngestResult,
    ) -> None:
        """Persist properties for a loan. Skips any that already exist by property_id."""
        # Check for existing properties
        stmt = select(Property.property_id).where(Property.loan_id == loan.id)
        existing = await self._session.execute(stmt)
        existing_ids = {row[0] for row in existing.all()}

        for prop_data in property_list:
            if prop_data.property_id in existing_ids:
                # Property already exists, skip
                continue

            prop = Property(
                loan_id=loan.id,
                property_id=prop_data.property_id,
                property_name=prop_data.property_name,
                property_address=prop_data.property_address,
                property_city=prop_data.property_city,
                property_state=prop_data.property_state,
                property_zip=prop_data.property_zip,
                property_type=prop_data.property_type,
                net_rentable_sq_ft=self._to_float(prop_data.net_rentable_sq_ft),
                year_built=prop_data.year_built,
                valuation_securitization=self._to_float(prop_data.valuation_securitization),
                valuation_securitization_date=prop_data.valuation_securitization_date,
                occupancy_securitization=self._to_float(prop_data.occupancy_securitization),
                occupancy_most_recent=self._to_float(prop_data.occupancy_most_recent),
                noi_securitization=self._to_float(prop_data.noi_securitization),
                noi_most_recent=self._to_float(prop_data.noi_most_recent),
                ncf_securitization=self._to_float(prop_data.ncf_securitization),
                ncf_most_recent=self._to_float(prop_data.ncf_most_recent),
                dscr_noi_securitization=self._to_float(prop_data.dscr_noi_securitization),
                dscr_noi_most_recent=self._to_float(prop_data.dscr_noi_most_recent),
                dscr_ncf_securitization=self._to_float(prop_data.dscr_ncf_securitization),
                dscr_ncf_most_recent=self._to_float(prop_data.dscr_ncf_most_recent),
                revenue_most_recent=self._to_float(prop_data.revenue_most_recent),
                operating_expenses_most_recent=self._to_float(prop_data.operating_expenses_most_recent),
                largest_tenant=prop_data.largest_tenant,
                largest_tenant_sf=prop_data.largest_tenant_sf,
                largest_tenant_lease_expiration=prop_data.largest_tenant_lease_expiration,
                largest_tenant_pct_nra=self._to_float(prop_data.largest_tenant_pct_nra),
                second_largest_tenant=prop_data.second_largest_tenant,
                second_largest_tenant_sf=prop_data.second_largest_tenant_sf,
                second_largest_tenant_lease_expiration=prop_data.second_largest_tenant_lease_expiration,
                second_largest_tenant_pct_nra=self._to_float(prop_data.second_largest_tenant_pct_nra),
                third_largest_tenant=prop_data.third_largest_tenant,
                third_largest_tenant_sf=prop_data.third_largest_tenant_sf,
                third_largest_tenant_lease_expiration=prop_data.third_largest_tenant_lease_expiration,
                third_largest_tenant_pct_nra=self._to_float(prop_data.third_largest_tenant_pct_nra),
                year_renovated=prop_data.year_renovated,
                number_of_units=prop_data.number_of_units,
                appraised_value=self._to_float(prop_data.appraised_value),
                appraisal_date=prop_data.appraisal_date,
                noi_date=prop_data.noi_date,
            )
            self._session.add(prop)
            result.properties_created += 1

    async def _deal_missing_properties(self, deal: Deal) -> bool:
        """Return True if any loans in this deal are missing properties."""
        # Single query: count total loans vs loans that have at least one property
        loans_with_props = (
            select(Property.loan_id)
            .where(Property.loan_id == Loan.id)
            .correlate(Loan)
            .exists()
        )
        stmt = (
            select(
                func.count(Loan.id).label("total"),
                func.count(Loan.id).filter(loans_with_props).label("with_props"),
            )
            .where(Loan.deal_id == deal.id)
        )
        row = (await self._session.execute(stmt)).one()
        total, with_props = row.total, row.with_props
        if total == 0:
            return False
        return with_props < total

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
        # Update property count if provided
        if hasattr(loan_data, 'property_count') and loan_data.property_count > 1:
            db_loan.property_count = loan_data.property_count
        # Modification fields — always update (these can change between filings)
        if loan_data.is_modified:
            db_loan.is_modified = True
            if loan_data.modification_date:
                db_loan.modification_date = loan_data.modification_date
            if loan_data.modification_code:
                db_loan.modification_code = loan_data.modification_code
            if loan_data.modified_interest_rate is not None:
                db_loan.modified_interest_rate = float(loan_data.modified_interest_rate)
            if loan_data.modified_maturity_date:
                db_loan.modified_maturity_date = loan_data.modified_maturity_date
            if loan_data.modified_payment_amount is not None:
                db_loan.modified_payment_amount = float(loan_data.modified_payment_amount)
            if loan_data.principal_forgiveness_amount is not None:
                db_loan.principal_forgiveness_amount = float(loan_data.principal_forgiveness_amount)
            if loan_data.principal_deferral_amount is not None:
                db_loan.principal_deferral_amount = float(loan_data.principal_deferral_amount)
            if loan_data.deferred_interest_amount is not None:
                db_loan.deferred_interest_amount = float(loan_data.deferred_interest_amount)
