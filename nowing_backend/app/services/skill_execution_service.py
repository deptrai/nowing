"""Service for executing modular skills (prompt augmentation or DSH mission dispatch)."""

from __future__ import annotations

import logging
import re
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import WorkspaceSkill
from app.services.dsh_mission_service import DshMissionService

logger = logging.getLogger(__name__)

_SKILL_PLACEHOLDER_PATTERN = re.compile(r"\{\{([a-zA-Z0-9_\-]+)\}\}")


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
                "skill_id": skill.id,
                "skill_slug": skill.slug,
                "mission_id": str(mission.id),
                "status": mission.status,
            }

        # prompt skill: single-pass template substitution with explicit
        # {{key}} placeholders. Values are escaped to prevent recursive/cascading
        # template injection.
        def _replace(match: re.Match[str]) -> str:
            key = match.group(1)
            value = params.get(key)
            if value is None:
                return match.group(0)
            # Render the value, but never re-introduce a placeholder.
            rendered = str(value).replace("{", "[").replace("}", "]")
            return rendered

        content = _SKILL_PLACEHOLDER_PATTERN.sub(_replace, skill.content_markdown)

        return {
            "type": "prompt",
            "skill_id": skill.id,
            "skill_slug": skill.slug,
            "content": content,
        }
