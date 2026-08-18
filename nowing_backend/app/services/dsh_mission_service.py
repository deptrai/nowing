from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import DshMission, DshMissionStatus
from app.redis_client import get_redis_client

logger = logging.getLogger(__name__)


class DshMissionServiceError(Exception):
    """Domain error raised by the DSH mission service."""

    pass


class DshPayloadTooLargeError(DshMissionServiceError):
    """Raised when the serialized payload exceeds the safe XADD limit."""

    pass


_VALID_STATUS_TRANSITIONS: dict[DshMissionStatus, set[DshMissionStatus]] = {
    DshMissionStatus.PENDING: {
        DshMissionStatus.PENDING,
        DshMissionStatus.RUNNING,
        DshMissionStatus.CANCELLED,
        DshMissionStatus.ERROR,
        DshMissionStatus.DLQ,
    },
    DshMissionStatus.RUNNING: {
        DshMissionStatus.RUNNING,
        DshMissionStatus.SUCCESS,
        DshMissionStatus.CANCELLED,
        DshMissionStatus.ERROR,
        DshMissionStatus.DLQ,
    },
    DshMissionStatus.SUCCESS: {DshMissionStatus.SUCCESS},
    DshMissionStatus.ERROR: {
        DshMissionStatus.ERROR,
        DshMissionStatus.PENDING,
        DshMissionStatus.DLQ,
    },
    DshMissionStatus.DLQ: {DshMissionStatus.DLQ},
    DshMissionStatus.CANCELLED: {
        DshMissionStatus.CANCELLED,
        DshMissionStatus.PENDING,
    },
}


class DshMissionService:
    """Business logic for creating, checkpointing and dispatching DSH missions."""

    @staticmethod
    def _default_checkpoint() -> dict[str, Any]:
        return {"version": 1, "phase": "crawl", "subtasks": []}

    async def create_mission(
        self,
        session: AsyncSession,
        workspace_id: int,
        user_id: uuid.UUID | None,
        mission_type: str,
        payload: dict[str, Any],
    ) -> DshMission:
        """Insert a pending mission row and flush so the UUID is generated."""
        mission = DshMission(
            workspace_id=workspace_id,
            user_id=user_id,
            mission_type=mission_type,
            status=DshMissionStatus.PENDING.value,
            phase="crawl",
            progress_percent=0,
            payload=payload or {},
            checkpoint=self._default_checkpoint(),
        )
        session.add(mission)
        await session.flush()
        return mission

    async def get_mission_or_404(
        self,
        session: AsyncSession,
        mission_id: uuid.UUID,
    ) -> DshMission:
        """Load a mission by UUID or raise a service-level 404."""
        mission = await session.get(DshMission, mission_id)
        if mission is None:
            raise DshMissionServiceError("Mission not found")
        return mission

    async def get_mission_for_workspace(
        self,
        session: AsyncSession,
        mission_id: uuid.UUID,
        workspace_id: int,
    ) -> DshMission:
        """Load a mission scoped to a workspace."""
        result = await session.execute(
            select(DshMission).where(
                DshMission.id == mission_id,
                DshMission.workspace_id == workspace_id,
            )
        )
        mission = result.scalars().first()
        if mission is None:
            raise DshMissionServiceError("Mission not found")
        return mission

    async def list_missions_for_workspace(
        self,
        session: AsyncSession,
        workspace_id: int,
        status_filter: str | None = None,
        hours: int = 24,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DshMission]:
        """List missions in a workspace filtered by status and age."""
        since = datetime.now(UTC) - timedelta(hours=hours)
        status_list = [
            s.strip()
            for s in (status_filter or "").split(",")
            if s.strip()
        ]
        stmt = (
            select(DshMission)
            .where(
                DshMission.workspace_id == workspace_id,
                DshMission.created_at >= since,
            )
            .order_by(DshMission.created_at.desc())
        )
        if status_list:
            stmt = stmt.where(DshMission.status.in_(status_list))
        stmt = stmt.limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    def _validate_status_transition(
        self,
        mission: DshMission,
        status: str,
    ) -> DshMissionStatus:
        try:
            new_status = DshMissionStatus(status)
        except ValueError as exc:
            raise DshMissionServiceError(f"Invalid mission status {status!r}") from exc
        try:
            old_status = DshMissionStatus(mission.status)
        except ValueError:
            # Defensive: if the DB somehow has an invalid status, allow recovery.
            logger.warning(
                "Mission %s has invalid status %s", mission.id, mission.status
            )
            return new_status

        allowed = _VALID_STATUS_TRANSITIONS.get(old_status, set())
        if old_status != new_status and new_status not in allowed:
            raise DshMissionServiceError(
                f"Invalid status transition from {old_status.value} to {new_status.value}"
            )
        return new_status

    def _bump_checkpoint_version(
        self, checkpoint: dict[str, Any] | None
    ) -> dict[str, Any]:
        checkpoint = self._default_checkpoint() if not checkpoint else dict(checkpoint)
        checkpoint["version"] = checkpoint.get("version", 0) + 1
        checkpoint["last_updated_at"] = datetime.now(UTC).isoformat()
        return checkpoint

    async def update_checkpoint(
        self,
        session: AsyncSession,
        mission: DshMission,
        checkpoint: dict[str, Any] | None = None,
        phase: str | None = None,
        progress_percent: int | None = None,
        current_subtask_id: str | None = None,
        status: str | None = None,
        retry_count: int | None = None,
        error: dict[str, Any] | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> DshMission:
        """Patch mission state from the sidecar."""
        if checkpoint is not None:
            current_version = (
                mission.checkpoint.get("version", 0)
                if isinstance(mission.checkpoint, dict)
                else 0
            )
            new_version = (
                checkpoint.get("version", 0) if isinstance(checkpoint, dict) else 0
            )
            if new_version < current_version:
                raise DshMissionServiceError(
                    f"Stale checkpoint version {new_version} < {current_version}"
                )
            mission.checkpoint = self._bump_checkpoint_version(checkpoint)
        if phase is not None:
            mission.phase = phase
        if progress_percent is not None:
            mission.progress_percent = max(0, min(100, progress_percent))
        if current_subtask_id is not None:
            mission.current_subtask_id = current_subtask_id
        if status is not None:
            mission.status = self._validate_status_transition(mission, status).value
        if retry_count is not None:
            mission.retry_count = retry_count
        if error is not None:
            mission.error = error
        if started_at is not None:
            mission.started_at = started_at
        if completed_at is not None:
            mission.completed_at = completed_at
        await session.flush()
        return mission

    def validate_payload_size(self, payload: dict[str, Any]) -> None:
        """Raise DshPayloadTooLargeError if the serialized payload is too big."""
        payload_json = json.dumps(payload or {})
        if len(payload_json.encode("utf-8")) > config.DSH_MAX_PAYLOAD_BYTES:
            raise DshPayloadTooLargeError(
                f"Payload exceeds {config.DSH_MAX_PAYLOAD_BYTES} bytes"
            )

    async def publish_to_stream(self, mission: DshMission) -> str:
        """Add the mission to the Redis Stream for workers to consume."""
        self.validate_payload_size(mission.payload)

        redis_client = await get_redis_client()
        payload_json = json.dumps(mission.payload)
        msg_id = await redis_client.xadd(
            config.DSH_STREAM_TASKS,
            {
                "mission_id": str(mission.id),
                "workspace_id": str(mission.workspace_id),
                "user_id": str(mission.user_id) if mission.user_id else "",
                "mission_type": mission.mission_type,
                "payload_json": payload_json,
                "created_at": mission.created_at.isoformat()
                if mission.created_at
                else "",
                "attempt": "1",
            },
        )
        return msg_id
