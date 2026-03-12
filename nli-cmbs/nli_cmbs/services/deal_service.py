from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nli_cmbs.db.models import Deal

if TYPE_CHECKING:
    from nli_cmbs.services.ingest_service import IngestResult


class DealService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_ticker(self, ticker: str) -> Deal | None:
        result = await self._session.execute(select(Deal).where(Deal.ticker == ticker))
        return result.scalar_one_or_none()

    async def create(self, **kwargs) -> Deal:
        deal = Deal(**kwargs)
        self._session.add(deal)
        await self._session.commit()
        await self._session.refresh(deal)
        return deal

    async def list_all(self) -> list[Deal]:
        result = await self._session.execute(select(Deal).order_by(Deal.created_at.desc()))
        return list(result.scalars().all())

    async def scan_deal(self, ticker: str) -> IngestResult:
        """Full pipeline: resolve CIK -> fetch filing -> download XML -> parse -> persist."""
        from nli_cmbs.edgar.cik_resolver import CikResolver
        from nli_cmbs.edgar.client import EdgarClient
        from nli_cmbs.edgar.filing_fetcher import FilingFetcher
        from nli_cmbs.services.ingest_service import IngestResult, IngestService

        client = EdgarClient()
        try:
            resolver = CikResolver(edgar_client=client, db_session=self._session)

            # Step 1: Resolve CIK
            mapping = await resolver.resolve(ticker)
            if not mapping:
                return IngestResult(
                    deal_ticker=ticker,
                    filing_accession="",
                    errors=[f"Could not resolve CIK for {ticker}"],
                )

            parsed_ticker = resolver.parse_ticker(ticker)
            normalized = parsed_ticker["normalized"] if parsed_ticker else ticker

            # Step 2: Fetch latest filing
            fetcher = FilingFetcher(edgar_client=client, db_session=self._session)
            filing = await fetcher.get_latest_filing(
                mapping.effective_cik, deal_ticker=normalized
            )
            if not filing:
                return IngestResult(
                    deal_ticker=normalized,
                    filing_accession="",
                    errors=[f"No ABS-EE filing found for CIK {mapping.effective_cik}"],
                )

            # Step 3: Download EX-102 XML
            xml_bytes = await fetcher.download_exhibit_102(filing)

            # Step 4: Get deal record
            deal = await self.get_by_ticker(normalized)
            if not deal:
                return IngestResult(
                    deal_ticker=normalized,
                    filing_accession=filing.accession_number,
                    errors=["Deal record not found after filing fetch"],
                )

            # Step 5: Ingest
            ingest_svc = IngestService(self._session)
            return await ingest_svc.ingest_filing(deal, filing, xml_bytes)
        finally:
            await client.close()
