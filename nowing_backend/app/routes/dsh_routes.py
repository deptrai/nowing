from __future__ import annotations

import hmac
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.config import config
from app.db import Permission, Workspace, get_async_session
from app.schemas.dsh import (
    DshMissionCheckpointUpdate,
    DshMissionInternalResponse,
    DshMissionRequest,
    DshMissionResponse,
)
from app.services.dsh_mission_service import (
    DshMissionService,
    DshMissionServiceError,
    DshPayloadTooLargeError,
)
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

    try:
        mission = await service.update_checkpoint(
            session,
            mission,
            checkpoint=body.checkpoint,
            phase=body.phase,
            progress_percent=body.progress_percent,
            current_subtask_id=body.current_subtask_id,
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

    return DshMissionInternalResponse.model_validate(mission)
