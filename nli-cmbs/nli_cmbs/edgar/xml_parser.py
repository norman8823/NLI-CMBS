"""Parse SEC EX-102 XML exhibits from ABS-EE CMBS filings into structured loan data."""

from __future__ import annotations

import logging
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from lxml import etree

from nli_cmbs.schemas.parsed_loan import ParsedFiling, ParsedLoan, ParsedLoanSnapshot, ParsedProperty

logger = logging.getLogger(__name__)

NS = "http://www.sec.gov/edgar/document/absee/cmbs/assetdata"
_NS_MAP = {"ns": NS}

# Pattern to identify property-level assets (e.g., "1-001", "1-002", "40-001")
# These are individual properties within a multi-property loan
PROPERTY_ASSET_PATTERN = re.compile(r"^(\d+)-(\d+)$")


class Ex102ParseError(Exception):
    """Raised when XML is fundamentally unparseable."""


class Ex102Parser:
    """Parse SEC EX-102 XML exhibits from ABS-EE filings into structured loan data.
    
    Handles two types of <assets> elements in CMBS filings:
    
    1. Loan-level assets (assetNumber like "1", "2", "9A"):
       - Contain loan terms: balance, interest rate, maturity date
       - For single-property loans: contain full property details
       - For multi-property loans: contain portfolio summary (e.g., "GNL Portfolio")
       
    2. Property-level assets (assetNumber like "1-001", "1-002"):
       - Individual properties within a multi-property loan
       - Linked to parent loan via the prefix (e.g., "1-001" belongs to loan "1")
       - No balance data (balance is at loan level)
       - Contain property-specific details: name, city, state, occupancy, etc.
    """

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
            asset_elements = root.findall("assets")
        if not asset_elements:
            raise Ex102ParseError(
                "No <assets> elements found in XML. "
                f"Expected EX-102 CMBS format with namespace {NS}"
            )

        # First pass: separate loan-level and property-level assets
        loan_elements: list[tuple[str, etree._Element]] = []
        property_elements: list[tuple[str, str, etree._Element]] = []  # (parent_loan_id, property_id, element)

        for asset_el in asset_elements:
            asset_number = self._get_text(asset_el, "assetNumber")
            if not asset_number:
                continue
                
            match = PROPERTY_ASSET_PATTERN.match(asset_number)
            if match:
                # Property-level asset: "1-001" -> parent="1", property_id="1-001"
                parent_loan_id = match.group(1)
                property_elements.append((parent_loan_id, asset_number, asset_el))
            else:
                # Loan-level asset
                loan_elements.append((asset_number, asset_el))

        # Second pass: parse loans
        loans: list[ParsedLoan] = []
        snapshots: dict[str, ParsedLoanSnapshot] = {}
        properties: dict[str, list[ParsedProperty]] = {}  # loan_id -> list of properties
        parse_errors: list[str] = []
        reporting_period_start: date | None = None
        reporting_period_end: date | None = None

        for asset_number, asset_el in loan_elements:
            try:
                result = self._parse_loan_element(asset_el)
                if result is None:
                    parse_errors.append(f"Loan {asset_number}: returned None")
                    continue
                loan, snapshot = result
                loans.append(loan)
                snapshots[loan.prospectus_loan_id] = snapshot

                if reporting_period_start is None and snapshot.reporting_period_begin_date:
                    reporting_period_start = snapshot.reporting_period_begin_date
                if reporting_period_end is None and snapshot.reporting_period_end_date:
                    reporting_period_end = snapshot.reporting_period_end_date
            except Exception as e:
                parse_errors.append(f"Loan {asset_number}: {e}")
                logger.warning("Failed to parse loan %s: %s", asset_number, e)

        # Third pass: parse properties and link to parent loans
        for parent_loan_id, property_id, asset_el in property_elements:
            try:
                prop = self._parse_property_element(asset_el, parent_loan_id, property_id)
                if prop:
                    if parent_loan_id not in properties:
                        properties[parent_loan_id] = []
                    properties[parent_loan_id].append(prop)
            except Exception as e:
                parse_errors.append(f"Property {property_id}: {e}")
                logger.warning("Failed to parse property %s: %s", property_id, e)

        # Fourth pass: create properties from inline <property> for single-property loans
        # Loans that already have entries in `properties` (from X-NNN assets) are multi-property
        # and don't need this. Only process loans with NO property entries.
        loan_el_map = {asset_number: asset_el for asset_number, asset_el in loan_elements}
        for loan in loans:
            lid = loan.prospectus_loan_id
            if lid in properties:
                continue  # Already has multi-property entries

            asset_el = loan_el_map.get(lid)
            if asset_el is None:
                continue

            # Check if there's a <property> child with real property details
            prop_el = asset_el.find(f"{{{NS}}}property")
            if prop_el is None:
                prop_el = asset_el.find("property")
            if prop_el is None:
                continue

            # Only create a property if it has actual property details
            # (propertyName, propertyCity, or propertyState)
            has_name = self._get_text(asset_el, "property/propertyName")
            has_city = self._get_text(asset_el, "property/propertyCity")
            has_state = self._get_text(asset_el, "property/propertyState")
            if not (has_name or has_city or has_state):
                continue

            synthetic_id = f"{lid}-001"
            prop = self._parse_property_element(asset_el, lid, synthetic_id)
            if prop:
                properties[lid] = [prop]

        # Update loan property counts
        for loan in loans:
            loan_props = properties.get(loan.prospectus_loan_id, [])
            if loan_props:
                loan.property_count = len(loan_props)
            else:
                loan.property_count = 1  # Single-property loan

        logger.info(
            "Parsed %d loans and %d properties from %d total asset elements",
            len(loans),
            sum(len(p) for p in properties.values()),
            len(asset_elements)
        )

        return ParsedFiling(
            loans=loans,
            snapshots=snapshots,
            properties=properties,
            reporting_period_start=reporting_period_start,
            reporting_period_end=reporting_period_end,
            total_loan_count=len(loans),
            parse_errors=parse_errors,
        )

    def _parse_loan_element(self, el: etree._Element) -> tuple[ParsedLoan, ParsedLoanSnapshot] | None:
        """Parse a loan-level <assets> element into a ParsedLoan and ParsedLoanSnapshot."""
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
            # Property fields for single-property loans or portfolio summary for multi-property
            property_name=self._get_text(el, "property/propertyName"),
            property_city=self._get_text(el, "property/propertyCity"),
            property_state=self._get_text(el, "property/propertyState"),
            property_type=self._get_text(el, "property/propertyTypeCode"),
            borrower_name=None,
            maturity_date=self._parse_date(self._get_text(el, "maturityDate")),
            original_term_months=self._parse_int(self._get_text(el, "originalTermLoanNumber")),
            original_amortization_term_months=self._parse_int(
                self._get_text(el, "originalAmortizationTermNumber")
            ),
            original_interest_rate=self._parse_decimal(
                self._get_text(el, "originalInterestRatePercentage")
            ),
            interest_only_indicator=self._parse_bool(self._get_text(el, "interestOnlyIndicator")),
            balloon_indicator=self._parse_bool(self._get_text(el, "balloonIndicator")),
            lien_position=self._get_text(el, "lienPositionSecuritizationCode"),
            property_count=1,  # Will be updated after parsing properties
        )

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

        self._extract_credit_metrics(el, snapshot)
        return loan, snapshot

    def _parse_property_element(
        self, el: etree._Element, parent_loan_id: str, property_id: str
    ) -> ParsedProperty | None:
        """Parse a property-level <assets> element into a ParsedProperty."""
        prop_el = el.find(f"{{{NS}}}property")
        if prop_el is None:
            prop_el = el.find("property")
        
        # Get property name - might be at asset level or property level
        property_name = self._get_text(el, "property/propertyName")
        if not property_name:
            # Some filings put tenant name as property identifier
            property_name = self._get_text(el, "property/largestTenant")
        
        return ParsedProperty(
            parent_loan_id=parent_loan_id,
            property_id=property_id,
            property_name=property_name,
            property_address=self._get_text(el, "property/propertyAddress"),
            property_city=self._get_text(el, "property/propertyCity"),
            property_state=self._get_text(el, "property/propertyState"),
            property_zip=self._get_text(el, "property/propertyZip"),
            property_type=self._get_text(el, "property/propertyTypeCode"),
            net_rentable_sq_ft=self._parse_decimal(
                self._get_text(el, "property/netRentableSquareFeetNumber") or
                self._get_text(el, "property/netRentableSquareFeetSecuritizationNumber")
            ),
            year_built=self._parse_int(self._get_text(el, "property/yearBuiltNumber")),
            valuation_securitization=self._parse_decimal(
                self._get_text(el, "property/valuationSecuritizationAmount")
            ),
            valuation_securitization_date=self._parse_date(
                self._get_text(el, "property/valuationSecuritizationDate")
            ),
            occupancy_securitization=self._parse_decimal(
                self._get_text(el, "property/physicalOccupancySecuritizationPercentage")
            ),
            occupancy_most_recent=self._parse_decimal(
                self._get_text(el, "property/mostRecentPhysicalOccupancyPercentage")
            ),
            noi_securitization=self._parse_decimal(
                self._get_text(el, "property/netOperatingIncomeSecuritizationAmount")
            ),
            noi_most_recent=self._parse_decimal(
                self._get_text(el, "property/mostRecentNetOperatingIncomeAmount")
            ),
            ncf_securitization=self._parse_decimal(
                self._get_text(el, "property/netCashFlowFlowSecuritizationAmount")
            ),
            ncf_most_recent=self._parse_decimal(
                self._get_text(el, "property/mostRecentNetCashFlowAmount")
            ),
            dscr_noi_securitization=self._parse_decimal(
                self._get_text(el, "property/debtServiceCoverageNetOperatingIncomeSecuritizationPercentage")
            ),
            dscr_noi_most_recent=self._parse_decimal(
                self._get_text(el, "property/mostRecentDebtServiceCoverageNetOperatingIncomePercentage")
            ),
            dscr_ncf_securitization=self._parse_decimal(
                self._get_text(el, "property/debtServiceCoverageNetCashFlowSecuritizationPercentage")
            ),
            dscr_ncf_most_recent=self._parse_decimal(
                self._get_text(el, "property/mostRecentDebtServiceCoverageNetCashFlowpercentage")
            ),
            revenue_most_recent=self._parse_decimal(
                self._get_text(el, "property/mostRecentRevenueAmount")
            ),
            operating_expenses_most_recent=self._parse_decimal(
                self._get_text(el, "property/operatingExpensesAmount")
            ),
            largest_tenant=self._get_text(el, "property/largestTenant"),
            second_largest_tenant=self._get_text(el, "property/secondLargestTenant"),
            third_largest_tenant=self._get_text(el, "property/thirdLargestTenant"),
        )

    def _extract_credit_metrics(self, el: etree._Element, snapshot: ParsedLoanSnapshot) -> None:
        """Extract DSCR, NOI, NCF, occupancy, appraised value from property element."""
        # Current/mostRecent metrics
        snapshot.dscr_noi = self._parse_decimal(
            self._get_text(el, "property/mostRecentDebtServiceCoverageNetOperatingIncomePercentage")
        )
        snapshot.dscr_ncf = self._parse_decimal(
            self._get_text(el, "property/mostRecentDebtServiceCoverageNetCashFlowpercentage")
        )
        snapshot.noi = self._parse_decimal(
            self._get_text(el, "property/mostRecentNetOperatingIncomeAmount")
        )
        snapshot.ncf = self._parse_decimal(
            self._get_text(el, "property/mostRecentNetCashFlowAmount")
        )
        snapshot.occupancy = self._parse_decimal(
            self._get_text(el, "property/mostRecentPhysicalOccupancyPercentage")
        )
        snapshot.revenue = self._parse_decimal(
            self._get_text(el, "property/mostRecentRevenueAmount")
        )
        snapshot.operating_expenses = self._parse_decimal(
            self._get_text(el, "property/operatingExpensesAmount")
        )
        snapshot.debt_service = self._parse_decimal(
            self._get_text(el, "property/mostRecentDebtServiceAmount")
        )

        # Securitization-time metrics
        snapshot.dscr_noi_at_securitization = self._parse_decimal(
            self._get_text(el, "property/debtServiceCoverageNetOperatingIncomeSecuritizationPercentage")
        )
        snapshot.dscr_ncf_at_securitization = self._parse_decimal(
            self._get_text(el, "property/debtServiceCoverageNetCashFlowSecuritizationPercentage")
        )
        snapshot.noi_at_securitization = self._parse_decimal(
            self._get_text(el, "property/netOperatingIncomeSecuritizationAmount")
        )
        snapshot.ncf_at_securitization = self._parse_decimal(
            self._get_text(el, "property/netCashFlowFlowSecuritizationAmount")
        )
        snapshot.occupancy_at_securitization = self._parse_decimal(
            self._get_text(el, "property/physicalOccupancySecuritizationPercentage")
        )
        snapshot.appraised_value_at_securitization = self._parse_decimal(
            self._get_text(el, "property/valuationSecuritizationAmount")
        )
        snapshot.appraised_value = snapshot.appraised_value_at_securitization

    def _get_text(self, parent: etree._Element, tag: str) -> str | None:
        """Get child element text, handling the default namespace and nested paths."""
        parts = tag.split("/")
        current = parent
        for part in parts:
            child = current.find(f"{{{NS}}}{part}")
            if child is None:
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

    @staticmethod
    def _parse_bool(value: str | None) -> bool | None:
        if value is None:
            return None
        return value.lower() in ("true", "1", "yes")
