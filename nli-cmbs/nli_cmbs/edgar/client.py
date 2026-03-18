import asyncio
import logging
import random
from typing import Any

import httpx

from nli_cmbs.config import settings

logger = logging.getLogger(__name__)


class EdgarError(Exception):
    """Base exception for EDGAR client errors."""


class EdgarRateLimitError(EdgarError):
    """Raised when EDGAR rate limit is exceeded and retries are exhausted."""


class EdgarNotFoundError(EdgarError):
    """Raised when the requested resource is not found (404)."""


class EdgarConnectionError(EdgarError):
    """Raised when a connection to EDGAR fails after retries."""


_MAX_RETRIES = 5
_BACKOFF_BASE = 2.0
_503_BACKOFF = [10.0, 30.0, 60.0, 120.0, 120.0]


def _jittered_delay(base_delay: float) -> float:
    """Add ±25% jitter to avoid thundering herd."""
    return base_delay * (0.75 + random.random() * 0.5)


class EdgarClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.EDGAR_BASE_URL,
            headers={"User-Agent": settings.EDGAR_USER_AGENT, "Accept": "application/json"},
            timeout=30.0,
        )
        self._semaphore = asyncio.Semaphore(3)

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        async with self._semaphore:
            last_exc: Exception | None = None
            for attempt in range(1, _MAX_RETRIES + 1):
                try:
                    if url.startswith("http://") or url.startswith("https://"):
                        response = await self._client.request(method, url, **kwargs)
                    else:
                        response = await self._client.request(method, url, **kwargs)

                    logger.info("EDGAR %s %s -> %d", method, url, response.status_code)

                    if response.status_code == 404:
                        raise EdgarNotFoundError(f"Not found: {url}")

                    if response.status_code == 429:
                        delay = _jittered_delay(_BACKOFF_BASE * (2 ** (attempt - 1)))
                        logger.warning("Rate limited (429), retry %d/%d in %.1fs", attempt, _MAX_RETRIES, delay)
                        last_exc = EdgarRateLimitError(f"Rate limited: {url}")
                        await asyncio.sleep(delay)
                        continue

                    if response.status_code == 503:
                        delay = _jittered_delay(_503_BACKOFF[min(attempt - 1, len(_503_BACKOFF) - 1)])
                        logger.warning(
                            "EDGAR 503 (slow down), retry %d/%d in %.0fs",
                            attempt, _MAX_RETRIES, delay,
                        )
                        last_exc = EdgarRateLimitError(f"503 slow down: {url}")
                        await asyncio.sleep(delay)
                        continue

                    if response.status_code >= 500:
                        delay = _jittered_delay(_BACKOFF_BASE * (2 ** (attempt - 1)))
                        logger.warning(
                            "Server error (%d), retry %d/%d in %.1fs",
                            response.status_code, attempt, _MAX_RETRIES, delay,
                        )
                        last_exc = EdgarConnectionError(f"Server error {response.status_code}: {url}")
                        await asyncio.sleep(delay)
                        continue

                    response.raise_for_status()
                    return response

                except httpx.HTTPStatusError:
                    raise
                except (httpx.ConnectError, httpx.TimeoutException) as exc:
                    delay = _jittered_delay(_BACKOFF_BASE * (2 ** (attempt - 1)))
                    logger.warning("Connection error, retry %d/%d in %.1fs: %s", attempt, _MAX_RETRIES, delay, exc)
                    last_exc = EdgarConnectionError(str(exc))
                    await asyncio.sleep(delay)

            if isinstance(last_exc, EdgarRateLimitError):
                raise last_exc
            raise last_exc or EdgarConnectionError(f"Request failed: {url}")

    async def get_submissions(self, cik: str) -> dict[str, Any]:
        """Fetch submission history for a CIK."""
        cik_padded = cik.zfill(10)
        response = await self._request("GET", f"/submissions/CIK{cik_padded}.json")
        return response.json()

    async def search_full_text(
        self,
        query: str,
        form_type: str | None = None,
        date_start: str | None = None,
        date_end: str | None = None,
    ) -> dict[str, Any]:
        """Search EDGAR full-text search API."""
        params: dict[str, str] = {"q": query}
        if form_type:
            params["forms"] = form_type
        if date_start:
            params["dateRange"] = "custom"
            params["startdt"] = date_start
        if date_end:
            params["dateRange"] = "custom"
            params["enddt"] = date_end
        response = await self._request("GET", "https://efts.sec.gov/LATEST/search-index", params=params)
        return response.json()

    async def download_filing_document(self, url: str) -> bytes:
        """Download a specific filing document (e.g. EX-102 XML)."""
        response = await self._request("GET", url)
        return response.content

    async def get_company_tickers(self) -> dict[str, Any]:
        """Fetch SEC's master company tickers file."""
        response = await self._request("GET", "https://www.sec.gov/files/company_tickers.json")
        return response.json()

    # Backward-compatible helpers used by cik_resolver and filing_fetcher
    async def get_json(self, path: str) -> dict:
        response = await self._request("GET", path)
        return response.json()

    async def get_text(self, path: str) -> str:
        response = await self._request("GET", path)
        return response.text

    async def close(self) -> None:
        await self._client.aclose()


_client_instance: EdgarClient | None = None


def get_edgar_client() -> EdgarClient:
    """Factory/singleton for FastAPI dependency injection."""
    global _client_instance
    if _client_instance is None:
        _client_instance = EdgarClient()
    return _client_instance
