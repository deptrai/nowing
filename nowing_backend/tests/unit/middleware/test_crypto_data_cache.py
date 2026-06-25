"""Unit tests for CryptoDataCacheMiddleware — AC1 through AC6 + args_hash discrimination."""
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import ToolMessage

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeRequest:
    def __init__(self, name: str, args: dict, call_id: str = "call_abc"):
        self.tool_call = {"name": name, "args": args, "id": call_id}


def _make_handler(return_value):
    async def _handler(request):
        return return_value

    return _handler


_DEFILLAMA_ARGS = {"protocol_slug": "uniswap"}
_CACHED_DATA = {"tvl": 1_234_567, "name": "Uniswap"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _enable_cache(monkeypatch):
    """Patch module-level flag so tests run with cache ON by default."""
    monkeypatch.setattr(
        "app.agents.new_chat.middleware.crypto_data_cache._CACHE_ENABLED", True
    )


class _SessionCtxManager:
    """Reusable async context manager mock for shielded_async_session."""

    def __init__(self):
        self.db = AsyncMock()

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, *args):
        pass


# ---------------------------------------------------------------------------
# AC1: Cache hit — no API call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ac1_cache_hit_returns_cached_data_and_skips_handler():
    """Fresh snapshot in DB → handler never called, cached data returned."""
    from app.agents.new_chat.middleware.crypto_data_cache import CryptoDataCacheMiddleware

    request = _FakeRequest("get_defillama_protocol", _DEFILLAMA_ARGS)
    handler = AsyncMock(side_effect=AssertionError("Handler must NOT be called on cache hit"))

    session = _SessionCtxManager()

    with patch(
        "app.agents.new_chat.middleware.crypto_data_cache.shielded_async_session",
        return_value=session,
    ), patch(
        "app.agents.new_chat.middleware.crypto_data_cache.CryptoProjectResolver"
    ) as MockResolver, patch(
        "app.agents.new_chat.middleware.crypto_data_cache.CryptoDataStore"
    ) as MockStore:
        MockResolver.return_value.resolve = AsyncMock(return_value=42)
        MockStore.return_value.get_fresh_snapshot = AsyncMock(return_value=_CACHED_DATA)

        mw = CryptoDataCacheMiddleware(search_space_id=1)
        result = await mw.awrap_tool_call(request, handler)

    assert isinstance(result, ToolMessage)
    assert json.loads(result.content) == _CACHED_DATA
    assert result.tool_call_id == "call_abc"
    handler.assert_not_called()


# ---------------------------------------------------------------------------
# AC2: Cache miss → API call → write snapshot
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ac2_cache_miss_calls_handler_and_writes_snapshot():
    """No snapshot in DB → handler called once, snapshot written."""
    from app.agents.new_chat.middleware.crypto_data_cache import CryptoDataCacheMiddleware

    request = _FakeRequest("get_defillama_protocol", _DEFILLAMA_ARGS)
    api_result = ToolMessage(
        content=json.dumps({"tvl": 999}), tool_call_id="call_abc", name="get_defillama_protocol"
    )
    handler = AsyncMock(return_value=api_result)

    sessions: list[_SessionCtxManager] = []

    def _make_session():
        s = _SessionCtxManager()
        sessions.append(s)
        return s

    with patch(
        "app.agents.new_chat.middleware.crypto_data_cache.shielded_async_session",
        side_effect=_make_session,
    ), patch(
        "app.agents.new_chat.middleware.crypto_data_cache.CryptoProjectResolver"
    ) as MockResolver, patch(
        "app.agents.new_chat.middleware.crypto_data_cache.CryptoDataStore"
    ) as MockStore:
        MockResolver.return_value.resolve = AsyncMock(return_value=7)
        MockStore.return_value.get_fresh_snapshot = AsyncMock(return_value=None)
        MockStore.return_value.write_snapshot = AsyncMock()

        mw = CryptoDataCacheMiddleware(search_space_id=1)
        result = await mw.awrap_tool_call(request, handler)

    handler.assert_called_once()
    assert result is api_result
    MockStore.return_value.write_snapshot.assert_called_once()
    write_kwargs = MockStore.return_value.write_snapshot.call_args[1]
    assert write_kwargs["is_error"] is False
    assert write_kwargs["ttl_seconds"] == 3600  # defi_tvl TTL


# ---------------------------------------------------------------------------
# AC3: Cache disabled → pass-through, no DB queries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ac3_cache_disabled_passes_through(monkeypatch):
    """CRYPTO_DATA_CACHE_ENABLED=false → handler called directly, no DB ops."""
    import app.agents.new_chat.middleware.crypto_data_cache as cache_mod

    monkeypatch.setattr(cache_mod, "_CACHE_ENABLED", False)
    from app.agents.new_chat.middleware.crypto_data_cache import CryptoDataCacheMiddleware

    request = _FakeRequest("get_defillama_protocol", _DEFILLAMA_ARGS)
    api_result = {"tvl": 500}
    handler = AsyncMock(return_value=api_result)

    with patch(
        "app.agents.new_chat.middleware.crypto_data_cache.shielded_async_session"
    ) as mock_session:
        mw = CryptoDataCacheMiddleware(search_space_id=1)
        result = await mw.awrap_tool_call(request, handler)

    mock_session.assert_not_called()
    handler.assert_called_once()
    assert result is api_result


# ---------------------------------------------------------------------------
# AC4: Graceful degradation — DB error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ac4_db_error_falls_back_to_handler():
    """DB lookup raises → middleware catches, calls handler, returns result."""
    from app.agents.new_chat.middleware.crypto_data_cache import CryptoDataCacheMiddleware

    request = _FakeRequest("get_defillama_protocol", _DEFILLAMA_ARGS)
    api_result = {"tvl": 200}
    handler = AsyncMock(return_value=api_result)

    class _FailingSession:
        async def __aenter__(self):
            raise OSError("DB down")

        async def __aexit__(self, *args):
            pass

    with patch(
        "app.agents.new_chat.middleware.crypto_data_cache.shielded_async_session",
        return_value=_FailingSession(),
    ):
        mw = CryptoDataCacheMiddleware(search_space_id=1)
        result = await mw.awrap_tool_call(request, handler)

    handler.assert_called_once()
    assert result is api_result


# ---------------------------------------------------------------------------
# AC5: Non-crypto tools — complete pass-through
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ac5_non_crypto_tool_passes_through():
    """Tool not in TOOL_CATEGORY_MAP → middleware is no-op."""
    from app.agents.new_chat.middleware.crypto_data_cache import CryptoDataCacheMiddleware

    request = _FakeRequest("generate_report", {})
    api_result = {"content": "report text"}
    handler = AsyncMock(return_value=api_result)

    with patch(
        "app.agents.new_chat.middleware.crypto_data_cache.shielded_async_session"
    ) as mock_session:
        mw = CryptoDataCacheMiddleware(search_space_id=1)
        result = await mw.awrap_tool_call(request, handler)

    mock_session.assert_not_called()
    handler.assert_called_once()
    assert result is api_result


# ---------------------------------------------------------------------------
# AC6: Error results stored with short TTL (300s), is_error=True
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ac6_error_result_written_with_short_ttl():
    """API returns error dict → stored with is_error=True, ttl_seconds=300."""
    from app.agents.new_chat.middleware.crypto_data_cache import CryptoDataCacheMiddleware

    request = _FakeRequest("get_defillama_protocol", _DEFILLAMA_ARGS)
    error_result = ToolMessage(
        content=json.dumps({"error": "rate_limited"}),
        tool_call_id="call_abc",
        name="get_defillama_protocol",
    )
    handler = AsyncMock(return_value=error_result)

    sessions: list[_SessionCtxManager] = []

    def _make_session():
        s = _SessionCtxManager()
        sessions.append(s)
        return s

    with patch(
        "app.agents.new_chat.middleware.crypto_data_cache.shielded_async_session",
        side_effect=_make_session,
    ), patch(
        "app.agents.new_chat.middleware.crypto_data_cache.CryptoProjectResolver"
    ) as MockResolver, patch(
        "app.agents.new_chat.middleware.crypto_data_cache.CryptoDataStore"
    ) as MockStore:
        MockResolver.return_value.resolve = AsyncMock(return_value=7)
        MockStore.return_value.get_fresh_snapshot = AsyncMock(return_value=None)
        MockStore.return_value.write_snapshot = AsyncMock()

        mw = CryptoDataCacheMiddleware(search_space_id=1)
        await mw.awrap_tool_call(request, handler)

    write_kwargs = MockStore.return_value.write_snapshot.call_args[1]
    assert write_kwargs["is_error"] is True
    assert write_kwargs["ttl_seconds"] == 300


# ---------------------------------------------------------------------------
# F8: args_hash discrimination — different args yield different cache entries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_f8_different_args_yield_cache_miss():
    """Same tool + project but different args → get_fresh_snapshot called with distinct args_hash."""
    from app.agents.new_chat.middleware.crypto_data_cache import CryptoDataCacheMiddleware
    from app.services.crypto_data_store import CryptoDataStore

    args_hashes_seen: list[str] = []

    async def _tracking_get_fresh(search_space_id, project_id, category, tool_name, args_hash):
        args_hashes_seen.append(args_hash)
        return None  # always miss

    session = _SessionCtxManager()

    with patch(
        "app.agents.new_chat.middleware.crypto_data_cache.shielded_async_session",
        return_value=session,
    ), patch(
        "app.agents.new_chat.middleware.crypto_data_cache.CryptoProjectResolver"
    ) as MockResolver, patch(
        "app.agents.new_chat.middleware.crypto_data_cache.CryptoDataStore"
    ) as MockStore:
        MockResolver.return_value.resolve = AsyncMock(return_value=42)
        MockStore.return_value.get_fresh_snapshot = _tracking_get_fresh
        MockStore.return_value.write_snapshot = AsyncMock()
        MockStore.compute_args_hash = CryptoDataStore.compute_args_hash

        mw = CryptoDataCacheMiddleware(search_space_id=1)

        result_a = ToolMessage(content="{}", tool_call_id="c1", name="get_defillama_protocol")
        handler_a = AsyncMock(return_value=result_a)
        request_a = _FakeRequest("get_defillama_protocol", {"protocol_slug": "uniswap"}, "c1")
        await mw.awrap_tool_call(request_a, handler_a)

        result_b = ToolMessage(content="{}", tool_call_id="c2", name="get_defillama_protocol")
        handler_b = AsyncMock(return_value=result_b)
        request_b = _FakeRequest("get_defillama_protocol", {"protocol_slug": "aave"}, "c2")
        await mw.awrap_tool_call(request_b, handler_b)

    assert len(args_hashes_seen) >= 2, f"Expected at least 2 get_fresh_snapshot calls, got {len(args_hashes_seen)}"
    # Collect unique hashes — each tool call produces a distinct args_hash
    unique_hashes = set(args_hashes_seen)
    assert len(unique_hashes) == 2, (
        "Different tool args must produce different args_hash values"
    )
    handler_a.assert_called_once()
    handler_b.assert_called_once()
