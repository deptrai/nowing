"""Public, PII-safe DSH mission control builder (Story 26.5 / AC-2)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import DshMission, Run, TokenUsage
from app.schemas.dsh import (
    DshMissionControlResponse,
    DshMissionDeliverable,
    DshMissionSubtask,
    TokenVelocity,
)


class MissionControlService:
    """Build a redacted, token-velocity-aware mission control view."""

    @staticmethod
    def _redact_subtask(raw: dict[str, Any]) -> DshMissionSubtask:
        """Keep only public, PII-safe subtask fields."""
        if not isinstance(raw, dict):
            raw = {}
        return DshMissionSubtask(
            id=raw.get("id") or "",
            title=raw.get("title") or "",
            status=raw.get("status") or "pending",
            phase=raw.get("phase"),
            reasoning_content=raw.get("reasoning_content"),
            tokens_used=raw.get("tokens_used") or 0,
            tokens_per_second=raw.get("tokens_per_second") or 0.0,
            run_id=raw.get("run_id"),
            cost_micros=raw.get("cost_micros") or 0,
            started_at=raw.get("started_at"),
            completed_at=raw.get("completed_at"),
        )

    @staticmethod
    def _redact_deliverable(raw: Any) -> DshMissionDeliverable | None:
        """Keep only public, safe deliverable fields (drop sandbox_path)."""
        if not isinstance(raw, dict):
            return None
        return DshMissionDeliverable(
            type=raw.get("type") or "xlsx",
            filename=raw.get("filename") or "",
            size=raw.get("size") or 0,
            created_at=raw.get("created_at"),
            include_pii=raw.get("include_pii") or False,
        )

    @staticmethod
    def _parse_uuid(value: Any) -> uuid.UUID | None:
        """Best-effort UUID parsing for run_id fallbacks."""
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(str(value))
        except ValueError:
            return None

    async def _resolve_token_usage(
        self,
        session: AsyncSession,
        workspace_id: int,
        run_id: uuid.UUID | None,
    ) -> tuple[int, int, float]:
        """Try TokenUsage first; return (tokens, cost_micros, tokens_per_second)."""
        if run_id is None:
            return 0, 0, 0.0

        # TokenUsage.run_id is the FK to the DSH subtask run. Prefer an exact
        # match, then fall back to the most recent dsh_mission row in the same
        # workspace. TokenUsage.id is an auto-increment integer, so we never
        # treat run_id as the primary key.
        result = await session.execute(
            select(TokenUsage)
            .where(
                TokenUsage.workspace_id == workspace_id,
                TokenUsage.usage_type == "dsh_mission",
                TokenUsage.run_id == run_id,
            )
            .order_by(TokenUsage.created_at.desc())
            .limit(1)
        )
        rows = list(result.scalars().all())
        if rows:
            row = rows[0]
            return (
                row.total_tokens or 0,
                row.cost_micros or 0,
                0.0,
            )

        # Fallback to the most recent dsh_mission usage row for the workspace.
        result = await session.execute(
            select(TokenUsage)
            .where(
                TokenUsage.workspace_id == workspace_id,
                TokenUsage.usage_type == "dsh_mission",
            )
            .order_by(TokenUsage.created_at.desc())
            .limit(1)
        )
        rows = list(result.scalars().all())
        if rows:
            row = rows[0]
            return (
                row.total_tokens or 0,
                row.cost_micros or 0,
                0.0,
            )

        return 0, 0, 0.0

    async def _resolve_run_cost(
        self,
        session: AsyncSession,
        run_id: uuid.UUID | None,
    ) -> int:
        """Return Run.cost_micros when token counts are missing."""
        if run_id is None:
            return 0
        row = await session.get(Run, run_id)
        if row is None:
            return 0
        return row.cost_micros or 0

    async def build_control_data(
        self,
        session: AsyncSession,
        mission: DshMission,
        requested_workspace_id: int | None = None,
    ) -> DshMissionControlResponse:
        """Build a PII-safe, token-velocity-aware control view.

        Raises ``ValueError`` when the requested workspace does not own the mission.
        """
        if (
            requested_workspace_id is not None
            and mission.workspace_id != requested_workspace_id
        ):
            raise ValueError("Mission not in workspace")

        checkpoint = mission.checkpoint or {}
        if not isinstance(checkpoint, dict):
            checkpoint = {}

        deliverables: list[DshMissionDeliverable] = [
            d
            for raw in checkpoint.get("deliverables", [])
            if (d := self._redact_deliverable(raw)) is not None
        ]

        subtasks: list[DshMissionSubtask] = []
        total_tokens = 0
        total_cost = 0
        weighted_tps = 0.0

        for raw in checkpoint.get("subtasks", []):
            subtask = self._redact_subtask(raw)
            subtasks.append(subtask)

            run_id = self._parse_uuid(subtask.run_id)
            tokens_used = subtask.tokens_used
            cost_micros = subtask.cost_micros
            tps = subtask.tokens_per_second

            # Primary source: checkpoint subtask already reports token/cost.
            # Fallback to TokenUsage or Run.cost_micros if missing.
            if (not tokens_used and not cost_micros) and run_id is not None:
                tu_tokens, tu_cost, _ = await self._resolve_token_usage(
                    session, mission.workspace_id, run_id
                )
                if tu_tokens or tu_cost:
                    tokens_used = tu_tokens
                    cost_micros = tu_cost
                    tps = 0.0

            if not cost_micros and not tokens_used and run_id is not None:
                cost_micros = await self._resolve_run_cost(session, run_id)
                tps = 0.0

            total_tokens += tokens_used
            total_cost += cost_micros
            if tokens_used > 0:
                weighted_tps += tokens_used * tps

        tokens_per_second = (
            weighted_tps / total_tokens if total_tokens > 0 else 0.0
        )

        now = datetime.now(UTC)
        return DshMissionControlResponse(
            id=mission.id,
            workspace_id=mission.workspace_id,
            mission_type=mission.mission_type,
            status=mission.status,
            phase=mission.phase,
            progress_percent=mission.progress_percent,
            current_subtask_id=mission.current_subtask_id,
            retry_count=getattr(mission, "retry_count", 0),
            created_at=getattr(mission, "created_at", None) or now,
            updated_at=getattr(mission, "updated_at", None) or now,
            token_velocity=TokenVelocity(
                tokens_total=total_tokens,
                tokens_per_second=tokens_per_second,
                cost_micros=total_cost,
                cost_credits=round(total_cost / 1_000_000, 6),
            ),
            subtasks=subtasks,
            deliverables=deliverables,
        )
