from nli_cmbs.edgar.xml_parser import Ex102Parser


class TestEx102Parser:
    def test_parse_sample(self, sample_ex102_xml):
        parser = Ex102Parser()
        loans = parser.parse(sample_ex102_xml)
        assert len(loans) == 1
        assert loans[0]["asset_number"] == 1
        assert loans[0]["prospectus_loan_id"] == "LOAN001"
        assert loans[0]["original_loan_amount"] == 10000000.00

    def test_parse_empty(self):
        parser = Ex102Parser()
        loans = parser.parse("<root></root>")
        assert loans == []
