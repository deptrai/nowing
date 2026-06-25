"""Integration tests for `crypto_tool_decorator` × rate limiter.

Round 2 review additions:
- Verify Circuit Breaker is checked BEFORE the rate limiter so a token is not
  wasted while the breaker is OPEN.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.new_chat.tools.utils import crypto_tool_decorator

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_decorator_respects_rate_limit():
    """If the rate limiter rejects, the wrapped tool must NOT run and the
    decorator returns a structured rate-limited error."""
    mock_limiter = AsyncMock()
    mock_limiter.acquire.return_value = False
    tool_called = {"flag": False}

    @crypto_tool_decorator(source="coingecko")
    async def my_tool():
        tool_called["flag"] = True
        return {"result": "ok"}

    with patch(
        "app.agents.new_chat.middleware.rate_limiter.get_limiter",
        return_value=mock_limiter,
    ), patch(
        "app.agents.new_chat.middleware.circuit_breaker.circuit_breaker.is_open",
        new=AsyncMock(return_value=False),
    ):
        result = await my_tool()

    assert result["status"] == "error"
    assert result["event"] == "rate_limited"
    assert "quota exhausted" in result["error"]
    assert tool_called["flag"] is False


@pytest.mark.asyncio
async def test_decorator_allows_execution_on_success():
    """Happy path: CB closed, rate limit acquired → tool runs."""
    mock_limiter = AsyncMock()
    mock_limiter.acquire.return_value = True

    @crypto_tool_decorator(source="defillama")
    async def my_tool():
        return {"status": "success", "data": 123}

    with patch(
        "app.agents.new_chat.middleware.rate_limiter.get_limiter",
        return_value=mock_limiter,
    ), patch(
        "app.agents.new_chat.middleware.circuit_breaker.circuit_breaker.is_open",
        new=AsyncMock(return_value=False),
    ), patch(
        "app.agents.new_chat.middleware.circuit_breaker.circuit_breaker.record_success",
        new=AsyncMock(return_value=None),
    ):
        result = await my_tool()

    assert result["status"] == "success"
    assert result["data"] == 123


@pytest.mark.asyncio
async def test_decorator_releases_token_on_tool_exception():
    """Story 11.7 T1: when the wrapped tool raises, the acquired token must be
    returned to the bucket — internal errors didn't actually charge the
    provider, so they shouldn't drain our local quota."""
    mock_limiter = AsyncMock()
    mock_limiter.acquire = AsyncMock(return_value=True)
    mock_limiter.release = AsyncMock(return_value=None)

    @crypto_tool_decorator(source="coingecko")
    async def broken_tool():
        raise RuntimeError("boom")

    with patch(
        "app.agents.new_chat.middleware.rate_limiter.get_limiter",
        return_value=mock_limiter,
    ), patch(
        "app.agents.new_chat.middleware.circuit_breaker.circuit_breaker.is_open",
        new=AsyncMock(return_value=False),
    ), patch(
        "app.agents.new_chat.middleware.circuit_breaker.circuit_breaker.record_failure",
        new=AsyncMock(return_value=None),
    ):
        result = await broken_tool()

    assert result["status"] == "error"
    mock_limiter.acquire.assert_called_once()
    mock_limiter.release.assert_called_once()


@pytest.mark.asyncio
async def test_decorator_releases_token_on_timeout():
    """Story 11.7 T1: TimeoutError path also releases — provider never received
    a billable request."""
    import asyncio as _asyncio

    mock_limiter = AsyncMock()
    mock_limiter.acquire = AsyncMock(return_value=True)
    mock_limiter.release = AsyncMock(return_value=None)

    @crypto_tool_decorator(source="defillama")
    async def slow_tool():
        raise _asyncio.TimeoutError()

    with patch(
        "app.agents.new_chat.middleware.rate_limiter.get_limiter",
        return_value=mock_limiter,
    ), patch(
        "app.agents.new_chat.middleware.circuit_breaker.circuit_breaker.is_open",
        new=AsyncMock(return_value=False),
    ), patch(
        "app.agents.new_chat.middleware.circuit_breaker.circuit_breaker.record_failure",
        new=AsyncMock(return_value=None),
    ):
        result = await slow_tool()

    assert "timed out" in result["error"]
    mock_limiter.release.assert_called_once()


@pytest.mark.asyncio
async def test_decorator_does_NOT_release_on_success():
    """Successful tool call must NOT call release — that would refund a
    legitimately-consumed token and bypass rate limiting."""
    mock_limiter = AsyncMock()
    mock_limiter.acquire = AsyncMock(return_value=True)
    mock_limiter.release = AsyncMock(return_value=None)

    @crypto_tool_decorator(source="defillama")
    async def good_tool():
        return {"status": "success", "data": 42}

    with patch(
        "app.agents.new_chat.middleware.rate_limiter.get_limiter",
        return_value=mock_limiter,
    ), patch(
        "app.agents.new_chat.middleware.circuit_breaker.circuit_breaker.is_open",
        new=AsyncMock(return_value=False),
    ), patch(
        "app.agents.new_chat.middleware.circuit_breaker.circuit_breaker.record_success",
        new=AsyncMock(return_value=None),
    ):
        result = await good_tool()

    assert result["status"] == "success"
    mock_limiter.release.assert_not_called()


@pytest.mark.asyncio
async def test_decorator_does_not_consume_token_when_circuit_breaker_open():
    """Round 2 review: the decorator must check Circuit Breaker BEFORE the
    rate limiter. If we consumed a token first, the bucket would drain to
    zero during a sustained provider outage — even though no outbound calls
    were ever made — and once the breaker closed legitimate traffic would
    starve."""
    mock_limiter = AsyncMock()
    mock_limiter.acquire = AsyncMock(return_value=True)

    @crypto_tool_decorator(source="coingecko")
    async def my_tool():
        return {"status": "success"}

    with patch(
        "app.agents.new_chat.middleware.rate_limiter.get_limiter",
        return_value=mock_limiter,
    ), patch(
        "app.agents.new_chat.middleware.circuit_breaker.circuit_breaker.is_open",
        new=AsyncMock(return_value=True),
    ):
        result = await my_tool()

    assert result["status"] == "error"
    assert "Circuit open" in result["error"]
    # Critical: the rate limiter MUST NOT have been consulted while the
    # circuit was open. Otherwise we'd drain the bucket on every blocked
    # request.
    mock_limiter.acquire.assert_not_called()
