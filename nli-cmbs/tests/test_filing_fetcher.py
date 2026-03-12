import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from nli_cmbs.db.models import Deal, Filing
from nli_cmbs.edgar.filing_fetcher import FilingFetcher


def _make_deal(**kwargs) -> Deal:
    defaults = {
        "id": uuid.uuid4(),
        "ticker": "BMARK 2024-V6",
        "trust_name": "Benchmark 2024-V6 Mortgage Trust",
        "depositor_cik": "2012265",
        "issuer_shelf": "BMARK",
        "issuance_year": 2024,
    }
    defaults.update(kwargs)
    return Deal(**defaults)


def _submissions_response(forms, accessions, dates):
    return {
        "name": "Benchmark 2024-V6 Mortgage Trust",
        "filings": {
            "recent": {
                "form": forms,
                "accessionNumber": accessions,
                "filingDate": dates,
                "primaryDocument": ["doc.htm"] * len(forms),
            }
        },
    }


SAMPLE_INDEX_HTML = b"""
<html><body>
<table class="tableFile" summary="Document Format Files">
<tr><th>Seq</th><th>Description</th><th>Document</th><th>Type</th><th>Size</th></tr>
<tr>
  <td>1</td><td></td>
  <td><a href="/Archives/edgar/data/2012265/000188852426002583/primary.htm">primary.htm</a></td>
  <td>ABS-EE</td><td>1234</td>
</tr>
<tr>
  <td>2</td><td>Asset Data File</td>
  <td><a href="/Archives/edgar/data/2012265/000188852426002583/ex102_asset.xml">ex102_asset.xml</a></td>
  <td>EX-102</td><td>5678</td>
</tr>
<tr>
  <td>3</td><td>Asset Related Document</td>
  <td><a href="/Archives/edgar/data/2012265/000188852426002583/ex103.pdf">ex103.pdf</a></td>
  <td>EX-103</td><td>9012</td>
</tr>
</table>
</body></html>
"""


class TestFetchAbsEeFilings:
    @pytest.mark.asyncio
    async def test_filters_for_abs_ee(self):
        mock_client = AsyncMock()
        mock_client.get_submissions.return_value = _submissions_response(
            forms=["ABS-EE", "10-K", "ABS-EE", "8-K"],
            accessions=["0001-24-000001", "0001-24-000002", "0001-24-000003", "0001-24-000004"],
            dates=["2024-11-15", "2024-10-01", "2024-10-15", "2024-09-01"],
        )

        fetcher = FilingFetcher(edgar_client=mock_client, db_session=AsyncMock())
        results = await fetcher._fetch_abs_ee_filings("2012265")

        assert len(results) == 2
        assert all(r["form_type"] == "ABS-EE" for r in results)
        assert results[0]["filing_date"] == "2024-11-15"
        assert results[1]["filing_date"] == "2024-10-15"


class TestGetFilingIndex:
    @pytest.mark.asyncio
    async def test_parses_html_index_to_exhibits(self):
        mock_client = AsyncMock()
        mock_client.download_filing_document.return_value = SAMPLE_INDEX_HTML

        fetcher = FilingFetcher(edgar_client=mock_client, db_session=AsyncMock())
        exhibits = await fetcher.get_filing_index("0001-24-000001", "2012265")

        assert "EX-102" in exhibits
        assert exhibits["EX-102"].endswith("ex102_asset.xml")
        assert "EX-103" in exhibits
        assert "ABS-EE" in exhibits

    @pytest.mark.asyncio
    async def test_constructs_correct_url(self):
        mock_client = AsyncMock()
        mock_client.download_filing_document.return_value = b"<html><body></body></html>"

        fetcher = FilingFetcher(edgar_client=mock_client, db_session=AsyncMock())
        await fetcher.get_filing_index("0001234567-24-000001", "2012265")

        call_url = mock_client.download_filing_document.call_args[0][0]
        assert "000123456724000001" in call_url
        assert "0001234567-24-000001-index.htm" in call_url
        assert "www.sec.gov" in call_url


class TestFindExhibit102:
    @pytest.mark.asyncio
    async def test_finds_ex102(self):
        mock_client = AsyncMock()
        mock_client.download_filing_document.return_value = SAMPLE_INDEX_HTML

        fetcher = FilingFetcher(edgar_client=mock_client, db_session=AsyncMock())
        url = await fetcher._find_exhibit_102("0001-24-000001", "2012265")

        assert url is not None
        assert "ex102_asset.xml" in url

    @pytest.mark.asyncio
    async def test_returns_none_when_no_ex102(self):
        html_no_ex102 = b"""
        <html><body>
        <table class="tableFile">
        <tr><td>1</td><td></td>
        <td><a href="/doc.htm">doc.htm</a></td>
        <td>ABS-EE</td><td>100</td></tr>
        </table>
        </body></html>
        """
        mock_client = AsyncMock()
        mock_client.download_filing_document.return_value = html_no_ex102

        fetcher = FilingFetcher(edgar_client=mock_client, db_session=AsyncMock())
        url = await fetcher._find_exhibit_102("0001-24-000001", "2012265")
        assert url is None


class TestGetLatestFiling:
    @pytest.mark.asyncio
    async def test_returns_cached_filing(self):
        deal = _make_deal()
        cached_filing = Filing(
            id=uuid.uuid4(),
            deal_id=deal.id,
            accession_number="0001-24-000001",
            filing_date=date.today() - timedelta(days=10),
            form_type="ABS-EE",
            exhibit_url="https://www.sec.gov/Archives/ex102.xml",
            parsed=False,
        )

        call_count = 0

        def mock_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = deal
            elif call_count == 2:
                result.scalar_one_or_none.return_value = cached_filing
            return result

        mock_session = AsyncMock()
        mock_session.execute.side_effect = mock_execute

        mock_client = AsyncMock()

        fetcher = FilingFetcher(edgar_client=mock_client, db_session=mock_session)
        result = await fetcher.get_latest_filing("2012265", deal_ticker="BMARK 2024-V6")

        assert result is cached_filing
        mock_client.get_submissions.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetches_from_edgar_on_cache_miss(self):
        deal = _make_deal()

        call_count = 0

        def mock_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = deal
            else:
                result.scalar_one_or_none.return_value = None
            return result

        mock_session = AsyncMock()
        mock_session.execute.side_effect = mock_execute

        mock_client = AsyncMock()
        mock_client.get_submissions.return_value = _submissions_response(
            forms=["ABS-EE"],
            accessions=["0001-24-000099"],
            dates=["2024-11-15"],
        )
        mock_client.download_filing_document.return_value = SAMPLE_INDEX_HTML

        fetcher = FilingFetcher(edgar_client=mock_client, db_session=mock_session)
        result = await fetcher.get_latest_filing("2012265", deal_ticker="BMARK 2024-V6")

        assert result is not None
        assert result.accession_number == "0001-24-000099"
        assert "ex102_asset.xml" in result.exhibit_url
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called()


class TestDownloadExhibit102:
    @pytest.mark.asyncio
    async def test_returns_bytes(self):
        xml_bytes = b'<?xml version="1.0"?><root><assetData/></root>'
        mock_client = AsyncMock()
        mock_client.download_filing_document.return_value = xml_bytes

        filing = Filing(
            id=uuid.uuid4(),
            deal_id=uuid.uuid4(),
            accession_number="0001-24-000001",
            filing_date=date.today(),
            form_type="ABS-EE",
            exhibit_url="https://www.sec.gov/Archives/ex102.xml",
        )

        fetcher = FilingFetcher(edgar_client=mock_client, db_session=AsyncMock())
        result = await fetcher.download_exhibit_102(filing)

        assert result == xml_bytes
        mock_client.download_filing_document.assert_called_once_with(filing.exhibit_url)
