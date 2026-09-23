"""Workspace routes for Telegram userbot monitored channel management (Story 34.2)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import Permission, WorkspaceMembership, get_async_session
from app.dependencies.auth import RequirePermission
from app.services.telegram_channel_service import TelegramChannelService
from app.users import get_auth_context

router = APIRouter(prefix="/workspaces/{workspace_id}/channels/telegram", tags=["telegram"])


class AddTelegramChannelRequest(BaseModel):
    """Request payload to add a Telegram channel for monitoring."""

    target: str = Field(..., min_length=1, max_length=255, description="Channel username (@channel) or URL")
    name: str | None = Field(None, max_length=255)
    category: str = Field(default="leads")
    scrape_interval_minutes: int = Field(default=15, ge=5, le=1440)


@router.get("", status_code=status.HTTP_200_OK)
async def list_telegram_channels(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(Permission.LEADS_READ.value, "Permission denied")
    ),
) -> dict[str, Any]:
    """List monitored Telegram channels and userbot status for a workspace."""
    service = TelegramChannelService(session)
    return await service.list_channels(workspace_id)


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_telegram_channel(
    workspace_id: int,
    body: AddTelegramChannelRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(Permission.LEADS_WRITE.value, "Permission denied")
    ),
) -> dict[str, Any]:
    """Add a new Telegram channel to monitor."""
    service = TelegramChannelService(session)
    result = await service.add_channel(
        workspace_id,
        target=body.target,
        name=body.name,
        category=body.category,
        scrape_interval_minutes=body.scrape_interval_minutes,
    )
    await session.commit()
    return result


@router.patch("/{target_id}/toggle", status_code=status.HTTP_200_OK)
async def toggle_telegram_channel(
    workspace_id: int,
    target_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(Permission.LEADS_WRITE.value, "Permission denied")
    ),
) -> dict[str, Any]:
    """Toggle is_active monitoring state for a channel."""
    service = TelegramChannelService(session)
    try:
        result = await service.toggle_channel(workspace_id, target_id)
        await session.commit()
        return result
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_telegram_channel(
    workspace_id: int,
    target_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(Permission.LEADS_WRITE.value, "Permission denied")
    ),
) -> None:
    """Remove a Telegram channel from monitoring."""
    service = TelegramChannelService(session)
    deleted = await service.delete_channel(workspace_id, target_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found"
        )
    await session.commit()
