"""Unit tests for third-party health probe Celery tasks and beat schedules (Story 25.7)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.celery_app import celery_app


def test_health_probe_tasks_registered() -> None:
    """Verify all health probe tasks are registered on the Celery app."""
    import app.tasks.celery_tasks.health_probe_task  # noqa: F401
    task_names = celery_app.tasks.keys()
    assert "health_probe_infra" in task_names
    assert "health_probe_model" in task_names
    assert "health_probe_scraper" in task_names
    assert "health_probe_connector" in task_names
    assert "health_probe_proxy" in task_names
    assert "health_probe_research" in task_names
    assert "health_probe_messaging" in task_names
    assert "health_probe_payment" in task_names
    assert "health_probe_storage" in task_names


def test_health_probe_beat_schedules() -> None:
    """Verify Celery beat schedules for all probe categories."""
    schedule = celery_app.conf.beat_schedule

    assert "health-probe-infra" in schedule
    assert schedule["health-probe-infra"]["schedule"] == 30.0

    for entry_name in [
        "health-probe-model",
        "health-probe-scraper",
        "health-probe-connector",
        "health-probe-proxy",
        "health-probe-research",
        "health-probe-messaging",
        "health-probe-payment",
        "health-probe-storage",
    ]:
        assert entry_name in schedule, f"Missing beat schedule: {entry_name}"


@pytest.mark.asyncio
async def test_health_probe_task_execution() -> None:
    """Verify _run_health_probe_for_category invokes HealthProbeScheduler."""
    from app.tasks.celery_tasks.health_probe_task import _run_health_probe_for_category

    with patch("app.services.health.scheduler.HealthProbeScheduler.run_category", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = []
        with patch("app.tasks.celery_tasks.health_probe_task.get_celery_session_maker") as mock_maker:
            mock_session = AsyncMock()
            mock_maker.return_value.__aenter__.return_value = mock_session
            res = await _run_health_probe_for_category("infra")
            assert res is not None
            assert res.get("category") == "infra"
            assert res.get("count") == 0
