"""Admin routes for managing In-App Broadcast Announcements (Story 25.6)."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import get_async_session
from app.rate_limiter import get_real_client_ip
from app.schemas.broadcasts import (
    BroadcastCreate,
    BroadcastListResponse,
    BroadcastRead,
    BroadcastUpdate,
)
from app.services.broadcast_service import BroadcastService
from app.users import require_superuser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/broadcasts", tags=["admin"])


def _extract_request_meta(request: Request) -> tuple[str, str | None, str]:
    client_ip = get_real_client_ip(request)
    user_agent = request.headers.get("user-agent")
    endpoint = str(request.url.path)
    return client_ip, user_agent, endpoint


@router.get(
    "",
    response_model=BroadcastListResponse,
    summary="List all broadcast announcements with derived status",
)
async def list_broadcasts(
    auth: Annotated[AuthContext, Depends(require_superuser)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> BroadcastListResponse:
    """Return all broadcasts sorted by creation date."""
    service = BroadcastService(session)
    result = await service.list_broadcasts()
    return BroadcastListResponse(
        items=[BroadcastRead(**item) for item in result["items"]],
        total=result["total"],
    )


@router.post(
    "",
    response_model=BroadcastRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new broadcast announcement",
)
async def create_broadcast(
    request: Request,
    payload: BroadcastCreate,
    auth: Annotated[AuthContext, Depends(require_superuser)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> BroadcastRead:
    """Create a new broadcast announcement with audit logging."""
    service = BroadcastService(session)
    client_ip, user_agent, endpoint = _extract_request_meta(request)

    try:
        announcement = await service.create_broadcast(
            title=payload.title,
            message=payload.message,
            banner_type=payload.banner_type,
            target_all=payload.target_all,
            target_workspace_ids=payload.target_workspace_ids,
            starts_at=payload.starts_at,
            expires_at=payload.expires_at,
            dismissible=payload.dismissible,
            is_active=payload.is_active,
            actor_id=auth.user_id,
            ip_address=client_ip,
            user_agent=user_agent,
            endpoint=endpoint,
        )
        await session.commit()
        status_val = service.compute_status(
            is_active=announcement.is_active,
            starts_at=announcement.starts_at,
            expires_at=announcement.expires_at,
        )
        read_dict = {
            "id": announcement.id,
            "title": announcement.title,
            "message": announcement.message,
            "banner_type": announcement.banner_type,
            "target_all": announcement.target_all,
            "target_workspace_ids": announcement.target_workspace_ids or [],
            "starts_at": announcement.starts_at,
            "expires_at": announcement.expires_at,
            "dismissible": announcement.dismissible,
            "is_active": announcement.is_active,
            "status": status_val,
            "created_by_user_id": announcement.created_by_user_id,
            "updated_by_user_id": announcement.updated_by_user_id,
            "created_at": announcement.created_at,
            "updated_at": announcement.updated_at,
        }
        return BroadcastRead(**read_dict)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.patch(
    "/{broadcast_id}",
    response_model=BroadcastRead,
    summary="Update an existing broadcast announcement",
)
async def update_broadcast(
    request: Request,
    broadcast_id: Annotated[uuid.UUID, Path(description="UUID of broadcast")],
    payload: BroadcastUpdate,
    auth: Annotated[AuthContext, Depends(require_superuser)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> BroadcastRead:
    """Update broadcast parameters and record audit diff."""
    service = BroadcastService(session)
    client_ip, user_agent, endpoint = _extract_request_meta(request)

    update_data = payload.model_dump(exclude_unset=True)
    try:
        updated = await service.update_broadcast(
            broadcast_id=broadcast_id,
            update_data=update_data,
            actor_id=auth.user_id,
            ip_address=client_ip,
            user_agent=user_agent,
            endpoint=endpoint,
        )
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Broadcast not found"
            )
        await session.commit()
        status_val = service.compute_status(
            is_active=updated.is_active,
            starts_at=updated.starts_at,
            expires_at=updated.expires_at,
        )
        read_dict = {
            "id": updated.id,
            "title": updated.title,
            "message": updated.message,
            "banner_type": updated.banner_type,
            "target_all": updated.target_all,
            "target_workspace_ids": updated.target_workspace_ids or [],
            "starts_at": updated.starts_at,
            "expires_at": updated.expires_at,
            "dismissible": updated.dismissible,
            "is_active": updated.is_active,
            "status": status_val,
            "created_by_user_id": updated.created_by_user_id,
            "updated_by_user_id": updated.updated_by_user_id,
            "created_at": updated.created_at,
            "updated_at": updated.updated_at,
        }
        return BroadcastRead(**read_dict)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.delete(
    "/{broadcast_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a broadcast announcement",
)
async def delete_broadcast(
    request: Request,
    broadcast_id: Annotated[uuid.UUID, Path(description="UUID of broadcast")],
    auth: Annotated[AuthContext, Depends(require_superuser)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> None:
    """Delete announcement and write AuditEvent."""
    service = BroadcastService(session)
    client_ip, user_agent, endpoint = _extract_request_meta(request)

    deleted = await service.delete_broadcast(
        broadcast_id=broadcast_id,
        actor_id=auth.user_id,
        ip_address=client_ip,
        user_agent=user_agent,
        endpoint=endpoint,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Broadcast not found"
        )
    await session.commit()
