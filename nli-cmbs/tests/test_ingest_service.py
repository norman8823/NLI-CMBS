"""Tests for IngestService — ingest parsed XML data to PostgreSQL."""

import uuid
from datetime import date
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from nli_cmbs.config import settings
from nli_cmbs.db.models import Base, Deal, Filing, Loan, LoanSnapshot
from nli_cmbs.services.ingest_service import IngestService

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        # Cleanup: delete test data
        await session.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def deal_and_filing(db_session: AsyncSession):
    """Create a test deal and filing."""
    deal = Deal(
        id=uuid.uuid4(),
        ticker="TEST-INGEST-2024",
        trust_name="Test Ingest Trust 2024",
        depositor_cik="9999999",
        issuer_shelf="TEST",
        issuance_year=2024,
    )
    db_session.add(deal)
    await db_session.flush()

    filing = Filing(
        id=uuid.uuid4(),
        deal_id=deal.id,
        accession_number=f"9999999-99-{uuid.uuid4().hex[:6]}",
        filing_date=date(2024, 6, 15),
        form_type="ABS-EE",
        exhibit_url="https://example.com/test-ex102.xml",
        parsed=False,
    )
    db_session.add(filing)
    await db_session.flush()

    yield deal, filing

    # Cleanup
    await db_session.execute(
        LoanSnapshot.__table__.delete().where(LoanSnapshot.filing_id == filing.id)
    )
    await db_session.execute(
        Loan.__table__.delete().where(Loan.deal_id == deal.id)
    )
    await db_session.execute(
        Filing.__table__.delete().where(Filing.deal_id == deal.id)
    )
    await db_session.execute(
        Deal.__table__.delete().where(Deal.id == deal.id)
    )
    await db_session.commit()


@pytest.fixture
def xml_bytes():
    return (FIXTURE_DIR / "ex102_bmark_2024_v6.xml").read_bytes()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ingest_creates_loans_and_snapshots(db_session, deal_and_filing, xml_bytes):
    """Ingest a parsed filing, verify Loan and LoanSnapshot records created."""
    deal, filing = deal_and_filing
    svc = IngestService(db_session)

    result = await svc.ingest_filing(deal, filing, xml_bytes)

    assert result.deal_ticker == "TEST-INGEST-2024"
    assert result.loans_created > 0
    assert result.snapshots_created > 0
    assert result.loans_created == result.snapshots_created
    assert not result.already_parsed

    # Verify DB records
    loan_count = await db_session.execute(
        select(func.count()).select_from(Loan).where(Loan.deal_id == deal.id)
    )
    assert loan_count.scalar() == result.loans_created

    snap_count = await db_session.execute(
        select(func.count()).select_from(LoanSnapshot).where(LoanSnapshot.filing_id == filing.id)
    )
    assert snap_count.scalar() == result.snapshots_created

    # Verify filing marked as parsed
    assert filing.parsed is True
    assert filing.reporting_period_start is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ingest_idempotent(db_session, deal_and_filing, xml_bytes):
    """Ingest same filing again, verify no duplicates."""
    deal, filing = deal_and_filing
    svc = IngestService(db_session)

    # First ingest
    result1 = await svc.ingest_filing(deal, filing, xml_bytes)
    loans_after_first = result1.loans_created
    snaps_after_first = result1.snapshots_created

    # Second ingest — should detect already parsed
    result2 = await svc.ingest_filing(deal, filing, xml_bytes)
    assert result2.already_parsed is True
    assert result2.loans_created == 0
    assert result2.snapshots_created == 0

    # Verify no duplicates in DB
    loan_count = await db_session.execute(
        select(func.count()).select_from(Loan).where(Loan.deal_id == deal.id)
    )
    assert loan_count.scalar() == loans_after_first

    snap_count = await db_session.execute(
        select(func.count()).select_from(LoanSnapshot).where(LoanSnapshot.filing_id == filing.id)
    )
    assert snap_count.scalar() == snaps_after_first


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ingest_result_stats_accurate(db_session, deal_and_filing, xml_bytes):
    """Verify IngestResult stats match actual DB counts."""
    deal, filing = deal_and_filing
    svc = IngestService(db_session)

    result = await svc.ingest_filing(deal, filing, xml_bytes)

    # Stats should match
    assert result.loans_created + result.loans_updated > 0
    assert result.snapshots_created == result.loans_created + result.loans_updated or \
           result.snapshots_created == result.loans_created  # first ingest: all created

    # Deal stats should be updated
    assert deal.loan_count == result.loans_created
    assert deal.original_balance is not None
    assert deal.original_balance > 0
