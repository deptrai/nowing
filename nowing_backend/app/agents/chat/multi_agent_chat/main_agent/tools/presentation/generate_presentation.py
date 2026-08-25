"""Main-agent tool for generating PPTX/Marp slide decks (Story 27.2a)."""

from __future__ import annotations

import contextlib
import logging
from typing import Any
from uuid import UUID

from langchain_core.tools import tool

from app.db import async_session_maker

logger = logging.getLogger(__name__)


def create_generate_presentation_tool(deps: dict[str, Any]):
    """Factory for the ``generate_presentation`` chat tool."""

    workspace_id: int = deps["workspace_id"]
    user_id_val = deps.get("user_id")
    user_id: UUID | None = None
    if user_id_val:
        try:
            user_id = (
                user_id_val if isinstance(user_id_val, UUID) else UUID(str(user_id_val))
            )
        except (ValueError, TypeError, AttributeError):
            logger.warning("generate_presentation: invalid user_id %r", user_id_val)

    @tool
    async def generate_presentation(
        prompt: str,
        output_format: str = "pptx",
        language: str = "en",
    ) -> dict[str, Any]:
        """Generate a PPTX or Marp Markdown slide deck from a description.

        Use this tool when the user wants a slide deck, pitch deck, or presentation.

        Args:
            prompt: Natural language description of the desired slide deck.
            output_format: Either "pptx" (default) or "marp".
            language: Target UI language (e.g. "en" or "vi").
        """
        from pydantic import ValidationError
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.config import config as app_config
        from app.db import Permission, Workspace, WorkspaceMembership
        from app.services.presentation.schemas import (
            GeneratePresentationInput,
            GeneratePresentationOutput,
        )
        from app.services.presentation.service import PresentationStudioService

        def _failed(error: str, *, status: str = "validation_failed") -> dict[str, Any]:
            return GeneratePresentationOutput(
                status=status,
                error=error,
                workspace_id=workspace_id,
            ).model_dump(mode="json")

        if not app_config.PRESENTATION_STUDIO_ENABLED:
            return _failed("Presentation Studio is not enabled on this workspace plan")

        if not prompt or not prompt.strip():
            return _failed("Prompt is required for generate_presentation")

        prompt = prompt.strip()

        if len(prompt) > app_config.PRESENTATION_MAX_PROMPT_CHARS:
            return _failed(
                "Prompt exceeds maximum allowed length of "
                f"{app_config.PRESENTATION_MAX_PROMPT_CHARS} characters."
            )

        normalized_format = (output_format or "pptx").strip().lower()
        if normalized_format not in {"pptx", "marp"}:
            return _failed("output_format must be 'pptx' or 'marp'")

        if user_id is None:
            return _failed(
                "You don't have permission to generate presentations in this workspace"
            )

        session = None
        try:
            async with async_session_maker() as session_:
                session = session_

                # Fail-closed workspace and feature-gate check
                ws = (
                    (
                        await session.execute(
                            select(Workspace).where(Workspace.id == workspace_id)
                        )
                    )
                    .scalars()
                    .first()
                )
                if ws is None or not ws.presentation_studio_enabled:
                    return _failed(
                        "Presentation Studio is not enabled on this workspace plan"
                    )

                membership = (
                    (
                        await session.execute(
                            select(WorkspaceMembership)
                            .where(
                                WorkspaceMembership.user_id == user_id,
                                WorkspaceMembership.workspace_id == workspace_id,
                            )
                            .options(selectinload(WorkspaceMembership.role))
                        )
                    )
                    .scalars()
                    .first()
                )
                if membership is None:
                    return _failed(
                        "You don't have permission to generate presentations in this workspace"
                    )

                permissions = (
                    membership.role.permissions or [] if membership.role else []
                )
                if not (
                    membership.is_owner
                    or Permission.FULL_ACCESS.value in permissions
                    or Permission.WEB_BUILDER_CREATE.value in permissions
                ):
                    return _failed(
                        "You don't have permission to generate presentations in this workspace"
                    )

                service = PresentationStudioService()
                result = await service.generate(
                    session=session,
                    build_input=GeneratePresentationInput(
                        prompt=prompt,
                        output_format=normalized_format,
                        workspace_id=workspace_id,
                        user_id=user_id,
                        language=language,
                    ),
                )
                return result.model_dump(mode="json")
        except ValidationError:
            logger.exception("generate_presentation input failed validation")
            return _failed("Invalid presentation input.")
        except Exception as exc:
            if session is not None:
                with contextlib.suppress(Exception):
                    await session.rollback()
            logger.exception("generate_presentation failed: %s", exc)
            return _failed("Error generating presentation.", status="error")

    return generate_presentation
