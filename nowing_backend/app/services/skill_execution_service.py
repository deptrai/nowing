"""Service for executing modular skills (prompt augmentation or DSH mission dispatch)."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import WorkspaceSkill
from app.services.dsh_mission_service import DshMissionService

logger = logging.getLogger(__name__)


class SkillExecutionService:
    """Dispatches skill execution based on skill_type."""

    def __init__(self, dsh_service: DshMissionService | None = None) -> None:
        self.dsh_service = dsh_service or DshMissionService()

    async def execute(
        self,
        session: AsyncSession,
        skill: WorkspaceSkill,
        workspace_id: int,
        user_id: UUID | None,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a skill.

        For prompt skills: returns rendered/augmented prompt content.
        For workflow skills: enqueues a DSH mission with mission_type='skill'.
        """
        params = parameters or {}

        if skill.skill_type == "workflow":
            mission = await self.dsh_service.create_mission(
                session=session,
                workspace_id=workspace_id,
                user_id=user_id,
                mission_type="skill",
                payload={
                    "skill_id": skill.id,
                    "skill_slug": skill.slug,
                    "parameters": params,
                },
            )
            return {
                "type": "workflow",
                "mission_id": str(mission.id),
                "status": mission.status.value,
            }

        # prompt skill: simple string template substitution if parameters given
        content = skill.content_markdown
        for key, val in params.items():
            content = content.replace(f"{{{{{key}}}}}", str(val))

        return {
            "type": "prompt",
            "skill_id": skill.id,
            "skill_slug": skill.slug,
            "content": content,
        }
