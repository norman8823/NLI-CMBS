"""Integration tests that hit live EDGAR APIs.

Run with: pytest -m integration tests/test_integration.py -v -s
Skipped by default in normal test runs.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from nli_cmbs.edgar.client import EdgarClient

pytestmark = pytest.mark.integration


async def _make_session() -> tuple[AsyncSession, object]:
    """Create a fresh engine+session per test to avoid connection pool conflicts."""
    from nli_cmbs.config import settings

    engine = create_async_engine(settings.DATABASE_URL, pool_size=1)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = factory()
    return session, engine


@pytest.mark.asyncio
async def test_full_pipeline_bmark_2024_v6():
    """End-to-end: resolve CIK, fetch filing, download EX-102 XML."""
    from nli_cmbs.edgar.cik_resolver import CikResolver
    from nli_cmbs.edgar.filing_fetcher import FilingFetcher

    session, engine = await _make_session()
    client = EdgarClient()
    try:
        # Step 1: Resolve CIK
        resolver = CikResolver(edgar_client=client, db_session=session)
        mapping = await resolver.resolve("BMARK 2024-V6")

        assert mapping is not None, "CIK resolution failed for BMARK 2024-V6"
        assert mapping.effective_cik, "No effective CIK returned"
        assert mapping.trust_name, "No trust name returned"
        print(f"\n  CIK resolved: {mapping.effective_cik} ({mapping.trust_name})")

        # Step 2: Fetch latest filing
        fetcher = FilingFetcher(edgar_client=client, db_session=session)
        filing = await fetcher.get_latest_filing(
            mapping.effective_cik, deal_ticker="BMARK 2024-V6"
        )

        assert filing is not None, "No ABS-EE filing found"
        assert filing.accession_number, "Filing has no accession number"
        assert filing.exhibit_url, "Filing has no EX-102 URL"
        assert filing.exhibit_url.endswith(".xml"), "EX-102 URL should end with .xml"
        print(f"  Filing: {filing.accession_number} ({filing.filing_date})")
        print(f"  EX-102: {filing.exhibit_url}")

        # Step 3: Download EX-102 XML
        xml_bytes = await fetcher.download_exhibit_102(filing)

        assert len(xml_bytes) > 0, "Downloaded XML is empty"
        assert xml_bytes[:5] == b"<?xml" or b"<" in xml_bytes[:100], "Downloaded content doesn't look like XML"
        print(f"  XML size: {len(xml_bytes):,} bytes")
        print(f"  XML preview: {xml_bytes[:200].decode('utf-8', errors='replace')}")
    finally:
        await session.close()
        await engine.dispose()
        await client.close()


@pytest.mark.asyncio
async def test_resolve_kaggle_deal():
    """Resolve a deal that should be in the Kaggle-seeded DB."""
    from nli_cmbs.edgar.cik_resolver import CikResolver

    session, engine = await _make_session()
    client = EdgarClient()
    try:
        resolver = CikResolver(edgar_client=client, db_session=session)
        mapping = await resolver.resolve("BBCMS 2023-C20")

        assert mapping is not None, "BBCMS 2023-C20 should resolve from Kaggle data"
        assert mapping.depositor_cik, "No depositor CIK"
        print(f"\n  BBCMS 2023-C20 → CIK {mapping.effective_cik} (source: {mapping.source})")
    finally:
        await session.close()
        await engine.dispose()
        await client.close()


@pytest.mark.asyncio
async def test_resolve_returns_none_for_fake_deal():
    """A nonsense ticker should return None, not crash."""
    from nli_cmbs.edgar.cik_resolver import CikResolver

    session, engine = await _make_session()
    client = EdgarClient()
    try:
        resolver = CikResolver(edgar_client=client, db_session=session)
        mapping = await resolver.resolve("ZZZZ 2099-X1")

        assert mapping is None, "Fake deal should not resolve"
        print("\n  ZZZZ 2099-X1 correctly returned None")
    finally:
        await session.close()
        await engine.dispose()
        await client.close()
