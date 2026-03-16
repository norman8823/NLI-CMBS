"""Tests for the report generation service."""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from nli_cmbs.ai.client import AnthropicClient
from nli_cmbs.ai.exceptions import AIGenerationError
from nli_cmbs.config import settings
from nli_cmbs.db.models import Deal, Filing, Loan, LoanSnapshot
from nli_cmbs.services.deal_service import DealService
from nli_cmbs.services.report_service import DealNotFoundError, ReportService

SAMPLE_REPORT = """# 1. EXECUTIVE SUMMARY
Test deal is performing well with stable metrics.

# 2. DEAL PERFORMANCE OVERVIEW
Current UPB is $49.5M against original balance of $1.2B.

# 3. DELINQUENCY & SPECIAL SERVICING
No delinquent loans. The pool is performing.

# 4. MATURITY & REFINANCING RISK
All loans mature in 2034.

# 5. TOP LOANS
Top loan is Test Property at $49.5M.

# 6. OUTLOOK
Deal outlook remains stable.

---
Data Source: ABS-EE filing dated 2024-06-15, Accession No. TEST-ACCESSION
SEC EDGAR: https://www.sec.gov/test-example"""

_TEST_PREFIX = "TESTRPT"


@pytest.fixture
def mock_ai_client():
    with patch("nli_cmbs.ai.client.anthropic.AsyncAnthropic"):
        client = AnthropicClient(api_key="test-key", model="test-model", max_tokens=4096, timeout=30)
        client.generate_report = AsyncMock(return_value=SAMPLE_REPORT)
        return client


@pytest.fixture
async def session():
    """Create a fresh async engine + session per test to avoid event loop issues."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.connect() as conn:
        async with conn.begin() as txn:
            s = AsyncSession(bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint")
            yield s
            await s.close()
            await txn.rollback()
    await engine.dispose()


async def _seed(s):
    """Seed test data and return the ticker."""
    tag = uuid.uuid4().hex[:6]
    ticker = f"{_TEST_PREFIX}-{tag}"
    accession = f"9999999999-99-{tag}"
    deal_id = uuid.uuid4()
    filing_id = uuid.uuid4()
    loan_id = uuid.uuid4()

    s.add(Deal(
        id=deal_id, ticker=ticker, trust_name=f"{ticker} Trust",
        depositor_cik="99999", issuer_shelf="TEST", issuance_year=2099,
        original_balance=1_200_000_000, loan_count=50,
    ))
    s.add(Filing(
        id=filing_id, deal_id=deal_id, accession_number=accession,
        filing_date=date(2024, 6, 15), form_type="ABS-EE",
        exhibit_url="https://www.sec.gov/test-example", parsed=True,
    ))
    s.add(Loan(
        id=loan_id, deal_id=deal_id, prospectus_loan_id="TESTLOAN001",
        asset_number=1, original_loan_amount=50_000_000,
        property_name="Test Property", property_city="New York",
        property_state="NY", maturity_date=date(2034, 6, 1),
        original_interest_rate=0.045,
    ))
    s.add(LoanSnapshot(
        loan_id=loan_id, filing_id=filing_id,
        reporting_period_begin_date=date(2024, 5, 1),
        reporting_period_end_date=date(2024, 5, 31),
        beginning_balance=50_000_000, ending_balance=49_500_000,
        current_interest_rate=0.045, delinquency_status="0",
        dscr_noi=1.35, occupancy=0.95,
    ))
    await s.flush()
    return ticker, accession


@pytest.mark.asyncio
async def test_generate_report(session, mock_ai_client):
    ticker, accession = await _seed(session)
    service = ReportService(session, mock_ai_client, DealService(session))

    result = await service.generate_surveillance_report(ticker)

    assert result.deal_ticker == ticker
    assert result.cached is False
    assert "EXECUTIVE SUMMARY" in result.report_text
    assert result.model_used == "test-model"
    assert result.filing_date == "2024-06-15"
    assert result.accession_number == accession
    mock_ai_client.generate_report.assert_awaited_once()


@pytest.mark.asyncio
async def test_cached_report(session, mock_ai_client):
    ticker, _ = await _seed(session)
    service = ReportService(session, mock_ai_client, DealService(session))

    result1 = await service.generate_surveillance_report(ticker)
    assert result1.cached is False

    result2 = await service.generate_surveillance_report(ticker)
    assert result2.cached is True
    assert result2.report_text == SAMPLE_REPORT

    assert mock_ai_client.generate_report.await_count == 1


@pytest.mark.asyncio
async def test_regenerate_bypasses_cache(session, mock_ai_client):
    ticker, _ = await _seed(session)
    service = ReportService(session, mock_ai_client, DealService(session))

    await service.generate_surveillance_report(ticker)

    result = await service.generate_surveillance_report(ticker, regenerate=True)
    assert result.cached is False
    assert mock_ai_client.generate_report.await_count == 2


@pytest.mark.asyncio
async def test_deal_not_found(session, mock_ai_client):
    service = ReportService(session, mock_ai_client, DealService(session))

    with pytest.raises(DealNotFoundError, match="NONEXISTENT"):
        await service.generate_surveillance_report("NONEXISTENT")


@pytest.mark.asyncio
async def test_ai_error_propagates(session, mock_ai_client):
    ticker, _ = await _seed(session)
    mock_ai_client.generate_report = AsyncMock(side_effect=AIGenerationError("API failed"))
    service = ReportService(session, mock_ai_client, DealService(session))

    with pytest.raises(AIGenerationError, match="API failed"):
        await service.generate_surveillance_report(ticker)
