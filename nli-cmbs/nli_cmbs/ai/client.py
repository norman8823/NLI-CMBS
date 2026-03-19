from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

import anthropic

from nli_cmbs.ai.exceptions import (
    AIContextLengthError,
    AIGenerationError,
    AIRateLimitError,
    AITimeoutError,
)

logger = logging.getLogger(__name__)


@dataclass
class InferenceResult:
    """Rich result from an AI inference call."""
    text: str
    model_id: str
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int | None

_RATE_LIMIT_MAX_RETRIES = 3
_RATE_LIMIT_BACKOFFS = [1, 2, 4]

_SERVER_ERROR_MAX_RETRIES = 2
_SERVER_ERROR_BACKOFFS = [1, 2]


class AnthropicClient:
    """Wrapper around the Anthropic API for CMBS report generation."""

    def __init__(self, api_key: str, model: str, max_tokens: int, timeout: int) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout)

    async def generate_report(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
    ) -> InferenceResult:
        """Generate a surveillance report.

        Returns an InferenceResult with text, model_id, token usage, and latency.

        Raises:
            AIRateLimitError: Rate limit hit after retries exhausted.
            AIContextLengthError: Input exceeds model context length.
            AITimeoutError: Request timed out after retries exhausted.
            AIGenerationError: Any other API failure.
        """
        rate_limit_retries = 0
        server_error_retries = 0
        start = time.monotonic()

        while True:
            try:
                response = await self._client.messages.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                elapsed_ms = int((time.monotonic() - start) * 1000)
                return InferenceResult(
                    text=response.content[0].text,
                    model_id=self._model,
                    prompt_tokens=getattr(response.usage, "input_tokens", None),
                    completion_tokens=getattr(response.usage, "output_tokens", None),
                    latency_ms=elapsed_ms,
                )

            except anthropic.RateLimitError as exc:
                rate_limit_retries += 1
                if rate_limit_retries > _RATE_LIMIT_MAX_RETRIES:
                    raise AIRateLimitError(f"Rate limit exceeded after {_RATE_LIMIT_MAX_RETRIES} retries") from exc
                backoff = _RATE_LIMIT_BACKOFFS[rate_limit_retries - 1]
                logger.warning(
                    "Rate limited (attempt %d/%d), retrying in %ds",
                    rate_limit_retries, _RATE_LIMIT_MAX_RETRIES, backoff,
                )
                await asyncio.sleep(backoff)

            except anthropic.APIStatusError as exc:
                if exc.status_code == 400 and "context" in str(exc).lower():
                    raise AIContextLengthError(str(exc)) from exc

                if 500 <= exc.status_code < 600:
                    server_error_retries += 1
                    if server_error_retries > _SERVER_ERROR_MAX_RETRIES:
                        msg = f"Server error after {_SERVER_ERROR_MAX_RETRIES} retries: {exc}"
                        raise AIGenerationError(msg) from exc
                    backoff = _SERVER_ERROR_BACKOFFS[server_error_retries - 1]
                    logger.warning(
                        "Server error %d (attempt %d/%d), retrying in %ds",
                        exc.status_code, server_error_retries, _SERVER_ERROR_MAX_RETRIES, backoff,
                    )
                    await asyncio.sleep(backoff)
                else:
                    # 4xx client errors (auth, bad request) — no retry
                    raise AIGenerationError(str(exc)) from exc

            except anthropic.APITimeoutError as exc:
                raise AITimeoutError(f"Request timed out: {exc}") from exc

            except anthropic.APIConnectionError as exc:
                raise AIGenerationError(f"Connection error: {exc}") from exc

    @property
    def model_id(self) -> str:
        """Public accessor for the model identifier."""
        return self._model


def get_anthropic_client() -> AnthropicClient:
    """Factory function for FastAPI dependency injection."""
    from nli_cmbs.config import settings

    return AnthropicClient(
        api_key=settings.ANTHROPIC_API_KEY,
        model=settings.ANTHROPIC_MODEL,
        max_tokens=settings.ANTHROPIC_MAX_TOKENS,
        timeout=settings.ANTHROPIC_TIMEOUT,
    )
