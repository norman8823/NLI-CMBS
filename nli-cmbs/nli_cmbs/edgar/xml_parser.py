"""Parse SEC EX-102 XML exhibits from ABS-EE CMBS filings into structured loan data."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal, InvalidOperation

from lxml import etree

from nli_cmbs.schemas.parsed_loan import ParsedFiling, ParsedLoan, ParsedLoanSnapshot

logger = logging.getLogger(__name__)

NS = "http://www.sec.gov/edgar/document/absee/cmbs/assetdata"
_NS_MAP = {"ns": NS}


class Ex102ParseError(Exception):
    """Raised when XML is fundamentally unparseable."""


class Ex102Parser:
    """Parse SEC EX-102 XML exhibits from ABS-EE filings into structured loan data."""

    def parse(self, xml_bytes: bytes | str) -> ParsedFiling:
        """Parse a complete EX-102 XML file into a ParsedFiling."""
        if isinstance(xml_bytes, str):
            xml_bytes = xml_bytes.encode("utf-8")

        try:
            root = etree.fromstring(xml_bytes)
        except etree.XMLSyntaxError as e:
            raise Ex102ParseError(f"Invalid XML: {e}") from e

        asset_elements = root.findall(f"{{{NS}}}assets")
        if not asset_elements:
            # Try without namespace as fallback
            asset_elements = root.findall("assets")
        if not asset_elements:
            raise Ex102ParseError(
                "No <assets> elements found in XML. "
                "Expected EX-102 CMBS format with namespace "
                f"{NS}"
            )

        loans: list[ParsedLoan] = []
        snapshots: dict[str, ParsedLoanSnapshot] = {}
        parse_errors: list[str] = []
        reporting_period_start: date | None = None
        reporting_period_end: date | None = None

        for i, asset_el in enumerate(asset_elements):
            try:
                result = self._parse_loan_element(asset_el)
                if result is None:
                    parse_errors.append(f"Asset element {i}: returned None (missing loan ID)")
                    continue
                loan, snapshot = result
                loans.append(loan)
                snapshots[loan.prospectus_loan_id] = snapshot

                # Capture reporting period from first loan
                if reporting_period_start is None and snapshot.reporting_period_begin_date:
                    reporting_period_start = snapshot.reporting_period_begin_date
                if reporting_period_end is None and snapshot.reporting_period_end_date:
                    reporting_period_end = snapshot.reporting_period_end_date
            except Exception as e:
                parse_errors.append(f"Asset element {i}: {e}")
                logger.warning("Failed to parse asset element %d: %s", i, e)

        return ParsedFiling(
            loans=loans,
            snapshots=snapshots,
            reporting_period_start=reporting_period_start,
            reporting_period_end=reporting_period_end,
            total_loan_count=len(loans),
            parse_errors=parse_errors,
        )

    def _parse_loan_element(self, el: etree._Element) -> tuple[ParsedLoan, ParsedLoanSnapshot] | None:
        """Parse a single <assets> element into a ParsedLoan and ParsedLoanSnapshot."""
        # The actual loan ID is assetNumber (assetTypeNumber is just a label).
        # assetNumber can be an int ("1") or a compound ID ("3-001") for multi-property loans.
        prospectus_loan_id = self._get_text(el, "assetNumber")
        if not prospectus_loan_id:
            return None

        asset_number = self._parse_int(prospectus_loan_id)

        loan = ParsedLoan(
            prospectus_loan_id=prospectus_loan_id,
            asset_number=asset_number,
            originator_name=self._get_text(el, "originatorName"),
            original_loan_amount=self._parse_decimal(self._get_text(el, "originalLoanAmount")),
            origination_date=self._parse_date(self._get_text(el, "originationDate")),
            property_name=self._get_text(el, "property/propertyName"),
            property_city=self._get_text(el, "property/propertyCity"),
            property_state=self._get_text(el, "property/propertyState"),
            property_type=self._get_text(el, "property/propertyTypeCode"),
            borrower_name=None,  # Not present in EX-102 CMBS schema
            maturity_date=self._parse_date(self._get_text(el, "maturityDate")),
            original_term_months=self._parse_int(self._get_text(el, "originalTermLoanNumber")),
            original_amortization_term_months=self._parse_int(
                self._get_text(el, "originalAmortizationTermNumber")
            ),
            original_interest_rate=self._parse_decimal(
                self._get_text(el, "originalInterestRatePercentage")
            ),
        )

        # No separate actual_interest/principal collected fields in schema;
        # use scheduled amounts as documented in the recon report.
        snapshot = ParsedLoanSnapshot(
            reporting_period_begin_date=self._parse_date(
                self._get_text(el, "reportingPeriodBeginningDate")
            ),
            reporting_period_end_date=self._parse_date(
                self._get_text(el, "reportingPeriodEndDate")
            ),
            beginning_balance=self._parse_decimal(
                self._get_text(el, "reportPeriodBeginningScheduleLoanBalanceAmount")
            ),
            ending_balance=self._parse_decimal(
                self._get_text(el, "reportPeriodEndScheduledLoanBalanceAmount")
            ),
            current_interest_rate=self._parse_decimal(
                self._get_text(el, "reportPeriodInterestRatePercentage")
            ),
            scheduled_interest_amount=self._parse_decimal(
                self._get_text(el, "scheduledInterestAmount")
            ),
            scheduled_principal_amount=self._parse_decimal(
                self._get_text(el, "scheduledPrincipalAmount")
            ),
            actual_interest_collected=self._parse_decimal(
                self._get_text(el, "scheduledInterestAmount")
            ),
            actual_principal_collected=self._parse_decimal(
                self._get_text(el, "unscheduledPrincipalCollectedAmount")
            ),
            actual_other_collected=self._parse_decimal(
                self._get_text(el, "otherInterestAdjustmentAmount")
            ),
            servicer_advanced_amount=self._parse_decimal(
                self._get_text(el, "totalPrincipalInterestAdvancedOutstandingAmount")
            ),
            delinquency_status=self._get_text(el, "paymentStatusLoanCode"),
            interest_paid_through_date=self._parse_date(
                self._get_text(el, "paidThroughDate")
            ),
            next_payment_amount_due=self._parse_decimal(
                self._get_text(el, "totalScheduledPrincipalInterestDueAmount")
            ),
        )

        return loan, snapshot

    def _get_text(self, parent: etree._Element, tag: str) -> str | None:
        """Get child element text, handling the default namespace and nested paths."""
        # Handle paths like "property/propertyName"
        parts = tag.split("/")
        current = parent
        for part in parts:
            child = current.find(f"{{{NS}}}{part}")
            if child is None:
                # Fallback: try without namespace
                child = current.find(part)
            if child is None:
                return None
            current = child
        return current.text.strip() if current.text else None

    @staticmethod
    def _parse_decimal(value: str | None) -> Decimal | None:
        if value is None:
            return None
        try:
            return Decimal(value)
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _parse_date(value: str | None) -> date | None:
        """Parse MM-DD-YYYY date format used in EX-102 XML."""
        if value is None:
            return None
        try:
            parts = value.split("-")
            if len(parts) == 3:
                month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
                return date(year, month, day)
        except (ValueError, IndexError):
            pass
        return None

    @staticmethod
    def _parse_int(value: str | None) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None
