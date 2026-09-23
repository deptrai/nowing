"""Snapshot Endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import (
    get_async_session,
)
from app.schemas.new_chat import (
    PublicChatSnapshotCreateResponse,
    PublicChatSnapshotListResponse,
)
from app.users import get_auth_context

router = APIRouter()

@router.post(
    "/threads/{thread_id}/snapshots", response_model=PublicChatSnapshotCreateResponse
)
async def create_thread_snapshot(
    thread_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Create a public snapshot of the thread.

    Returns existing snapshot URL if content unchanged (deduplication).
    """
    from app.services.public_chat_service import create_snapshot

    return await create_snapshot(
        session=session,
        thread_id=thread_id,
        auth=auth,
    )

@router.get(
    "/threads/{thread_id}/snapshots", response_model=PublicChatSnapshotListResponse
)
async def list_thread_snapshots(
    thread_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    List all public snapshots for this thread.

    Only the thread owner can view snapshots.
    """
    from app.services.public_chat_service import list_snapshots_for_thread

    return PublicChatSnapshotListResponse(
        snapshots=await list_snapshots_for_thread(
            session=session,
            thread_id=thread_id,
            auth=auth,
        )
    )

@router.delete("/threads/{thread_id}/snapshots/{snapshot_id}")
async def delete_thread_snapshot(
    thread_id: int,
    snapshot_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Delete a specific snapshot.

    Only the thread owner can delete snapshots.
    """
    from app.services.public_chat_service import delete_snapshot

    await delete_snapshot(
        session=session,
        thread_id=thread_id,
        snapshot_id=snapshot_id,
        auth=auth,
    )
    return {"message": "Snapshot deleted successfully"}

__all__ = ["router"]
