"""Unit tests for ChainlensResearchService."""

import importlib
import time

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.services.chainlens_research_service import (
    ChainlensResearchService,
    ChainlensUnavailableError,
)


@pytest.fixture(autouse=True)
def _reset_service_state():
    """Reset class-level cache + cooldown before each test to avoid cross-test leakage."""
    ChainlensResearchService._health_cache = (False, 0.0)
    ChainlensResearchService._error_cooldown_until = 0.0
    yield
    ChainlensResearchService._health_cache = (False, 0.0)
    ChainlensResearchService._error_cooldown_until = 0.0


def _mock_http_client(**method_mocks) -> MagicMock:
    """Build an httpx.AsyncClient mock with per-method AsyncMock return/side_effect."""
    inner = MagicMock(**method_mocks)
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=inner)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


def _patch_config(**kwargs):
    """Helper to patch config attributes on the service module."""
    defaults = {
        "CHAINLENS_RESEARCH_ENABLED": True,
        "CHAINLENS_RESEARCH_API_URL": "https://api.chainlens.example",
        "CHAINLENS_RESEARCH_API_KEY": "test-api-key",
        "CHAINLENS_HEALTH_CACHE_TTL": 30,
    }
    defaults.update(kwargs)
    patcher = patch("app.services.chainlens_research_service.config")
    mock_config = patcher.start()
    for k, v in defaults.items():
        setattr(mock_config, k, v)
    return patcher, mock_config


# ---------------------------------------------------------------------------
# is_available() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "config_override",
    [
        {"CHAINLENS_RESEARCH_ENABLED": False},
        {"CHAINLENS_RESEARCH_API_URL": ""},
    ],
    ids=["flag_disabled", "url_empty"],
)
async def test_is_available_returns_false_without_network(config_override):
    """AC#1: disabled flag or empty URL → return False without making any network call."""
    patcher, _ = _patch_config(**config_override)
    try:
        with patch("httpx.AsyncClient") as mock_client:
            result = await ChainlensResearchService.is_available()
        assert result is False
        mock_client.assert_not_called()
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_is_available_health_check_returns_true_on_200():
    """AC#2: Health endpoint returns 200 → is_available() returns True."""
    patcher, _ = _patch_config()
    try:
        mock_response = MagicMock(status_code=200)
        mock_get = AsyncMock(return_value=mock_response)
        client = _mock_http_client(get=mock_get)

        with patch("httpx.AsyncClient", return_value=client):
            result = await ChainlensResearchService.is_available()

        assert result is True
        mock_get.assert_called_once_with(
            "https://api.chainlens.example/api/v1/b2b/health"
        )
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_is_available_caches_result_within_ttl():
    """AC#2: Two calls within TTL → only 1 network call."""
    patcher, _ = _patch_config()
    try:
        mock_response = MagicMock(status_code=200)
        mock_get = AsyncMock(return_value=mock_response)
        client = _mock_http_client(get=mock_get)

        with patch("httpx.AsyncClient", return_value=client):
            result1 = await ChainlensResearchService.is_available()
            result2 = await ChainlensResearchService.is_available()

        assert result1 is True
        assert result2 is True
        assert mock_get.call_count == 1, "Should only call network once within TTL"
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_is_available_returns_false_during_error_cooldown():
    """After research() failure, is_available returns False during cooldown window."""
    patcher, _ = _patch_config()
    try:
        ChainlensResearchService._health_cache = (True, time.monotonic())
        ChainlensResearchService._error_cooldown_until = time.monotonic() + 10

        with patch("httpx.AsyncClient") as mock_client:
            result = await ChainlensResearchService.is_available()

        assert result is False
        mock_client.assert_not_called()
    finally:
        patcher.stop()


# ---------------------------------------------------------------------------
# research() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_research_success_verifies_headers_and_payload():
    """AC#3: research() sends correct headers and body, returns parsed JSON."""
    patcher, _ = _patch_config()
    try:
        health_response = MagicMock(status_code=200)
        research_response = MagicMock(status_code=200)
        research_response.json.return_value = {"message": "result", "sources": []}

        mock_get = AsyncMock(return_value=health_response)
        mock_post = AsyncMock(return_value=research_response)
        client = _mock_http_client(get=mock_get, post=mock_post)

        with patch("httpx.AsyncClient", return_value=client):
            result = await ChainlensResearchService.research("test query", ["web"])

        assert result == {"message": "result", "sources": []}

        kwargs = mock_post.call_args
        assert kwargs[0][0] == "https://api.chainlens.example/api/v1/b2b/research"
        assert kwargs[1]["json"]["query"] == "test query"
        assert kwargs[1]["json"]["sources"] == ["web"]
        assert kwargs[1]["json"]["stream"] is False
        assert kwargs[1]["headers"]["Authorization"] == "Bearer test-api-key"
        assert kwargs[1]["headers"]["Content-Type"] == "application/json"
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_research_empty_query_raises_value_error():
    """Input validation: empty/whitespace query → ValueError."""
    patcher, _ = _patch_config()
    try:
        with pytest.raises(ValueError, match="non-empty"):
            await ChainlensResearchService.research("   ")
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_research_invalid_sources_raises_value_error():
    """Input validation: invalid source values → ValueError listing valid options."""
    patcher, _ = _patch_config()
    try:
        with pytest.raises(ValueError, match="Invalid sources"):
            await ChainlensResearchService.research("q", ["wikipedia"])
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_research_timeout_retries_then_raises_and_sets_cooldown():
    """AC#4: Timeout → retry 1x, then raise + trigger cooldown (health_cache untouched)."""
    patcher, _ = _patch_config()
    try:
        ChainlensResearchService._health_cache = (True, time.monotonic())

        mock_post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        client = _mock_http_client(post=mock_post)

        with patch("httpx.AsyncClient", return_value=client), \
             patch("asyncio.sleep", new=AsyncMock()):
            with pytest.raises(ChainlensUnavailableError, match="timed out"):
                await ChainlensResearchService.research("query")

        assert mock_post.call_count == 2, "Should retry once on timeout"
        assert ChainlensResearchService._error_cooldown_until > time.monotonic()
        # health_cache remains truthy — error cooldown is the circuit breaker
        assert ChainlensResearchService._health_cache[0] is True
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_research_http_500_retries_then_raises():
    """AC#4: HTTP 500 → retry 1x, then raise + trigger cooldown."""
    patcher, _ = _patch_config()
    try:
        ChainlensResearchService._health_cache = (True, time.monotonic())

        error_response = MagicMock(status_code=500, text="Internal Server Error")
        mock_post = AsyncMock(return_value=error_response)
        client = _mock_http_client(post=mock_post)

        with patch("httpx.AsyncClient", return_value=client), \
             patch("asyncio.sleep", new=AsyncMock()):
            with pytest.raises(ChainlensUnavailableError, match="HTTP 500"):
                await ChainlensResearchService.research("query")

        assert mock_post.call_count == 2, "Should retry once on 5xx"
        assert ChainlensResearchService._error_cooldown_until > time.monotonic()
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_research_http_400_does_not_retry():
    """4xx errors are not retryable — single attempt, cooldown still triggered."""
    patcher, _ = _patch_config()
    try:
        ChainlensResearchService._health_cache = (True, time.monotonic())

        error_response = MagicMock(status_code=400, text="Bad Request")
        mock_post = AsyncMock(return_value=error_response)
        client = _mock_http_client(post=mock_post)

        with patch("httpx.AsyncClient", return_value=client):
            with pytest.raises(ChainlensUnavailableError, match="HTTP 400"):
                await ChainlensResearchService.research("query")

        assert mock_post.call_count == 1
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_research_json_parse_error_does_not_trigger_cooldown():
    """Malformed 200 JSON body → ChainlensUnavailableError but no cooldown (data bug)."""
    patcher, _ = _patch_config()
    try:
        ChainlensResearchService._health_cache = (True, time.monotonic())

        bad_response = MagicMock(status_code=200)
        bad_response.json.side_effect = ValueError("bad json")
        mock_post = AsyncMock(return_value=bad_response)
        client = _mock_http_client(post=mock_post)

        with patch("httpx.AsyncClient", return_value=client):
            with pytest.raises(ChainlensUnavailableError, match="parse error"):
                await ChainlensResearchService.research("query")

        # Cooldown NOT triggered — parse error is data bug, not availability
        assert ChainlensResearchService._error_cooldown_until == 0.0
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_is_available_with_empty_url_does_not_raise():
    """AC#5: Missing URL → no exception, is_available returns False."""
    patcher, _ = _patch_config(
        CHAINLENS_RESEARCH_API_URL="",
        CHAINLENS_RESEARCH_ENABLED=False,
    )
    try:
        result = await ChainlensResearchService.is_available()
        assert result is False
    finally:
        patcher.stop()


def test_startup_warning_logs_when_url_empty(caplog):
    """DEPRECATED: Obsolete since Story 7.4 (D1+D2) — module-import-time
    `_log_startup_warning()` was removed in favor of the single-source-of-truth
    lifespan validator `_validate_chainlens_config()` in `app/app.py`.

    Equivalent coverage now lives in
    `tests/unit/app/test_chainlens_config_validation.py::test_enabled_missing_api_url_logs_warning`.
    """
    pytest.skip(
        "obsolete — replaced by test_enabled_missing_api_url_logs_warning in "
        "tests/unit/app/test_chainlens_config_validation.py (Story 7.4 D1+D2)"
    )
