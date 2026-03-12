from unittest.mock import AsyncMock, MagicMock

import pytest

from nli_cmbs.db.models import CikMapping
from nli_cmbs.edgar.cik_resolver import CikResolver


class TestParseTicker:
    @pytest.mark.parametrize(
        "input_ticker,expected",
        [
            ("BMARK 2024-V6", {"shelf": "BMARK", "year": "2024", "series": "V6", "normalized": "BMARK 2024-V6"}),
            ("bmark-2024-v6", {"shelf": "BMARK", "year": "2024", "series": "V6", "normalized": "BMARK 2024-V6"}),
            ("BMARK2024V6", {"shelf": "BMARK", "year": "2024", "series": "V6", "normalized": "BMARK 2024-V6"}),
            ("GSMS 2023-GC15", {"shelf": "GSMS", "year": "2023", "series": "GC15", "normalized": "GSMS 2023-GC15"}),
            (
                "BANK5 2024-5YR9",
                {"shelf": "BANK5", "year": "2024", "series": "5YR9", "normalized": "BANK5 2024-5YR9"},
            ),
            ("BMO 2023-5C1", {"shelf": "BMO", "year": "2023", "series": "5C1", "normalized": "BMO 2023-5C1"}),
            ("BBCMS 2023-C20", {"shelf": "BBCMS", "year": "2023", "series": "C20", "normalized": "BBCMS 2023-C20"}),
        ],
    )
    def test_normalization(self, input_ticker, expected):
        result = CikResolver.parse_ticker(input_ticker)
        assert result == expected

    def test_invalid_ticker_returns_none(self):
        assert CikResolver.parse_ticker("") is None
        assert CikResolver.parse_ticker("NOTVALID") is None


def _efts_response(display_names, ciks):
    """Build a mock EFTS search response."""
    return {
        "hits": {
            "hits": [
                {
                    "_source": {
                        "display_names": display_names,
                        "ciks": ciks,
                    }
                }
            ]
        }
    }


class TestResolveFromDb:
    @pytest.mark.asyncio
    async def test_exact_match(self):
        mapping = CikMapping(
            deal_ticker="BBCMS 2023-C20",
            trust_name="BBCMS Mortgage Trust 2023-C20",
            depositor_cik="1981769",
            issuer_shelf="BBCMS",
            source="kaggle_cmdrvl",
            verified=True,
        )
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mapping
        mock_session.execute.return_value = mock_result

        resolver = CikResolver(edgar_client=AsyncMock(), db_session=mock_session)
        result = await resolver.resolve_from_db("BBCMS 2023-C20")
        assert result is mapping
        assert result.depositor_cik == "1981769"


class TestResolveFromSearch:
    @pytest.mark.asyncio
    async def test_search_hit_caches_result(self):
        mock_client = AsyncMock()
        mock_client.search_full_text.return_value = _efts_response(
            display_names=["Benchmark 2024-V6 Mortgage Trust  (CIK 0002012265)"],
            ciks=["0002012265"],
        )

        mock_session = AsyncMock()
        mock_cache_result = MagicMock()
        mock_cache_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_cache_result

        resolver = CikResolver(edgar_client=mock_client, db_session=mock_session)
        result = await resolver.resolve_from_search("BMARK", "2024", "V6")

        assert result is not None
        # depositor_cik should be from seed data (Deutsche Mortgage), not the trust
        assert result.depositor_cik == "1013454"
        # trust_cik should be the trust entity from EFTS
        assert result.trust_cik == "2012265"
        assert result.trust_name == "Benchmark 2024-V6 Mortgage Trust"
        assert result.source == "edgar_search"
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_multi_entity_picks_trust(self):
        mock_client = AsyncMock()
        mock_client.search_full_text.return_value = _efts_response(
            display_names=[
                "DEUTSCHE MORTGAGE & ASSET RECEIVING CORP  (CIK 0001013454)",
                "Benchmark 2024-V6 Mortgage Trust  (CIK 0002012265)",
            ],
            ciks=["0001013454", "0002012265"],
        )

        mock_session = AsyncMock()
        mock_cache_result = MagicMock()
        mock_cache_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_cache_result

        resolver = CikResolver(edgar_client=mock_client, db_session=mock_session)
        result = await resolver.resolve_from_search("BMARK", "2024", "V6")

        assert result is not None
        # depositor_cik should be from seed data, trust_cik from EFTS
        assert result.depositor_cik == "1013454"
        assert result.trust_cik == "2012265"
        assert "Benchmark" in result.trust_name

    @pytest.mark.asyncio
    async def test_search_miss_returns_none(self):
        mock_client = AsyncMock()
        mock_client.search_full_text.return_value = {"hits": {"hits": []}}

        resolver = CikResolver(edgar_client=mock_client, db_session=AsyncMock())
        result = await resolver.resolve_from_search("BMARK", "2099", "Z1")
        assert result is None


class TestResolveStrategyOrder:
    @pytest.mark.asyncio
    async def test_db_hit_skips_edgar(self):
        """A 2023 deal in the DB should resolve without hitting EDGAR."""
        mapping = CikMapping(
            deal_ticker="BBCMS 2023-C20",
            trust_name="BBCMS Mortgage Trust 2023-C20",
            depositor_cik="1981769",
            issuer_shelf="BBCMS",
            source="kaggle_cmdrvl",
            verified=True,
        )
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mapping
        mock_session.execute.return_value = mock_result

        mock_client = AsyncMock()

        resolver = CikResolver(edgar_client=mock_client, db_session=mock_session)
        result = await resolver.resolve("BBCMS 2023-C20")

        assert result is mapping
        mock_client.search_full_text.assert_not_called()
        mock_client.get_submissions.assert_not_called()

    @pytest.mark.asyncio
    async def test_db_miss_falls_to_edgar_search(self):
        """A 2024 deal not in DB should fall through to EDGAR search."""
        mock_session = AsyncMock()
        mock_db_result = MagicMock()
        mock_db_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_db_result

        mock_client = AsyncMock()
        mock_client.search_full_text.return_value = _efts_response(
            display_names=["Benchmark 2024-V6 Mortgage Trust  (CIK 0002012265)"],
            ciks=["0002012265"],
        )

        resolver = CikResolver(edgar_client=mock_client, db_session=mock_session)
        result = await resolver.resolve("BMARK 2024-V6")

        assert result is not None
        assert result.depositor_cik == "1013454"  # from seed data (Deutsche Mortgage)
        assert result.trust_cik == "2012265"  # trust CIK from EFTS
        assert result.source == "edgar_search"
        mock_client.search_full_text.assert_called()

    @pytest.mark.asyncio
    async def test_all_miss_returns_none(self):
        """If all strategies fail, return None."""
        mock_session = AsyncMock()
        mock_db_result = MagicMock()
        mock_db_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_db_result

        mock_client = AsyncMock()
        mock_client.search_full_text.return_value = {"hits": {"hits": []}}
        mock_client.get_submissions.return_value = {
            "name": "Unrelated Entity",
            "filings": {"recent": {"form": [], "primaryDocument": [], "primaryDocDescription": []}},
        }

        resolver = CikResolver(edgar_client=mock_client, db_session=mock_session)
        result = await resolver.resolve("ZZZZ 2099-X1")
        assert result is None


class TestCaching:
    @pytest.mark.asyncio
    async def test_cached_result_reused(self):
        """After EDGAR search caches a result, second resolve hits DB."""
        mapping = CikMapping(
            deal_ticker="BMARK 2024-V6",
            trust_name="Benchmark 2024-V6 Mortgage Trust",
            depositor_cik="1013454",
            trust_cik="2012265",
            issuer_shelf="BMARK",
            source="edgar_search",
            verified=False,
        )

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            # First two calls: DB miss (resolve_from_db exact + fuzzy)
            # Third call: cache_mapping check (no existing)
            # Fourth+ calls: DB hit (cached)
            if call_count <= 3:
                mock_result.scalar_one_or_none.return_value = None
            else:
                mock_result.scalar_one_or_none.return_value = mapping
            return mock_result

        mock_session = AsyncMock()
        mock_session.execute.side_effect = side_effect

        mock_client = AsyncMock()
        mock_client.search_full_text.return_value = _efts_response(
            display_names=["Benchmark 2024-V6 Mortgage Trust  (CIK 0002012265)"],
            ciks=["0002012265"],
        )

        resolver = CikResolver(edgar_client=mock_client, db_session=mock_session)

        # First call: DB miss → EDGAR search → cached
        result1 = await resolver.resolve("BMARK 2024-V6")
        assert result1 is not None
        assert mock_client.search_full_text.call_count == 1

        # Second call: DB hit (cached)
        result2 = await resolver.resolve("BMARK 2024-V6")
        assert result2 is mapping
        assert mock_client.search_full_text.call_count == 1


class TestExtractEntityFromEfts:
    def test_single_entity(self):
        source = {
            "display_names": ["Benchmark 2024-V6 Mortgage Trust  (CIK 0002012265)"],
            "ciks": ["0002012265"],
        }
        name, cik = CikResolver._extract_entity_from_efts(source, "Benchmark 2024-V6 Mortgage Trust")
        assert name == "Benchmark 2024-V6 Mortgage Trust"
        assert cik == "2012265"

    def test_multi_entity_picks_trust(self):
        source = {
            "display_names": [
                "DEUTSCHE MORTGAGE & ASSET RECEIVING CORP  (CIK 0001013454)",
                "Benchmark 2024-V6 Mortgage Trust  (CIK 0002012265)",
            ],
            "ciks": ["0001013454", "0002012265"],
        }
        name, cik = CikResolver._extract_entity_from_efts(source, "Benchmark 2024-V6 Mortgage Trust")
        assert name == "Benchmark 2024-V6 Mortgage Trust"
        assert cik == "2012265"

    def test_empty_returns_empty_cik(self):
        name, cik = CikResolver._extract_entity_from_efts({}, "query")
        assert cik == ""


class TestParseAtom:
    def test_parse_atom_empty(self):
        xml = '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        result = CikResolver._parse_atom(xml)
        assert result == []

    def test_parse_atom_with_entries(self):
        xml = """<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <entry>
                <title>Benchmark 2024-V6 Mortgage Trust</title>
                <content><cik>0001234567</cik></content>
            </entry>
        </feed>"""
        result = CikResolver._parse_atom(xml)
        assert len(result) == 1
        assert result[0]["title"] == "Benchmark 2024-V6 Mortgage Trust"
        assert result[0]["cik"] == "0001234567"
