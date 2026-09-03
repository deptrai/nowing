"""Unit tests for AdminHealthAlertEngine."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.admin_health import AdminHealthAlertRule
from app.services.health.alert_engine import AdminHealthAlertEngine
from app.services.health.probe_base import HealthResult


@pytest.mark.asyncio
async def test_alert_engine_creates_alert_on_unavailable() -> None:
    rule = AdminHealthAlertRule(
        id=1,
        name="Service Unavailable",
        category="model",
        condition_json={"status": "unavailable", "consecutive_probes": 1},
        severity="critical",
        enabled=True,
        cooldown_minutes=15,
    )

    result = HealthResult(
        service_id="model/gpt-5",
        service_name="GPT 5",
        category="model",
        display_group="Chat Models",
        status="unavailable",
        error_rate_15m=100.0,
    )

    mock_session = AsyncMock()

    # 1. rules query
    mock_rules_res = MagicMock()
    mock_rules_res.scalars.return_value.all.return_value = [rule]

    # 2. active alert query (returns None -> no cooldown)
    mock_alert_res = MagicMock()
    mock_alert_res.scalar_one_or_none.return_value = None

    mock_session.execute = AsyncMock(side_effect=[mock_rules_res, mock_alert_res])

    with patch.object(AdminHealthAlertEngine, "_dispatch_notification", new_callable=AsyncMock) as mock_dispatch:
        alerts = await AdminHealthAlertEngine.evaluate_result(mock_session, result)
        assert len(alerts) == 1
        assert alerts[0].service_id == "model/gpt-5"
        assert alerts[0].severity == "critical"
        assert mock_dispatch.call_count == 1
