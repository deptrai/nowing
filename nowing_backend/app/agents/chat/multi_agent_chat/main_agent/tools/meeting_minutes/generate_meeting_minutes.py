"""Main-agent tool for generating meeting minutes (Story 27.2b)."""

from __future__ import annotations

import contextlib
import logging
from typing import Any
from uuid import UUID

from langchain_core.tools import tool

from app.db import async_session_maker
from app.services.meeting_minutes.service import MeetingMinutesService

logger = logging.getLogger(__name__)


def create_generate_meeting_minutes_tool(deps: dict[str, Any]):
    """Factory for the ``generate_meeting_minutes`` chat tool."""

    workspace_id: int = deps["workspace_id"]
    user_id_val = deps.get("user_id")
    user_id: UUID | None = None
    if user_id_val:
        try:
            user_id = user_id_val if isinstance(user_id_val, UUID) else UUID(str(user_id_val))
        except (ValueError, TypeError, AttributeError):
            logger.warning("generate_meeting_minutes: invalid user_id %r", user_id_val)

    @tool
    async def generate_meeting_minutes(
        audio_url: str | None = None,
        document_id: int | None = None,
        language: str | None = None,
    ) -> dict[str, Any]:
        """Generate structured meeting minutes from an audio recording.

        Use this tool when the user wants to summarize a meeting, extract action
        items, or get a transcript with speaker labels.

        Args:
            audio_url: Public or private URL to the audio recording.
            document_id: ID of an already-uploaded audio Document in the workspace.
            language: Optional language code (e.g. "en", "vi").
        """
        from app.config import config as app_config
        from app.services.meeting_minutes.schemas import GenerateMeetingMinutesOutput

        if not app_config.MEETING_MINUTES_ENABLED:
            return GenerateMeetingMinutesOutput(
                status="validation_failed",
                error="Meeting Minutes is not enabled on this workspace plan",
            ).model_dump(mode="json")

        if not audio_url and not document_id:
            return GenerateMeetingMinutesOutput(
                status="validation_failed",
                error="Provide an audio file or URL",
            ).model_dump(mode="json")

        if audio_url and document_id:
            return GenerateMeetingMinutesOutput(
                status="validation_failed",
                error="Provide either an audio URL or a document, not both",
            ).model_dump(mode="json")

        if audio_url and audio_url.strip() == "":
            return GenerateMeetingMinutesOutput(
                status="validation_failed",
                error="Provide an audio file or URL",
            ).model_dump(mode="json")

        if not user_id:
            return GenerateMeetingMinutesOutput(
                status="validation_failed",
                error="You don't have permission to generate meeting minutes in this workspace",
            ).model_dump(mode="json")

        session = None
        try:
            async with async_session_maker() as session_:
                session = session_

                from app.db import NewChatThread

                thread_id = None
                if deps.get("thread_id"):
                    thread_id = deps["thread_id"]

                service = MeetingMinutesService()
                result = await service.create(
                    session,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    audio_url=audio_url,
                    document_id=document_id,
                    thread_id=thread_id,
                    language=language,
                )

                # Metadata: capture original language if provided.
                if thread_id and language:
                    row = await session.get(NewChatThread, thread_id)
                    if row is not None:
                        row.platform_metadata = row.platform_metadata or {}
                        row.platform_metadata["language"] = language
                        await session.commit()

                return result.model_dump(mode="json")
        except Exception as exc:
            if session is not None:
                with contextlib.suppress(Exception):
                    await session.rollback()
            logger.exception("generate_meeting_minutes failed: %s", exc)
            return GenerateMeetingMinutesOutput(
                status="error",
                error=f"Error generating meeting minutes: {exc}",
            ).model_dump(mode="json")

    return generate_meeting_minutes
