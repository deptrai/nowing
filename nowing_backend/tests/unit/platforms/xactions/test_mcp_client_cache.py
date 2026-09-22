"""Unit tests for XActions MCP client loop-scoped cache, lifecycle, and serialization (Story 36.2)."""

from __future__ import annotations

import asyncio
import concurrent.futures
import gc
from contextlib import asynccontextmanager, contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import anyio
import httpx
import pytest

from app.proprietary.platforms.xactions.adapter_v2 import XActionsSocialAdapterV2
from app.proprietary.platforms.xactions.mcp_client import (
    _CLIENTS_LOCK,
    _LOOP_CLIENTS,
    XActionsMcpClient,
    get_shared_client,
    release_shared_client_for_loop,
)

pytestmark = pytest.mark.unit


class DummyTransportCM:
    """Mock transport context manager."""

    def __init__(self) -> None:
        self.exited = False

    async def __aenter__(self) -> tuple[MagicMock, MagicMock, None]:
        return MagicMock(), MagicMock(), None

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.exited = True


@contextmanager
def patch_mcp_session(call_tool_side_effect=None, list_tools_return=None):
    """Context manager to mock streamablehttp_client and ClientSession."""
    mock_session = AsyncMock()
    mock_session.initialize = AsyncMock()
    mock_session.list_tools = AsyncMock(
        return_value=MagicMock(tools=list_tools_return or [])
    )

    if call_tool_side_effect:
        mock_session.call_tool = AsyncMock(side_effect=call_tool_side_effect)
    else:
        mock_session.call_tool = AsyncMock(
            return_value=MagicMock(
                isError=False,
                content=[MagicMock(text='{"success": true, "data": [], "meta": {}}')],
            )
        )

    transport = DummyTransportCM()

    with (
        patch(
            "app.proprietary.platforms.xactions.mcp_client.streamablehttp_client",
            return_value=transport,
        ),
        patch(
            "app.proprietary.platforms.xactions.mcp_client.ClientSession",
            return_value=mock_session,
        ),
    ):
        yield mock_session, transport


@pytest.fixture(autouse=True)
def clean_shared_clients():
    """Ensure _LOOP_CLIENTS is clean before and after each test."""
    with _CLIENTS_LOCK:
        _LOOP_CLIENTS.clear()
    yield
    with _CLIENTS_LOCK:
        _LOOP_CLIENTS.clear()


# ---------------------------------------------------------------------------
# 1. 2-Loop Sequential Lifecycle
# ---------------------------------------------------------------------------
def test_two_loop_sequential_lifecycle():
    """Loop 1 initializes and calls tool; closes. Loop 2 initializes fresh client

    without 'Event loop is closed' or 'Future attached to different loop' errors.
    """
    with patch_mcp_session() as (session1, transport1):
        loop1 = asyncio.new_event_loop()
        asyncio.set_event_loop(loop1)

        async def _run1():
            c1 = await get_shared_client()
            res = await c1.call_tool("x_test", {})
            assert res["success"] is True
            return c1

        client1 = loop1.run_until_complete(_run1())
        loop1.run_until_complete(release_shared_client_for_loop(loop1))
        loop1.close()

    with patch_mcp_session() as (session2, transport2):
        loop2 = asyncio.new_event_loop()
        asyncio.set_event_loop(loop2)

        async def _run2():
            c2 = await get_shared_client()
            assert c2 is not client1
            res = await c2.call_tool("x_test", {})
            assert res["success"] is True
            return c2

        client2 = loop2.run_until_complete(_run2())
        loop2.run_until_complete(release_shared_client_for_loop(loop2))
        loop2.close()

    assert client1 is not client2


# ---------------------------------------------------------------------------
# 2. Concurrent Tool Call Serialization
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_concurrent_tool_call_serialization():
    """5 concurrent call_tool operations serialize via client.serialize_lock,

    ensuring in_flight <= 1 throughout execution.
    """
    in_flight = 0
    max_in_flight = 0

    async def _mock_call(*args, **kwargs):
        nonlocal in_flight, max_in_flight
        in_flight += 1
        if in_flight > max_in_flight:
            max_in_flight = in_flight
        await asyncio.sleep(0.02)
        in_flight -= 1
        return MagicMock(
            isError=False,
            content=[MagicMock(text='{"success": true, "data": []}')],
        )

    with patch_mcp_session(call_tool_side_effect=_mock_call):
        client = await get_shared_client()
        results = await asyncio.gather(*(client.call_tool("x_test", {}) for _ in range(5)))
        assert len(results) == 5
        assert max_in_flight <= 1


# ---------------------------------------------------------------------------
# 3. List Tools & Call Tool Shared Lock
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_list_tools_and_call_tool_shared_lock():
    """list_tools() and call_tool() share client.serialize_lock and cannot interleave."""
    in_flight = 0
    max_in_flight = 0

    async def _mock_list(*args, **kwargs):
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.02)
        in_flight -= 1
        return MagicMock(tools=[MagicMock(name="x_tool", description="", inputSchema={})])

    async def _mock_call(*args, **kwargs):
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.02)
        in_flight -= 1
        return MagicMock(
            isError=False,
            content=[MagicMock(text='{"success": true, "data": []}')],
        )

    with patch_mcp_session():
        client = await get_shared_client()
        client._session.list_tools = AsyncMock(side_effect=_mock_list)
        client._session.call_tool = AsyncMock(side_effect=_mock_call)

        await asyncio.gather(
            client.list_tools(),
            client.call_tool("x_test", {}),
            client.list_tools(),
            client.call_tool("x_test2", {}),
        )
        assert max_in_flight <= 1


# ---------------------------------------------------------------------------
# 4. Initialization Failure Cleanup & Retry
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_initialization_failure_cleanup_and_retry():
    """If session.initialize() fails, entry is evicted from cache, transport is

    closed, and subsequent call on same loop re-initializes successfully.
    """
    loop = asyncio.get_running_loop()
    fail = True

    mock_session = AsyncMock()

    async def _maybe_fail_init():
        nonlocal fail
        if fail:
            fail = False
            raise RuntimeError("Handshake failed")

    mock_session.initialize = AsyncMock(side_effect=_maybe_fail_init)
    mock_session.call_tool = AsyncMock(
        return_value=MagicMock(
            isError=False,
            content=[MagicMock(text='{"success": true, "data": []}')],
        )
    )

    transport = DummyTransportCM()
    with (
        patch(
            "app.proprietary.platforms.xactions.mcp_client.streamablehttp_client",
            return_value=transport,
        ),
        patch(
            "app.proprietary.platforms.xactions.mcp_client.ClientSession",
            return_value=mock_session,
        ),
    ):
        with pytest.raises(RuntimeError, match="Handshake failed"):
            await get_shared_client()

        with _CLIENTS_LOCK:
            assert loop not in _LOOP_CLIENTS
        assert transport.exited is True

        # Second call on same loop should re-initialize and succeed
        client = await get_shared_client()
        assert client is not None
        assert client._session is not None
        with _CLIENTS_LOCK:
            assert loop in _LOOP_CLIENTS


# ---------------------------------------------------------------------------
# 5. Stranded Waiters Recovery
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stranded_waiters_recovery():
    """When coroutine A fails during initialization, coroutine B (which was

    waiting on entry.connecting) wakes up, detects eviction, retries, and
    successfully initializes a fresh client.
    """
    loop = asyncio.get_running_loop()
    attempt = 0

    mock_session = AsyncMock()

    async def _init_side_effect():
        nonlocal attempt
        attempt += 1
        if attempt == 1:
            await asyncio.sleep(0.02)
            raise RuntimeError("Init error in A")
        # Attempt 2 succeeds

    mock_session.initialize = AsyncMock(side_effect=_init_side_effect)
    mock_session.call_tool = AsyncMock(
        return_value=MagicMock(
            isError=False,
            content=[MagicMock(text='{"success": true, "data": []}')],
        )
    )

    with (
        patch(
            "app.proprietary.platforms.xactions.mcp_client.streamablehttp_client",
            return_value=DummyTransportCM(),
        ),
        patch(
            "app.proprietary.platforms.xactions.mcp_client.ClientSession",
            return_value=mock_session,
        ),
    ):
        res_a, res_b = await asyncio.gather(
            get_shared_client(),
            get_shared_client(),
            return_exceptions=True,
        )

        # One failed with the error, the other recovered and returned a valid client
        if isinstance(res_a, Exception):
            assert isinstance(res_a, RuntimeError)
            assert str(res_a) == "Init error in A"
            assert isinstance(res_b, XActionsMcpClient)
            assert res_b._session is not None
        else:
            assert isinstance(res_b, RuntimeError)
            assert str(res_b) == "Init error in A"
            assert isinstance(res_a, XActionsMcpClient)
            assert res_a._session is not None

        with _CLIENTS_LOCK:
            assert loop in _LOOP_CLIENTS


# ---------------------------------------------------------------------------
# 6. Passive & Active Memory Recovery
# ---------------------------------------------------------------------------
def test_passive_and_active_memory_recovery():
    """Active release pops entry from _LOOP_CLIENTS; passive loop deletion

    and gc.collect() evicts loop without memory leaks.
    """
    # Active release:
    with patch_mcp_session():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            client = loop.run_until_complete(get_shared_client())
            with _CLIENTS_LOCK:
                assert loop in _LOOP_CLIENTS
            loop.run_until_complete(release_shared_client_for_loop(loop))
            with _CLIENTS_LOCK:
                assert loop not in _LOOP_CLIENTS
        finally:
            loop.close()

    # Passive GC collection:
    def _run_isolated():
        temp_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(temp_loop)
        try:
            with patch_mcp_session():
                temp_client = temp_loop.run_until_complete(get_shared_client())
                with _CLIENTS_LOCK:
                    assert temp_loop in _LOOP_CLIENTS
        finally:
            asyncio.set_event_loop(None)
            temp_loop.close()
        return id(temp_loop)

    _run_isolated()
    gc.collect()
    with _CLIENTS_LOCK:
        assert len(_LOOP_CLIENTS) == 0


# ---------------------------------------------------------------------------
# 7. Default Adapter Integration
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_default_adapter_integration():
    """Default adapter uses get_shared_client(); adapter.close() is a no-op

    that preserves the shared session.
    """
    with patch_mcp_session():
        adapter = XActionsSocialAdapterV2()
        assert adapter._is_shared is True

        client = await adapter._get_client()
        shared = await get_shared_client()
        assert client is shared

        class _FakeTarget:
            id = 1
            platform = "facebook_page"
            target_id = "test_page"
            account_id = None
            proxy_url = None
            target_url = None

        # Verify full tool invocation path through default adapter
        posts = await adapter.fetch_posts_for_target(_FakeTarget())
        assert isinstance(posts, list)

        await adapter.close()
        # Shared client session remains open
        assert client._session is not None
        res = await client.call_tool("x_test", {})
        assert res["success"] is True


# ---------------------------------------------------------------------------
# 8. Injected Standalone Adapter Integration
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_injected_standalone_adapter_integration():
    """Injected standalone client adapter closes the custom client on adapter.close()."""
    custom = MagicMock()
    custom.__aexit__ = AsyncMock()

    adapter = XActionsSocialAdapterV2(client=custom)
    assert adapter._is_shared is False

    c = await adapter._get_client()
    assert c is custom

    await adapter.close()
    assert custom.__aexit__.await_count == 1
    assert adapter.client is None


# ---------------------------------------------------------------------------
# 9. Direct Async With Protection
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_direct_async_with_protection():
    """Using 'async with client:' on a shared managed client does not close

    the session upon context exit.
    """
    with patch_mcp_session():
        shared = await get_shared_client()
        assert shared._is_managed is True

        async with shared as c:
            assert c is shared

        # Exiting async with must NOT have closed _session
        assert shared._session is not None
        res = await shared.call_tool("x_test", {})
        assert res["success"] is True


# ---------------------------------------------------------------------------
# 10. Fatal Transport Drop Eviction
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fatal_transport_drop_eviction():
    """httpx.TransportError in call_tool taints client and evicts entry from cache."""
    loop = asyncio.get_running_loop()

    with patch_mcp_session():
        client = await get_shared_client()
        client._session.call_tool = AsyncMock(
            side_effect=httpx.TransportError("Socket reset by peer")
        )

        with pytest.raises(httpx.TransportError):
            await client.call_tool("x_test", {})

        assert client._tainted is True
        assert client._session is None
        with _CLIENTS_LOCK:
            assert loop not in _LOOP_CLIENTS


# ---------------------------------------------------------------------------
# 11. Artifact Fetching Outside Lock
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_artifact_fetching_outside_lock():
    """Artifact fetching runs outside client.serialize_lock so serialize_lock.locked() is False."""
    lock_was_locked_during_fetch = None

    async def _fake_fetch_artifact(path: str):
        nonlocal lock_was_locked_during_fetch
        lock_was_locked_during_fetch = client.serialize_lock.locked()
        return [{"id": "artifact_post"}]

    with patch_mcp_session() as (session, _):
        session.call_tool = AsyncMock(
            return_value=MagicMock(
                isError=False,
                content=[
                    MagicMock(
                        text='{"success": true, "data": [], "meta": {"datasetArtifactPath": "http://xactions/art.json"}}'
                    )
                ],
            )
        )
        client = await get_shared_client()
        client._fetch_artifact = _fake_fetch_artifact

        res = await client.call_tool("x_test", {})
        assert res["success"] is True
        assert res["data"] == [{"id": "artifact_post"}]
        assert lock_was_locked_during_fetch is False


# ---------------------------------------------------------------------------
# 14. Thread-Safety Multi-Thread Access
# ---------------------------------------------------------------------------
def test_thread_safety_multi_thread_access():
    """ThreadPoolExecutor running get_shared_client() on multiple threads

    does not encounter 'dictionary changed size during iteration' or race crashes.
    """

    def _worker(thread_id: int):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async def _run():
                c = await get_shared_client()
                res = await c.call_tool("x_test", {"thread": thread_id})
                assert res["success"] is True
                await release_shared_client_for_loop(loop)

            loop.run_until_complete(_run())
        finally:
            asyncio.set_event_loop(None)
            loop.close()

    with patch_mcp_session():
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(_worker, i) for i in range(10)]
            for f in concurrent.futures.as_completed(futures):
                f.result()


# ---------------------------------------------------------------------------
# 15. Multi-Tenancy Arguments Non-Persistence
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_multi_tenancy_arguments_non_persistence():
    """accountId and proxyUrl passed in tool arguments are never persisted

    onto client attributes or headers.
    """
    with patch_mcp_session():
        client = await get_shared_client()
        initial_headers = dict(client._headers)

        await client.call_tool(
            "x_test",
            {
                "accountId": "tenant_xyz",
                "proxyUrl": "socks5://proxy:1080",
                "context": {"workspaceId": "ws_1"},
            },
        )

        assert not hasattr(client, "accountId")
        assert not hasattr(client, "proxyUrl")
        assert client._headers == initial_headers
        assert "accountId" not in client._headers
        assert "proxyUrl" not in client._headers


# ---------------------------------------------------------------------------
# 16. Custom Parameters Rejection
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_custom_parameters_rejection():
    """Passing custom connection parameters into get_shared_client() raises ValueError."""
    with pytest.raises(ValueError, match="Custom url"):
        await get_shared_client(url="http://custom:3001/mcp")

    with pytest.raises(ValueError, match="Custom api_key"):
        await get_shared_client(api_key="custom_secret_key")

    with pytest.raises(ValueError, match="Custom consumer_id"):
        await get_shared_client(consumer_id="different_consumer")


# ---------------------------------------------------------------------------
# Extra: Tainted client re-check in call_tool & list_tools
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tainted_client_raises_in_call_and_list_tools():
    """If client is tainted, call_tool and list_tools raise RuntimeError."""
    with patch_mcp_session():
        client = await get_shared_client()
        client._tainted = True

        with pytest.raises(RuntimeError, match="session is closed or tainted"):
            await client.call_tool("x_test", {})

        with pytest.raises(RuntimeError, match="session is closed or tainted"):
            await client.list_tools()


# ---------------------------------------------------------------------------
# Extra: Anyio fatal error eviction
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc_cls",
    [ConnectionError, anyio.ClosedResourceError, anyio.EndOfStream],
)
async def test_anyio_fatal_transport_eviction(exc_cls):
    """ClosedResourceError and EndOfStream taint and evict client."""
    loop = asyncio.get_running_loop()
    with patch_mcp_session():
        client = await get_shared_client()
        client._session.call_tool = AsyncMock(side_effect=exc_cls())

        with pytest.raises(exc_cls):
            await client.call_tool("x_test", {})

        assert client._tainted is True
        with _CLIENTS_LOCK:
            assert loop not in _LOOP_CLIENTS
