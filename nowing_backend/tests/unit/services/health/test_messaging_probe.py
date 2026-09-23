"""Unit tests for MessagingHealthProbe."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.health.probes.messaging_probe import MessagingHealthProbe


@pytest.mark.asyncio
async def test_messaging_probe_telegram_not_configured() -> None:
    probe = MessagingHealthProbe(provider="telegram")
    assert probe.service_id == "messaging/telegram"
    assert probe.category == "messaging"

    with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": ""}, clear=False):
        result = await probe.probe()
        assert result.status == "not_configured"
        assert "TELEGRAM_BOT_TOKEN" in (result.suggested_action or "")


@pytest.mark.asyncio
async def test_messaging_probe_telegram_healthy() -> None:
    probe = MessagingHealthProbe(provider="telegram")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "12345:token"}, clear=False), \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client_cls.return_value.__aexit__.return_value = False

        result = await probe.probe()
        assert result.status == "healthy"


@pytest.mark.asyncio
async def test_messaging_probe_telegram_degraded_on_401() -> None:
    probe = MessagingHealthProbe(provider="telegram")

    mock_resp = MagicMock()
    mock_resp.status_code = 401

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "12345:token"}, clear=False), \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client_cls.return_value.__aexit__.return_value = False

        result = await probe.probe()
        assert result.status == "degraded"
        assert "rejected" in (result.last_error or "").lower()


@pytest.mark.asyncio
async def test_messaging_probe_slack_unavailable_on_500() -> None:
    probe = MessagingHealthProbe(provider="slack")

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": False, "error": "fatal_error"}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch.dict("os.environ", {"SLACK_BOT_TOKEN": "xoxb-123"}, clear=False), \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client_cls.return_value.__aexit__.return_value = False

        result = await probe.probe()
        assert result.status == "unavailable"
