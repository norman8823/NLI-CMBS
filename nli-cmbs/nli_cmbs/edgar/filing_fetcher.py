import logging
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nli_cmbs.db.models import Deal, Filing
from nli_cmbs.edgar.client import EdgarClient

logger = logging.getLogger(__name__)


class FilingFetcher:
    def __init__(self, edgar_client: EdgarClient, db_session: AsyncSession) -> None:
        self.edgar = edgar_client
        self.db = db_session

    async def get_latest_filing(self, cik: str, deal_ticker: str | None = None) -> Filing | None:
        """Get the most recent ABS-EE filing for a CIK.

        1. Check DB for cached filing within the last 35 days
        2. If no cache hit, fetch from EDGAR submissions API
        3. Parse filing index to find EX-102 exhibit URL
        4. Store Filing in DB and return it
        """
        deal = await self._ensure_deal(cik, deal_ticker)
        if not deal:
            return None

        # Strategy 1: Check DB cache (filing within last 35 days)
        cached = await self._get_cached_filing(deal.id)
        if cached:
            logger.info("Cache hit: filing %s from %s", cached.accession_number, cached.filing_date)
            return cached

        # Strategy 2: Fetch from EDGAR
        filings_data = await self._fetch_abs_ee_filings(cik)
        if not filings_data:
            logger.warning("No ABS-EE filings found for CIK %s", cik)
            return None

        # Take the most recent
        latest = filings_data[0]
        accession = latest["accession_number"]

        # Check if this accession is already in DB (older than 35 days)
        stmt = select(Filing).where(Filing.accession_number == accession)
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        # Parse filing index to find EX-102
        exhibit_url = await self._find_exhibit_102(accession, cik)
        if not exhibit_url:
            logger.warning("No EX-102 exhibit found for filing %s", accession)
            return None

        filing = Filing(
            deal_id=deal.id,
            accession_number=accession,
            filing_date=date.fromisoformat(latest["filing_date"]),
            form_type="ABS-EE",
            exhibit_url=exhibit_url,
            parsed=False,
        )
        self.db.add(filing)
        await self.db.commit()
        await self.db.refresh(filing)
        logger.info("Stored filing %s (EX-102: %s)", accession, exhibit_url)
        return filing

    async def get_filings_history(self, cik: str, deal_ticker: str | None = None, limit: int = 12) -> list[Filing]:
        """Get the last N ABS-EE filings for time-series analysis."""
        deal = await self._ensure_deal(cik, deal_ticker)
        if not deal:
            return []

        # Check how many we already have in DB
        stmt = (
            select(Filing)
            .where(Filing.deal_id == deal.id)
            .order_by(Filing.filing_date.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        cached = list(result.scalars().all())

        if len(cached) >= limit:
            return cached

        # Fetch more from EDGAR
        filings_data = await self._fetch_abs_ee_filings(cik)
        existing_accessions = {f.accession_number for f in cached}

        for fd in filings_data[:limit]:
            if fd["accession_number"] in existing_accessions:
                continue

            exhibit_url = await self._find_exhibit_102(fd["accession_number"], cik)
            if not exhibit_url:
                continue

            filing = Filing(
                deal_id=deal.id,
                accession_number=fd["accession_number"],
                filing_date=date.fromisoformat(fd["filing_date"]),
                form_type="ABS-EE",
                exhibit_url=exhibit_url,
                parsed=False,
            )
            self.db.add(filing)
            cached.append(filing)

        await self.db.commit()
        cached.sort(key=lambda f: f.filing_date, reverse=True)
        return cached[:limit]

    async def download_exhibit_102(self, filing: Filing) -> bytes:
        """Download the EX-102 XML document for a filing."""
        return await self.edgar.download_filing_document(filing.exhibit_url)

    async def get_filing_index(self, accession_number: str, cik: str) -> dict[str, str]:
        """Parse HTML filing index from www.sec.gov to find exhibit URLs.

        Returns dict mapping exhibit type (e.g. "EX-102") to full URL.
        """
        from lxml import html

        cik_num = str(int(cik))
        acc_no_dashes = accession_number.replace("-", "")
        index_url = (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{cik_num}/{acc_no_dashes}/{accession_number}-index.htm"
        )

        response = await self.edgar.download_filing_document(index_url)
        tree = html.fromstring(response)

        exhibits: dict[str, str] = {}
        for row in tree.xpath('//table[@class="tableFile"]//tr'):
            cells = row.xpath("td")
            if len(cells) >= 4:
                doc_type = cells[3].text_content().strip()
                link = cells[2].xpath(".//a/@href")
                if link:
                    doc_url = link[0]
                    if not doc_url.startswith("http"):
                        doc_url = f"https://www.sec.gov{doc_url}"
                    exhibits[doc_type] = doc_url

        return exhibits

    async def _find_exhibit_102(self, accession_number: str, cik: str) -> str | None:
        """Find the EX-102 exhibit URL from a filing index."""
        try:
            exhibits = await self.get_filing_index(accession_number, cik)
        except Exception:
            logger.warning("Failed to fetch filing index for %s", accession_number)
            return None

        for doc_type, url in exhibits.items():
            if "EX-102" in doc_type.upper() and url.endswith(".xml"):
                return url

        return None

    async def _fetch_abs_ee_filings(self, cik: str) -> list[dict]:
        """Fetch ABS-EE filings from EDGAR submissions API, sorted by date desc."""
        submissions = await self.edgar.get_submissions(cik)
        recent = submissions.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accessions = recent.get("accessionNumber", [])
        dates = recent.get("filingDate", [])

        results = []
        for i, form in enumerate(forms):
            if form == "ABS-EE":
                results.append({
                    "accession_number": accessions[i],
                    "filing_date": dates[i],
                    "form_type": form,
                })

        # EDGAR returns most recent first, but sort explicitly
        results.sort(key=lambda x: x["filing_date"], reverse=True)
        return results

    async def _get_cached_filing(self, deal_id) -> Filing | None:
        """Check DB for a filing within the last 35 days."""
        cutoff = datetime.utcnow().date() - timedelta(days=35)
        stmt = (
            select(Filing)
            .where(Filing.deal_id == deal_id, Filing.filing_date >= cutoff)
            .order_by(Filing.filing_date.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _ensure_deal(self, cik: str, deal_ticker: str | None) -> Deal | None:
        """Get or create a Deal record for this CIK."""
        # Try by ticker first
        if deal_ticker:
            stmt = select(Deal).where(Deal.ticker == deal_ticker)
            result = await self.db.execute(stmt)
            deal = result.scalar_one_or_none()
            if deal:
                return deal

        # Try by CIK
        stmt = select(Deal).where(Deal.depositor_cik == cik)
        result = await self.db.execute(stmt)
        deal = result.scalar_one_or_none()
        if deal:
            return deal

        # Create a stub Deal if we have a ticker
        if deal_ticker:
            from nli_cmbs.edgar.cik_resolver import CikResolver

            parsed = CikResolver.parse_ticker(deal_ticker)
            shelf = parsed["shelf"] if parsed else "UNKNOWN"
            year = int(parsed["year"]) if parsed else 2024

            deal = Deal(
                ticker=deal_ticker,
                trust_name=deal_ticker,
                depositor_cik=cik,
                issuer_shelf=shelf,
                issuance_year=year,
            )
            self.db.add(deal)
            await self.db.commit()
            await self.db.refresh(deal)
            return deal

        return None
