from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
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


class DshMissionService:
    """Business logic for creating, checkpointing and dispatching DSH missions."""

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
            checkpoint={"phase": "crawl", "subtasks": []},
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
            mission.checkpoint = checkpoint
        if phase is not None:
            mission.phase = phase
        if progress_percent is not None:
            mission.progress_percent = max(0, min(100, progress_percent))
        if current_subtask_id is not None:
            mission.current_subtask_id = current_subtask_id
        if status is not None:
            mission.status = status
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

    async def publish_to_stream(self, mission: DshMission) -> str:
        """Add the mission to the Redis Stream for workers to consume."""
        redis_client = await get_redis_client()
        msg_id = await redis_client.xadd(
            config.DSH_STREAM_TASKS,
            {
                "mission_id": str(mission.id),
                "workspace_id": str(mission.workspace_id),
                "mission_type": mission.mission_type,
                "payload": json.dumps(mission.payload),
            },
        )
        return msg_id
