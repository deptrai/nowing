from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.schemas.dsh import ResumeMissionPayload

pytestmark = [pytest.mark.unit]


def _fixed_uuid():
    class _MockUUID:
        hex = "abc123"
    return _MockUUID()


@pytest.mark.asyncio
async def test_cdp_subgraph_push_event():
    """should push CDPCommand event containing {action, url, command_id} to the SSE stream queue."""
    from app.tasks.dsh_worker_browser_operator import BrowserOperatorCdpSubgraph

    redis_mock = AsyncMock()
    redis_mock.pubsub_numsub.return_value = [(b"cdp_stream:user-1", 1)]
    redis_mock.blpop.return_value = (
        b"key",
        b'{"command_id": "abc123", "result": {"navigatedUrl": "https://test.com", "tabId": 42}, "sources": [{"url": "https://test.com"}]}',
    )

    with (
        patch("app.tasks.dsh_worker_browser_operator.get_redis_client", return_value=redis_mock),
        patch("app.tasks.dsh_worker_browser_operator.uuid.uuid4", return_value=_fixed_uuid()),
    ):
        subgraph = BrowserOperatorCdpSubgraph(None)
        state = {
            "mission_id": "test-mission",
            "user_id": "user-1",
            "payload": {"target_url": "https://test.com"},
            "workspace_id": 1,
        }
        new_state = await subgraph._cdp_crawl_node(state, {})

        assert redis_mock.publish.called
        assert new_state["checkpoint"]["cdp_last_result"]["navigatedUrl"] == "https://test.com"
        assert len(new_state["sources"]) == 1
        assert new_state["sources"][0]["url"] == "https://test.com"


@pytest.mark.asyncio
async def test_cdp_timeout():
    """should raise HumanInterventionRequired when the extension does not respond in time."""
    from app.tasks.dsh_worker_browser_operator import (
        BrowserOperatorCdpSubgraph,
        HumanInterventionRequired,
    )

    redis_mock = AsyncMock()
    redis_mock.pubsub_numsub.return_value = [(b"cdp_stream:user-1", 1)]
    redis_mock.blpop.return_value = None  # Timeout

    with patch("app.tasks.dsh_worker_browser_operator.get_redis_client", return_value=redis_mock):
        subgraph = BrowserOperatorCdpSubgraph(None)
        state = {
            "mission_id": "test-mission",
            "user_id": "user-1",
            "payload": {"target_url": "https://test.com"},
            "workspace_id": 1,
        }
        with pytest.raises(HumanInterventionRequired, match="CDP takeover timed out"):
            await subgraph._cdp_crawl_node(state, {})


@pytest.mark.asyncio
async def test_cdp_missing_extension():
    """should raise HumanInterventionRequired when no extension is listening."""
    from app.tasks.dsh_worker_browser_operator import (
        BrowserOperatorCdpSubgraph,
        HumanInterventionRequired,
    )

    redis_mock = AsyncMock()
    redis_mock.pubsub_numsub.return_value = [(b"cdp_stream:user-1", 0)]

    with patch("app.tasks.dsh_worker_browser_operator.get_redis_client", return_value=redis_mock):
        subgraph = BrowserOperatorCdpSubgraph(None)
        state = {
            "mission_id": "test-mission",
            "user_id": "user-1",
            "payload": {"target_url": "https://test.com"},
            "workspace_id": 1,
        }
        with pytest.raises(HumanInterventionRequired, match="No extension listening"):
            await subgraph._cdp_crawl_node(state, {})


@pytest.mark.asyncio
async def test_cdp_result_requires_human():
    """should raise HumanInterventionRequired when the extension reports a challenge."""
    from app.tasks.dsh_worker_browser_operator import (
        BrowserOperatorCdpSubgraph,
        HumanInterventionRequired,
    )

    redis_mock = AsyncMock()
    redis_mock.pubsub_numsub.return_value = [(b"cdp_stream:user-1", 1)]
    redis_mock.blpop.return_value = (
        b"key",
        b'{"command_id": "abc123", "requires_human": true, "challenge": "recaptcha"}',
    )

    with (
        patch("app.tasks.dsh_worker_browser_operator.get_redis_client", return_value=redis_mock),
        patch("app.tasks.dsh_worker_browser_operator.uuid.uuid4", return_value=_fixed_uuid()),
    ):
        subgraph = BrowserOperatorCdpSubgraph(None)
        state = {
            "mission_id": "test-mission",
            "user_id": "user-1",
            "payload": {"target_url": "https://test.com"},
            "workspace_id": 1,
        }
        with pytest.raises(HumanInterventionRequired, match="recaptcha"):
            await subgraph._cdp_crawl_node(state, {})


@pytest.mark.asyncio
async def test_cdp_invalid_url_rejected():
    """should reject non-http(s) target URLs."""
    from app.tasks.dsh_worker_browser_operator import BrowserOperatorCdpSubgraph

    subgraph = BrowserOperatorCdpSubgraph(None)
    state = {
        "mission_id": "test-mission",
        "user_id": "user-1",
        "payload": {"target_url": "javascript:alert(1)"},
        "workspace_id": 1,
    }
    with pytest.raises(ValueError, match="Invalid CDP mission payload"):
        await subgraph._cdp_crawl_node(state, {})


@pytest.mark.asyncio
async def test_cdp_stream_disconnect():
    """should cleanly unsubscribe and close Redis pubsub on client disconnect."""
    redis_mock = AsyncMock()
    redis_mock.pubsub_numsub.return_value = [["cdp_stream:user-1", 0]]
    pubsub_mock = AsyncMock()
    pubsub_mock.subscribe = AsyncMock()
    pubsub_mock.unsubscribe = AsyncMock()
    pubsub_mock.close = AsyncMock()
    redis_mock.pubsub = MagicMock(return_value=pubsub_mock)

    request_mock = AsyncMock()
    request_mock.is_disconnected.return_value = True

    with patch("app.routes.dsh_routes.get_redis_client", return_value=redis_mock):
        from app.routes.dsh_routes import cdp_stream
        auth_mock = MagicMock()
        auth_mock.user.id = "user-1"

        response = await cdp_stream(request_mock, auth_mock)
        generator = response.body_iterator
        async for _ in generator:
            pass

        assert pubsub_mock.unsubscribe.called
        assert pubsub_mock.close.called


def test_resume_invalid_payload():
    """should handle None or empty payload to /resume gracefully (422 Unprocessable Entity)."""
    with pytest.raises(ValidationError):
        ResumeMissionPayload()
