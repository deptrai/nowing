"""Stateful scheduled DSH mission worker (Story 6.10)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from app.automations.triggers.builtin.schedule import compute_next_fire_at
from app.config import config
from app.db import DshMission
from app.exceptions import NowingError
from app.services.dsh_mission_service import DshMissionService

logger = logging.getLogger(__name__)

MAX_CHECKPOINT_BYTES = int(
    getattr(config, "DSH_MAX_CHECKPOINT_BYTES", 1 * 1024 * 1024)
)


def audit(*, action: str, **kwargs: Any) -> None:
    """Emit a structured audit log entry."""
    extra = {"action": action, **kwargs}
    logger.info("scheduled_mission.audit", extra=extra)


def _compute_progress(ingested_count: int, expected_count: int) -> int:
    """Compute progress percent clamped to [0, 100]."""
    if expected_count <= 0:
        return 0
    return min(100, int(ingested_count / expected_count * 100))


class ScheduledMissionWorker:
    """Worker that runs a single scheduled ``recurring_report`` mission."""

    def __init__(
        self,
        *,
        mission_id: str,
        workspace_id: int,
        schedule: dict[str, Any] | None = None,
        checkpoint: dict[str, Any] | None = None,
    ) -> None:
        self.mission_id = mission_id
        self.workspace_id = workspace_id
        self.schedule = schedule or {}
        self.checkpoint = checkpoint or {"version": 1, "phase": "ingestion", "subtasks": []}

    def _prune_if_needed(self) -> None:
        """Prune checkpoint history if it exceeds the size budget."""
        size = len(json.dumps(self.checkpoint).encode("utf-8"))
        if size > MAX_CHECKPOINT_BYTES:
            self._prune_checkpoint()

    def _prune_checkpoint(self) -> None:
        """Remove older schedule_state history entries while preserving subtasks."""
        state = self.checkpoint.get("schedule_state", {})
        if isinstance(state, dict) and "history" in state:
            state["history"] = state["history"][-100:]
        self.checkpoint["schedule_state"] = state

    def _merge_checkpoint(self, new_state: dict[str, Any]) -> None:
        """Merge new state into checkpoint without overwriting subtasks."""
        if not isinstance(self.checkpoint, dict):
            self.checkpoint = {"version": 1, "phase": "ingestion", "subtasks": []}

        previous_schedule_state = self.checkpoint.get("schedule_state") or {}

        for key, value in new_state.items():
            if key == "subtasks" and "subtasks" in self.checkpoint:
                continue
            if key == "schedule_state" and isinstance(value, dict):
                merged = dict(previous_schedule_state)
                for sub_key, sub_value in value.items():
                    if sub_key == "last_run_sources" and not sub_value:
                        # Preserve previous sources when the current run produced nothing new.
                        merged[sub_key] = previous_schedule_state.get(
                            "last_run_sources", []
                        )
                    else:
                        merged[sub_key] = sub_value
                self.checkpoint[key] = merged
            else:
                self.checkpoint[key] = value

        self._patch_checkpoint(checkpoint=self.checkpoint)
        self._prune_if_needed()

    def _ingest(self) -> list[dict[str, Any]]:
        """Placeholder ingestion node: return list of new sources."""
        # Real implementation would call ChainLens / internal research API.
        return []

    def _patch_checkpoint(self, checkpoint: dict[str, Any]) -> None:
        """Persist checkpoint update (placeholder for DB write)."""
        pass

    def _update_status(self, status: str) -> None:
        """Persist mission status (placeholder for DB write)."""
        pass

    def _update_next_fire_at(self, next_fire_at: datetime) -> None:
        """Persist next_fire_at update (placeholder for DB write)."""
        pass

    def _publish_to_redis(self) -> None:
        """Publish mission to the Redis stream (placeholder)."""
        pass

    def _rollback_mission(self) -> None:
        """Rollback mission creation on publish failure."""
        pass

    def _advance_schedule(self) -> datetime:
        """Compute the next fire time from the schedule expression."""
        now = datetime.now(timezone.utc)
        schedule = self.schedule

        if schedule.get("type") == "interval":
            minutes = int(schedule.get("minutes", 60))
            return now + timedelta(minutes=minutes)

        if schedule.get("type") == "cron" and schedule.get("expression"):
            tz = schedule.get("timezone", "UTC")
            try:
                return compute_next_fire_at(
                    schedule["expression"], tz, after=now
                )
            except Exception as exc:
                logger.warning("Failed to compute next_fire_at: %s", exc)

        return now + timedelta(hours=1)

    def run(self) -> None:
        """Execute the scheduled mission once and update checkpoint / next fire."""
        previous_state = self.checkpoint.get("schedule_state", {})

        try:
            ingested = self._ingest()
        except Exception as exc:
            logger.exception("Scheduled mission %s ingestion failed", self.mission_id)
            audit(
                action="scheduled_mission_ingestion_failed",
                mission_id=self.mission_id,
                error_code=type(exc).__name__,
                workspace_id=self.workspace_id,
            )
            self._update_status("error")
            return

        new_state = {
            "schedule_state": {
                "last_run_sources": ingested,
                "last_run_deliverables": [],
                "last_fired_at": datetime.now(timezone.utc).isoformat(),
            }
        }

        if previous_state:
            new_state["schedule_state"]["previous_sources"] = previous_state.get(
                "last_run_sources", []
            )
        if not ingested and previous_state:
            new_state["schedule_state"]["last_run_sources"] = previous_state.get(
                "last_run_sources", []
            )

        self._merge_checkpoint(new_state)

        progress = _compute_progress(len(ingested), max(len(ingested), 1))
        if "progress" in new_state:
            new_state["progress"] = progress

        next_fire_at = self._advance_schedule()
        self._update_next_fire_at(next_fire_at)
        self._update_status("pending")

    def _enqueue_mission(self) -> None:
        """Publish a newly-created recurring mission to the Redis stream."""
        try:
            self._publish_to_redis()
        except NowingError as exc:
            self._rollback_mission()
            raise NowingError(
                "EMAIL_REDIS_PUBLISH_FAILED",
                code="EMAIL_REDIS_PUBLISH_FAILED",
                status_code=503,
            ) from exc
