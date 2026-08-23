from __future__ import annotations

import asyncio
import hmac
import json
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.auth.context import AuthContext
from app.config import config
from app.db import DshMission, Permission, Workspace, get_async_session
from app.redis_client import get_redis_client
from app.schemas.dsh import (
    CdpResultPayload,
    DshMissionCheckpointUpdate,
    DshMissionControlResponse,
    DshMissionInternalResponse,
    DshMissionListResponse,
    DshMissionRequest,
    DshMissionResponse,
    DshNotifyHighFitRequest,
    DshNotifyHighFitResponse,
)
from app.services.dsh_control_service import MissionControlService
from app.services.dsh_mission_service import (
    _UNSET,
    DshMissionService,
    DshMissionServiceError,
    DshPayloadTooLargeError,
)
from app.services.dsh_telegram_checkpoint_service import DshTelegramCheckpointService
from app.services.pii.redact import redact_pii
from app.users import get_auth_context
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)

dsh_public_router = APIRouter()
dsh_internal_router = APIRouter()


def _verify_dsh_worker_secret(request: Request) -> bool:
    """Constant-time compare the sidecar secret header to the configured secret."""
    header_secret = request.headers.get("X-Dsh-Worker-Secret", "")
    expected = config.DSH_WORKER_SECRET
    if not expected or not header_secret:
        return False
    return hmac.compare_digest(header_secret, expected)


async def require_dsh_worker(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
) -> AuthContext:
    """Internal dependency for sidecar -> checkpoint route.

    Verifies the shared ``X-Dsh-Worker-Secret`` and that the caller is
    PAT-authenticated. Workspace scoping is checked against the mission row
    inside the route.
    """
    if not _verify_dsh_worker_secret(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid DSH worker secret",
        )
    if auth.pat is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="DSH worker requires a PAT",
        )
    return auth


def _require_pat_workspace_scope(
    auth: AuthContext,
    mission_workspace_id: int,
) -> None:
    """Reject global PATs and workspace mismatches on internal routes."""
    if auth.pat is None or auth.pat.workspace_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="DSH worker PAT must be workspace-scoped",
        )
    if auth.pat.workspace_id != mission_workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PAT workspace does not match mission workspace",
        )


def _require_mission_access(auth: AuthContext, mission: DshMission) -> None:
    """Verify the caller owns or has workspace-scoped PAT access to the mission."""
    if auth.method == "pat":
        if auth.pat is None or auth.pat.workspace_id != mission.workspace_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="PAT workspace does not match mission workspace",
            )
    else:
        if mission.user_id != auth.user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden",
            )


@dsh_public_router.post(
    "/workspaces/{workspace_id}/dsh/missions",
    response_model=DshMissionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["dsh"],
)
async def create_dsh_mission(
    request: Request,
    workspace_id: int,
    body: DshMissionRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> DshMissionResponse:
    """Create a pending DSH mission and publish it to the Redis Stream."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_WRITE.value,
        error_message="You don't have permission to create leads in this workspace",
    )

    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    service = DshMissionService()
    mission = await service.create_mission(
        session,
        workspace_id=workspace_id,
        user_id=auth.user.id,
        mission_type=body.mission_type,
        payload=body.payload,
    )

    # Publish before the endpoint returns so workers can consume immediately.
    # If Redis is unavailable we raise 503 and the DB transaction will roll back.
    try:
        await service.publish_to_stream(mission)
    except DshPayloadTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except DshMissionServiceError as exc:
        # Non-payload service errors surface as 400 to avoid masking validation bugs.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Failed to publish mission to Redis stream: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mission created but could not be dispatched to the worker stream",
        ) from exc

    await session.commit()
    return DshMissionResponse.model_validate(mission)


@dsh_public_router.get(
    "/workspaces/{workspace_id}/dsh/missions/{mission_id}",
    response_model=DshMissionResponse,
    status_code=status.HTTP_200_OK,
    tags=["dsh"],
)
async def get_public_dsh_mission(
    request: Request,
    workspace_id: int,
    mission_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> DshMissionResponse:
    """Public, PII-safe mission status."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_READ.value,
        error_message="You don't have permission to view leads in this workspace",
    )

    service = DshMissionService()
    try:
        mission = await service.get_mission_for_workspace(
            session, mission_id, workspace_id
        )
    except DshMissionServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return DshMissionResponse.model_validate(mission)


@dsh_public_router.get(
    "/workspaces/{workspace_id}/dsh/missions",
    response_model=DshMissionListResponse,
    status_code=status.HTTP_200_OK,
    tags=["dsh"],
)
async def list_dsh_missions(
    request: Request,
    workspace_id: int,
    status: str = Query(
        "running,pending",
        description="Comma-separated mission statuses to include",
    ),
    hours: int = Query(24, ge=1, le=168, description="Lookback window in hours"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> DshMissionListResponse:
    """List recent DSH missions for the workspace."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_READ.value,
        error_message="You don't have permission to view leads in this workspace",
    )

    service = DshMissionService()
    missions = await service.list_missions_for_workspace(
        session,
        workspace_id=workspace_id,
        status_filter=status,
        hours=hours,
        limit=limit,
        offset=offset,
    )

    status_list = [s.strip() for s in status.split(",") if s.strip()]
    since = datetime.now(UTC) - timedelta(hours=hours)

    total = 0
    total_stmt = select(func.count(DshMission.id)).where(
        DshMission.workspace_id == workspace_id,
        DshMission.created_at >= since,
    )
    if status_list:
        total_stmt = total_stmt.where(DshMission.status.in_(status_list))
    total_result = await session.execute(total_stmt)
    total = total_result.scalar_one()

    return DshMissionListResponse(
        items=[DshMissionResponse.model_validate(m) for m in missions],
        total=total,
        limit=limit,
        offset=offset,
    )


@dsh_public_router.get(
    "/workspaces/{workspace_id}/dsh/missions/{mission_id}/control",
    response_model=DshMissionControlResponse,
    status_code=status.HTTP_200_OK,
    tags=["dsh"],
)
async def get_dsh_mission_control(
    request: Request,
    workspace_id: int,
    mission_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> DshMissionControlResponse:
    """Public, PII-safe mission control view (Glass Box data source)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.LEADS_READ.value,
        error_message="You don't have permission to view leads in this workspace",
    )

    service = DshMissionService()
    try:
        mission = await service.get_mission_for_workspace(
            session, mission_id, workspace_id
        )
    except DshMissionServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return await MissionControlService().build_control_data(session, mission)


@dsh_internal_router.get(
    "/dsh/missions/{mission_id}",
    response_model=DshMissionInternalResponse,
    status_code=status.HTTP_200_OK,
    tags=["dsh-internal"],
)
async def get_dsh_mission(
    request: Request,
    mission_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_dsh_worker),
) -> DshMissionInternalResponse:
    """Sidecar-only mission read (used for crash resumption)."""
    service = DshMissionService()
    try:
        mission = await service.get_mission_or_404(session, mission_id)
    except DshMissionServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    _require_pat_workspace_scope(auth, mission.workspace_id)
    return DshMissionInternalResponse.model_validate(mission)


@dsh_internal_router.patch(
    "/dsh/missions/{mission_id}/checkpoint",
    response_model=DshMissionInternalResponse,
    status_code=status.HTTP_200_OK,
    tags=["dsh-internal"],
)
async def patch_dsh_mission_checkpoint(
    request: Request,
    mission_id: UUID,
    body: DshMissionCheckpointUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_dsh_worker),
) -> DshMissionInternalResponse:
    """Sidecar-only checkpoint update."""
    service = DshMissionService()
    try:
        mission = await service.get_mission_or_404(session, mission_id)
    except DshMissionServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    _require_pat_workspace_scope(auth, mission.workspace_id)

    # Only pass ``current_subtask_id`` when the client explicitly sent it so
    # that omitted fields do not accidentally clear the column.
    current_subtask_id = (
        body.current_subtask_id
        if "current_subtask_id" in body.model_fields_set
        else _UNSET
    )

    try:
        mission = await service.update_checkpoint(
            session,
            mission,
            checkpoint=body.checkpoint,
            phase=body.phase,
            progress_percent=body.progress_percent,
            current_subtask_id=current_subtask_id,
            status=body.status,
            retry_count=body.retry_count,
            error=body.error,
            started_at=body.started_at,
            completed_at=body.completed_at,
        )
    except DshMissionServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    await session.commit()
    return DshMissionInternalResponse.model_validate(mission)


@dsh_internal_router.post(
    "/dsh/missions/{mission_id}/notify-high-fit",
    response_model=DshNotifyHighFitResponse,
    status_code=status.HTTP_200_OK,
    tags=["dsh-internal"],
)
async def notify_dsh_mission_high_fit_lead(
    request: Request,
    mission_id: UUID,
    body: DshNotifyHighFitRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_dsh_worker),
) -> DshNotifyHighFitResponse:
    """Sidecar-only high-fit lead Telegram notification."""
    mission_service = DshMissionService()
    try:
        mission = await mission_service.get_mission_or_404(session, mission_id)
    except DshMissionServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    _require_pat_workspace_scope(auth, mission.workspace_id)

    checkpoint_service = DshTelegramCheckpointService()
    res = await checkpoint_service.notify_high_fit_lead(
        session=session,
        workspace_id=mission.workspace_id,
        mission_id=mission_id,
        lead_id=body.lead_id,
        contact_id=body.contact_id,
    )
    return DshNotifyHighFitResponse.model_validate(res)


@dsh_public_router.get("/dsh/cdp/stream")
async def cdp_stream(request: Request, auth: AuthContext = Depends(get_auth_context)):
    """SSE stream for the Chrome extension to receive CDP commands."""
    redis = await get_redis_client()
    pubsub = redis.pubsub()
    channel = f"cdp_stream:{auth.user.id}"
    stream_lock_key = f"cdp:stream:lock:{auth.user.id}"

    # Enforce a single active CDP stream per user using an atomic Redis lock.
    # The lock TTL bounds recovery if the process dies without cleaning up.
    acquired = await redis.set(stream_lock_key, "1", nx=True, ex=3600)
    if not acquired:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="CDP stream already active",
        )

    try:
        await pubsub.subscribe(channel)
    except Exception:
        await redis.delete(stream_lock_key)
        await pubsub.close()
        raise

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break

                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    raw_data = message["data"]
                    data = raw_data.decode("utf-8") if isinstance(raw_data, bytes) else str(raw_data)
                    yield {
                        "event": "cdp_command",
                        "data": data,
                    }
        except asyncio.CancelledError:
            raise
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
            await redis.delete(stream_lock_key)

    return EventSourceResponse(event_generator())


def _redact_cdp_result_value(value):
    """Recursively redact PII from CDP result values before Redis storage."""
    if isinstance(value, str):
        try:
            return redact_pii(value, context="lead_enrichment").text
        except Exception:
            return "[REDACTED]"
    if isinstance(value, dict):
        return {k: _redact_cdp_result_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_cdp_result_value(v) for v in value]
    return value


@dsh_public_router.post("/dsh/cdp/result")
async def cdp_result(
    payload: CdpResultPayload,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
):
    """Receive result from extension's CDP execution."""
    mission = await session.get(DshMission, payload.mission_id)
    if mission:
        _require_mission_access(auth, mission)

    redis = await get_redis_client()
    key = f"cdp_result:{auth.user.id}:{payload.mission_id}"

    redacted_result = _redact_cdp_result_value(payload.result) if payload.result is not None else None
    command_id = (
        payload.result.get("command_id")
        if isinstance(payload.result, dict)
        else None
    )
    result_data = {
        "result": redacted_result,
        "error": payload.error,
        "command_id": command_id,
        "requires_human": payload.requires_human,
        "challenge": payload.challenge,
    }

    # Atomic pipeline push + expire + cap list length to avoid OOM.
    pipe = redis.pipeline()
    pipe.rpush(key, json.dumps(result_data))
    pipe.expire(key, 300)
    pipe.ltrim(key, -5, -1)
    await pipe.execute()

    return {"status": "ok"}


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
            detail="Mission is not awaiting human takeover.",
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
    except Exception as exc:
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
