"""REST API endpoints for meeting minutes (Story 27.2b)."""

from __future__ import annotations

import io
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.config import config
from app.db import MeetingMinutes, Permission, Workspace, get_async_session
from app.routes.rbac_routes import check_permission
from app.services.meeting_minutes.schemas import GenerateMeetingMinutesInput
from app.services.meeting_minutes.service import MeetingMinutesService
from app.users import get_auth_context

router = APIRouter(prefix="/api/v1/meeting-minutes", tags=["meeting-minutes"])


def check_meeting_minutes_enabled() -> None:
    """Fail-closed gate checking MEETING_MINUTES_ENABLED configuration."""
    if not config.MEETING_MINUTES_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Meeting Minutes is not enabled on this workspace plan",
        )


async def require_workspace_member(
    session: AsyncSession,
    auth: AuthContext,
    workspace_id: int,
) -> None:
    """Ensure the caller is a member and the feature is enabled."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.FULL_ACCESS.value,
        error_message="You don't have access to this workspace",
    )

    ws = (
        (await session.execute(select(Workspace).where(Workspace.id == workspace_id)))
        .scalars()
        .first()
    )
    if ws is None or not config.MEETING_MINUTES_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Meeting Minutes is not enabled on this workspace plan",
        )


@router.get("")
async def list_meeting_minutes(
    workspace_id: Annotated[int, Query()],
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """List meeting minutes for a workspace."""
    check_meeting_minutes_enabled()
    await require_workspace_member(session, auth, workspace_id)

    rows = (
        await session.execute(
            select(MeetingMinutes)
            .where(MeetingMinutes.workspace_id == workspace_id)
            .order_by(MeetingMinutes.id.desc())
        )
    ).scalars().all()

    return [
        {
            "id": row.id,
            "workspace_id": row.workspace_id,
            "status": row.status.value,
            "title": row.title,
            "error": row.error,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        for row in rows
    ]


@router.post("")
async def create_meeting_minutes(
    request: Request,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Create a meeting minutes job from audio_url or document_id."""
    check_meeting_minutes_enabled()

    payload = await request.json()
    try:
        data = GenerateMeetingMinutesInput.model_validate(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid payload: {exc}",
        ) from exc

    await require_workspace_member(session, auth, data.workspace_id)

    service = MeetingMinutesService()
    result = await service.create(
        session,
        workspace_id=data.workspace_id,
        user_id=auth.user.id,
        audio_url=data.audio_url,
        document_id=data.document_id,
        language=data.language,
    )

    if result.status == "validation_failed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result.error or "Validation failed",
        )

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content=result.model_dump(mode="json"),
    )


@router.get("/{meeting_minutes_id}")
async def get_meeting_minutes(
    meeting_minutes_id: int,
    workspace_id: Annotated[int, Query()],
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Get a single meeting minutes record."""
    check_meeting_minutes_enabled()
    await require_workspace_member(session, auth, workspace_id)

    service = MeetingMinutesService()
    try:
        row = await service.get(session, meeting_minutes_id, workspace_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting minutes not found",
        ) from None

    return {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "status": row.status.value,
        "title": row.title,
        "transcript": row.transcript,
        "action_items": row.action_items,
        "summary": row.summary,
        "error": row.error,
        "download_url": f"/api/v1/meeting-minutes/{row.id}/download",
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


@router.delete("/{meeting_minutes_id}")
async def delete_meeting_minutes(
    meeting_minutes_id: int,
    workspace_id: Annotated[int, Query()],
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Delete a meeting minutes record and its transcript."""
    check_meeting_minutes_enabled()
    await require_workspace_member(session, auth, workspace_id)

    service = MeetingMinutesService()
    deleted = await service.delete(session, meeting_minutes_id, workspace_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting minutes not found",
        )

    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content={})


@router.get("/{meeting_minutes_id}/download")
async def download_meeting_minutes(
    meeting_minutes_id: int,
    workspace_id: Annotated[int, Query()],
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Return a JSON download of the meeting minutes."""
    check_meeting_minutes_enabled()
    await require_workspace_member(session, auth, workspace_id)

    service = MeetingMinutesService()
    try:
        row = await service.get(session, meeting_minutes_id, workspace_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting minutes not found",
        ) from None

    payload = {
        "id": row.id,
        "title": row.title,
        "summary": row.summary,
        "action_items": row.action_items,
        "transcript": row.transcript,
        "raw_transcript": row.raw_transcript,
    }
    data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    filename = f"meeting_minutes_{row.id}.json"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
