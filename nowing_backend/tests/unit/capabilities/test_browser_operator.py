from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.capabilities.browser_operator.executor import build_browser_operator_executor
from app.capabilities.browser_operator.schemas import BrowserOperatorInput
from app.capabilities.core.types import CapabilityContext

pytestmark = pytest.mark.unit


def _fake_redis_client(sub_count: int = 1, result_data: dict | None = None):
    redis = AsyncMock()
    redis.pubsub_numsub.return_value = [["cdp_stream:user-1", sub_count]]
    redis.blpop.return_value = ("cdp_result:user-1:chat-abc", json.dumps(result_data or {}))
    return redis


@pytest.mark.asyncio
async def test_browser_operator_returns_success_with_result():
    """should parse the result returned by the extension."""
    redis = _fake_redis_client(
        result_data={
            "result": {
                "navigatedUrl": "https://example.com",
                "title": "Example",
                "command_id": "cmd-123",
            },
            "error": None,
        }
    )

    with patch("app.capabilities.browser_operator.executor.get_redis_client", return_value=redis):
        execute = build_browser_operator_executor()
        ctx = CapabilityContext(session=MagicMock(), workspace_id=1, user_id="user-1")
        output = await execute(BrowserOperatorInput(action="navigate", url="https://example.com"), ctx)

    assert output.success is True
    assert output.action == "navigate"
    assert output.data == {
        "navigatedUrl": "https://example.com",
        "title": "Example",
        "command_id": "cmd-123",
    }


@pytest.mark.asyncio
async def test_browser_operator_returns_human_takeover_when_challenge():
    """should treat requires_human/challenge as a human-takeover condition."""
    redis = _fake_redis_client(
        result_data={
            "result": None,
            "error": ".recaptcha",
            "requires_human": True,
            "challenge": ".recaptcha",
            "command_id": "cmd-456",
        }
    )

    with patch("app.capabilities.browser_operator.executor.get_redis_client", return_value=redis):
        execute = build_browser_operator_executor()
        ctx = CapabilityContext(session=MagicMock(), workspace_id=1, user_id="user-1")
        output = await execute(BrowserOperatorInput(action="click", selector="button"), ctx)

    assert output.success is False
    assert "Human takeover" in output.message
    assert output.data["challenge"] == ".recaptcha"


@pytest.mark.asyncio
async def test_browser_operator_returns_error_when_extension_reports_error():
    """should surface extension errors without crashing."""
    redis = _fake_redis_client(
        result_data={
            "result": None,
            "error": "Selector not found: #missing",
            "command_id": "cmd-789",
        }
    )

    with patch("app.capabilities.browser_operator.executor.get_redis_client", return_value=redis):
        execute = build_browser_operator_executor()
        ctx = CapabilityContext(session=MagicMock(), workspace_id=1, user_id="user-1")
        output = await execute(BrowserOperatorInput(action="click", selector="#missing"), ctx)

    assert output.success is False
    assert output.message == "Selector not found: #missing"


@pytest.mark.asyncio
async def test_browser_operator_rejects_missing_user_id():
    """should fail gracefully when the executor lacks a user context."""
    execute = build_browser_operator_executor()
    output = await execute(BrowserOperatorInput(action="navigate", url="https://example.com"), None)

    assert output.success is False
    assert "authentication context" in output.message.lower()
