"""Main-agent tool for generating a sales/marketing web app (Story 27.1a)."""

from __future__ import annotations

import contextlib
import logging
from typing import Any
from uuid import UUID

from langchain_core.tools import tool

from app.db import async_session_maker

logger = logging.getLogger(__name__)


def create_build_web_app_tool(deps: dict[str, Any]):
    """Factory for the ``build_web_app`` chat tool."""

    workspace_id: int = deps["workspace_id"]
    user_id_val = deps.get("user_id")
    user_id: UUID | None = None
    if user_id_val:
        try:
            user_id = (
                user_id_val if isinstance(user_id_val, UUID) else UUID(str(user_id_val))
            )
        except (ValueError, TypeError, AttributeError):
            logger.warning("build_web_app: invalid user_id %r", user_id_val)

    @tool
    async def build_web_app(
        prompt: str,
        app_name: str | None = None,
        language: str = "en",
        app_id: str | None = None,
    ) -> str:
        """Build or modify a lightweight sales/marketing Next.js web app from a description.

        Use this tool when the user wants to create or modify a landing page, pricing page,
        lead capture form, waitlist, or marketing report site.
        Pass app_id if refining an existing app created earlier in the conversation.

        Args:
            prompt: Natural language description of the desired web app or requested modification.
            app_name: Optional override for the generated app name/slug.
            language: Target UI language (e.g. "en" or "vi").
            app_id: Optional existing app ID when modifying an existing application in follow-up turns.
        """
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.config import config as app_config
        from app.db import Workspace, WorkspaceMembership
        from app.services.web_builder.generator import WebBuilderService
        from app.services.web_builder.schemas import (
            WebAppBuildInput,
            WebAppBuildOutput,
        )

        if not app_config.WEB_BUILDER_ENABLED:
            return WebAppBuildOutput(
                app_id=app_id or "",
                workspace_id=workspace_id,
                name=app_name or "Web App",
                slug="",
                status="validation_failed",
                error="Web Builder is not enabled on this workspace plan",
            ).model_dump_json()

        if not prompt or not prompt.strip():
            return WebAppBuildOutput(
                app_id=app_id or "",
                workspace_id=workspace_id,
                name=app_name or "Web App",
                slug="",
                status="validation_failed",
                error="Prompt is required for build_web_app",
            ).model_dump_json()

        prompt = prompt.strip()
        if len(prompt) > app_config.WEB_BUILDER_MAX_PROMPT_CHARS:
            return WebAppBuildOutput(
                app_id=app_id or "",
                workspace_id=workspace_id,
                name=app_name or "Web App",
                slug="",
                status="validation_failed",
                error=(
                    f"Prompt exceeds maximum allowed length of "
                    f"{app_config.WEB_BUILDER_MAX_PROMPT_CHARS} characters."
                ),
            ).model_dump_json()

        build_input = WebAppBuildInput(
            prompt=prompt,
            workspace_id=workspace_id,
            user_id=user_id,
            app_id=app_id,
            app_name=app_name,
            language=language,
        )

        service = WebBuilderService(
            storage_base_path=app_config.FILE_STORAGE_LOCAL_PATH,
        )

        session = None
        try:
            async with async_session_maker() as session_:
                session = session_

                # Re-check workspace gating in case plan changed since thread start.
                ws = (
                    await session.execute(
                        select(Workspace).where(Workspace.id == workspace_id)
                    )
                ).scalars().first()
                if ws is None or ws.web_builder_enabled is False:
                    return WebAppBuildOutput(
                        app_id=app_id or "",
                        workspace_id=workspace_id,
                        name=app_name or "Web App",
                        slug="",
                        status="validation_failed",
                        error="Web Builder is not enabled on this workspace plan",
                    ).model_dump_json()

                # Best-effort membership check (tool may be called after a role change).
                membership = (
                    await session.execute(
                        select(WorkspaceMembership)
                        .where(
                            WorkspaceMembership.user_id == user_id,
                            WorkspaceMembership.workspace_id == workspace_id,
                        )
                        .options(selectinload(WorkspaceMembership.role))
                    )
                ).scalars().first()
                if membership and not (
                    membership.is_owner
                    or (
                        membership.role
                        and "web_builder:create" in (membership.role.permissions or [])
                    )
                ):
                    return WebAppBuildOutput(
                        app_id=app_id or "",
                        workspace_id=workspace_id,
                        name=app_name or "Web App",
                        slug="",
                        status="validation_failed",
                        error="You don't have permission to build web apps in this workspace",
                    ).model_dump_json()

                result = await service.generate_project(build_input, session=session)
                return result.model_dump_json()
        except Exception as exc:
            if session is not None:
                with contextlib.suppress(Exception):
                    await session.rollback()
            logger.exception("build_web_app failed: %s", exc)
            return WebAppBuildOutput(
                app_id="",
                workspace_id=workspace_id,
                name=app_name or "Web App",
                slug="",
                status="error",
                error=f"Error building web app: {exc}",
            ).model_dump_json()

    return build_web_app
