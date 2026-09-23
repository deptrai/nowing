"""Unit tests for AdminHealthAlertEngine."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.admin_health import AdminHealthAlert, AdminHealthAlertRule
from app.services.health.alert_engine import AdminHealthAlertEngine
from app.services.health.probe_base import HealthResult


def _make_session(mock_history: list[tuple] | None = None) -> MagicMock:
    """Create a mock AsyncSession with required async methods."""
    session = MagicMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    session.get = AsyncMock()
    return session


def _make_rule(
    rule_id: int = 1,
    category: str = "model",
    condition_json: dict | None = None,
    cooldown_minutes: int = 15,
) -> AdminHealthAlertRule:
    return AdminHealthAlertRule(
        id=rule_id,
        name="Test Rule",
        category=category,
        condition_json=condition_json or {"status": "unavailable", "consecutive_probes": 1},
        severity="critical",
        enabled=True,
        cooldown_minutes=cooldown_minutes,
    )


def _make_result(status: str = "unavailable") -> HealthResult:
    return HealthResult(
        service_id="model/gpt-5",
        service_name="GPT 5",
        category="model",
        display_group="Chat Models",
        status=status,
        error_rate_15m=100.0 if status != "healthy" else 0.0,
        success_rate_15m=0.0 if status != "healthy" else 100.0,
    )


@pytest.mark.asyncio
async def test_alert_engine_creates_alert_on_unavailable() -> None:
    rule = _make_rule(condition_json={"status": "unavailable", "consecutive_probes": 1})
    result = _make_result("unavailable")

    mock_rules_res = MagicMock()
    mock_rules_res.scalars.return_value.all.return_value = [rule]

    mock_alert_res = MagicMock()
    mock_alert_res.scalar_one_or_none.return_value = None

    session = _make_session()
    session.execute = AsyncMock(side_effect=[mock_rules_res, mock_alert_res])

    with patch.object(AdminHealthAlertEngine, "_dispatch_notification", new_callable=AsyncMock) as mock_dispatch:
        alerts = await AdminHealthAlertEngine.evaluate_result(session, result)
        assert len(alerts) == 1
        assert alerts[0].service_id == "model/gpt-5"
        assert alerts[0].severity == "critical"
        assert mock_dispatch.call_count == 1


@pytest.mark.asyncio
async def test_alert_engine_respects_consecutive_probes() -> None:
    """A rule with consecutive_probes=2 should not trigger on first unavailable result."""
    rule = _make_rule(condition_json={"status": "unavailable", "consecutive_probes": 2})
    result = _make_result("unavailable")

    mock_rules_res = MagicMock()
    mock_rules_res.scalars.return_value.all.return_value = [rule]

    # History returns only 1 past unavailable (total 1, not enough)
    mock_history_res = MagicMock()
    mock_history_res.scalars.return_value.all.return_value = ["unavailable"]

    mock_alert_res = MagicMock()
    mock_alert_res.scalar_one_or_none.return_value = None

    session = _make_session()
    # Order: rules, then history (inside _check_rule_condition), then alert dedup
    session.execute = AsyncMock(side_effect=[mock_rules_res, mock_history_res, mock_alert_res])

    with patch.object(AdminHealthAlertEngine, "_dispatch_notification", new_callable=AsyncMock) as mock_dispatch:
        alerts = await AdminHealthAlertEngine.evaluate_result(session, result)
        assert len(alerts) == 0
        assert mock_dispatch.call_count == 0


@pytest.mark.asyncio
async def test_alert_engine_enforces_cooldown() -> None:
    """An existing alert within cooldown should suppress a new alert."""
    rule = _make_rule(condition_json={"status": "unavailable", "consecutive_probes": 1}, cooldown_minutes=15)
    result = _make_result("unavailable")

    existing_alert = AdminHealthAlert(
        id=1,
        rule_id=rule.id,
        service_id=result.service_id,
        status="open",
        severity="critical",
        message="Previous alert",
        triggered_at=datetime.now(UTC) - timedelta(minutes=5),
    )

    mock_rules_res = MagicMock()
    mock_rules_res.scalars.return_value.all.return_value = [rule]

    mock_alert_res = MagicMock()
    mock_alert_res.scalar_one_or_none.return_value = existing_alert

    session = _make_session()
    session.execute = AsyncMock(side_effect=[mock_rules_res, mock_alert_res])

    with patch.object(AdminHealthAlertEngine, "_dispatch_notification", new_callable=AsyncMock) as mock_dispatch:
        alerts = await AdminHealthAlertEngine.evaluate_result(session, result)
        assert len(alerts) == 0
        assert mock_dispatch.call_count == 0
        assert existing_alert.status == "open"


@pytest.mark.asyncio
async def test_alert_engine_reopens_after_cooldown_expires() -> None:
    """When cooldown has expired, the existing alert should be reopened with a new timestamp."""
    rule = _make_rule(condition_json={"status": "unavailable", "consecutive_probes": 1}, cooldown_minutes=15)
    result = _make_result("unavailable")

    existing_alert = AdminHealthAlert(
        id=1,
        rule_id=rule.id,
        service_id=result.service_id,
        status="open",
        severity="critical",
        message="Previous alert",
        triggered_at=datetime.now(UTC) - timedelta(minutes=20),
    )

    mock_rules_res = MagicMock()
    mock_rules_res.scalars.return_value.all.return_value = [rule]

    mock_alert_res = MagicMock()
    mock_alert_res.scalar_one_or_none.return_value = existing_alert

    session = _make_session()
    session.execute = AsyncMock(side_effect=[mock_rules_res, mock_alert_res])

    with patch.object(AdminHealthAlertEngine, "_dispatch_notification", new_callable=AsyncMock) as mock_dispatch:
        alerts = await AdminHealthAlertEngine.evaluate_result(session, result)
        # Cooldown expired -> a new alert is created and the existing one is reopened
        assert len(alerts) == 1
        assert existing_alert.status == "open"
        assert existing_alert.triggered_at > datetime.now(UTC) - timedelta(minutes=1)
        assert mock_dispatch.call_count == 1


@pytest.mark.asyncio
async def test_alert_engine_resolves_on_two_consecutive_healthy() -> None:
    """Two consecutive healthy probes should resolve open alerts."""
    result = _make_result("healthy")

    # History returns one healthy immediately before this result
    mock_history_res = MagicMock()
    mock_history_res.scalars.return_value.all.return_value = ["healthy"]

    existing_alert = AdminHealthAlert(
        id=1,
        rule_id=1,
        service_id=result.service_id,
        status="open",
        severity="critical",
        message="Alert",
    )

    mock_alerts_res = MagicMock()
    mock_alerts_res.scalars.return_value.all.return_value = [existing_alert]

    mock_status_res = MagicMock()
    mock_status_res.scalar_one_or_none.return_value = MagicMock()

    session = _make_session()
    session.execute = AsyncMock(side_effect=[mock_history_res, mock_alerts_res, mock_status_res])

    alerts = await AdminHealthAlertEngine.evaluate_result(session, result)
    assert len(alerts) == 0
    assert existing_alert.status == "resolved"


@pytest.mark.asyncio
async def test_alert_engine_does_not_resolve_on_single_healthy() -> None:
    """A single healthy probe should not resolve open alerts."""
    result = _make_result("healthy")

    mock_history_res = MagicMock()
    mock_history_res.scalars.return_value.all.return_value = ["unavailable"]

    session = _make_session()
    session.execute = AsyncMock(return_value=mock_history_res)

    alerts = await AdminHealthAlertEngine.evaluate_result(session, result)
    assert len(alerts) == 0


@pytest.mark.asyncio
async def test_alert_engine_metric_condition_success_rate() -> None:
    """A metric rule with success_rate_15m < threshold should trigger."""
    rule = _make_rule(
        condition_json={"metric": "success_rate_15m", "op": "<", "threshold": 50.0},
        cooldown_minutes=0,
    )
    result = _make_result("degraded")
    result.success_rate_15m = 30.0
    result.error_rate_15m = 70.0

    mock_rules_res = MagicMock()
    mock_rules_res.scalars.return_value.all.return_value = [rule]

    mock_alert_res = MagicMock()
    mock_alert_res.scalar_one_or_none.return_value = None

    session = _make_session()
    session.execute = AsyncMock(side_effect=[mock_rules_res, mock_alert_res])

    with patch.object(AdminHealthAlertEngine, "_dispatch_notification", new_callable=AsyncMock) as mock_dispatch:
        alerts = await AdminHealthAlertEngine.evaluate_result(session, result)
        assert len(alerts) == 1
        assert mock_dispatch.call_count == 1


@pytest.mark.asyncio
async def test_alert_engine_metric_condition_does_not_trigger_when_healthy() -> None:
    """A metric rule should not trigger when the value is above threshold."""
    rule = _make_rule(
        condition_json={"metric": "success_rate_15m", "op": "<", "threshold": 50.0},
        cooldown_minutes=0,
    )
    result = _make_result("healthy")
    result.success_rate_15m = 100.0
    result.error_rate_15m = 0.0

    mock_rules_res = MagicMock()
    mock_rules_res.scalars.return_value.all.return_value = [rule]

    session = _make_session()
    session.execute = AsyncMock(return_value=mock_rules_res)

    with patch.object(AdminHealthAlertEngine, "_dispatch_notification", new_callable=AsyncMock) as mock_dispatch:
        alerts = await AdminHealthAlertEngine.evaluate_result(session, result)
        assert len(alerts) == 0
        assert mock_dispatch.call_count == 0


@pytest.mark.asyncio
async def test_acknowledge_alert_updates_status_and_snoozes() -> None:
    """acknowledge_alert should update alert and corresponding status record."""
    alert = AdminHealthAlert(
        id=1,
        rule_id=1,
        service_id="model/gpt-5",
        status="open",
        severity="critical",
        message="Alert",
        triggered_at=datetime.now(UTC),
    )

    status_record = MagicMock()

    mock_alert_res = MagicMock()
    mock_alert_res.scalar_one_or_none.return_value = alert

    mock_status_res = MagicMock()
    mock_status_res.scalar_one_or_none.return_value = status_record

    session = _make_session()
    session.execute = AsyncMock(side_effect=[mock_alert_res, mock_status_res])

    result = await AdminHealthAlertEngine.acknowledge_alert(session, alert_id=1, duration_minutes=30)
    assert result is not None
    assert result.status == "acknowledged"
    assert result.acknowledged_until is not None
    assert status_record.acknowledged_until is not None


@pytest.mark.asyncio
async def test_acknowledge_alert_returns_none_for_resolved() -> None:
    """acknowledge_alert should return None for already-resolved alerts."""
    alert = AdminHealthAlert(
        id=1,
        rule_id=1,
        service_id="model/gpt-5",
        status="resolved",
        severity="critical",
        message="Alert",
        triggered_at=datetime.now(UTC),
        resolved_at=datetime.now(UTC),
    )

    mock_alert_res = MagicMock()
    mock_alert_res.scalar_one_or_none.return_value = alert

    session = _make_session()
    session.execute = AsyncMock(return_value=mock_alert_res)

    result = await AdminHealthAlertEngine.acknowledge_alert(session, alert_id=1, duration_minutes=30)
    assert result is None


@pytest.mark.asyncio
async def test_resolve_alert_sets_status_resolved() -> None:
    """resolve_alert should mark an open alert as resolved."""
    alert = AdminHealthAlert(
        id=1,
        rule_id=1,
        service_id="model/gpt-5",
        status="open",
        severity="critical",
        message="Alert",
        triggered_at=datetime.now(UTC),
    )

    status_record = MagicMock()

    mock_alert_res = MagicMock()
    mock_alert_res.scalar_one_or_none.return_value = alert

    mock_status_res = MagicMock()
    mock_status_res.scalar_one_or_none.return_value = status_record

    session = _make_session()
    session.execute = AsyncMock(side_effect=[mock_alert_res, mock_status_res])

    result = await AdminHealthAlertEngine.resolve_alert(session, alert_id=1)
    assert result is not None
    assert result.status == "resolved"
    assert result.resolved_at is not None
