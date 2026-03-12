from pathlib import Path

import pytest

from nli_cmbs.edgar.xml_parser import Ex102ParseError, Ex102Parser

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def bmark_xml() -> bytes:
    return (FIXTURES / "ex102_bmark_2024_v6.xml").read_bytes()


@pytest.fixture
def bank5_xml() -> bytes:
    return (FIXTURES / "ex102_bank5_second_deal.xml").read_bytes()


class TestEx102ParserBmark:
    def test_total_loan_count(self, bmark_xml):
        result = Ex102Parser().parse(bmark_xml)
        assert result.total_loan_count == 129

    def test_first_loan_fields(self, bmark_xml):
        result = Ex102Parser().parse(bmark_xml)
        loan = result.loans[0]
        assert loan.prospectus_loan_id is not None
        assert loan.original_loan_amount is not None
        assert loan.maturity_date is not None

    def test_snapshot_balances(self, bmark_xml):
        result = Ex102Parser().parse(bmark_xml)
        first_id = result.loans[0].prospectus_loan_id
        snap = result.snapshots[first_id]
        assert snap.beginning_balance is not None
        assert snap.ending_balance is not None

    def test_property_fields_populated(self, bmark_xml):
        result = Ex102Parser().parse(bmark_xml)
        has_property_name = any(loan.property_name for loan in result.loans)
        has_property_city = any(loan.property_city for loan in result.loans)
        assert has_property_name
        assert has_property_city


class TestEx102ParserBank5:
    def test_total_loan_count(self, bank5_xml):
        result = Ex102Parser().parse(bank5_xml)
        assert result.total_loan_count == 94

    def test_first_loan_fields(self, bank5_xml):
        result = Ex102Parser().parse(bank5_xml)
        loan = result.loans[0]
        assert loan.prospectus_loan_id is not None
        assert loan.original_loan_amount is not None
        assert loan.maturity_date is not None


class TestEx102ParserErrorHandling:
    def test_malformed_xml_raises(self):
        with pytest.raises(Ex102ParseError):
            Ex102Parser().parse(b"<not valid xml>>>")

    def test_no_assets_raises(self):
        with pytest.raises(Ex102ParseError):
            Ex102Parser().parse(b"<root></root>")

    def test_single_malformed_loan_does_not_abort(self):
        """A single bad asset element should be skipped, not abort the parse."""
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <assetData xmlns="http://www.sec.gov/edgar/document/absee/cmbs/assetdata">
          <assets>
            <assetNumber>1</assetNumber>
            <originalLoanAmount>100000.00</originalLoanAmount>
            <maturityDate>01-01-2030</maturityDate>
            <reportingPeriodBeginningDate>01-01-2025</reportingPeriodBeginningDate>
            <reportingPeriodEndDate>02-01-2025</reportingPeriodEndDate>
            <reportPeriodBeginningScheduleLoanBalanceAmount>100000.00</reportPeriodBeginningScheduleLoanBalanceAmount>
            <reportPeriodEndScheduledLoanBalanceAmount>99000.00</reportPeriodEndScheduledLoanBalanceAmount>
          </assets>
          <assets>
            <!-- Missing assetNumber - will be skipped -->
            <originalLoanAmount>bad</originalLoanAmount>
          </assets>
          <assets>
            <assetNumber>3</assetNumber>
            <originalLoanAmount>200000.00</originalLoanAmount>
            <maturityDate>06-15-2031</maturityDate>
            <reportingPeriodBeginningDate>01-01-2025</reportingPeriodBeginningDate>
            <reportingPeriodEndDate>02-01-2025</reportingPeriodEndDate>
            <reportPeriodBeginningScheduleLoanBalanceAmount>200000.00</reportPeriodBeginningScheduleLoanBalanceAmount>
            <reportPeriodEndScheduledLoanBalanceAmount>198000.00</reportPeriodEndScheduledLoanBalanceAmount>
          </assets>
        </assetData>"""
        result = Ex102Parser().parse(xml)
        assert result.total_loan_count == 2
        assert len(result.parse_errors) == 1
