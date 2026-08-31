"""Red-phase unit tests for app.tasks.dsh_worker_scheduled_mission (Story 6.10)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

pytestmark = [pytest.mark.unit]


def test_ingestion_writes_schedule_state_to_checkpoint(mocker):
    """AC-5 P1: checkpoint['schedule_state'] written, subtasks preserved."""
    from app.tasks.dsh_worker_scheduled_mission import ScheduledMissionWorker

    worker = ScheduledMissionWorker(mission_id="m1", workspace_id=1)
    patch_mock = mocker.patch.object(worker, "_patch_checkpoint")

    new_state = {
        "schedule_state": {
            "last_run_sources": [{"url": "vcb.com"}],
            "last_run_deliverables": [{"id": "d1"}],
            "last_fired_at": datetime.now(timezone.utc).isoformat(),
        }
    }
    worker._merge_checkpoint(new_state)

    patch_mock.assert_called_once()
    assert patch_mock.call_args.kwargs["checkpoint"]["schedule_state"] is not None
    assert patch_mock.call_args.kwargs["checkpoint"]["subtasks"] == []


def test_resume_from_checkpoint_compares_previous_state(mocker):
    """AC-5 P1/P3: next run loads checkpoint and resumes from last state."""
    from app.tasks.dsh_worker_scheduled_mission import ScheduledMissionWorker

    previous = {
        "schedule_state": {
            "last_run_sources": [{"url": "vcb.com"}],
            "last_run_deliverables": [{"id": "d1"}],
            "last_fired_at": "2026-08-30T00:00:00+00:00",
        }
    }
    worker = ScheduledMissionWorker(mission_id="m1", workspace_id=1, checkpoint=previous)
    ingest_mock = mocker.patch.object(worker, "_ingest", return_value=[])

    worker.run()

    ingest_mock.assert_called_once()
    assert worker.checkpoint["schedule_state"]["last_run_sources"] == [{"url": "vcb.com"}]


def test_first_run_with_empty_schedule_state_full_run(mocker):
    """AC-5 P3: empty schedule_state means no comparison, full run."""
    from app.tasks.dsh_worker_scheduled_mission import ScheduledMissionWorker

    worker = ScheduledMissionWorker(mission_id="m1", workspace_id=1, checkpoint={})
    ingest_mock = mocker.patch.object(worker, "_ingest", return_value=[{"url": "vcb.com"}])

    worker.run()

    ingest_mock.assert_called_once()
    assert "schedule_state" in worker.checkpoint


def test_ingestion_error_sets_status_error(mocker):
    """AC-5 P2: ingestion node throwing sets mission status=error and logs audit."""
    from app.tasks.dsh_worker_scheduled_mission import ScheduledMissionWorker

    worker = ScheduledMissionWorker(mission_id="m1", workspace_id=1)
    mocker.patch.object(worker, "_ingest", side_effect=RuntimeError("ingest failed"))
    update_mock = mocker.patch.object(worker, "_update_status")
    audit_mock = mocker.patch("app.tasks.dsh_worker_scheduled_mission.audit")

    worker.run()

    update_mock.assert_called_once_with("error")
    audit_mock.assert_called_once()
    assert audit_mock.call_args.kwargs["action"] == "scheduled_mission_ingestion_failed"


def test_progress_percent_computed_from_ingested_count():
    """AC-5 P4: progress_percent = min(100, int(ingested/expected * 100))."""
    from app.tasks.dsh_worker_scheduled_mission import _compute_progress

    assert _compute_progress(ingested_count=0, expected_count=10) == 0
    assert _compute_progress(ingested_count=5, expected_count=10) == 50
    assert _compute_progress(ingested_count=10, expected_count=10) == 100
    assert _compute_progress(ingested_count=15, expected_count=10) == 100


def test_next_fire_at_advanced_after_successful_ingestion(mocker):
    """AC-5 P4: next_fire_at updated using compute_next_fire_at."""
    from app.tasks.dsh_worker_scheduled_mission import ScheduledMissionWorker

    schedule = {"type": "cron", "expression": "0 9 * * 1", "timezone": "Asia/Ho_Chi_Minh"}
    worker = ScheduledMissionWorker(mission_id="m1", workspace_id=1, schedule=schedule)
    mocker.patch.object(worker, "_ingest", return_value=[{"url": "vcb.com"}])
    update_mock = mocker.patch.object(worker, "_update_next_fire_at")

    worker.run()

    update_mock.assert_called_once()
    args = update_mock.call_args.args[0]
    assert args > datetime.now(timezone.utc)


def test_checkpoint_size_exceeds_max_prunes_history(mocker):
    """AC-5 P3: checkpoint > MAX_CHECKPOINT_BYTES prunes schedule_state history."""
    from app.tasks.dsh_worker_scheduled_mission import ScheduledMissionWorker

    big_state = {
        "schedule_state": {
            "history": [{"data": "x" * 1024} for _ in range(10000)]
        },
        "subtasks": [],
    }
    worker = ScheduledMissionWorker(mission_id="m1", workspace_id=1, checkpoint=big_state)
    prune_mock = mocker.patch.object(worker, "_prune_checkpoint")

    worker._prune_if_needed()

    prune_mock.assert_called_once()


def test_redis_publish_failure_rollback_and_503(mocker):
    """AC-4 P2: Redis stream publish fails -> 503 and DB rollback."""
    from app.tasks.dsh_worker_scheduled_mission import ScheduledMissionWorker
    from app.exceptions import NowingError

    worker = ScheduledMissionWorker(mission_id="m1", workspace_id=1)
    mocker.patch.object(worker, "_publish_to_redis", side_effect=NowingError("EMAIL_REDIS_PUBLISH_FAILED"))
    rollback_mock = mocker.patch.object(worker, "_rollback_mission")

    with pytest.raises(NowingError) as exc_info:
        worker._enqueue_mission()

    assert "503" in str(exc_info.value) or "EMAIL_REDIS_PUBLISH_FAILED" in str(exc_info.value)
    rollback_mock.assert_called_once()


async def test_create_recurring_report_mission_accepts_schedule_and_source(mocker):
    """AC-4 P1/P2: DshMissionService.create_mission accepts schedule, source, request_text, next_fire_at."""
    from app.services.dsh_mission_service import DshMissionService

    service = DshMissionService()
    session = mocker.AsyncMock()
    session.add = mocker.MagicMock()
    payload = {
        "query": "Theo dõi giá cổ phiếu VCB trong 30 ngày",
        "source": "email",
        "from_address": "user@example.com",
        "attachment_document_ids": [],
    }
    schedule = {
        "type": "interval",
        "minutes": 360,
        "next_fire_at": (datetime.now(timezone.utc) + timedelta(minutes=360)).isoformat(),
    }

    mission = await service.create_mission(
        session=session,
        workspace_id=1,
        user_id=None,
        mission_type="recurring_report",
        payload=payload,
        schedule=schedule,
        source="email",
        request_text="Theo dõi giá cổ phiếu VCB trong 30 ngày",
        next_fire_at=datetime.now(timezone.utc) + timedelta(minutes=360),
    )

    assert mission.mission_type == "recurring_report"
    assert mission.payload["source"] == "email"
    assert mission.request_text == "Theo dõi giá cổ phiếu VCB trong 30 ngày"
    assert mission.schedule == schedule
