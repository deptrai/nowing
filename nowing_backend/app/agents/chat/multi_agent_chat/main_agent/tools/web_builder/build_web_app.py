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
    ) -> dict[str, Any]:
        """Build a lightweight sales/marketing Next.js web app from a description.

        Use this tool when the user wants to create a landing page, pricing page,
        lead capture form, waitlist, or marketing report site.

        Args:
            prompt: Natural language description of the desired web app.
            app_name: Optional override for the generated app name/slug.
            language: Target UI language (e.g. "en" or "vi").
        """
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.capabilities.web_builder.build_app import (
            WebBuilderCapabilityInput,
            execute_build_app,
        )
        from app.config import config as app_config
        from app.db import Permission, Workspace, WorkspaceMembership
        from app.services.web_builder.schemas import WebAppBuildOutput

        if not app_config.WEB_BUILDER_ENABLED:
            return WebAppBuildOutput(
                app_id="",
                workspace_id=workspace_id,
                name=app_name or "Web App",
                slug="",
                status="validation_failed",
                error="Web Builder is not enabled on this workspace plan",
            ).model_dump(mode="json")

        if not prompt or not prompt.strip():
            return WebAppBuildOutput(
                app_id="",
                workspace_id=workspace_id,
                name=app_name or "Web App",
                slug="",
                status="validation_failed",
                error="Prompt is required for build_web_app",
            ).model_dump(mode="json")

        prompt = prompt.strip()
        if len(prompt) < 3:
            return WebAppBuildOutput(
                app_id="",
                workspace_id=workspace_id,
                name=app_name or "Web App",
                slug="",
                status="validation_failed",
                error="Prompt must be at least 3 characters",
            ).model_dump(mode="json")

        if len(prompt) > app_config.WEB_BUILDER_MAX_PROMPT_CHARS:
            return WebAppBuildOutput(
                app_id="",
                workspace_id=workspace_id,
                name=app_name or "Web App",
                slug="",
                status="validation_failed",
                error=(
                    f"Prompt exceeds maximum allowed length of "
                    f"{app_config.WEB_BUILDER_MAX_PROMPT_CHARS} characters."
                ),
            ).model_dump(mode="json")

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
                        app_id="",
                        workspace_id=workspace_id,
                        name=app_name or "Web App",
                        slug="",
                        status="validation_failed",
                        error="Web Builder is not enabled on this workspace plan",
                    ).model_dump(mode="json")

                # Fail-closed membership check: a missing or invalid user is denied.
                if user_id is None:
                    return WebAppBuildOutput(
                        app_id="",
                        workspace_id=workspace_id,
                        name=app_name or "Web App",
                        slug="",
                        status="validation_failed",
                        error="You don't have permission to build web apps in this workspace",
                    ).model_dump(mode="json")

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
                if membership is None:
                    return WebAppBuildOutput(
                        app_id="",
                        workspace_id=workspace_id,
                        name=app_name or "Web App",
                        slug="",
                        status="validation_failed",
                        error="You don't have permission to build web apps in this workspace",
                    ).model_dump(mode="json")

                permissions = membership.role.permissions or [] if membership.role else []
                if not (
                    membership.is_owner
                    or Permission.FULL_ACCESS.value in permissions
                    or Permission.WEB_BUILDER_CREATE.value in permissions
                ):
                    return WebAppBuildOutput(
                        app_id="",
                        workspace_id=workspace_id,
                        name=app_name or "Web App",
                        slug="",
                        status="validation_failed",
                        error="You don't have permission to build web apps in this workspace",
                    ).model_dump(mode="json")

                cap_input = WebBuilderCapabilityInput(
                    prompt=prompt,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    app_name=app_name,
                    language=language,
                )
                cap_result = await execute_build_app(session, cap_input)
                return WebAppBuildOutput(
                    app_id=cap_result.app_id,
                    workspace_id=cap_result.workspace_id,
                    name=cap_result.name,
                    slug=cap_result.slug,
                    status=cap_result.status,
                    preview_url=cap_result.preview_url,
                    public_url=cap_result.public_url,
                    files=cap_result.files,
                    message=cap_result.message,
                    error=cap_result.error,
                ).model_dump(mode="json")
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
            ).model_dump(mode="json")

    return build_web_app
