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


_UNSET = object()
"""Sentinel for optional arguments that should not be updated."""


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
        *,
        schedule: dict[str, Any] | None = None,
        source: str | None = None,
        request_text: str | None = None,
        next_fire_at: datetime | None = None,
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
            schedule=schedule if schedule is not None else {},
            source=source,
            request_text=request_text,
            next_fire_at=next_fire_at,
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
        current_subtask_id: str | None | Any = _UNSET,
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
        if current_subtask_id is not _UNSET:
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

    async def abort_takeover_mission(
        self,
        session: AsyncSession,
        mission_id: uuid.UUID | str,
    ) -> DshMission:
        """Abort a mission awaiting human takeover, setting status to cancelled and phase to aborted_timeout."""
        if isinstance(mission_id, str):
            try:
                mission_uuid = uuid.UUID(mission_id)
            except ValueError as exc:
                raise DshMissionServiceError(f"Invalid mission ID {mission_id!r}") from exc
        else:
            mission_uuid = mission_id

        mission = await session.get(DshMission, mission_uuid)
        if mission is None:
            raise DshMissionServiceError("Mission not found")

        # Idempotent return if already aborted_timeout
        if (
            mission.status == DshMissionStatus.CANCELLED.value
            and mission.phase == "aborted_timeout"
        ):
            return mission

        if mission.phase != "waiting_for_human":
            raise DshMissionServiceError(
                f"Mission is in phase {mission.phase!r}, only waiting_for_human missions can be aborted"
            )

        now = datetime.now(UTC)
        mission.status = DshMissionStatus.CANCELLED.value
        mission.phase = "aborted_timeout"
        mission.updated_at = now
        mission.completed_at = now

        checkpoint = dict(mission.checkpoint) if isinstance(mission.checkpoint, dict) else {}
        takeover = checkpoint.setdefault("takeover", {})
        if isinstance(takeover, dict):
            takeover["aborted_at"] = now.isoformat()
            takeover["aborted_reason"] = "user_aborted"
        checkpoint["takeover"] = takeover
        mission.checkpoint = checkpoint
        session.add(mission)

        # Atomically release the Redis takeover lock
        try:
            redis = await get_redis_client()
            takeover_key = f"dsh:lock:takeover:{mission.workspace_id}:{mission.id}"
            await redis.delete(takeover_key)
        except Exception as redis_exc:
            logger.warning(
                "Failed to delete Redis takeover lock for mission %s: %s",
                mission.id,
                redis_exc,
            )

        await session.flush()
        return mission

    async def sweep_expired_takeovers(
        self,
        session: AsyncSession,
        *,
        timeout_seconds: int = 900,
        workspace_id: int | None = None,
    ) -> list[DshMission]:
        """Scan and transition expired waiting_for_human missions to cancelled/aborted_timeout."""
        now = datetime.now(UTC)
        stmt = select(DshMission).where(
            DshMission.phase == "waiting_for_human",
            DshMission.status != DshMissionStatus.CANCELLED.value,
        )
        if workspace_id is not None:
            stmt = stmt.where(DshMission.workspace_id == workspace_id)
        result = await session.execute(stmt)
        candidates = list(result.scalars().all())

        swept_missions: list[DshMission] = []
        redis = None
        try:
            redis = await get_redis_client()
        except Exception as redis_exc:
            logger.warning("Could not connect to Redis during takeover sweep: %s", redis_exc)

        for mission in candidates:
            checkpoint = mission.checkpoint if isinstance(mission.checkpoint, dict) else {}
            takeover = checkpoint.get("takeover") if isinstance(checkpoint, dict) else {}
            expires_at = None

            if isinstance(takeover, dict) and takeover.get("expires_at"):
                try:
                    expires_at = datetime.fromisoformat(takeover["expires_at"])
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=UTC)
                except (ValueError, TypeError):
                    expires_at = None

            if expires_at is None:
                ref_time = mission.updated_at or mission.created_at or now
                if ref_time.tzinfo is None:
                    ref_time = ref_time.replace(tzinfo=UTC)
                expires_at = ref_time + timedelta(seconds=timeout_seconds)

            if now >= expires_at:
                mission.status = DshMissionStatus.CANCELLED.value
                mission.phase = "aborted_timeout"
                mission.updated_at = now
                mission.completed_at = now

                if isinstance(checkpoint, dict):
                    takeover = checkpoint.setdefault("takeover", {})
                    if isinstance(takeover, dict):
                        takeover["aborted_at"] = now.isoformat()
                        takeover["aborted_reason"] = "timeout"
                    checkpoint["takeover"] = takeover
                mission.checkpoint = checkpoint
                session.add(mission)

                if redis is not None:
                    try:
                        takeover_key = f"dsh:lock:takeover:{mission.workspace_id}:{mission.id}"
                        await redis.delete(takeover_key)
                    except Exception as del_exc:
                        logger.warning(
                            "Failed to delete Redis takeover lock for swept mission %s: %s",
                            mission.id,
                            del_exc,
                        )

                swept_missions.append(mission)
                logger.info(
                    "Takeover timed out for mission %s; marked as aborted_timeout",
                    mission.id,
                )

        if swept_missions:
            await session.flush()

        return swept_missions


async def abort_takeover_mission(
    session: AsyncSession,
    mission_id: uuid.UUID | str,
) -> DshMission:
    """Module-level helper to abort a takeover mission."""
    return await DshMissionService().abort_takeover_mission(session, mission_id)


async def sweep_expired_takeovers(
    session: AsyncSession,
    *,
    timeout_seconds: int = 900,
    workspace_id: int | None = None,
) -> list[DshMission]:
    """Module-level helper to sweep expired takeover missions."""
    return await DshMissionService().sweep_expired_takeovers(
        session, timeout_seconds=timeout_seconds, workspace_id=workspace_id
    )

