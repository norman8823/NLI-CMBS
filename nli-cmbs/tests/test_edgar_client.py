import pytest

from nli_cmbs.edgar.client import (
    EdgarClient,
    EdgarConnectionError,
    EdgarNotFoundError,
    EdgarRateLimitError,
)


@pytest.fixture
def client():
    return EdgarClient()


class TestGetSubmissions:
    @pytest.mark.asyncio
    async def test_successful_fetch(self, httpx_mock, client):
        expected = {"cik": "1234567", "filings": {"recent": {"form": ["ABS-EE"]}}}
        httpx_mock.add_response(
            url="https://data.sec.gov/submissions/CIK0001234567.json",
            json=expected,
        )
        result = await client.get_submissions("1234567")
        assert result == expected

    @pytest.mark.asyncio
    async def test_cik_padded_to_10_digits(self, httpx_mock, client):
        httpx_mock.add_response(
            url="https://data.sec.gov/submissions/CIK0000000042.json",
            json={"cik": "42"},
        )
        result = await client.get_submissions("42")
        assert result["cik"] == "42"


class TestNotFoundHandling:
    @pytest.mark.asyncio
    async def test_404_raises_not_found(self, httpx_mock, client):
        httpx_mock.add_response(
            url="https://data.sec.gov/submissions/CIK0000099999.json",
            status_code=404,
        )
        with pytest.raises(EdgarNotFoundError):
            await client.get_submissions("99999")


class TestRateLimitRetry:
    @pytest.mark.asyncio
    async def test_retries_on_429_then_succeeds(self, httpx_mock, client, monkeypatch):
        monkeypatch.setattr("nli_cmbs.edgar.client._BACKOFF_BASE", 0.0)
        httpx_mock.add_response(
            url="https://data.sec.gov/submissions/CIK0001234567.json",
            status_code=429,
        )
        httpx_mock.add_response(
            url="https://data.sec.gov/submissions/CIK0001234567.json",
            json={"ok": True},
        )
        result = await client.get_submissions("1234567")
        assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_raises_after_max_retries_on_429(self, httpx_mock, client, monkeypatch):
        monkeypatch.setattr("nli_cmbs.edgar.client._BACKOFF_BASE", 0.0)
        for _ in range(3):
            httpx_mock.add_response(
                url="https://data.sec.gov/submissions/CIK0001234567.json",
                status_code=429,
            )
        with pytest.raises(EdgarRateLimitError):
            await client.get_submissions("1234567")


class TestServerErrorRetry:
    @pytest.mark.asyncio
    async def test_retries_on_500_then_succeeds(self, httpx_mock, client, monkeypatch):
        monkeypatch.setattr("nli_cmbs.edgar.client._BACKOFF_BASE", 0.0)
        httpx_mock.add_response(
            url="https://data.sec.gov/submissions/CIK0001234567.json",
            status_code=500,
        )
        httpx_mock.add_response(
            url="https://data.sec.gov/submissions/CIK0001234567.json",
            json={"recovered": True},
        )
        result = await client.get_submissions("1234567")
        assert result == {"recovered": True}

    @pytest.mark.asyncio
    async def test_raises_after_max_retries_on_500(self, httpx_mock, client, monkeypatch):
        monkeypatch.setattr("nli_cmbs.edgar.client._BACKOFF_BASE", 0.0)
        for _ in range(3):
            httpx_mock.add_response(
                url="https://data.sec.gov/submissions/CIK0001234567.json",
                status_code=500,
            )
        with pytest.raises(EdgarConnectionError):
            await client.get_submissions("1234567")


class TestUserAgentHeader:
    @pytest.mark.asyncio
    async def test_user_agent_is_set(self, httpx_mock, client):
        httpx_mock.add_response(
            url="https://data.sec.gov/submissions/CIK0000000001.json",
            json={},
        )
        await client.get_submissions("1")
        request = httpx_mock.get_request()
        assert "NLIntelligence" in request.headers["user-agent"]


class TestDownloadFilingDocument:
    @pytest.mark.asyncio
    async def test_returns_raw_bytes(self, httpx_mock, client):
        content = b"<xml>loan data</xml>"
        httpx_mock.add_response(url="https://www.sec.gov/Archives/edgar/data/123/doc.xml", content=content)
        result = await client.download_filing_document("https://www.sec.gov/Archives/edgar/data/123/doc.xml")
        assert result == content


class TestGetCompanyTickers:
    @pytest.mark.asyncio
    async def test_returns_json(self, httpx_mock, client):
        expected = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
        httpx_mock.add_response(url="https://www.sec.gov/files/company_tickers.json", json=expected)
        result = await client.get_company_tickers()
        assert result == expected
