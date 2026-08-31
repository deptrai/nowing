"""Red-phase unit tests for app.tasks.celery_tasks.schedule_mission_tick (Story 6.10)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

pytestmark = [pytest.mark.unit]


def test_tick_claims_missions_due_now(mocker):
    """AC-6 P1: claim missions where next_fire_at <= now and status in pending/running."""
    from app.tasks.celery_tasks.schedule_mission_tick import schedule_mission_tick

    mission = mocker.MagicMock()
    mission.id = "m1"
    mission.workspace_id = 1
    mission.schedule = {}

    claim_mock = mocker.patch(
        "app.tasks.celery_tasks.schedule_mission_tick._claim_due_missions",
        return_value=[mission],
    )
    run_mock = mocker.patch(
        "app.tasks.celery_tasks.schedule_mission_tick.run_scheduled_mission",
    )

    schedule_mission_tick()

    claim_mock.assert_called_once()
    run_mock.assert_called_once()
    call = run_mock.call_args
    assert call.kwargs["mission_id"] == "m1"
    assert call.kwargs["resume_from_checkpoint"] is True


def test_tick_skips_missions_not_due(mocker):
    """AC-6 P1: missions with next_fire_at > now are skipped."""
    from app.tasks.celery_tasks.schedule_mission_tick import schedule_mission_tick

    claim_mock = mocker.patch(
        "app.tasks.celery_tasks.schedule_mission_tick._claim_due_missions",
        return_value=[],
    )
    run_mock = mocker.patch(
        "app.tasks.celery_tasks.schedule_mission_tick.run_scheduled_mission",
    )

    schedule_mission_tick()

    assert run_mock.called is False


def test_postgres_connection_error_logs_and_retries(mocker):
    """AC-6 P2: Postgres connection error during claim logs exception and retries next tick."""
    from app.tasks.celery_tasks.schedule_mission_tick import schedule_mission_tick

    mocker.patch(
        "app.tasks.celery_tasks.schedule_mission_tick._claim_due_missions",
        side_effect=Exception("postgres connection failed"),
    )
    log_mock = mocker.patch("app.tasks.celery_tasks.schedule_mission_tick.logger.exception")

    schedule_mission_tick()

    log_mock.assert_called_once()
    assert "scheduled_mission_tick_failed" in str(log_mock.call_args.args[0])


def test_executor_timeout_sets_status_error_and_increment_retry(mocker):
    """AC-6 P2: LangGraphMissionExecutor timeout sets status=error and retry_count++."""
    from app.tasks.celery_tasks.schedule_mission_tick import run_scheduled_mission

    mocker.patch(
        "app.tasks.celery_tasks.schedule_mission_tick.LangGraphMissionExecutor",
        side_effect=TimeoutError("executor timeout"),
    )
    update_mock = mocker.patch(
        "app.tasks.celery_tasks.schedule_mission_tick._update_mission_status",
    )

    run_scheduled_mission(mission_id="m1", resume_from_checkpoint=True)

    update_mock.assert_called_once()
    assert update_mock.call_args.kwargs["status"] == "error"
    assert update_mock.call_args.kwargs["retry_count"] == 1


def test_past_due_mission_run_once_and_advance(mocker):
    """AC-6 P3: next_fire_at > 24h past still runs once and advances."""
    from app.tasks.celery_tasks.schedule_mission_tick import schedule_mission_tick

    past = datetime.now(timezone.utc) - timedelta(hours=25)
    mission = mocker.MagicMock()
    mission.id = "m1"
    mission.workspace_id = 1
    mission.schedule = {}

    claim_mock = mocker.patch(
        "app.tasks.celery_tasks.schedule_mission_tick._claim_due_missions",
        return_value=[mission],
    )
    run_mock = mocker.patch(
        "app.tasks.celery_tasks.schedule_mission_tick.run_scheduled_mission",
    )
    advance_mock = mocker.patch(
        "app.tasks.celery_tasks.schedule_mission_tick._advance_next_fire_at",
    )

    schedule_mission_tick()

    claim_mock.assert_called_once()
    run_mock.assert_called_once()
    advance_mock.assert_called_once()


def test_error_status_with_retry_count_below_max_retries(mocker):
    """AC-6 P3: status=error and retry_count < MAX_RETRIES is retried on next tick."""
    from app.tasks.celery_tasks.schedule_mission_tick import _should_retry

    assert _should_retry("error", retry_count=0, max_retries=3) is True
    assert _should_retry("error", retry_count=3, max_retries=3) is False


def test_concurrent_claim_only_one_wins(mocker):
    """AC-6 P3: two Beat workers claim same mission, only one wins status transition."""
    from app.tasks.celery_tasks.schedule_mission_tick import _claim_mission

    mocker.patch(
        "app.tasks.celery_tasks.schedule_mission_tick._transition_status",
        return_value=False,
    )

    result = _claim_mission(mission_id="m1")
    assert result is None


def test_batch_size_computed_min_tick_batch_and_remaining():
    """AC-6 P4: batch size = min(_TICK_BATCH, remaining_due)."""
    from app.tasks.celery_tasks.schedule_mission_tick import _compute_batch_size

    assert _compute_batch_size(remaining_due=50, tick_batch=200) == 50
    assert _compute_batch_size(remaining_due=250, tick_batch=200) == 200


def test_next_fire_at_advanced_even_on_no_op(mocker):
    """AC-6 P4: next_fire_at still advanced when ingestion is no-op."""
    from app.tasks.celery_tasks.schedule_mission_tick import run_scheduled_mission

    mocker.patch(
        "app.tasks.celery_tasks.schedule_mission_tick.LangGraphMissionExecutor",
        return_value=mocker.MagicMock(run=lambda: None),
    )
    mocker.patch(
        "app.tasks.celery_tasks.schedule_mission_tick._ingestion_result",
        return_value={"new_data": False},
    )
    advance_mock = mocker.patch(
        "app.tasks.celery_tasks.schedule_mission_tick._advance_next_fire_at",
    )

    run_scheduled_mission(mission_id="m1", resume_from_checkpoint=True)

    advance_mock.assert_called_once()
