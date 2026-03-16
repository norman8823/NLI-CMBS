from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nli_cmbs.ai.client import AnthropicClient
from nli_cmbs.ai.exceptions import (
    AIContextLengthError,
    AIGenerationError,
    AIRateLimitError,
    AITimeoutError,
)


@pytest.fixture
def client():
    with patch("nli_cmbs.ai.client.anthropic.AsyncAnthropic") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        c = AnthropicClient(api_key="test-key", model="test-model", max_tokens=1024, timeout=30)
        yield c, mock_instance


@pytest.mark.asyncio
async def test_generate_report_success(client):
    c, mock_anthropic = client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Generated report content")]
    mock_anthropic.messages.create = AsyncMock(return_value=mock_response)

    result = await c.generate_report(system_prompt="You are an analyst.", user_prompt="Analyze this deal.")

    assert result == "Generated report content"
    mock_anthropic.messages.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_report_rate_limit_retry(client):
    import anthropic as anthropic_mod

    c, mock_anthropic = client

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Success after retry")]

    rate_limit_error = anthropic_mod.RateLimitError(
        message="rate limited",
        response=MagicMock(status_code=429, headers={}),
        body=None,
    )

    mock_anthropic.messages.create = AsyncMock(side_effect=[rate_limit_error, mock_response])

    with patch("nli_cmbs.ai.client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await c.generate_report(system_prompt="system", user_prompt="user")

    assert result == "Success after retry"
    mock_sleep.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_generate_report_rate_limit_exhausted(client):
    import anthropic as anthropic_mod

    c, mock_anthropic = client

    rate_limit_error = anthropic_mod.RateLimitError(
        message="rate limited",
        response=MagicMock(status_code=429, headers={}),
        body=None,
    )

    mock_anthropic.messages.create = AsyncMock(side_effect=rate_limit_error)

    with patch("nli_cmbs.ai.client.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(AIRateLimitError, match="Rate limit exceeded"):
            await c.generate_report(system_prompt="system", user_prompt="user")


@pytest.mark.asyncio
async def test_generate_report_timeout(client):
    import anthropic as anthropic_mod

    c, mock_anthropic = client

    timeout_error = anthropic_mod.APITimeoutError(request=MagicMock())

    mock_anthropic.messages.create = AsyncMock(side_effect=timeout_error)

    with pytest.raises(AITimeoutError, match="timed out"):
        await c.generate_report(system_prompt="system", user_prompt="user")


@pytest.mark.asyncio
async def test_generate_report_context_length_error(client):
    import anthropic as anthropic_mod

    c, mock_anthropic = client

    context_error = anthropic_mod.BadRequestError(
        message="context length exceeded",
        response=MagicMock(status_code=400, headers={}),
        body=None,
    )

    mock_anthropic.messages.create = AsyncMock(side_effect=context_error)

    with pytest.raises(AIContextLengthError):
        await c.generate_report(system_prompt="system", user_prompt="user")


@pytest.mark.asyncio
async def test_generate_report_server_error_retry(client):
    import anthropic as anthropic_mod

    c, mock_anthropic = client

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Recovered")]

    server_error = anthropic_mod.InternalServerError(
        message="internal error",
        response=MagicMock(status_code=500, headers={}),
        body=None,
    )

    mock_anthropic.messages.create = AsyncMock(side_effect=[server_error, mock_response])

    with patch("nli_cmbs.ai.client.asyncio.sleep", new_callable=AsyncMock):
        result = await c.generate_report(system_prompt="system", user_prompt="user")

    assert result == "Recovered"


@pytest.mark.asyncio
async def test_generate_report_auth_error_no_retry(client):
    import anthropic as anthropic_mod

    c, mock_anthropic = client

    auth_error = anthropic_mod.AuthenticationError(
        message="invalid api key",
        response=MagicMock(status_code=401, headers={}),
        body=None,
    )

    mock_anthropic.messages.create = AsyncMock(side_effect=auth_error)

    with pytest.raises(AIGenerationError, match="invalid api key"):
        await c.generate_report(system_prompt="system", user_prompt="user")


def test_count_tokens(client):
    c, _ = client
    assert c.count_tokens("hello world") == 2  # 11 chars // 4
    assert c.count_tokens("a" * 100) == 25
    assert c.count_tokens("") == 0
