from lxml import etree


class Ex102Parser:
    """Parse SEC EX-102 XML exhibits from ABS-EE filings into structured loan data."""

    NAMESPACE = {"abs": "http://xbrl.sec.gov/abs-ee/2024"}

    def parse(self, xml_text: str) -> list[dict]:
        root = etree.fromstring(xml_text.encode())
        assets = root.findall(".//abs:assetData", self.NAMESPACE)
        if not assets:
            assets = root.findall(".//{*}assetData")
        loans = []
        for asset in assets:
            loans.append(self._extract_loan(asset))
        return loans

    def _extract_loan(self, element) -> dict:
        def _text(tag: str) -> str | None:
            el = element.find(f"abs:{tag}", self.NAMESPACE)
            if el is None:
                el = element.find(f"{{*}}{tag}")
            return el.text.strip() if el is not None and el.text else None

        def _decimal(tag: str) -> float | None:
            val = _text(tag)
            return float(val) if val else None

        def _int(tag: str) -> int | None:
            val = _text(tag)
            return int(val) if val else None

        return {
            "asset_number": _int("assetNumber"),
            "prospectus_loan_id": _text("prospectusLoanId") or "",
            "originator_name": _text("originatorName"),
            "original_loan_amount": _decimal("originalLoanAmount"),
            "origination_date": _text("originationDate"),
            "maturity_date": _text("maturityDate"),
            "original_term_months": _int("originalTermMonths"),
            "original_amortization_term_months": _int("originalAmortizationTermMonths"),
            "original_interest_rate": _decimal("originalInterestRate"),
            "property_type": _text("propertyType"),
        }
