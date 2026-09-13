"""Unit tests for XActionsHealthProbe (Story 21.8a)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.health.probes.xactions_probe import XActionsHealthProbe

pytestmark = pytest.mark.unit


@pytest.fixture
def probe() -> XActionsHealthProbe:
    return XActionsHealthProbe()


@pytest.mark.asyncio
async def test_xactions_probe_healthy(probe: XActionsHealthProbe) -> None:
    mock_client = AsyncMock()
    mock_client.call_tool.side_effect = [
        {"data": {"healthyProxyCount": 5, "backpressure": "none"}},
        {"metrics": {"length": 100, "lag": 0}},
        {"data": []},
    ]

    with patch("app.services.health.probes.xactions_probe.XActionsMcpClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_cls.return_value.__aexit__.return_value = False

        result = await probe.probe()

    assert result.service_id == "scraper/xactions"
    assert result.status == "healthy"
    assert result.last_error is None
    assert result.metadata["healthy_proxies"] == 5
    assert result.metadata["backpressure"] == "none"
    assert result.metadata["stream_metrics"] == {"length": 100, "lag": 0}


@pytest.mark.asyncio
async def test_xactions_probe_calls_x_governor_status(probe: XActionsHealthProbe) -> None:
    mock_client = AsyncMock()
    mock_client.call_tool.side_effect = [
        {"data": {"healthyProxyCount": 5, "backpressure": "none"}},
        {"metrics": {}},
        {"data": []},
    ]

    with patch("app.services.health.probes.xactions_probe.XActionsMcpClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_cls.return_value.__aexit__.return_value = False

        await probe.probe()

    assert mock_client.call_tool.call_args_list[0].args[0] == "x_governor_status"


@pytest.mark.asyncio
async def test_xactions_probe_degraded_low_proxies(probe: XActionsHealthProbe) -> None:
    mock_client = AsyncMock()
    mock_client.call_tool.side_effect = [
        {"data": {"healthyProxyCount": 2, "backpressure": "none"}},
        {"metrics": {}},
        {"data": []},
    ]

    with patch("app.services.health.probes.xactions_probe.XActionsMcpClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_cls.return_value.__aexit__.return_value = False

        result = await probe.probe()

    assert result.status == "degraded"
    assert "Low healthy proxies: 2" in (result.last_error or "")
    assert result.suggested_action == "Check XActions proxy pool and governor"


@pytest.mark.asyncio
async def test_xactions_probe_degraded_moderate_backpressure(probe: XActionsHealthProbe) -> None:
    mock_client = AsyncMock()
    mock_client.call_tool.side_effect = [
        {"data": {"healthyProxyCount": 10, "backpressure": "moderate"}},
        {"metrics": {}},
        {"data": []},
    ]

    with patch("app.services.health.probes.xactions_probe.XActionsMcpClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_cls.return_value.__aexit__.return_value = False

        result = await probe.probe()

    assert result.status == "degraded"


@pytest.mark.asyncio
async def test_xactions_probe_unavailable_critical_backpressure(probe: XActionsHealthProbe) -> None:
    mock_client = AsyncMock()
    mock_client.call_tool.side_effect = [
        {"data": {"healthyProxyCount": 5, "backpressure": "critical"}},
        {"metrics": {}},
        {"data": []},
    ]

    with patch("app.services.health.probes.xactions_probe.XActionsMcpClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_cls.return_value.__aexit__.return_value = False

        result = await probe.probe()

    assert result.status == "unavailable"
    assert "critical" in (result.last_error or "")


@pytest.mark.asyncio
async def test_xactions_probe_unavailable_zero_proxies(probe: XActionsHealthProbe) -> None:
    mock_client = AsyncMock()
    mock_client.call_tool.side_effect = [
        {"data": {"healthyProxyCount": 0, "backpressure": "none"}},
        {"metrics": {}},
        {"data": []},
    ]

    with patch("app.services.health.probes.xactions_probe.XActionsMcpClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_cls.return_value.__aexit__.return_value = False

        result = await probe.probe()

    assert result.status == "unavailable"


@pytest.mark.asyncio
async def test_xactions_probe_stream_alerts_triggers_degraded_and_fires_rules(
    probe: XActionsHealthProbe,
) -> None:
    mock_client = AsyncMock()
    mock_client.call_tool.side_effect = [
        {"data": {"healthyProxyCount": 5, "backpressure": "none"}},
        {"metrics": {}},
        {"data": {"activeAlerts": ["queue_depth_exceeded"]}},
    ]

    with patch("app.services.health.probes.xactions_probe.XActionsMcpClient") as mock_cls, \
         patch.object(probe, "_fire_alert_rules_for_stream_breach", new=AsyncMock()) as mock_fire:
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_cls.return_value.__aexit__.return_value = False

        result = await probe.probe()

    assert result.status == "degraded"
    assert "queue_depth_exceeded" in (result.last_error or "")
    mock_fire.assert_called_once_with(["queue_depth_exceeded"])


@pytest.mark.asyncio
async def test_xactions_probe_mcp_connection_failure(probe: XActionsHealthProbe) -> None:
    with patch("app.services.health.probes.xactions_probe.XActionsMcpClient") as mock_cls:
        mock_cls.return_value.__aenter__.side_effect = ConnectionRefusedError("Daemon down")

        result = await probe.probe()

    assert result.status == "unavailable"
    assert "ConnectionRefusedError" in (result.last_error or "")
    assert "Verify XACTIONS_MCP_URL" in (result.suggested_action or "")


@pytest.mark.asyncio
async def test_fire_alert_rules_for_stream_breach_executes_rules(
    probe: XActionsHealthProbe,
) -> None:
    rule1 = MagicMock(id=1, enabled=True)
    rule2 = MagicMock(id=2, enabled=True)

    fake_result = MagicMock()
    fake_result.scalars.return_value.all.return_value = [rule1, rule2]

    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(return_value=fake_result)
    fake_session.commit = AsyncMock()

    with patch("app.services.health.probes.xactions_probe.async_session_maker") as mock_sm, \
         patch("app.services.health.probes.xactions_probe.execute_alert_rule", new=AsyncMock()) as mock_exec:
        mock_sm.return_value.__aenter__.return_value = fake_session
        mock_sm.return_value.__aexit__.return_value = False

        await probe._fire_alert_rules_for_stream_breach(["alert_1"])

    assert mock_exec.call_count == 2
    fake_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_fire_alert_rules_no_matching_rules(probe: XActionsHealthProbe) -> None:
    fake_result = MagicMock()
    fake_result.scalars.return_value.all.return_value = []

    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(return_value=fake_result)

    with patch("app.services.health.probes.xactions_probe.async_session_maker") as mock_sm, \
         patch("app.services.health.probes.xactions_probe.execute_alert_rule", new=AsyncMock()) as mock_exec:
        mock_sm.return_value.__aenter__.return_value = fake_session
        mock_sm.return_value.__aexit__.return_value = False

        await probe._fire_alert_rules_for_stream_breach(["alert_1"])

    mock_exec.assert_not_called()
