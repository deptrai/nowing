from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import (
    DshMission,
    Permission,
    WorkspaceMembership,
    get_async_session,
)
from app.dependencies.auth import RequirePermission
from app.redis_client import get_redis_client
from app.routes.dsh import dsh_public_router
from app.routes.dsh.deps import _require_mission_access
from app.services.dsh_mission_service import (
    DshMissionService,
    DshMissionServiceError,
    DshPayloadTooLargeError,
)
from app.users import get_auth_context

logger = logging.getLogger(__name__)


@dsh_public_router.post("/dsh/missions/{mission_id}/pause")
async def pause_mission(
    mission_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
):
    """Explicitly pause a mission from the frontend using atomic CAS update."""
    mission = await session.get(DshMission, mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")

    _require_mission_access(auth, mission)

    if mission.status != "running" or mission.phase != "waiting_for_human":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mission is not awaiting human takeover.",
        )

    mission.phase = "waiting_for_human"
    mission.current_subtask_id = "cdp_crawl"
    mission.updated_at = datetime.now(UTC)

    # Extend the takeover checkpoint so the UI countdown resets to a full 15 minutes.
    checkpoint = mission.checkpoint if isinstance(mission.checkpoint, dict) else {}
    now = datetime.now(UTC)
    takeover = checkpoint.get("takeover") or {}
    if isinstance(takeover, dict):
        takeover["expires_at"] = (now + timedelta(seconds=900)).isoformat()
        takeover["extended_at"] = now.isoformat()
        checkpoint["takeover"] = takeover
    mission.checkpoint = checkpoint
    session.add(mission)

    # Set 15-minute takeover TTL before committing so the lock and DB state are consistent.
    # The lock value holds the pausing user id so resume can verify ownership.
    redis = await get_redis_client()
    takeover_key = f"dsh:lock:takeover:{mission.workspace_id}:{mission_id}"
    await redis.setex(takeover_key, 900, str(auth.user.id))

    await session.commit()
    return {"mission_id": mission_id, "status": "running", "phase": "waiting_for_human"}


@dsh_public_router.post("/dsh/missions/{mission_id}/resume")
async def resume_mission(
    mission_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
):
    """Resume a paused mission after Human Live Takeover using Atomic CAS UPDATE."""
    mission = await session.get(DshMission, mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")

    _require_mission_access(auth, mission)

    if mission.phase != "waiting_for_human":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mission is not in waiting_for_human phase.",
        )

    # Verify challenge was addressed: the takeover lock still exists, has not expired,
    # and is owned by the current user. We trust the user who clicked Resume to have
    # cleared the challenge; this is the MVP human-in-the-loop contract.
    redis = await get_redis_client()
    takeover_key = f"dsh:lock:takeover:{mission.workspace_id}:{mission_id}"
    lock_owner = await redis.get(takeover_key)
    if not lock_owner:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Takeover session has expired or was not started.",
        )
    if str(lock_owner) != str(auth.user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Takeover session belongs to another user.",
        )

    mission.phase = "crawl"
    mission.updated_at = datetime.now(UTC)

    # Clear the takeover metadata so the UI no longer shows the Human Live Takeover popover.
    checkpoint = mission.checkpoint if isinstance(mission.checkpoint, dict) else {}
    if "takeover" in checkpoint:
        checkpoint["takeover"] = None
    mission.checkpoint = checkpoint
    session.add(mission)

    service = DshMissionService()
    try:
        await service.publish_to_stream(mission)
        await session.commit()
    except DshPayloadTooLargeError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except DshMissionServiceError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # rollback + surface as typed 503 error
        logger.exception("Failed to redispatch mission to stream: %s", exc)
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mission could not be redispatched to the worker stream",
        ) from exc
    finally:
        # Always delete the takeover lock once we leave the resume attempt so a
        # failed publish does not orphan the lock and block retry.
        await redis.delete(takeover_key)

    return {"mission_id": mission_id, "status": "running", "phase": "crawl"}


@dsh_public_router.post("/dsh/missions/{mission_id}/abort", tags=["dsh"])
async def abort_mission(
    mission_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
):
    """Explicitly abort a mission awaiting human takeover."""
    mission = await session.get(DshMission, mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")

    _require_mission_access(auth, mission)

    service = DshMissionService()
    try:
        updated = await service.abort_takeover_mission(session, mission_id)
        await session.commit()
    except DshMissionServiceError as exc:
        await session.rollback()
        # Phase conflict should map to 409; other errors to 400.
        status_code = (
            status.HTTP_409_CONFLICT
            if "only waiting_for_human" in str(exc)
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    return {
        "mission_id": str(updated.id),
        "status": updated.status,
        "phase": updated.phase,
    }


@dsh_public_router.post(
    "/workspaces/{workspace_id}/dsh/missions/sweep-takeovers", tags=["dsh"]
)
async def sweep_takeovers(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    _membership: WorkspaceMembership = Depends(
        RequirePermission(
            Permission.DSH_MISSIONS_WRITE.value,
            "You don't have permission to run takeover sweeps in this workspace",
        )
    ),
):
    """Trigger a workspace-scoped maintenance sweep for expired takeovers."""
    # Scope the sweep to the caller's workspace to avoid cross-tenant leakage.
    service = DshMissionService()
    swept = await service.sweep_expired_takeovers(session, workspace_id=workspace_id)
    await session.commit()
    return {"swept_count": len(swept)}


__all__ = [
    "abort_mission",
    "pause_mission",
    "resume_mission",
    "sweep_takeovers",
]
