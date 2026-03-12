import logging
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nli_cmbs.db.models import CikMapping
from nli_cmbs.edgar.client import EdgarClient, EdgarNotFoundError
from nli_cmbs.edgar.seed_data import CMBS_SHELVES

logger = logging.getLogger(__name__)


class CikResolver:
    def __init__(self, edgar_client: EdgarClient, db_session: AsyncSession) -> None:
        self.edgar = edgar_client
        self.db = db_session

    async def resolve(self, deal_ticker: str) -> CikMapping | None:
        """Main resolution method. Tries strategies in strict priority order:
        1. DB lookup (Kaggle data, 2015-2023)
        2. EDGAR full-text search (2024+ deals)
        3. Depositor CIK traversal (last resort)
        """
        parsed = self.parse_ticker(deal_ticker)
        if not parsed:
            logger.warning("Could not parse ticker: %s", deal_ticker)
            return None

        normalized = parsed["normalized"]
        shelf = parsed["shelf"]
        year = parsed["year"]
        series = parsed["series"]

        # Strategy 1: DB lookup
        result = await self.resolve_from_db(normalized)
        if result:
            logger.info("Strategy 1 (DB): resolved %s → CIK %s", normalized, result.depositor_cik)
            return result

        # Strategy 2: EDGAR full-text search
        result = await self.resolve_from_search(shelf, year, series)
        if result:
            logger.info("Strategy 2 (EDGAR search): resolved %s → CIK %s", normalized, result.depositor_cik)
            return result

        # Strategy 3: Depositor CIK traversal (last resort)
        result = await self.resolve_from_seed(shelf, year, series)
        if result:
            logger.info("Strategy 3 (seed traversal): resolved %s → CIK %s", normalized, result.depositor_cik)
            return result

        logger.warning("All strategies failed for ticker: %s", deal_ticker)
        return None

    @staticmethod
    def parse_ticker(ticker: str) -> dict | None:
        """Parse a deal ticker into components and normalize.

        Handles formats like:
          "BMARK 2024-V6", "bmark-2024-v6", "BMARK2024V6",
          "BANK5 2024-5YR9", "GSMS 2023-GC15"
        """
        cleaned = ticker.strip().upper()
        cleaned = re.sub(r"[_]", " ", cleaned)

        # Match: SHELF (with optional trailing digits like BANK5), then YEAR, then SERIES
        # Allow separators: space, dash, or nothing between components
        m = re.match(
            r"^([A-Z]+\d*)[\s\-]*(\d{4})[\s\-]*([A-Z0-9]+)$",
            cleaned,
        )
        if not m:
            return None

        shelf = m.group(1)
        year = m.group(2)
        series = m.group(3)

        return {
            "shelf": shelf,
            "year": year,
            "series": series,
            "normalized": f"{shelf} {year}-{series}",
        }

    async def resolve_from_db(self, normalized_ticker: str) -> CikMapping | None:
        """Strategy 1: Query cik_mappings table with ilike matching."""
        stmt = select(CikMapping).where(CikMapping.deal_ticker.ilike(normalized_ticker))
        result = await self.db.execute(stmt)
        mapping = result.scalar_one_or_none()
        if mapping:
            return mapping

        # Try fuzzy match if exact didn't work
        stmt = select(CikMapping).where(CikMapping.deal_ticker.ilike(f"%{normalized_ticker}%"))
        result = await self.db.execute(stmt)
        mapping = result.scalar_one_or_none()
        return mapping

    async def resolve_from_search(self, shelf: str, year: str, series: str) -> CikMapping | None:
        """Strategy 2: Search EDGAR full-text for the trust name."""
        normalized = f"{shelf} {year}-{series}"

        # Build search query from shelf pattern or default
        shelf_info = CMBS_SHELVES.get(shelf)
        if shelf_info:
            trust_query = shelf_info["trust_name_pattern"].format(year=year, series=series)
        else:
            trust_query = normalized

        try:
            data = await self.edgar.search_full_text(f'"{trust_query}"', form_type="ABS-EE")
        except Exception:
            logger.warning("EDGAR search failed for %s", trust_query)
            return None

        hits = data.get("hits", {}).get("hits", [])
        if not hits:
            # Try simpler query without quotes
            try:
                data = await self.edgar.search_full_text(normalized, form_type="ABS-EE")
            except Exception:
                return None
            hits = data.get("hits", {}).get("hits", [])

        if not hits:
            return None

        # EFTS response: _source.display_names = ["Entity Name  (CIK 0001234567)"]
        #                _source.ciks = ["0001234567"]
        hit = hits[0]
        source_data = hit.get("_source", {})
        entity_name, cik = self._extract_entity_from_efts(source_data, trust_query)

        if not cik:
            return None

        # Determine trust_cik vs depositor_cik.
        # EFTS often returns only the trust entity (e.g. "Benchmark 2024-V6
        # Mortgage Trust" with its unique CIK). The depositor is not listed.
        # We need to detect this and assign the CIK to the correct field.
        trust_cik: str | None = None
        depositor_cik = cik

        if "trust" in entity_name.lower():
            # The CIK from EFTS is the trust CIK, not the depositor
            trust_cik = cik
            # Look up depositor CIK from seed data
            if shelf_info:
                depositor_cik = shelf_info["depositor_ciks"][0].lstrip("0") or "0"
            else:
                depositor_cik = cik  # fallback: can't determine depositor

        # For multi-entity responses, try to separate them
        if not trust_cik:
            trust_cik = self._extract_trust_cik(source_data, entity_name, cik)

        mapping = CikMapping(
            deal_ticker=normalized,
            trust_name=entity_name,
            depositor_cik=depositor_cik,
            trust_cik=trust_cik,
            issuer_shelf=shelf,
            depositor_name=shelf_info["depositor_name"] if shelf_info else None,
            verified=False,
            source="edgar_search",
        )
        await self.cache_mapping(mapping)
        return mapping

    @staticmethod
    def _extract_entity_from_efts(source_data: dict, trust_query: str) -> tuple[str, str]:
        """Extract entity name and CIK from EFTS search response _source.

        EFTS returns:
          display_names: ["Entity Name  (CIK 0001234567)"]
          ciks: ["0001234567"]

        For multi-entity filings (depositor + trust), prefer the trust entity
        whose display_name matches the trust query.
        """
        display_names = source_data.get("display_names", [])
        ciks = source_data.get("ciks", [])

        if not display_names or not ciks:
            return trust_query, ""

        # If only one entity, use it
        if len(display_names) == 1:
            name = re.sub(r"\s*\(CIK \d+\)\s*$", "", display_names[0]).strip()
            return name, ciks[0].lstrip("0") or "0"

        # Multiple entities — find the one matching the trust name
        query_lower = trust_query.lower()
        for i, dn in enumerate(display_names):
            name_clean = re.sub(r"\s*\(CIK \d+\)\s*$", "", dn).strip()
            if query_lower in name_clean.lower() or name_clean.lower() in query_lower:
                cik = ciks[i] if i < len(ciks) else ciks[-1]
                return name_clean, cik.lstrip("0") or "0"

        # Default to first entity
        name = re.sub(r"\s*\(CIK \d+\)\s*$", "", display_names[0]).strip()
        return name, ciks[0].lstrip("0") or "0"

    @staticmethod
    def _extract_trust_cik(source_data: dict, entity_name: str, depositor_cik: str) -> str | None:
        """Extract trust-specific CIK from EFTS multi-entity response.

        In CMBS filings, there are typically two entities:
        - The depositor (shared across deals on the same shelf)
        - The trust (unique per deal)

        If we identified the depositor CIK, the trust CIK is the OTHER entity.
        If the entity_name looks like a trust name (contains "Trust" or year pattern),
        the depositor_cik IS the trust CIK already.
        """
        display_names = source_data.get("display_names", [])
        ciks = source_data.get("ciks", [])

        if len(display_names) <= 1 or len(ciks) <= 1:
            return None

        # If entity_name contains "Trust", the CIK we have IS the trust CIK
        if "trust" in entity_name.lower():
            return depositor_cik

        # Otherwise, look for the trust entity (the other one)
        for i, dn in enumerate(display_names):
            name_clean = re.sub(r"\s*\(CIK \d+\)\s*$", "", dn).strip()
            if "trust" in name_clean.lower() and i < len(ciks):
                return ciks[i].lstrip("0") or "0"

        return None

    @staticmethod
    def _names_match(entity_name: str, trust_pattern: str, normalized: str) -> bool:
        """Check if an EDGAR entity name matches the expected deal."""
        entity_lower = entity_name.lower()
        return (
            trust_pattern.lower() in entity_lower
            or normalized.lower() in entity_lower
        )

    @staticmethod
    def _filing_matches_deal(
        forms: list, descriptions: list, filing_names: list,
        trust_pattern: str, normalized: str,
    ) -> bool:
        """Check if any ABS-EE filing in submissions matches the deal."""
        normalized_lower = normalized.lower()
        trust_lower = trust_pattern.lower()

        for i, form in enumerate(forms):
            if form != "ABS-EE":
                continue
            doc = descriptions[i].lower() if i < len(descriptions) else ""
            desc = filing_names[i].lower() if i < len(filing_names) else ""
            if (
                normalized_lower in doc
                or normalized_lower in desc
                or trust_lower in doc
                or trust_lower in desc
            ):
                return True
        return False

    async def resolve_from_seed(self, shelf: str, year: str, series: str) -> CikMapping | None:
        """Strategy 3 (LAST RESORT): Depositor CIK traversal.

        Iterates through all known depositor CIKs for the shelf and checks
        each one's EDGAR submissions for matching ABS-EE filings.
        """
        normalized = f"{shelf} {year}-{series}"
        shelf_info = CMBS_SHELVES.get(shelf)
        if not shelf_info:
            logger.warning("Shelf %s not in seed data", shelf)
            return None

        depositor_ciks = shelf_info["depositor_ciks"]
        trust_pattern = shelf_info["trust_name_pattern"].format(year=year, series=series)

        for depositor_cik in depositor_ciks:
            try:
                submissions = await self.edgar.get_submissions(depositor_cik)
            except EdgarNotFoundError:
                logger.warning("Depositor CIK %s not found on EDGAR", depositor_cik)
                continue
            except Exception:
                logger.warning("Failed to fetch submissions for CIK %s", depositor_cik)
                continue

            entity_name = submissions.get("name", "")
            recent = submissions.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            descriptions = recent.get("primaryDocument", [])
            filing_names = recent.get("primaryDocDescription", [])

            # Check entity name or filing descriptions for match
            if self._names_match(entity_name, trust_pattern, normalized):
                found_deal = True
            elif self._filing_matches_deal(forms, descriptions, filing_names, trust_pattern, normalized):
                found_deal = True
            else:
                logger.debug(
                    "CIK %s (%s) does not match deal %s, trying next depositor",
                    depositor_cik, entity_name, normalized,
                )
                continue

            if found_deal:
                logger.warning(
                    "Strategy 3 resolved %s via seed data. CIK %s (%s) is from seed data "
                    "and should be manually verified.",
                    normalized, depositor_cik, entity_name,
                )

                mapping = CikMapping(
                    deal_ticker=normalized,
                    trust_name=entity_name,
                    depositor_cik=depositor_cik.lstrip("0") or "0",
                    issuer_shelf=shelf,
                    depositor_name=shelf_info["depositor_name"],
                    verified=False,
                    source="seed_traversal",
                )
                await self.cache_mapping(mapping)
                return mapping

        logger.warning(
            "Strategy 3 exhausted all %d depositor CIKs for shelf %s without finding %s",
            len(depositor_ciks), shelf, normalized,
        )
        return None

    async def cache_mapping(self, mapping: CikMapping) -> None:
        """Save resolved mapping to PostgreSQL for future lookups."""
        # Check if already exists
        stmt = select(CikMapping).where(CikMapping.deal_ticker.ilike(mapping.deal_ticker))
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return
        self.db.add(mapping)
        await self.db.commit()
        await self.db.refresh(mapping)
        logger.info("Cached CIK mapping: %s → %s", mapping.deal_ticker, mapping.depositor_cik)

    @staticmethod
    def _parse_atom(xml_text: str) -> list[dict]:
        """Parse EDGAR ATOM feed response (kept for backward compatibility)."""
        from lxml import etree

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = etree.fromstring(xml_text.encode())
        entries = []
        for entry in root.findall("atom:entry", ns):
            title = entry.findtext("atom:title", default="", namespaces=ns)
            cik_el = entry.find("atom:content/atom:cik", ns)
            cik = cik_el.text if cik_el is not None else ""
            entries.append({"title": title.strip(), "cik": cik.strip(), "source": "edgar"})
        return entries
