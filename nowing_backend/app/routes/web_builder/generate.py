"""REST API endpoints for Web Builder (Story 27.1 / Story 27.1b / AD-113 / AD-113a / AD-114)."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import (
    StreamingResponse,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import get_async_session
from app.services.web_builder.builder import BuilderService
from app.services.web_builder.generator import WebBuilderService
from app.services.web_builder.schemas import (
    WebAppBuildInput,
    WebAppBuildOutput,
)
from app.users import get_auth_context

from ._helpers import check_web_builder_enabled, require_workspace_member

logger = logging.getLogger(__name__)


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/generate", response_model=WebAppBuildOutput)
async def generate_web_app(
    payload: WebAppBuildInput,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> WebAppBuildOutput:
    """Generate Next.js + Tailwind project from a natural-language description (AC-1)."""
    check_web_builder_enabled()
    await require_workspace_member(session, auth, payload.workspace_id)
    payload.user_id = auth.user.id
    service = WebBuilderService()
    result = await service.generate_project(payload, session=session)
    if result.status == "generated":
        # The async worker handles status, quota debit, and duplicate-guard (R-02).
        await BuilderService.trigger_async_build(result.app_id, payload.workspace_id)
    return result


@router.post("/generate/stream")
async def generate_web_app_stream(
    payload: WebAppBuildInput,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Stream real-time Next.js code generation tokens and file writing steps via SSE."""
    check_web_builder_enabled()
    await require_workspace_member(session, auth, payload.workspace_id)
    payload.user_id = auth.user.id
    service = WebBuilderService()
    return StreamingResponse(
        service.generate_project_stream(payload, session=session),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
