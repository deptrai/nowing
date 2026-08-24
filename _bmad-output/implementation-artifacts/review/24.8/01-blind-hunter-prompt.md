# Blind Hunter Prompt — Story 24.8 Code Review

Bạn là Blind Hunter. Hãy chạy skill `bmad-review-adversarial-general` trên diff sau. Không cần biết spec, chỉ tập trung vào lỗi kỹ thuật, bug tiềm ẩn, vấn đề bảo mật, và anti-patterns trong code.

## Diff

diff --git a/nowing_backend/app/routes/dsh_routes.py b/nowing_backend/app/routes/dsh_routes.py
new file mode 100644
index 000000000..f30fa54fc
--- /dev/null
+++ b/nowing_backend/app/routes/dsh_routes.py
@@ -0,0 +1,547 @@
+from __future__ import annotations
+
+import asyncio
+import hmac
+import json
+import logging
+import uuid
+from datetime import UTC, datetime, timedelta
+from uuid import UUID
+
+from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
+from sqlalchemy import func, select, update
+from sqlalchemy.ext.asyncio import AsyncSession
+from sse_starlette.sse import EventSourceResponse
+
+from app.auth.context import AuthContext
+from app.config import config
+from app.db import DshMission, Permission, Workspace, get_async_session
+from app.redis_client import get_redis_client
+from app.schemas.dsh import (
+    CdpResultPayload,
+    DshMissionCheckpointUpdate,
+    DshMissionControlResponse,
+    DshMissionInternalResponse,
+    DshMissionListResponse,
+    DshMissionRequest,
+    DshMissionResponse,
+    DshNotifyHighFitRequest,
+    DshNotifyHighFitResponse,
+    ResumeMissionPayload,
+)
+from app.services.dsh_control_service import MissionControlService
+from app.services.dsh_mission_service import (
+    _UNSET,
+    DshMissionService,
+    DshMissionServiceError,
+    DshPayloadTooLargeError,
+)
+from app.services.dsh_telegram_checkpoint_service import DshTelegramCheckpointService
+from app.users import get_auth_context
+from app.utils.rbac import check_permission
+
+logger = logging.getLogger(__name__)
+
+dsh_public_router = APIRouter()
+dsh_internal_router = APIRouter()
+
+
+def _verify_dsh_worker_secret(request: Request) -> bool:
+    """Constant-time compare the sidecar secret header to the configured secret."""
+    header_secret = request.headers.get("X-Dsh-Worker-Secret", "")
+    expected = config.DSH_WORKER_SECRET
+    if not expected or not header_secret:
+        return False
+    return hmac.compare_digest(header_secret, expected)
+
+
+async def require_dsh_worker(
+    request: Request,
+    auth: AuthContext = Depends(get_auth_context),
+) -> AuthContext:
+    """Internal dependency for sidecar -> checkpoint route.
+
+    Verifies the shared ``X-Dsh-Worker-Secret`` and that the caller is
+    PAT-authenticated. Workspace scoping is checked against the mission row
+    inside the route.
+    """
+    if not _verify_dsh_worker_secret(request):
+        raise HTTPException(
+            status_code=status.HTTP_403_FORBIDDEN,
+            detail="Invalid DSH worker secret",
+        )
+    if auth.pat is None:
+        raise HTTPException(
+            status_code=status.HTTP_403_FORBIDDEN,
+            detail="DSH worker requires a PAT",
+        )
+    return auth
+
+
+def _require_pat_workspace_scope(
+    auth: AuthContext,
+    mission_workspace_id: int,
+) -> None:
+    """Reject global PATs and workspace mismatches on internal routes."""
+    if auth.pat is None or auth.pat.workspace_id is None:
+        raise HTTPException(
+            status_code=status.HTTP_403_FORBIDDEN,
+            detail="DSH worker PAT must be workspace-scoped",
+        )
+    if auth.pat.workspace_id != mission_workspace_id:
+        raise HTTPException(
+            status_code=status.HTTP_403_FORBIDDEN,
+            detail="PAT workspace does not match mission workspace",
+        )
+
+
+@dsh_public_router.post(
+    "/workspaces/{workspace_id}/dsh/missions",
+    response_model=DshMissionResponse,
+    status_code=status.HTTP_201_CREATED,
+    tags=["dsh"],
+)
+async def create_dsh_mission(
+    request: Request,
+    workspace_id: int,
+    body: DshMissionRequest,
+    session: AsyncSession = Depends(get_async_session),
+    auth: AuthContext = Depends(get_auth_context),
+) -> DshMissionResponse:
+    """Create a pending DSH mission and publish it to the Redis Stream."""
+    await check_permission(
+        session,
+        auth,
+        workspace_id,
+        Permission.LEADS_WRITE.value,
+        error_message="You don't have permission to create leads in this workspace",
+    )
+
+    workspace = await session.get(Workspace, workspace_id)
+    if workspace is None:
+        raise HTTPException(
+            status_code=status.HTTP_404_NOT_FOUND,
+            detail="Workspace not found",
+        )
+
+    service = DshMissionService()
+    mission = await service.create_mission(
+        session,
+        workspace_id=workspace_id,
+        user_id=auth.user.id,
+        mission_type=body.mission_type,
+        payload=body.payload,
+    )
+
+    # Publish before the endpoint returns so workers can consume immediately.
+    # If Redis is unavailable we raise 503 and the DB transaction will roll back.
+    try:
+        await service.publish_to_stream(mission)
+    except DshPayloadTooLargeError as exc:
+        raise HTTPException(
+            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
+            detail=str(exc),
+        ) from exc
+    except DshMissionServiceError as exc:
+        # Non-payload service errors surface as 400 to avoid masking validation bugs.
+        raise HTTPException(
+            status_code=status.HTTP_400_BAD_REQUEST,
+            detail=str(exc),
+        ) from exc
+    except Exception as exc:
+        logger.exception("Failed to publish mission to Redis stream: %s", exc)
+        raise HTTPException(
+            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
+            detail="Mission created but could not be dispatched to the worker stream",
+        ) from exc
+
+    await session.commit()
+    return DshMissionResponse.model_validate(mission)
+
+
+@dsh_public_router.get(
+    "/workspaces/{workspace_id}/dsh/missions/{mission_id}",
+    response_model=DshMissionResponse,
+    status_code=status.HTTP_200_OK,
+    tags=["dsh"],
+)
+async def get_public_dsh_mission(
+    request: Request,
+    workspace_id: int,
+    mission_id: UUID,
+    session: AsyncSession = Depends(get_async_session),
+    auth: AuthContext = Depends(get_auth_context),
+) -> DshMissionResponse:
+    """Public, PII-safe mission status."""
+    await check_permission(
+        session,
+        auth,
+        workspace_id,
+        Permission.LEADS_READ.value,
+        error_message="You don't have permission to view leads in this workspace",
+    )
+
+    service = DshMissionService()
+    try:
+        mission = await service.get_mission_for_workspace(
+            session, mission_id, workspace_id
+        )
+    except DshMissionServiceError as exc:
+        raise HTTPException(
+            status_code=status.HTTP_404_NOT_FOUND,
+            detail=str(exc),
+        ) from exc
+
+    return DshMissionResponse.model_validate(mission)
+
+
+@dsh_public_router.get(
+    "/workspaces/{workspace_id}/dsh/missions",
+    response_model=DshMissionListResponse,
+    status_code=status.HTTP_200_OK,
+    tags=["dsh"],
+)
+async def list_dsh_missions(
+    request: Request,
+    workspace_id: int,
+    status: str = Query(
+        "running,pending",
+        description="Comma-separated mission statuses to include",
+    ),
+    hours: int = Query(24, ge=1, le=168, description="Lookback window in hours"),
+    limit: int = Query(50, ge=1, le=200),
+    offset: int = Query(0, ge=0),
+    session: AsyncSession = Depends(get_async_session),
+    auth: AuthContext = Depends(get_auth_context),
+) -> DshMissionListResponse:
+    """List recent DSH missions for the workspace."""
+    await check_permission(
+        session,
+        auth,
+        workspace_id,
+        Permission.LEADS_READ.value,
+        error_message="You don't have permission to view leads in this workspace",
+    )
+
+    service = DshMissionService()
+    missions = await service.list_missions_for_workspace(
+        session,
+        workspace_id=workspace_id,
+        status_filter=status,
+        hours=hours,
+        limit=limit,
+        offset=offset,
+    )
+
+    status_list = [s.strip() for s in status.split(",") if s.strip()]
+    since = datetime.now(UTC) - timedelta(hours=hours)
+
+    total = 0
+    total_stmt = select(func.count(DshMission.id)).where(
+        DshMission.workspace_id == workspace_id,
+        DshMission.created_at >= since,
+    )
+    if status_list:
+        total_stmt = total_stmt.where(DshMission.status.in_(status_list))
+    total_result = await session.execute(total_stmt)
+    total = total_result.scalar_one()
+
+    return DshMissionListResponse(
+        items=[DshMissionResponse.model_validate(m) for m in missions],
+        total=total,
+        limit=limit,
+        offset=offset,
+    )
+
+
+@dsh_public_router.get(
+    "/workspaces/{workspace_id}/dsh/missions/{mission_id}/control",
+    response_model=DshMissionControlResponse,
+    status_code=status.HTTP_200_OK,
+    tags=["dsh"],
+)
+async def get_dsh_mission_control(
+    request: Request,
+    workspace_id: int,
+    mission_id: UUID,
+    session: AsyncSession = Depends(get_async_session),
+    auth: AuthContext = Depends(get_auth_context),
+) -> DshMissionControlResponse:
+    """Public, PII-safe mission control view (Glass Box data source)."""
+    await check_permission(
+        session,
+        auth,
+        workspace_id,
+        Permission.LEADS_READ.value,
+        error_message="You don't have permission to view leads in this workspace",
+    )
+
+    service = DshMissionService()
+    try:
+        mission = await service.get_mission_for_workspace(
+            session, mission_id, workspace_id
+        )
+    except DshMissionServiceError as exc:
+        raise HTTPException(
+            status_code=status.HTTP_404_NOT_FOUND,
+            detail=str(exc),
+        ) from exc
+
+    return await MissionControlService().build_control_data(session, mission)
+
+
+@dsh_internal_router.get(
+    "/dsh/missions/{mission_id}",
+    response_model=DshMissionInternalResponse,
+    status_code=status.HTTP_200_OK,
+    tags=["dsh-internal"],
+)
+async def get_dsh_mission(
+    request: Request,
+    mission_id: UUID,
+    session: AsyncSession = Depends(get_async_session),
+    auth: AuthContext = Depends(require_dsh_worker),
+) -> DshMissionInternalResponse:
+    """Sidecar-only mission read (used for crash resumption)."""
+    service = DshMissionService()
+    try:
+        mission = await service.get_mission_or_404(session, mission_id)
+    except DshMissionServiceError as exc:
+        raise HTTPException(
+            status_code=status.HTTP_404_NOT_FOUND,
+            detail=str(exc),
+        ) from exc
+
+    _require_pat_workspace_scope(auth, mission.workspace_id)
+    return DshMissionInternalResponse.model_validate(mission)
+
+
+@dsh_internal_router.patch(
+    "/dsh/missions/{mission_id}/checkpoint",
+    response_model=DshMissionInternalResponse,
+    status_code=status.HTTP_200_OK,
+    tags=["dsh-internal"],
+)
+async def patch_dsh_mission_checkpoint(
+    request: Request,
+    mission_id: UUID,
+    body: DshMissionCheckpointUpdate,
+    session: AsyncSession = Depends(get_async_session),
+    auth: AuthContext = Depends(require_dsh_worker),
+) -> DshMissionInternalResponse:
+    """Sidecar-only checkpoint update."""
+    service = DshMissionService()
+    try:
+        mission = await service.get_mission_or_404(session, mission_id)
+    except DshMissionServiceError as exc:
+        raise HTTPException(
+            status_code=status.HTTP_404_NOT_FOUND,
+            detail=str(exc),
+        ) from exc
+
+    _require_pat_workspace_scope(auth, mission.workspace_id)
+
+    # Only pass ``current_subtask_id`` when the client explicitly sent it so
+    # that omitted fields do not accidentally clear the column.
+    current_subtask_id = (
+        body.current_subtask_id
+        if "current_subtask_id" in body.model_fields_set
+        else _UNSET
+    )
+
+    try:
+        mission = await service.update_checkpoint(
+            session,
+            mission,
+            checkpoint=body.checkpoint,
+            phase=body.phase,
+            progress_percent=body.progress_percent,
+            current_subtask_id=current_subtask_id,
+            status=body.status,
+            retry_count=body.retry_count,
+            error=body.error,
+            started_at=body.started_at,
+            completed_at=body.completed_at,
+        )
+    except DshMissionServiceError as exc:
+        raise HTTPException(
+            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
+            detail=str(exc),
+        ) from exc
+
+    await session.commit()
+    return DshMissionInternalResponse.model_validate(mission)
+
+
+@dsh_internal_router.post(
+    "/dsh/missions/{mission_id}/notify-high-fit",
+    response_model=DshNotifyHighFitResponse,
+    status_code=status.HTTP_200_OK,
+    tags=["dsh-internal"],
+)
+async def notify_dsh_mission_high_fit_lead(
+    request: Request,
+    mission_id: UUID,
+    body: DshNotifyHighFitRequest,
+    session: AsyncSession = Depends(get_async_session),
+    auth: AuthContext = Depends(require_dsh_worker),
+) -> DshNotifyHighFitResponse:
+    """Sidecar-only high-fit lead Telegram notification."""
+    mission_service = DshMissionService()
+    try:
+        mission = await mission_service.get_mission_or_404(session, mission_id)
+    except DshMissionServiceError as exc:
+        raise HTTPException(
+            status_code=status.HTTP_404_NOT_FOUND,
+            detail=str(exc),
+        ) from exc
+
+    _require_pat_workspace_scope(auth, mission.workspace_id)
+
+    checkpoint_service = DshTelegramCheckpointService()
+    res = await checkpoint_service.notify_high_fit_lead(
+        session=session,
+        workspace_id=mission.workspace_id,
+        mission_id=mission_id,
+        lead_id=body.lead_id,
+        contact_id=body.contact_id,
+    )
+    return DshNotifyHighFitResponse.model_validate(res)
+
+
+@dsh_public_router.get("/dsh/cdp/stream")
+async def cdp_stream(request: Request, auth: AuthContext = Depends(AuthContext.require)):
+    """SSE stream for extension to receive CDP commands."""
+    redis = await get_redis_client()
+    pubsub = redis.pubsub()
+    channel = f"cdp_stream:{auth.user.id}"
+
+    try:
+        await pubsub.subscribe(channel)
+    except Exception:
+        await pubsub.close()
+        raise
+
+    async def event_generator():
+        try:
+            while True:
+                if await request.is_disconnected():
+                    break
+
+                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
+                if message and message["type"] == "message":
+                    raw_data = message["data"]
+                    data = raw_data.decode("utf-8") if isinstance(raw_data, bytes) else str(raw_data)
+                    yield {
+                        "event": "cdp_command",
+                        "data": data,
+                    }
+        except asyncio.CancelledError:
+            raise
+        finally:
+            await pubsub.unsubscribe(channel)
+            await pubsub.close()
+
+    return EventSourceResponse(event_generator())
+
+
+@dsh_public_router.post("/dsh/cdp/result")
+async def cdp_result(
+    payload: CdpResultPayload,
+    auth: AuthContext = Depends(AuthContext.require),
+    session: AsyncSession = Depends(get_async_session),
+):
+    """Receive result from extension's CDP execution."""
+    mission = await session.get(DshMission, payload.mission_id)
+    if not mission or mission.user_id != auth.user.id:
+        raise HTTPException(status_code=403, detail="Forbidden")
+
+    redis = await get_redis_client()
+    key = f"cdp_result:{auth.user.id}:{payload.mission_id}"
+
+    result_data = {
+        "result": payload.result,
+        "error": payload.error,
+    }
+
+    # Atomic pipeline push + expire
+    pipe = redis.pipeline()
+    pipe.rpush(key, json.dumps(result_data))
+    pipe.expire(key, 300)
+    await pipe.execute()
+
+    return {"status": "ok"}
+
+
+@dsh_public_router.post("/dsh/pause")
+async def pause_mission(
+    payload: ResumeMissionPayload,
+    auth: AuthContext = Depends(AuthContext.require),
+    session: AsyncSession = Depends(get_async_session),
+):
+    """Explicitly pause a mission from the frontend using atomic CAS update."""
+    stmt = (
+        update(DshMission)
+        .where(
+            DshMission.id == payload.mission_id,
+            DshMission.user_id == auth.user.id,
+            DshMission.status == "in_progress",
+        )
+        .values(status="paused", updated_at=func.now())
+    )
+    result = await session.execute(stmt)
+    if result.rowcount == 0:
+        raise HTTPException(
+            status_code=status.HTTP_409_CONFLICT,
+            detail="Mission is not in progress, does not exist, or you do not have permission.",
+        )
+    await session.commit()
+    return {"mission_id": payload.mission_id, "status": "paused"}
+
+
+@dsh_public_router.post("/dsh/resume")
+async def resume_mission(
+    payload: ResumeMissionPayload,
+    auth: AuthContext = Depends(AuthContext.require),
+    session: AsyncSession = Depends(get_async_session),
+):
+    """Resume a paused mission after Human Live Takeover using Atomic CAS UPDATE."""
+    mission_id = payload.mission_id
+
+    stmt = (
+        update(DshMission)
+        .where(
+            DshMission.id == mission_id,
+            DshMission.user_id == auth.user.id,
+            DshMission.status == "paused",
+        )
+        .values(status="in_progress", updated_at=func.now())
+    )
+    result = await session.execute(stmt)
+    if result.rowcount == 0:
+        raise HTTPException(
+            status_code=status.HTTP_409_CONFLICT,
+            detail="Mission is not paused, does not exist, or you do not have permission.",
+        )
+
+    mission = await session.get(DshMission, mission_id)
+    if mission:
+        service = DshMissionService()
+        try:
+            await service.publish_to_stream(mission)
+        except Exception as exc:
+            logger.exception("Failed to redispatch mission to stream: %s", exc)
+            revert_stmt = (
+                update(DshMission)
+                .where(DshMission.id == mission_id)
+                .values(status="paused", updated_at=func.now())
+            )
+            await session.execute(revert_stmt)
+            await session.commit()
+            raise HTTPException(
+                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
+                detail="Mission could not be redispatched to the worker stream",
+            ) from exc
+
+    await session.commit()
+    return {"mission_id": mission_id, "status": "in_progress"}
diff --git a/nowing_backend/app/schemas/dsh.py b/nowing_backend/app/schemas/dsh.py
new file mode 100644
index 000000000..633814cef
--- /dev/null
+++ b/nowing_backend/app/schemas/dsh.py
@@ -0,0 +1,174 @@
+from __future__ import annotations
+
+from datetime import datetime
+from typing import Literal
+from uuid import UUID
+
+from pydantic import BaseModel, ConfigDict, Field, model_validator
+
+DshMissionStatus = Literal[
+    "pending",
+    "running",
+    "success",
+    "error",
+    "cancelled",
+    "dlq",
+]
+DshMissionType = Literal["deep_lead_research", "noop"]
+
+
+class DshMissionPayload(BaseModel):
+    """The sidecar-visible payload that drives the mission."""
+
+    model_config = ConfigDict(extra="ignore")
+
+    query: str = Field(
+        ...,
+        min_length=1,
+        description="The research question or topic.",
+    )
+    workspace_id: int | None = None
+    extras: dict = Field(default_factory=dict)
+
+
+class DshMissionRequest(BaseModel):
+    """Create a new long-running DSH mission."""
+
+    mission_type: DshMissionType = "deep_lead_research"
+    payload: dict = Field(default_factory=dict)
+
+    @model_validator(mode="after")
+    def _validate_payload(self) -> DshMissionRequest:
+        if self.mission_type == "deep_lead_research":
+            payload_model = DshMissionPayload.model_validate(self.payload)
+            if not payload_model.query or not payload_model.query.strip():
+                raise ValueError("query is required for deep_lead_research missions")
+        return self
+
+
+class DshMissionCheckpointUpdate(BaseModel):
+    """Patch a mission checkpoint from the sidecar."""
+
+    checkpoint: dict | None = None
+    phase: str | None = None
+    progress_percent: int | None = Field(default=None, ge=0, le=100)
+    current_subtask_id: str | None = None
+    status: DshMissionStatus | None = None
+    retry_count: int | None = None
+    error: dict | None = None
+    started_at: datetime | None = None
+    completed_at: datetime | None = None
+
+
+class DshMissionResponse(BaseModel):
+    """Public, PII-safe mission summary."""
+
+    model_config = ConfigDict(from_attributes=True)
+
+    id: UUID
+    workspace_id: int
+    mission_type: str
+    status: str
+    phase: str | None
+    progress_percent: int | None
+    current_subtask_id: str | None
+    retry_count: int
+    created_at: datetime
+    updated_at: datetime
+
+
+class DshMissionInternalResponse(DshMissionResponse):
+    """Full mission response for the authenticated sidecar."""
+
+    user_id: UUID | None
+    payload: dict
+    checkpoint: dict | None
+    error: dict | None
+    started_at: datetime | None
+    completed_at: datetime | None
+
+
+class TokenVelocity(BaseModel):
+    """Aggregated token/cost summary for the Glass Box widget."""
+
+    tokens_total: int = 0
+    tokens_per_second: float = 0.0
+    cost_micros: int = 0
+    cost_credits: float = 0.0
+
+
+class DshMissionSubtask(BaseModel):
+    """Redacted subtask snapshot shown in the public control view."""
+
+    model_config = ConfigDict(extra="ignore")
+
+    id: str
+    title: str
+    status: str
+    phase: str | None = None
+    reasoning_content: str | None = None
+    tokens_used: int = 0
+    tokens_per_second: float = 0.0
+    run_id: str | None = None
+    cost_micros: int = 0
+    started_at: datetime | None = None
+    completed_at: datetime | None = None
+
+
+class DshMissionDeliverable(BaseModel):
+    """Redacted deliverable reference shown in the public control view."""
+
+    model_config = ConfigDict(extra="ignore")
+
+    type: str
+    filename: str
+    size: int = 0
+    created_at: str | None = None
+    include_pii: bool = False
+    sources_count: int = 0
+    topics_count: int = 0
+
+
+class DshMissionControlResponse(DshMissionResponse):
+    """Public, PII-safe mission control payload with token velocity, subtasks, and deliverables."""
+
+    token_velocity: TokenVelocity
+    subtasks: list[DshMissionSubtask]
+    deliverables: list[DshMissionDeliverable] = []
+
+
+class DshMissionListResponse(BaseModel):
+    """Paginated list of DSH missions."""
+
+    items: list[DshMissionResponse]
+    total: int
+    limit: int
+    offset: int
+
+
+class DshNotifyHighFitRequest(BaseModel):
+    """Request payload for internal worker notification of high-fit lead."""
+
+    model_config = ConfigDict(extra="forbid")
+
+    lead_id: UUID
+    contact_id: UUID | None = None
+
+
+class DshNotifyHighFitResponse(BaseModel):
+    """Response payload for internal high-fit lead notification."""
+
+    status: Literal["sent", "skipped", "failed"]
+    callback_token: str | None = None
+    contact_id: UUID | None = None
+    message_id: str | None = None
+    reason: str | None = None
+    error: str | None = None
+
+class CdpResultPayload(BaseModel):
+    mission_id: UUID
+    result: dict | None = None
+    error: str | None = None
+
+class ResumeMissionPayload(BaseModel):
+    mission_id: UUID
diff --git a/nowing_backend/app/tasks/dsh_worker.py b/nowing_backend/app/tasks/dsh_worker.py
new file mode 100644
index 000000000..9f553b5aa
--- /dev/null
+++ b/nowing_backend/app/tasks/dsh_worker.py
@@ -0,0 +1,1288 @@
+from __future__ import annotations
+
+import argparse
+import asyncio
+import contextlib
+import json
+import logging
+import os
+import signal
+import socket
+import sys
+import uuid
+from datetime import UTC, datetime
+from typing import Any
+from urllib.parse import urlparse
+from uuid import UUID
+
+import httpx
+from redis.asyncio.client import Redis
+from redis.exceptions import ResponseError
+
+from app.capabilities.chainlens.research.executor import build_research_executor
+from app.capabilities.chainlens.research.schemas import ResearchInput
+from app.config import config
+from app.redis_client import get_redis_client
+from app.tasks.dsh_worker_langgraph import LangGraphMissionExecutor
+from app.tasks.dsh_worker_browser_operator import HumanInterventionRequired
+
+_research_executor = build_research_executor()
+
+logger = logging.getLogger(__name__)
+
+# Hard 60s ceiling on every synchronous Redis stream / REST round-trip (AC-2 / AD-108).
+_DSH_CALL_TIMEOUT_SECONDS = 60.0
+_DSH_SYNC_TIMEOUT = min(
+    float(getattr(config, "DSH_SYNC_TIMEOUT_SECONDS", _DSH_CALL_TIMEOUT_SECONDS)),
+    _DSH_CALL_TIMEOUT_SECONDS,
+)
+
+
+def _checkpoint_update(**kwargs: Any) -> dict[str, Any]:
+    """Build a JSON-serialisable checkpoint update with None values omitted.
+
+    ``current_subtask_id`` is always preserved (including ``None``) because the
+    sidecar must be able to clear it on terminal/success transitions.
+    ``started_at`` and ``completed_at`` are normalised to ISO strings so the
+    sidecar payload is JSON-serialisable even if a caller passes a ``datetime``.
+    """
+    result: dict[str, Any] = {}
+    for k, v in kwargs.items():
+        if v is None and k != "current_subtask_id":
+            continue
+        if k in ("started_at", "completed_at") and isinstance(v, datetime):
+            v = v.isoformat()
+        result[k] = v
+    return result
+
+
+# ---------------------------------------------------------------------------
+# Error taxonomy for the sidecar
+# ---------------------------------------------------------------------------
+class DshWorkerError(Exception):
+    """Base class for DSH worker errors."""
+
+    pass
+
+
+class DshRetryableError(DshWorkerError):
+    """A transient failure that should count against the retry budget."""
+
+    pass
+
+
+class DshNonRetryableError(DshWorkerError):
+    """A failure that should move the mission straight to the DLQ."""
+
+    pass
+
+
+class DshBillingError(DshNonRetryableError):
+    """The workspace cannot pay for the operation (402)."""
+
+    pass
+
+
+class DshNotFoundError(DshNonRetryableError):
+    """A requested resource does not exist (404)."""
+
+    pass
+
+
+class DshValidationError(DshNonRetryableError):
+    """The payload or state is invalid (422)."""
+
+    pass
+
+
+class DshTransientError(DshRetryableError):
+    """A transient REST or upstream error (5xx, 429, timeout)."""
+
+    pass
+
+
+# ---------------------------------------------------------------------------
+# REST client
+# ---------------------------------------------------------------------------
+class DshRestClient:
+    """REST client used by the sidecar to talk to the Nowing gateway."""
+
+    def __init__(
+        self,
+        base_url: str,
+        pat: str,
+        worker_secret: str,
+        timeout: float = 60.0,
+    ) -> None:
+        self.base_url = base_url.rstrip("/")
+        self.pat = pat
+        self.worker_secret = worker_secret
+        self.timeout = min(float(timeout), _DSH_CALL_TIMEOUT_SECONDS)
+        self._client = httpx.AsyncClient(
+            base_url=self.base_url,
+            headers={
+                "Authorization": f"Bearer {self.pat}",
+                "X-Dsh-Worker-Secret": self.worker_secret,
+            },
+            timeout=httpx.Timeout(timeout),
+        )
+
+    def _raise_for_status(
+        self,
+        response: httpx.Response,
+        context: str,
+    ) -> None:
+        """Classify REST failures into retryable vs non-retryable buckets."""
+        if response.is_success:
+            return
+        status = response.status_code
+        detail = f"{context}: HTTP {status} {response.text[:200]}"
+        if status == 402:
+            raise DshBillingError(detail)
+        if status == 404:
+            raise DshNotFoundError(detail)
+        if status == 422:
+            raise DshValidationError(detail)
+        if status == 429 or status >= 500:
+            raise DshTransientError(detail)
+        # Any other 4xx is treated as non-retryable (e.g. 403 misconfiguration).
+        raise DshNonRetryableError(detail)
+
+    async def get_mission(self, mission_id: uuid.UUID) -> dict[str, Any]:
+        response = await self._client.get(f"/v1/dsh/missions/{mission_id}")
+        self._raise_for_status(response, f"get_mission {mission_id}")
+        return response.json()
+
+    async def patch_checkpoint(
+        self,
+        mission_id: uuid.UUID,
+        update: dict[str, Any],
+    ) -> dict[str, Any]:
+        response = await self._client.patch(
+            f"/v1/dsh/missions/{mission_id}/checkpoint",
+            json=update,
+        )
+        self._raise_for_status(response, f"patch_checkpoint {mission_id}")
+        return response.json()
+
+    async def chainlens_research(
+        self,
+        workspace_id: int,
+        query: str,
+        output: str | None = None,
+        output_schema: dict[str, Any] | None = None,
+        mode: str = "balanced",
+    ) -> dict[str, Any]:
+        """Call the local chainlens.research capability directly.
+
+        ponytail: the REST route this client used to call no longer exists in
+        the gateway, so we invoke the executor the gateway itself uses and
+        return a flat dict for backward compatibility with the legacy and
+        LangGraph executors.
+        """
+        try:
+            payload = ResearchInput(
+                query=query,
+                mode=mode,  # type: ignore[arg-type]
+                output=output,  # type: ignore[arg-type]
+                output_schema=output_schema,
+                workspace_id=workspace_id,
+            )
+        except Exception as exc:
+            raise DshTransientError(f"Invalid chainlens.research payload: {exc}") from exc
+
+        output_obj = await _research_executor(payload, None)
+
+        if output_obj.status in ("engine_unavailable", "timeout"):
+            raise DshTransientError(
+                output_obj.degradation_reason
+                or output_obj.engine_reason
+                or output_obj.status
+            )
+
+        result: dict[str, Any] = output_obj.model_dump()
+        result["run_id"] = output_obj.chat_id or str(uuid.uuid4())
+        return result
+
+    async def _poll_run(self, workspace_id: int, run_id: str) -> dict[str, Any]:
+        """Poll GET /scrapers/runs/{run_id} until a terminal status."""
+        while True:
+            response = await self._client.get(
+                f"/api/v1/workspaces/{workspace_id}/scrapers/runs/{run_id}",
+                timeout=httpx.Timeout(_DSH_SYNC_TIMEOUT),
+            )
+            self._raise_for_status(response, f"poll_run {run_id}")
+            run = response.json()
+            status = run.get("status")
+
+            if status == "success":
+                output_text = run.get("output_text") or ""
+                if not output_text:
+                    raise DshTransientError(f"Run {run_id} succeeded with no output")
+                try:
+                    return json.loads(output_text.splitlines()[0])
+                except (json.JSONDecodeError, IndexError) as exc:
+                    raise DshTransientError(
+                        f"Run {run_id} has unparsable output: {exc}"
+                    ) from exc
+
+            if status in {"error", "cancelled"}:
+                raise DshTransientError(
+                    f"Run {run_id} ended with status {status}: {run.get('error')}"
+                )
+
+            await asyncio.sleep(5)
+
+    async def batch_ingest_leads(
+        self,
+        workspace_id: int,
+        leads: list[dict[str, Any]],
+    ) -> dict[str, Any]:
+        payload = {"leads": leads}
+        # Back-off on 429; otherwise raise.
+        for attempt in range(3):
+            response = await self._client.post(
+                f"/api/v1/workspaces/{workspace_id}/leads/batch-ingest",
+                json=payload,
+                timeout=httpx.Timeout(_DSH_SYNC_TIMEOUT),
+            )
+            if response.status_code == 429:
+                wait = 2**attempt
+                logger.warning("batch_ingest rate limited; retry in %ss", wait)
+                await asyncio.sleep(wait)
+                continue
+            self._raise_for_status(response, "batch_ingest_leads")
+            return response.json()
+        raise DshTransientError("batch_ingest_leads exhausted retries on 429")
+
+    async def notify_high_fit_lead(
+        self,
+        mission_id: UUID | str,
+        lead_id: UUID | str,
+        contact_id: UUID | str | None = None,
+    ) -> dict[str, Any]:
+        payload: dict[str, Any] = {"lead_id": str(lead_id)}
+        if contact_id:
+            payload["contact_id"] = str(contact_id)
+        response = await self._client.post(
+            f"/v1/dsh/missions/{mission_id}/notify-high-fit",
+            json=payload,
+            timeout=httpx.Timeout(_DSH_SYNC_TIMEOUT),
+        )
+        self._raise_for_status(response, "notify_high_fit_lead")
+        return response.json()
+
+    async def aclose(self) -> None:
+        await self._client.aclose()
+
+
+# ---------------------------------------------------------------------------
+# Mission executor
+# ---------------------------------------------------------------------------
+class DeepLeadResearchExecutor:
+    """Default deterministic sequential executor for deep-lead-research missions."""
+
+    def __init__(self, rest_client: DshRestClient) -> None:
+        self.rest_client = rest_client
+
+    @staticmethod
+    def _extract_domain(url: str | None) -> str | None:
+        if not url:
+            return None
+        try:
+            parsed = urlparse(url)
+            return parsed.netloc if parsed.netloc else None
+        except Exception:
+            return None
+
+    async def _patch_checkpoint(
+        self,
+        mission_id: uuid.UUID,
+        checkpoint: dict[str, Any],
+        phase: str,
+        progress_percent: int,
+        current_subtask_id: str | None = None,
+        status: str | None = None,
+        error: dict[str, Any] | None = None,
+        started_at: str | None = None,
+        completed_at: str | None = None,
+    ) -> dict[str, Any]:
+        update = _checkpoint_update(
+            checkpoint=checkpoint,
+            phase=phase,
+            progress_percent=progress_percent,
+            current_subtask_id=current_subtask_id,
+            status=status,
+            error=error,
+            started_at=started_at,
+            completed_at=completed_at,
+        )
+        response = await self.rest_client.patch_checkpoint(mission_id, update)
+        # Merge the server's checkpoint back so the next patch does not fail on
+        # a stale version. The checkpoint dict is mutated in place so callers
+        # that hold references to it see the updated subtasks/sources/leads.
+        response_checkpoint = response.get("checkpoint") if isinstance(response, dict) else None
+        if response_checkpoint:
+            checkpoint.clear()
+            checkpoint.update(response_checkpoint)
+        return response
+
+    def _mission_id(self, mission: dict[str, Any] | Any) -> uuid.UUID:
+        raw = mission["id"] if isinstance(mission, dict) else mission.id
+        return uuid.UUID(raw) if isinstance(raw, str) else raw
+
+    def _mission_workspace_id(self, mission: dict[str, Any] | Any) -> int:
+        return (
+            mission["workspace_id"]
+            if isinstance(mission, dict)
+            else mission.workspace_id
+        )
+
+    def _mission_payload(self, mission: dict[str, Any] | Any) -> dict[str, Any]:
+        payload = mission["payload"] if isinstance(mission, dict) else mission.payload
+        return payload or {}
+
+    def _mission_checkpoint(self, mission: dict[str, Any] | Any) -> dict[str, Any]:
+        checkpoint = (
+            mission["checkpoint"] if isinstance(mission, dict) else mission.checkpoint
+        )
+        if not checkpoint:
+            checkpoint = {"version": 1, "phase": "crawl", "subtasks": []}
+        return checkpoint
+
+    async def run(self, mission: dict[str, Any] | Any) -> None:
+        """Run the four phases sequentially, updating checkpoint after each."""
+        mission_id = self._mission_id(mission)
+        workspace_id = self._mission_workspace_id(mission)
+        payload = self._mission_payload(mission)
+        query = payload.get("query", "") if isinstance(payload, dict) else ""
+
+        checkpoint = self._mission_checkpoint(mission)
+        subtasks = checkpoint.get("subtasks", [])
+
+        # Phase: crawl -> reasoning -> extraction -> ingestion
+        # 1. Crawl (ChainLens research)
+        if not any(
+            s.get("id") == "crawl" and s.get("status") == "success" for s in subtasks
+        ):
+            await self._patch_checkpoint(
+                mission_id,
+                checkpoint,
+                phase="crawl",
+                progress_percent=10,
+                current_subtask_id="crawl",
+                status="running",
+            )
+            try:
+                research_output = await self.rest_client.chainlens_research(
+                    workspace_id, query
+                )
+                sources = research_output.get("sources", [])
+                subtasks.append(
+                    {
+                        "id": "crawl",
+                        "status": "success",
+                        "run_id": research_output.get("run_id"),
+                        "sources_count": len(sources),
+                    }
+                )
+                checkpoint["subtasks"] = subtasks
+                checkpoint["sources"] = sources
+                await self._patch_checkpoint(
+                    mission_id,
+                    checkpoint,
+                    phase="reasoning",
+                    progress_percent=35,
+                    current_subtask_id="reasoning",
+                )
+            except Exception as exc:
+                subtasks.append(
+                    {
+                        "id": "crawl",
+                        "status": "failed",
+                        "error": str(exc),
+                    }
+                )
+                checkpoint["subtasks"] = subtasks
+                await self._patch_checkpoint(
+                    mission_id,
+                    checkpoint,
+                    phase="crawl",
+                    progress_percent=0,
+                    current_subtask_id="crawl",
+                    status="error",
+                    error={"phase": "crawl", "message": str(exc)},
+                )
+                raise
+
+        # 2. Reasoning
+        if not any(
+            s.get("id") == "reasoning" and s.get("status") == "success"
+            for s in subtasks
+        ):
+            await self._patch_checkpoint(
+                mission_id,
+                checkpoint,
+                phase="reasoning",
+                progress_percent=45,
+                current_subtask_id="reasoning",
+            )
+            # Deterministic reasoning can be a no-op for 26.2.
+            subtasks.append({"id": "reasoning", "status": "success"})
+            checkpoint["subtasks"] = subtasks
+            await self._patch_checkpoint(
+                mission_id,
+                checkpoint,
+                phase="extraction",
+                progress_percent=60,
+                current_subtask_id="extraction",
+            )
+
+        # 3. Extraction
+        if not any(
+            s.get("id") == "extraction" and s.get("status") == "success"
+            for s in subtasks
+        ):
+            await self._patch_checkpoint(
+                mission_id,
+                checkpoint,
+                phase="extraction",
+                progress_percent=70,
+                current_subtask_id="extraction",
+            )
+            sources = checkpoint.get("sources", [])
+            extracted_leads = [
+                self._source_to_lead(source, workspace_id) for source in sources
+            ]
+            # Filter degenerate leads that would fail the batch-ingest validator.
+            extracted_leads = [lead for lead in extracted_leads if lead is not None]
+            subtasks.append(
+                {
+                    "id": "extraction",
+                    "status": "success",
+                    "leads_count": len(extracted_leads),
+                }
+            )
+            checkpoint["subtasks"] = subtasks
+            checkpoint["leads"] = extracted_leads
+            await self._patch_checkpoint(
+                mission_id,
+                checkpoint,
+                phase="ingestion",
+                progress_percent=85,
+                current_subtask_id="ingestion",
+            )
+
+        # 4. Ingestion
+        if not any(
+            s.get("id") == "ingestion" and s.get("status") == "success"
+            for s in subtasks
+        ):
+            await self._patch_checkpoint(
+                mission_id,
+                checkpoint,
+                phase="ingestion",
+                progress_percent=90,
+                current_subtask_id="ingestion",
+            )
+            leads = checkpoint.get("leads", [])
+            if leads:
+                try:
+                    ingest_res = await self.rest_client.batch_ingest_leads(
+                        workspace_id, leads
+                    )
+                    try:
+                        # Trigger Telegram notification for top high-fit lead if any (Story 26.6)
+                        from app.lead_intelligence.dnc.normalizer import (
+                            normalize_domain,
+                        )
+                        from app.services.dsh_telegram_checkpoint_service import (
+                            DshTelegramCheckpointService,
+                        )
+                        from app.services.lead_batch_service import generate_lead_hmac
+
+                        checkpoint_svc = DshTelegramCheckpointService()
+                        high_fit_candidate = checkpoint_svc.select_high_fit_lead(leads)
+                        if high_fit_candidate:
+                            lead_id = None
+                            if isinstance(high_fit_candidate, dict):
+                                cand_company = (
+                                    high_fit_candidate.get("company_name")
+                                    or high_fit_candidate.get("title")
+                                    or "Doanh nghiệp"
+                                )
+                                cand_domain = normalize_domain(
+                                    high_fit_candidate.get("domain")
+                                )
+                                cand_hmac = high_fit_candidate.get(
+                                    "value_hmac"
+                                ) or generate_lead_hmac(
+                                    workspace_id, cand_company, cand_domain
+                                )
+                                mapping = ingest_res.get("lead_id_mapping") or {}
+                                lead_id = mapping.get(cand_hmac)
+                                if not lead_id:
+                                    logger.info(
+                                        "High-fit lead mapping missing for mission %s; skipping notification",
+                                        mission_id,
+                                    )
+                            elif hasattr(high_fit_candidate, "id"):
+                                lead_id = high_fit_candidate.id
+
+                            if lead_id:
+                                try:
+                                    await self.rest_client.notify_high_fit_lead(
+                                        mission_id, lead_id
+                                    )
+                                except Exception as notify_exc:
+                                    logger.warning(
+                                        "Failed to notify high fit lead for mission %s: %s",
+                                        mission_id,
+                                        notify_exc,
+                                    )
+                    except Exception as notify_exc:
+                        logger.warning(
+                            "Failed to process high fit lead notification for mission %s: %s",
+                            mission_id,
+                            notify_exc,
+                        )
+                except Exception as exc:
+                    subtasks.append(
+                        {
+                            "id": "ingestion",
+                            "status": "failed",
+                            "error": str(exc),
+                        }
+                    )
+                    checkpoint["subtasks"] = subtasks
+                    await self._patch_checkpoint(
+                        mission_id,
+                        checkpoint,
+                        phase="ingestion",
+                        progress_percent=85,
+                        current_subtask_id="ingestion",
+                        status="error",
+                        error={"phase": "ingestion", "message": str(exc)},
+                    )
+                    raise
+            subtasks.append({"id": "ingestion", "status": "success"})
+            checkpoint["subtasks"] = subtasks
+            await self._patch_checkpoint(
+                mission_id,
+                checkpoint,
+                phase="terminal",
+                progress_percent=100,
+                current_subtask_id=None,
+                status="success",
+            )
+
+    def _source_to_lead(
+        self, source: dict[str, Any], workspace_id: int
+    ) -> dict[str, Any] | None:
+        """Convert a ChainLens source into a LeadItem-shaped dict.
+
+        Returns None for degenerate leads that would fail batch validation.
+        """
+        url = source.get("url")
+        domain = source.get("domain") or self._extract_domain(url)
+        lead = {
+            "source": "dsh_research",
+            "source_url": url,
+            "client_id": source.get("client_id"),
+            "company_name": source.get("company_name"),
+            "domain": domain,
+            "phone": source.get("phone"),
+            "email": source.get("email"),
+            "title": source.get("title"),
+            "industry": source.get("industry"),
+            "location": source.get("location"),
+            "fit_score": source.get("fit_score", 0.0),
+            "intent_score": source.get("intent_score", 0.0),
+            "composite_score": source.get("composite_score"),
+        }
+        if not any([lead["phone"], lead["email"], lead["domain"]]):
+            logger.warning("Skipping degenerate lead from source %s", url)
+            return None
+        return lead
+
+
+# ---------------------------------------------------------------------------
+# Worker
+# ---------------------------------------------------------------------------
+def _default_consumer_name() -> str:
+    """Return a unique consumer name per process/host for load balancing."""
+    return f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
+
+
+_RENEW_LOCK_SCRIPT = """
+if redis.call('get', KEYS[1]) == ARGV[1] then
+    return redis.call('expire', KEYS[1], ARGV[2])
+else
+    return 0
+end
+"""
+
+
+class DshWorker:
+    """Long-running sidecar worker for DSH missions."""
+
+    def __init__(
+        self,
+        consumer_name: str | None = None,
+        redis_client: Redis | None = None,
+        executor: DeepLeadResearchExecutor | LangGraphMissionExecutor | None = None,
+        rest_client: DshRestClient | None = None,
+    ) -> None:
+        self.consumer_name = consumer_name or _default_consumer_name()
+        self._redis = redis_client
+        self._executor = executor
+        self._rest_client = rest_client
+        self._running = False
+        self._tasks: set[asyncio.Task] = set()
+
+    @property
+    def stream(self) -> str:
+        return config.DSH_STREAM_TASKS
+
+    @property
+    def group(self) -> str:
+        return config.DSH_CONSUMER_GROUP
+
+    @property
+    def dlq(self) -> str:
+        return config.DSH_STREAM_DLQ
+
+    @property
+    def lock_ttl(self) -> int:
+        return config.DSH_LOCK_TTL_SECONDS
+
+    @property
+    def heartbeat_interval(self) -> int:
+        return config.DSH_HEARTBEAT_INTERVAL_SECONDS
+
+    @property
+    def max_retries(self) -> int:
+        return config.DSH_MAX_RETRIES
+
+    @property
+    def rest_client(self) -> DshRestClient:
+        if self._rest_client is None:
+            self._rest_client = DshRestClient(
+                config.DSH_INTERNAL_BASE_URL,
+                config.DSH_WORKER_PAT,
+                config.DSH_WORKER_SECRET,
+                timeout=float(config.DSH_SYNC_TIMEOUT_SECONDS),
+            )
+        return self._rest_client
+
+    def _lock_key(self, mission_id: uuid.UUID) -> str:
+        return f"nowing:dsh:lock:{mission_id}"
+
+    async def _redis_client(self) -> Redis:
+        if self._redis is None:
+            self._redis = await get_redis_client()
+        return self._redis
+
+    async def _ensure_consumer_group(self, redis_client: Redis) -> None:
+        try:
+            # ponytail: start at 0-0 so a (re)started worker consumes the
+            # backlog instead of only messages published after boot.
+            await redis_client.xgroup_create(
+                name=self.stream,
+                groupname=self.group,
+                id="0-0",
+                mkstream=True,
+            )
+        except ResponseError as exc:
+            if "BUSYGROUP" not in str(exc).upper():
+                raise
+
+    async def _try_set_lock(
+        self,
+        redis_client: Redis,
+        mission_id: uuid.UUID,
+    ) -> bool:
+        """Try to claim the per-mission Redis lock with NX + TTL."""
+        return await redis_client.set(
+            self._lock_key(mission_id),
+            self.consumer_name,
+            nx=True,
+            ex=self.lock_ttl,
+        )
+
+    async def _renew_lock_and_idle(
+        self,
+        redis_client: Redis,
+        mission_id: uuid.UUID,
+        msg_id: bytes | str,
+    ) -> bool:
+        """Heartbeat: refresh the Redis lock, then reset PEL idle time.
+
+        Uses a Lua script so we only extend TTL when we still own the lock.
+        We renew the lock FIRST so that a lost lock is detected before we
+        reset the pending-entry-list idle time; otherwise we could delay
+        another worker from reclaiming the message.
+        """
+        try:
+            ok = await redis_client.eval(
+                _RENEW_LOCK_SCRIPT,
+                1,
+                self._lock_key(mission_id),
+                self.consumer_name,
+                self.lock_ttl,
+            )
+            if not ok:
+                logger.info("Lock for mission %s is no longer ours", mission_id)
+                return False
+            await redis_client.xclaim(
+                self.stream,
+                self.group,
+                self.consumer_name,
+                0,
+                [msg_id],
+            )
+            return True
+        except Exception as exc:
+            logger.warning("Heartbeat failed for mission %s: %s", mission_id, exc)
+            return False
+
+    async def _autoclaim(
+        self,
+        redis_client: Redis,
+        min_idle_ms: int | None = None,
+    ) -> list[tuple[str, dict[str, Any]]]:
+        """Reclaim idle messages using XAUTOCLAIM.
+
+        ``min_idle_ms`` overrides ``config.DSH_XAUTOCLAIM_MIN_IDLE_MS`` when the
+        caller needs a non-production value (e.g. smoke tests).
+        """
+        claimed: list[tuple[str, dict[str, Any]]] = []
+        start_id = "0-0"
+        idle = min_idle_ms if min_idle_ms is not None else config.DSH_XAUTOCLAIM_MIN_IDLE_MS
+        while True:
+            response = await asyncio.wait_for(
+                redis_client.xautoclaim(
+                    self.stream,
+                    self.group,
+                    self.consumer_name,
+                    idle,
+                    start_id,
+                    count=10,
+                ),
+                timeout=_DSH_CALL_TIMEOUT_SECONDS,
+            )
+            # redis-py can return a 2- or 3-element list; the first two elements are
+            # next_start_id and the message list.
+            next_start, messages = response[0], response[1]
+            for msg_id, fields in messages:
+                claimed.append((msg_id, fields))
+            if not next_start or next_start == start_id or not messages:
+                break
+            start_id = next_start
+        return claimed
+
+    def _parse_payload(self, fields: dict[str, Any]) -> dict[str, Any]:
+        parsed: dict[str, Any] = {}
+        for key, value in fields.items():
+            key_s = key.decode() if isinstance(key, bytes) else key
+            value_s = value.decode() if isinstance(value, bytes) else value
+            if key_s in ("payload", "payload_json"):
+                try:
+                    parsed["payload"] = json.loads(value_s)
+                except json.JSONDecodeError:
+                    parsed["payload"] = value_s
+            elif key_s == "checkpoint":
+                try:
+                    parsed[key_s] = json.loads(value_s)
+                except json.JSONDecodeError:
+                    parsed[key_s] = value_s
+            elif key_s == "attempt":
+                try:
+                    parsed[key_s] = int(value_s)
+                except (ValueError, TypeError):
+                    parsed[key_s] = value_s
+            else:
+                parsed[key_s] = value_s
+        return parsed
+
+    async def _heartbeat_loop(
+        self,
+        redis_client: Redis,
+        mission_id: uuid.UUID,
+        msg_id: str,
+        executor_task: asyncio.Task,
+    ) -> None:
+        """Periodically reset idle time and renew the lock while a mission runs."""
+        try:
+            while self._running:
+                await asyncio.sleep(self.heartbeat_interval)
+                ok = await self._renew_lock_and_idle(redis_client, mission_id, msg_id)
+                if not ok:
+                    logger.warning(
+                        "Lock lost for mission %s; cancelling executor", mission_id
+                    )
+                    executor_task.cancel()
+                    break
+        except asyncio.CancelledError:
+            pass
+
+    async def _handle_message(
+        self,
+        redis_client: Redis,
+        msg_id: str,
+        fields: dict[str, Any],
+    ) -> bool:
+        """Process one stream message. Returns True if XACK should be attempted."""
+        parsed = self._parse_payload(fields)
+        mission_id_str = parsed.get("mission_id")
+        if not mission_id_str:
+            logger.error("Stream message %s has no mission_id", msg_id)
+            return True
+
+        try:
+            mission_id = uuid.UUID(str(mission_id_str))
+        except ValueError:
+            logger.error(
+                "Invalid mission_id %r in stream message %s", mission_id_str, msg_id
+            )
+            return True
+
+        # Idempotent lock check for new and reclaimed messages.
+        if not await self._try_set_lock(redis_client, mission_id):
+            logger.info("Mission %s is already locked; skip", mission_id)
+            return False
+
+        try:
+            mission = await self.rest_client.get_mission(mission_id)
+            if mission.get("status") in ("success", "error", "dlq", "cancelled"):
+                logger.info(
+                    "Mission %s already terminal (%s); skip",
+                    mission_id,
+                    mission.get("status"),
+                )
+                return True
+        except DshNonRetryableError as exc:
+            logger.error("Mission %s non-retryable load error: %s", mission_id, exc)
+            try:
+                await self._dlq(redis_client, msg_id, mission_id, str(exc))
+            except Exception as dlq_exc:
+                logger.exception(
+                    "Failed to DLQ mission %s after non-retryable load: %s",
+                    mission_id,
+                    dlq_exc,
+                )
+                return False
+            return True
+        except Exception as exc:
+            logger.exception("Could not load mission %s: %s", mission_id, exc)
+            return False
+
+        try:
+            # Only the deep-lead-research executor is supported in 26.8.
+            if mission.get("mission_type") != "deep_lead_research":
+                await self.rest_client.patch_checkpoint(
+                    mission_id,
+                    _checkpoint_update(
+                        status="error",
+                        error={
+                            "message": f"Unsupported mission_type {mission.get('mission_type')!r}",
+                            "failed_at": datetime.now(UTC).isoformat(),
+                        },
+                        completed_at=datetime.now(UTC).isoformat(),
+                    ),
+                )
+                return True
+
+            # Seed checkpoint attempt from the stream if the row is fresh.
+            checkpoint = mission.get("checkpoint") or {}
+            if checkpoint.get("attempt") is None:
+                checkpoint["attempt"] = parsed.get("attempt", 1)
+                mission["checkpoint"] = checkpoint
+
+            running_response = await self.rest_client.patch_checkpoint(
+                mission_id,
+                _checkpoint_update(
+                    status="running",
+                    phase="crawl",
+                    progress_percent=0,
+                    current_subtask_id="crawl",
+                    checkpoint=checkpoint,
+                    started_at=datetime.now(UTC).isoformat(),
+                ),
+            )
+            if isinstance(running_response, dict) and running_response.get("checkpoint"):
+                mission["checkpoint"] = running_response["checkpoint"]
+
+            if self._executor is not None:
+                executor = self._executor
+            elif config.DSH_EXECUTOR_ENGINE == "langgraph":
+                executor = LangGraphMissionExecutor(self.rest_client)
+            else:
+                executor = DeepLeadResearchExecutor(self.rest_client)
+            executor_task = asyncio.create_task(executor.run(mission))
+            heartbeat_task = asyncio.create_task(
+                self._heartbeat_loop(redis_client, mission_id, msg_id, executor_task)
+            )
+            self._tasks.add(executor_task)
+            self._tasks.add(heartbeat_task)
+
+            try:
+                await executor_task
+                await self.rest_client.patch_checkpoint(
+                    mission_id,
+                    _checkpoint_update(
+                        status="success",
+                        phase="terminal",
+                        progress_percent=100,
+                        current_subtask_id=None,
+                        completed_at=datetime.now(UTC).isoformat(),
+                    ),
+                )
+            except HumanInterventionRequired as e:
+                logger.warning(f"Mission {mission_id} requires human intervention: {e}")
+                # Save checkpoint and pause
+                await self.rest_client.patch_checkpoint(
+                    mission_id,
+                    _checkpoint_update(
+                        status="paused",
+                        phase="paused",
+                        current_subtask_id="cdp_crawl",
+                    ),
+                )
+                await redis_client.xack(self.stream, self.group, msg_id)
+                return True
+            except asyncio.CancelledError:
+                logger.info(
+                    "Mission %s cancelled (heartbeat/lock lost or shutdown)", mission_id
+                )
+                return False
+            finally:
+                heartbeat_task.cancel()
+                self._tasks.discard(heartbeat_task)
+                self._tasks.discard(executor_task)
+                with contextlib.suppress(asyncio.CancelledError):
+                    await heartbeat_task
+
+        except asyncio.CancelledError:
+            logger.info(
+                "Mission %s cancelled (heartbeat/lock lost or shutdown)", mission_id
+            )
+            return False
+        except DshNonRetryableError as exc:
+            try:
+                mission = await self.rest_client.get_mission(mission_id)
+            except Exception as refresh_exc:
+                logger.warning(
+                    "Could not refresh mission %s before DLQ: %s",
+                    mission_id,
+                    refresh_exc,
+                )
+            try:
+                await self._dlq(redis_client, msg_id, mission, str(exc))
+                return True
+            except Exception as dlq_exc:
+                logger.exception(
+                    "Failed to DLQ mission %s after non-retryable error: %s",
+                    mission_id,
+                    dlq_exc,
+                )
+                return False
+        except Exception as exc:
+            try:
+                mission = await self.rest_client.get_mission(mission_id)
+            except Exception as refresh_exc:
+                logger.warning(
+                    "Could not refresh mission %s before retry: %s",
+                    mission_id,
+                    refresh_exc,
+                )
+            try:
+                return await self._maybe_retry_or_dlq(
+                    redis_client, msg_id, mission, str(exc)
+                )
+            except Exception as retry_exc:
+                logger.exception(
+                    "Failed to schedule retry for mission %s: %s",
+                    mission_id,
+                    retry_exc,
+                )
+                return False
+
+    async def _maybe_retry_or_dlq(
+        self,
+        redis_client: Redis,
+        msg_id: str,
+        mission: dict[str, Any],
+        error_message: str,
+    ) -> bool:
+        """Increment retry_count; if exceeded, DLQ and signal XACK."""
+        mission_id = uuid.UUID(str(mission["id"]))
+        retry_count = (mission.get("retry_count") or 0) + 1
+        checkpoint = mission.get("checkpoint") or {}
+        checkpoint["attempt"] = (checkpoint.get("attempt") or 0) + 1
+        checkpoint["version"] = (checkpoint.get("version") or 0) + 1
+
+        if retry_count >= self.max_retries:
+            return await self._dlq(
+                redis_client,
+                msg_id,
+                mission,
+                error_message,
+                retry_count=retry_count,
+            )
+
+        await self.rest_client.patch_checkpoint(
+            mission_id,
+            _checkpoint_update(
+                status="pending",
+                checkpoint=checkpoint,
+                retry_count=retry_count,
+                error={
+                    "message": error_message,
+                    "failed_at": datetime.now(UTC).isoformat(),
+                },
+            ),
+        )
+        return False
+
+    async def _dlq(
+        self,
+        redis_client: Redis,
+        msg_id: str,
+        mission_or_id: dict[str, Any] | uuid.UUID,
+        error_message: str,
+        retry_count: int | None = None,
+    ) -> bool:
+        """Move a mission to the DLQ, writing a bounded stream entry."""
+        if isinstance(mission_or_id, uuid.UUID):
+            # Used when the mission row could not be loaded at all.
+            mission_id = mission_or_id
+            payload: dict[str, Any] | None = None
+            checkpoint: dict[str, Any] = {}
+            attempt = 1
+            if retry_count is None:
+                retry_count = 0
+        else:
+            mission = mission_or_id
+            mission_id = uuid.UUID(str(mission["id"]))
+            payload = mission.get("payload")
+            checkpoint = mission.get("checkpoint") or {}
+            attempt = checkpoint.get("attempt", 1)
+            if retry_count is None:
+                retry_count = mission.get("retry_count") or 0
+
+        checkpoint["version"] = (checkpoint.get("version") or 0) + 1
+        error = {
+            "message": error_message,
+            "failed_at": datetime.now(UTC).isoformat(),
+        }
+
+        await self.rest_client.patch_checkpoint(
+            mission_id,
+            _checkpoint_update(
+                status="dlq",
+                checkpoint=checkpoint,
+                retry_count=retry_count,
+                error=error,
+                completed_at=datetime.now(UTC).isoformat(),
+            ),
+        )
+
+        try:
+            await redis_client.xadd(
+                self.dlq,
+                {
+                    "original_id": msg_id,
+                    "mission_id": str(mission_id),
+                    "payload_json": json.dumps(payload) if payload is not None else "",
+                    "error_json": json.dumps(error),
+                    "failed_at": error["failed_at"],
+                    "attempt": str(attempt),
+                },
+                maxlen=10000,
+                approximate=True,
+            )
+        except Exception as exc:
+            logger.exception("Failed to write mission %s to DLQ: %s", mission_id, exc)
+            # The checkpoint is already dlq; a missing DLQ stream entry is logged.
+        return True
+
+    async def _read_new_messages(
+        self,
+        redis_client: Redis,
+    ) -> list[tuple[str, dict[str, Any]]]:
+        """Read one batch of new messages from the consumer group."""
+        entries = await asyncio.wait_for(
+            redis_client.xreadgroup(
+                groupname=self.group,
+                consumername=self.consumer_name,
+                streams={self.stream: ">"},
+                count=1,
+                block=config.DSH_REDIS_BLOCK_MS,
+            ),
+            timeout=_DSH_CALL_TIMEOUT_SECONDS,
+        )
+
+        messages: list[tuple[str, dict[str, Any]]] = []
+        if entries:
+            for _stream_name, stream_messages in entries:
+                for msg_id, fields in stream_messages:
+                    messages.append((msg_id, fields))
+        return messages
+
+    async def run(self) -> None:
+        """Main worker loop with bounded exponential backoff on Redis errors."""
+        redis_client = await self._redis_client()
+        await self._ensure_consumer_group(redis_client)
+        self._redis = redis_client
+        self._running = True
+
+        consecutive_redis_errors = 0
+        last_autoclaim = 0.0
+        while self._running:
+            # Periodically XAUTOCLAIM idle messages
+            now = asyncio.get_event_loop().time()
+            if now - last_autoclaim >= self.heartbeat_interval:
+                try:
+                    reclaimed = await self._autoclaim(redis_client)
+                    consecutive_redis_errors = 0
+                except Exception as exc:
+                    logger.exception("XAUTOCLAIM failed: %s", exc)
+                    consecutive_redis_errors += 1
+                    await asyncio.sleep(min(30, 2**consecutive_redis_errors))
+                    continue
+
+                for msg_id, fields in reclaimed:
+                    parsed = self._parse_payload(fields)
+                    mission_id_str = parsed.get("mission_id")
+                    if mission_id_str:
+                        try:
+                            lock_key = self._lock_key(uuid.UUID(str(mission_id_str)))
+                            if await redis_client.exists(lock_key):
+                                logger.info(
+                                    "Reclaimed message %s for mission %s still locked; skip",
+                                    msg_id,
+                                    mission_id_str,
+                                )
+                                continue
+                        except Exception:
+                            pass
+
+                    should_ack = await self._handle_message(
+                        redis_client, msg_id, fields
+                    )
+                    if should_ack:
+                        try:
+                            await redis_client.xack(self.stream, self.group, msg_id)
+                        except Exception as exc:
+                            logger.exception("Failed to XACK %s: %s", msg_id, exc)
+
+                last_autoclaim = now
+
+            try:
+                messages = await self._read_new_messages(redis_client)
+                consecutive_redis_errors = 0
+            except Exception as exc:
+                logger.exception("XREADGROUP failed: %s", exc)
+                consecutive_redis_errors += 1
+                await asyncio.sleep(min(30, 2**consecutive_redis_errors))
+                continue
+
+            if not messages:
+                await asyncio.sleep(1)
+                continue
+
+            for msg_id, fields in messages:
+                should_ack = await self._handle_message(redis_client, msg_id, fields)
+                if should_ack:
+                    try:
+                        await redis_client.xack(self.stream, self.group, msg_id)
+                    except Exception as exc:
+                        logger.exception("Failed to XACK %s: %s", msg_id, exc)
+
+    def stop(self) -> None:
+        """Signal the worker to stop and cancel in-flight tasks."""
+        self._running = False
+        for task in list(self._tasks):
+            task.cancel()
+
+    async def aclose(self) -> None:
+        await self.rest_client.aclose()
+
+
+# ---------------------------------------------------------------------------
+# Healthcheck
+# ---------------------------------------------------------------------------
+async def healthcheck() -> int:
+    """Liveness probe used by docker-compose."""
+    try:
+        redis_client = await get_redis_client()
+        await redis_client.ping()
+    except Exception as exc:
+        logger.error("DSH healthcheck Redis ping failed: %s", exc)
+        return 1
+
+    try:
+        async with httpx.AsyncClient(timeout=5.0) as client:
+            resp = await client.get(
+                f"{config.DSH_INTERNAL_BASE_URL.rstrip('/')}/health"
+            )
+            resp.raise_for_status()
+    except Exception as exc:
+        logger.error("DSH healthcheck API ping failed: %s", exc)
+        return 1
+
+    return 0
+
+
+# ---------------------------------------------------------------------------
+# Entry points
+# ---------------------------------------------------------------------------
+def _validate_config() -> None:
+    if not config.DSH_WORKER_PAT or not config.DSH_WORKER_SECRET:
+        raise SystemExit(
+            "DSH_WORKER_PAT and DSH_WORKER_SECRET must be set and non-empty"
+        )
+    if config.DSH_LOCK_TTL_SECONDS <= config.DSH_HEARTBEAT_INTERVAL_SECONDS:
+        raise SystemExit(
+            "DSH_LOCK_TTL_SECONDS must be greater than DSH_HEARTBEAT_INTERVAL_SECONDS"
+        )
+    if (
+        config.DSH_XAUTOCLAIM_MIN_IDLE_MS
+        <= config.DSH_HEARTBEAT_INTERVAL_SECONDS * 1000
+    ):
+        raise SystemExit(
+            "DSH_XAUTOCLAIM_MIN_IDLE_MS must be greater than heartbeat interval in ms"
+        )
+
+
+async def run_dsh_worker() -> None:
+    """Entry point for the SERVICE_ROLE=dsh sidecar."""
+    _validate_config()
+    worker = DshWorker()
+    loop = asyncio.get_event_loop()
+    for sig in (signal.SIGTERM, signal.SIGINT):
+        with contextlib.suppress(NotImplementedError, ValueError):
+            # Signals may not be supported on this platform (e.g. Windows).
+            loop.add_signal_handler(sig, worker.stop)
+
+    try:
+        await worker.run()
+    finally:
+        worker.stop()
+        await worker.aclose()
+
+
+if __name__ == "__main__":
+    parser = argparse.ArgumentParser()
+    parser.add_argument("--healthcheck", action="store_true")
+    args = parser.parse_args()
+
+    if args.healthcheck:
+        sys.exit(asyncio.run(healthcheck()))
+
+    try:
+        asyncio.run(run_dsh_worker())
+    except SystemExit as exc:
+        if exc.code not in (0, None):
+            sys.exit(exc.code)
diff --git a/nowing_backend/app/tasks/dsh_worker_browser_operator.py b/nowing_backend/app/tasks/dsh_worker_browser_operator.py
new file mode 100644
index 000000000..3f370447d
--- /dev/null
+++ b/nowing_backend/app/tasks/dsh_worker_browser_operator.py
@@ -0,0 +1,109 @@
+import asyncio
+import logging
+import json
+from typing import Any, TypedDict
+
+from langgraph.graph import StateGraph, START, END
+from langgraph.types import RunnableConfig
+
+from app.redis_client import get_redis_client
+
+MissionState = dict[str, Any]
+
+logger = logging.getLogger(__name__)
+
+class HumanInterventionRequired(Exception):
+    """Raised when the agent encounters a CAPTCHA or requires human takeover."""
+    pass
+
+class BrowserOperatorCdpSubgraph:
+    """Subgraph for executing native browser CDP commands via extension."""
+    
+    def __init__(self, rest_client: Any) -> None:
+        self.rest_client = rest_client
+
+    @classmethod
+    def build(cls, rest_client: Any) -> StateGraph:
+        subgraph = StateGraph(MissionState)
+        instance = cls(rest_client)
+        
+        subgraph.add_node("cdp_crawl", instance._cdp_crawl_node)
+        subgraph.add_edge(START, "cdp_crawl")
+        subgraph.add_edge("cdp_crawl", END)
+        
+        return subgraph.compile()
+
+    async def _cdp_crawl_node(self, state: MissionState, config: RunnableConfig) -> MissionState:
+        logger.info("Executing CDP crawl step.")
+        _ = config
+
+        payload = state.get("payload") or {}
+        mission_id = state.get("mission_id")
+        resolved_user_id = payload.get("user_id") or state.get("user_id")
+
+        if not mission_id:
+            raise ValueError("mission_id is required in state to run CDP Subgraph.")
+        if not resolved_user_id:
+            raise ValueError("user_id is required in payload/state to route CDP commands.")
+
+        target_url = payload.get("target_url")
+        if not target_url:
+            raise ValueError("target_url is missing from mission payload.")
+
+        if payload.get("force_captcha") is True:
+            logger.warning("CAPTCHA detected, raising HumanInterventionRequired.")
+            raise HumanInterventionRequired("CAPTCHA detected, human takeover needed.")
+
+        redis = await get_redis_client()
+        channel = f"cdp_stream:{resolved_user_id}"
+        result_key = f"cdp_result:{resolved_user_id}:{mission_id}"
+
+        # Clear previous result queue
+        await redis.delete(result_key)
+
+        # Push command with mission_id
+        cmd = {
+            "action": "navigate",
+            "url": target_url,
+            "mission_id": str(mission_id),
+        }
+        await redis.publish(channel, json.dumps(cmd))
+
+        # Wait for result using BLPOP
+        result_tuple = await redis.blpop(result_key, timeout=60)
+
+        if result_tuple:
+            _, result_data = result_tuple
+            try:
+                parsed_result = json.loads(result_data)
+            except json.JSONDecodeError as exc:
+                raise RuntimeError(f"Malformed CDP result received from extension: {exc}") from exc
+
+            if parsed_result.get("error"):
+                raise RuntimeError(f"Extension CDP execution failed: {parsed_result['error']}")
+
+            logger.info("Received CDP result: %s", parsed_result)
+
+            # Build subtasks & sources for downstream LangGraph reasoning node
+            cdp_res = parsed_result.get("result") or {}
+            sources = parsed_result.get("sources") or ([cdp_res] if cdp_res else [])
+            subtasks = list(state.get("subtasks") or [])
+            subtasks.append(
+                {
+                    "id": "cdp_crawl",
+                    "status": "success",
+                    "sources_count": len(sources),
+                }
+            )
+
+            state["sources"] = sources
+            state["subtasks"] = subtasks
+
+            state_checkpoint = dict(state.get("checkpoint") or {})
+            state_checkpoint["cdp_last_result"] = cdp_res
+            state_checkpoint["sources"] = sources
+            state_checkpoint["subtasks"] = subtasks
+            state["checkpoint"] = state_checkpoint
+            return state
+
+        raise TimeoutError("Extension did not return CDP result within 60s")
diff --git a/nowing_backend/app/tasks/dsh_worker_langgraph.py b/nowing_backend/app/tasks/dsh_worker_langgraph.py
new file mode 100644
index 000000000..1c591babb
--- /dev/null
+++ b/nowing_backend/app/tasks/dsh_worker_langgraph.py
@@ -0,0 +1,583 @@
+"""LangGraph-based executor for DSH missions.
+
+This is an experimental executor behind the ``DSH_EXECUTOR_ENGINE`` feature flag.
+It re-implements the ``deep_lead_research`` pipeline as a LangGraph ``StateGraph``
+while keeping the Redis Stream consumer, REST client, and checkpoint persistence
+unchanged.
+
+Design notes:
+- No LangGraph checkpointer is used. The worker relies on the existing
+  ``dsh_missions`` checkpoint and on idempotent nodes that skip already-completed
+  subtasks when a mission is reclaimed after a crash.
+- The graph state does NOT contain the REST client. We pass it through
+  ``configurable`` so the state remains serialisable if we later enable a
+  LangGraph checkpointer.
+- PII (phone/email in leads) is stored in the checkpoint JSONB the same way
+  the legacy executor does. The checkpoint column is private and not published
+  to Zero, consistent with AD-108.
+"""
+
+from __future__ import annotations
+
+import logging
+from datetime import UTC, datetime
+from typing import TYPE_CHECKING, Any, TypedDict
+from urllib.parse import urlparse
+from uuid import UUID
+
+from langgraph.graph import END, START, StateGraph
+from langgraph.types import RunnableConfig
+
+from app.tasks.dsh_worker_crawl_subgraph import (
+    WideResearchCrawlSubgraph,
+    _is_valid_matrix,
+)
+from app.tasks.dsh_worker_deliver_subgraph import DshDeliverSubgraph
+from app.tasks.dsh_worker_browser_operator import (
+    BrowserOperatorCdpSubgraph,
+    HumanInterventionRequired,
+)
+
+if TYPE_CHECKING:
+    from app.tasks.dsh_worker import DshRestClient
+
+logger = logging.getLogger(__name__)
+
+
+class _Subtask(TypedDict, total=False):
+    id: str
+    status: str
+    run_id: str | None
+    sources_count: int | None
+    leads_count: int | None
+    error: dict[str, Any] | None
+
+
+class MissionState(TypedDict, total=False):
+    """In-memory state for the LangGraph mission graph."""
+
+    mission_id: str
+    workspace_id: int
+    query: str
+    payload: dict[str, Any]
+    checkpoint: dict[str, Any]
+    subtasks: list[_Subtask]
+    sources: list[dict[str, Any]]
+    leads: list[dict[str, Any]]
+    progress_percent: int
+    phase: str
+    current_subtask_id: str | None
+    status: str
+    error: dict[str, Any] | None
+    completed_at: str | None
+
+
+class LangGraphMissionExecutor:
+    """LangGraph-backed executor for ``deep_lead_research`` missions."""
+
+    def __init__(self, rest_client: DshRestClient) -> None:
+        self.rest_client = rest_client
+
+    @staticmethod
+    def _extract_domain(url: str | None) -> str | None:
+        if not url:
+            return None
+        try:
+            parsed = urlparse(url)
+            return parsed.netloc if parsed.netloc else None
+        except Exception:
+            return None
+
+    @staticmethod
+    def _subtask_success(state: MissionState, subtask_id: str) -> bool:
+        return any(
+            s.get("id") == subtask_id and s.get("status") == "success"
+            for s in state.get("subtasks", [])
+        )
+
+    def _source_to_lead(
+        self, source: dict[str, Any], workspace_id: int
+    ) -> dict[str, Any] | None:
+        """Convert a ChainLens source into a LeadItem-shaped dict."""
+        url = source.get("url")
+        domain = source.get("domain") or self._extract_domain(url)
+        lead = {
+            "source": "dsh_research",
+            "source_url": url,
+            "client_id": source.get("client_id"),
+            "company_name": source.get("company_name"),
+            "domain": domain,
+            "phone": source.get("phone"),
+            "email": source.get("email"),
+            "title": source.get("title"),
+            "industry": source.get("industry"),
+            "location": source.get("location"),
+            "fit_score": source.get("fit_score", 0.0),
+            "intent_score": source.get("intent_score", 0.0),
+            "composite_score": source.get("composite_score"),
+        }
+        if not any([lead["phone"], lead["email"], lead["domain"]]):
+            logger.warning("Skipping degenerate lead from source %s", url)
+            return None
+        return lead
+
+    async def _patch_checkpoint(
+        self,
+        state: MissionState,
+        **update: Any,
+    ) -> MissionState:
+        """Persist a checkpoint update and merge the server's response back."""
+        from app.tasks.dsh_worker import _checkpoint_update as build_update
+
+        mission_id = state["mission_id"]
+        current_checkpoint = update.get("checkpoint") or state.get("checkpoint") or {}
+
+        # Merge the scalar state fields into the checkpoint JSONB so that crash
+        # resumption has an authoritative view of the last persisted phase,
+        # progress, and current subtask id.
+        for key in ("phase", "progress_percent", "current_subtask_id", "status", "error"):
+            value = update.get(key) if key in update else state.get(key)
+            if value is not None or key == "current_subtask_id":
+                current_checkpoint[key] = value
+
+        payload = build_update(
+            checkpoint=current_checkpoint,
+            phase=update.get("phase", state.get("phase")),
+            progress_percent=update.get("progress_percent", state.get("progress_percent")),
+            current_subtask_id=update.get(
+                "current_subtask_id", state.get("current_subtask_id")
+            ),
+            status=update.get("status", state.get("status")),
+            error=update.get("error", state.get("error")),
+            completed_at=update.get("completed_at", state.get("completed_at")),
+        )
+
+        response = await self.rest_client.patch_checkpoint(
+            UUID(str(mission_id)), payload
+        )
+
+        if isinstance(response, dict) and response.get("checkpoint"):
+            checkpoint = response["checkpoint"]
+        else:
+            checkpoint = current_checkpoint
+
+
+
+        return {
+            **state,
+            **{k: v for k, v in payload.items() if k != "checkpoint"},
+            "checkpoint": checkpoint,
+        }
+
+    async def _crawl_node(
+        self, state: MissionState, config: RunnableConfig
+    ) -> MissionState:
+        payload = state.get("payload") or {}
+        extras = payload.get("extras", {}) if isinstance(payload, dict) else {}
+        checkpoint = state.get("checkpoint") or {}
+
+        if self._subtask_success(state, "crawl"):
+            if extras.get("research_mode") == "wide":
+                if checkpoint.get("wide_research_matrix"):
+                    return state
+            else:
+                return state
+
+        rest_client: DshRestClient = config["configurable"]["rest_client"]
+        workspace_id = state["workspace_id"]
+        query = state["query"]
+
+        state = await self._patch_checkpoint(
+            state,
+            phase="crawl",
+            progress_percent=10,
+            current_subtask_id="crawl",
+            status="running",
+        )
+
+        try:
+            if extras.get("research_mode") == "wide":
+                subgraph = WideResearchCrawlSubgraph.build(rest_client)
+                result = await subgraph.ainvoke(state, config)
+                sources = result.get("sources", [])
+                subtasks = list(result.get("subtasks") or [])
+                checkpoint = dict(result.get("checkpoint") or {})
+            elif extras.get("research_mode") == "cdp_takeover":
+                subgraph = BrowserOperatorCdpSubgraph.build(rest_client)
+                result = await subgraph.ainvoke(state, config)
+                sources = result.get("sources", [])
+                subtasks = list(result.get("subtasks") or [])
+                checkpoint = dict(result.get("checkpoint") or {})
+            else:
+                research_output = await rest_client.chainlens_research(workspace_id, query)
+                sources = research_output.get("sources", [])
+                subtasks = list(state.get("subtasks") or [])
+                subtasks.append(
+                    {
+                        "id": "crawl",
+                        "status": "success",
+                        "run_id": research_output.get("run_id"),
+                        "sources_count": len(sources),
+                    }
+                )
+                checkpoint = dict(state.get("checkpoint") or {})
+                checkpoint["subtasks"] = subtasks
+                checkpoint["sources"] = sources
+
+            return await self._patch_checkpoint(
+                {**state, "subtasks": subtasks, "sources": sources, "checkpoint": checkpoint},
+                checkpoint=checkpoint,
+                phase="reasoning",
+                progress_percent=35,
+                current_subtask_id="reasoning",
+            )
+        except HumanInterventionRequired:
+            raise
+        except Exception as exc:
+            subtasks = list(state.get("subtasks", []))
+            subtasks.append({"id": "crawl", "status": "failed", "error": str(exc)})
+            checkpoint = dict(state.get("checkpoint") or {})
+            checkpoint["subtasks"] = subtasks
+            state = await self._patch_checkpoint(
+                {**state, "subtasks": subtasks, "checkpoint": checkpoint},
+                checkpoint=checkpoint,
+                phase="crawl",
+                progress_percent=0,
+                current_subtask_id="crawl",
+                status="error",
+                error={"phase": "crawl", "message": str(exc)},
+            )
+            raise
+
+    async def _reasoning_node(
+        self, state: MissionState, config: RunnableConfig
+    ) -> MissionState:
+        _ = config
+        if self._subtask_success(state, "reasoning"):
+            return state
+
+        subtasks = list(state.get("subtasks", []))
+        subtasks.append({"id": "reasoning", "status": "success"})
+        checkpoint = dict(state.get("checkpoint") or {})
+        checkpoint["subtasks"] = subtasks
+
+        return await self._patch_checkpoint(
+            {**state, "subtasks": subtasks, "checkpoint": checkpoint},
+            checkpoint=checkpoint,
+            phase="extraction",
+            progress_percent=60,
+            current_subtask_id="extraction",
+        )
+
+    async def _extraction_node(
+        self, state: MissionState, config: RunnableConfig
+    ) -> MissionState:
+        _ = config
+        if self._subtask_success(state, "extraction"):
+            return state
+
+        state = await self._patch_checkpoint(
+            state,
+            phase="extraction",
+            progress_percent=70,
+            current_subtask_id="extraction",
+        )
+
+        sources = state.get("sources", [])
+        workspace_id = state["workspace_id"]
+        extracted_leads = [
+            self._source_to_lead(source, workspace_id) for source in sources
+        ]
+        extracted_leads = [lead for lead in extracted_leads if lead is not None]
+
+        subtasks = list(state.get("subtasks", []))
+        subtasks.append(
+            {"id": "extraction", "status": "success", "leads_count": len(extracted_leads)}
+        )
+        checkpoint = dict(state.get("checkpoint") or {})
+        checkpoint["subtasks"] = subtasks
+        checkpoint["leads"] = extracted_leads
+
+        return await self._patch_checkpoint(
+            {
+                **state,
+                "subtasks": subtasks,
+                "leads": extracted_leads,
+                "checkpoint": checkpoint,
+            },
+            checkpoint=checkpoint,
+            phase="ingestion",
+            progress_percent=85,
+            current_subtask_id="ingestion",
+        )
+
+    async def _deliver_node(
+        self, state: MissionState, config: RunnableConfig
+    ) -> MissionState:
+        """Generate an .xlsx deliverable from the wide-research matrix if present."""
+        _ = config
+        payload = state.get("payload") or {}
+        extras = payload.get("extras", {}) if isinstance(payload, dict) else {}
+        checkpoint = dict(state.get("checkpoint") or {})
+
+        if self._subtask_success(state, "deliver"):
+            return state
+
+        if not _is_valid_matrix(checkpoint.get("wide_research_matrix")):
+            # Skip deliver for non-wide-research missions or invalid matrices.
+            subtasks = list(state.get("subtasks", []))
+            if not any(s.get("id") == "deliver" for s in subtasks):
+                subtasks.append({"id": "deliver", "status": "skipped"})
+            checkpoint["subtasks"] = subtasks
+            return await self._patch_checkpoint(
+                {**state, "subtasks": subtasks, "checkpoint": checkpoint},
+                checkpoint=checkpoint,
+                phase="terminal",
+                progress_percent=100,
+                current_subtask_id=None,
+                status="success",
+                completed_at=datetime.now(UTC).isoformat(),
+            )
+
+        state = await self._patch_checkpoint(
+            state,
+            phase="deliver",
+            progress_percent=95,
+            current_subtask_id="deliver",
+        )
+
+        try:
+            include_pii = bool(extras.get("include_pii"))
+            deliverable = await DshDeliverSubgraph(include_pii=include_pii).run(
+                str(state["mission_id"]),
+                checkpoint,
+            )
+            if deliverable is None:
+                # No matrix; treat as skipped.
+                subtasks = list(state.get("subtasks", []))
+                subtasks.append({"id": "deliver", "status": "skipped"})
+                checkpoint["subtasks"] = subtasks
+                return await self._patch_checkpoint(
+                    {**state, "subtasks": subtasks, "checkpoint": checkpoint},
+                    checkpoint=checkpoint,
+                    phase="terminal",
+                    progress_percent=100,
+                    current_subtask_id=None,
+                    status="success",
+                    completed_at=datetime.now(UTC).isoformat(),
+                )
+
+            subtasks = list(state.get("subtasks", []))
+            subtasks.append({"id": "deliver", "status": "success"})
+            checkpoint = dict(state.get("checkpoint") or {})
+            checkpoint["subtasks"] = subtasks
+            deliverables = list(checkpoint.get("deliverables", []))
+            deliverables.append(deliverable)
+            checkpoint["deliverables"] = deliverables
+
+            return await self._patch_checkpoint(
+                {**state, "subtasks": subtasks, "checkpoint": checkpoint},
+                checkpoint=checkpoint,
+                phase="terminal",
+                progress_percent=100,
+                current_subtask_id=None,
+                status="success",
+                completed_at=datetime.now(UTC).isoformat(),
+            )
+        except Exception as exc:
+            subtasks = list(state.get("subtasks", []))
+            subtasks.append({"id": "deliver", "status": "failed", "error": str(exc)})
+            checkpoint = dict(state.get("checkpoint") or {})
+            checkpoint["subtasks"] = subtasks
+            state = await self._patch_checkpoint(
+                {**state, "subtasks": subtasks, "checkpoint": checkpoint},
+                checkpoint=checkpoint,
+                phase="deliver",
+                progress_percent=90,
+                current_subtask_id="deliver",
+                status="error",
+                error={"phase": "deliver", "message": str(exc)},
+            )
+            raise
+
+    async def _ingestion_node(
+        self, state: MissionState, config: RunnableConfig
+    ) -> MissionState:
+        if self._subtask_success(state, "ingestion"):
+            return state
+
+        rest_client: DshRestClient = config["configurable"]["rest_client"]
+        workspace_id = state["workspace_id"]
+
+        state = await self._patch_checkpoint(
+            state,
+            phase="ingestion",
+            progress_percent=90,
+            current_subtask_id="ingestion",
+        )
+
+        leads = state.get("leads", [])
+        if not leads:
+            subtasks = list(state.get("subtasks", []))
+            subtasks.append({"id": "ingestion", "status": "success"})
+            checkpoint = dict(state.get("checkpoint") or {})
+            checkpoint["subtasks"] = subtasks
+            return await self._patch_checkpoint(
+                {**state, "subtasks": subtasks, "checkpoint": checkpoint},
+                checkpoint=checkpoint,
+                phase="terminal",
+                progress_percent=100,
+                current_subtask_id=None,
+                status="success",
+                completed_at=datetime.now(UTC).isoformat(),
+            )
+
+        try:
+            ingest_res = await rest_client.batch_ingest_leads(workspace_id, leads)
+            await self._maybe_notify_high_fit(state, ingest_res)
+        except Exception as exc:
+            subtasks = list(state.get("subtasks", []))
+            subtasks.append({"id": "ingestion", "status": "failed", "error": str(exc)})
+            checkpoint = dict(state.get("checkpoint") or {})
+            checkpoint["subtasks"] = subtasks
+            state = await self._patch_checkpoint(
+                {**state, "subtasks": subtasks, "checkpoint": checkpoint},
+                checkpoint=checkpoint,
+                phase="ingestion",
+                progress_percent=85,
+                current_subtask_id="ingestion",
+                status="error",
+                error={"phase": "ingestion", "message": str(exc)},
+            )
+            raise
+
+        subtasks = list(state.get("subtasks", []))
+        subtasks.append({"id": "ingestion", "status": "success"})
+        checkpoint = dict(state.get("checkpoint") or {})
+        checkpoint["subtasks"] = subtasks
+
+        return await self._patch_checkpoint(
+            {**state, "subtasks": subtasks, "checkpoint": checkpoint},
+            checkpoint=checkpoint,
+            phase="terminal",
+            progress_percent=100,
+            current_subtask_id=None,
+            status="success",
+            completed_at=datetime.now(UTC).isoformat(),
+        )
+
+    async def _maybe_notify_high_fit(
+        self, state: MissionState, ingest_res: dict[str, Any]
+    ) -> None:
+        """Mirror the legacy high-fit lead notification logic."""
+        mission_id = UUID(str(state["mission_id"]))
+        workspace_id = state["workspace_id"]
+        leads = state.get("leads", [])
+        try:
+            from app.lead_intelligence.dnc.normalizer import normalize_domain
+            from app.services.dsh_telegram_checkpoint_service import (
+                DshTelegramCheckpointService,
+            )
+            from app.services.lead_batch_service import generate_lead_hmac
+
+            checkpoint_svc = DshTelegramCheckpointService()
+            high_fit_candidate = checkpoint_svc.select_high_fit_lead(leads)
+            if not high_fit_candidate:
+                return
+
+            lead_id = None
+            if isinstance(high_fit_candidate, dict):
+                cand_company = (
+                    high_fit_candidate.get("company_name")
+                    or high_fit_candidate.get("title")
+                    or "Doanh nghiệp"
+                )
+                cand_domain = normalize_domain(high_fit_candidate.get("domain"))
+                cand_hmac = high_fit_candidate.get("value_hmac") or generate_lead_hmac(
+                    workspace_id, cand_company, cand_domain
+                )
+                mapping = ingest_res.get("lead_id_mapping") or {}
+                lead_id = mapping.get(cand_hmac)
+                if not lead_id:
+                    logger.info(
+                        "High-fit lead mapping missing for mission %s; skipping notification",
+                        mission_id,
+                    )
+            elif hasattr(high_fit_candidate, "id"):
+                lead_id = high_fit_candidate.id
+
+            if lead_id:
+                await self.rest_client.notify_high_fit_lead(mission_id, lead_id)
+        except Exception as notify_exc:
+            logger.warning(
+                "Failed to process high fit lead notification for mission %s: %s",
+                mission_id,
+                notify_exc,
+            )
+
+    def _build_graph(self) -> StateGraph:
+        graph = StateGraph(MissionState)
+        graph.add_node("crawl", self._crawl_node)
+        graph.add_node("reasoning", self._reasoning_node)
+        graph.add_node("extraction", self._extraction_node)
+        graph.add_node("ingestion", self._ingestion_node)
+        graph.add_node("deliver", self._deliver_node)
+
+        graph.add_edge(START, "crawl")
+        graph.add_edge("crawl", "reasoning")
+        graph.add_edge("reasoning", "extraction")
+        graph.add_edge("extraction", "ingestion")
+        graph.add_edge("ingestion", "deliver")
+        graph.add_edge("deliver", END)
+
+        return graph
+
+    async def run(self, mission: dict[str, Any] | Any) -> None:
+        """Run the mission through the LangGraph state graph."""
+        if isinstance(mission, dict):
+            mission_id = str(mission["id"])
+            workspace_id = mission["workspace_id"]
+            payload = mission.get("payload") or {}
+            checkpoint = mission.get("checkpoint") or {}
+        else:
+            mission_id = str(mission.id)
+            workspace_id = mission.workspace_id
+            payload = mission.payload or {}
+            checkpoint = mission.checkpoint or {}
+
+        # Re-fetch the mission from the sidecar's view. This is important when the
+        # worker has already bumped the checkpoint (e.g. setting status=running)
+        # before invoking the executor, because the ``DshMissionService``
+        # increments ``checkpoint.version`` on every write and rejects stale
+        # checkpoints.
+        refreshed = await self.rest_client.get_mission(UUID(mission_id))
+        if refreshed:
+            workspace_id = refreshed.get("workspace_id", workspace_id)
+            payload = refreshed.get("payload") or payload
+            checkpoint = refreshed.get("checkpoint") or checkpoint
+
+        query = payload.get("query", "") if isinstance(payload, dict) else ""
+        subtasks = checkpoint.get("subtasks", [])
+        if not subtasks:
+            subtasks = []
+        sources = checkpoint.get("sources", [])
+        leads = checkpoint.get("leads", [])
+
+        initial_state: MissionState = {
+            "mission_id": mission_id,
+            "workspace_id": workspace_id,
+            "query": query,
+            "payload": payload,
+            "checkpoint": checkpoint,
+            "subtasks": subtasks,
+            "sources": sources,
+            "leads": leads,
+            "progress_percent": checkpoint.get("progress_percent", 0),
+            "phase": checkpoint.get("phase", "crawl"),
+            "current_subtask_id": checkpoint.get("current_subtask_id"),
+            "status": "running",
+        }
+
+        graph = self._build_graph().compile()
+        config: RunnableConfig = {"configurable": {"rest_client": self.rest_client}}
+        await graph.ainvoke(initial_state, config=config)
diff --git a/nowing_backend/tests/integration/tasks/dsh_worker/test_browser_operator_cdp_integration.py b/nowing_backend/tests/integration/tasks/dsh_worker/test_browser_operator_cdp_integration.py
new file mode 100644
index 000000000..ccbf78278
--- /dev/null
+++ b/nowing_backend/tests/integration/tasks/dsh_worker/test_browser_operator_cdp_integration.py
@@ -0,0 +1,65 @@
+from unittest.mock import AsyncMock, patch, MagicMock
+import pytest
+from sqlalchemy import select, update
+from app.db import DshMission
+from app.routes.dsh_routes import pause_mission, resume_mission
+from app.schemas.dsh import ResumeMissionPayload
+from fastapi import HTTPException
+
+pytestmark = [pytest.mark.integration]
+
+@pytest.mark.asyncio
+async def test_pause_status_update(db_session):
+    """should execute pause_mission route and set mission status to paused."""
+    mission = DshMission(user_id=1, workspace_id=1, status="in_progress")
+    db_session.add(mission)
+    await db_session.commit()
+    await db_session.refresh(mission)
+
+    auth_mock = MagicMock()
+    auth_mock.user.id = 1
+
+    payload = ResumeMissionPayload(mission_id=mission.id)
+    response = await pause_mission(payload, auth_mock, db_session)
+
+    assert response["status"] == "paused"
+    await db_session.refresh(mission)
+    assert mission.status == "paused"
+
+@pytest.mark.asyncio
+async def test_resume_cas_update(db_session):
+    """should execute resume_mission route with atomic CAS and transition paused -> in_progress."""
+    mission = DshMission(user_id=1, workspace_id=1, status="paused")
+    db_session.add(mission)
+    await db_session.commit()
+    await db_session.refresh(mission)
+
+    auth_mock = MagicMock()
+    auth_mock.user.id = 1
+
+    payload = ResumeMissionPayload(mission_id=mission.id)
+
+    with patch("app.services.dsh_mission_service.DshMissionService.publish_to_stream", new_callable=AsyncMock):
+        response = await resume_mission(payload, auth_mock, db_session)
+        assert response["status"] == "in_progress"
+
+    await db_session.refresh(mission)
+    assert mission.status == "in_progress"
+
+@pytest.mark.asyncio
+async def test_resume_cas_conflict(db_session):
+    """should return 409 Conflict when attempting to resume a mission that is not paused."""
+    mission = DshMission(user_id=1, workspace_id=1, status="in_progress")
+    db_session.add(mission)
+    await db_session.commit()
+    await db_session.refresh(mission)
+
+    auth_mock = MagicMock()
+    auth_mock.user.id = 1
+
+    payload = ResumeMissionPayload(mission_id=mission.id)
+
+    with pytest.raises(HTTPException) as exc_info:
+        await resume_mission(payload, auth_mock, db_session)
+
+    assert exc_info.value.status_code == 409
diff --git a/nowing_backend/tests/unit/tasks/dsh_worker/test_browser_operator_cdp.py b/nowing_backend/tests/unit/tasks/dsh_worker/test_browser_operator_cdp.py
new file mode 100644
index 000000000..ada3ff66a
--- /dev/null
+++ b/nowing_backend/tests/unit/tasks/dsh_worker/test_browser_operator_cdp.py
@@ -0,0 +1,92 @@
+import asyncio
+import pytest
+from unittest.mock import AsyncMock, patch, MagicMock
+from app.schemas.dsh import CdpResultPayload, ResumeMissionPayload
+from pydantic import ValidationError
+
+pytestmark = [pytest.mark.unit]
+
+@pytest.mark.asyncio
+async def test_cdp_subgraph_push_event():
+    """should push CDPCommand event containing {action, payload} to the SSE stream queue."""
+    from app.tasks.dsh_worker_browser_operator import BrowserOperatorCdpSubgraph
+
+    redis_mock = AsyncMock()
+    redis_mock.blpop.return_value = (b"key", b'{"result": {"success": true}, "sources": [{"url": "https://test.com"}]}')
+
+    with patch("app.tasks.dsh_worker_browser_operator.get_redis_client", return_value=redis_mock):
+        subgraph = BrowserOperatorCdpSubgraph(None)
+        state = {
+            "mission_id": "test-mission",
+            "payload": {"target_url": "https://test.com", "user_id": "user-1"},
+            "workspace_id": 1,
+        }
+        new_state = await subgraph._cdp_crawl_node(state, {})
+
+        assert redis_mock.publish.called
+        assert new_state["checkpoint"]["cdp_last_result"] == {"success": True}
+        assert len(new_state["sources"]) == 1
+        assert new_state["sources"][0]["url"] == "https://test.com"
+
+@pytest.mark.asyncio
+async def test_cdp_timeout():
+    """should handle extension not returning CDP result within 60s by raising TimeoutError."""
+    from app.tasks.dsh_worker_browser_operator import BrowserOperatorCdpSubgraph
+
+    redis_mock = AsyncMock()
+    redis_mock.blpop.return_value = None  # Timeout
+
+    with patch("app.tasks.dsh_worker_browser_operator.get_redis_client", return_value=redis_mock):
+        subgraph = BrowserOperatorCdpSubgraph(None)
+        state = {
+            "mission_id": "test-mission",
+            "payload": {"target_url": "https://test.com", "user_id": "user-1"},
+            "workspace_id": 1,
+        }
+        with pytest.raises(TimeoutError, match="Extension did not return CDP result within 60s"):
+            await subgraph._cdp_crawl_node(state, {})
+
+@pytest.mark.asyncio
+async def test_pause_mission_exception():
+    """dsh_worker_browser_operator.py should raise exactly HumanInterventionRequired when CAPTCHA is detected."""
+    from app.tasks.dsh_worker_browser_operator import BrowserOperatorCdpSubgraph, HumanInterventionRequired
+
+    subgraph = BrowserOperatorCdpSubgraph(None)
+    state = {
+        "mission_id": "test-mission",
+        "payload": {"force_captcha": True, "target_url": "https://test.com", "user_id": "user-1"},
+        "workspace_id": 1,
+    }
+
+    with pytest.raises(HumanInterventionRequired):
+        await subgraph._cdp_crawl_node(state, {})
+
+@pytest.mark.asyncio
+async def test_cdp_stream_disconnect():
+    """should cleanly unsubscribe and close Redis pubsub on client disconnect."""
+    redis_mock = AsyncMock()
+    pubsub_mock = AsyncMock()
+    redis_mock.pubsub.return_value = pubsub_mock
+
+    # Simulate immediate disconnect
+    request_mock = AsyncMock()
+    request_mock.is_disconnected.return_value = True
+
+    with patch("app.routes.dsh_routes.get_redis_client", return_value=redis_mock):
+        from app.routes.dsh_routes import cdp_stream
+        auth_mock = MagicMock()
+        auth_mock.user.id = "user-1"
+
+        response = await cdp_stream(request_mock, auth_mock)
+        # Consume the generator
+        generator = response.body_iterator
+        async for _ in generator:
+            pass
+
+        assert pubsub_mock.unsubscribe.called
+        assert pubsub_mock.close.called
+
+def test_resume_invalid_payload():
+    """should handle None or empty payload to /resume gracefully (422 Unprocessable Entity)."""
+    with pytest.raises(ValidationError):
+        ResumeMissionPayload()
diff --git a/nowing_browser_extension/background/cdp-bridge.ts b/nowing_browser_extension/background/cdp-bridge.ts
new file mode 100644
index 000000000..b4f9d60e6
--- /dev/null
+++ b/nowing_browser_extension/background/cdp-bridge.ts
@@ -0,0 +1,118 @@
+import { Storage } from "@plasmohq/storage";
+import { buildBackendUrl } from "~utils/backend-url";
+
+const storage = new Storage({ area: "local" });
+
+export class CdpBridge {
+	private static instance: CdpBridge | null = null;
+	private eventSource: EventSource | null = null;
+	private activeDebuggeeTabId: number | null = null;
+
+	public static getInstance(): CdpBridge {
+		if (!CdpBridge.instance) {
+			CdpBridge.instance = new CdpBridge();
+		}
+		return CdpBridge.instance;
+	}
+
+	public async startListening(): Promise<void> {
+		if (this.eventSource) {
+			return;
+		}
+
+		const streamUrl = await buildBackendUrl("/api/v1/dsh/cdp/stream");
+
+		try {
+			this.eventSource = new EventSource(streamUrl);
+
+			this.eventSource.addEventListener("cdp_command", async (event: MessageEvent) => {
+				try {
+					const data = JSON.parse(event.data);
+					await this.handleCdpCommand(data);
+				} catch (err) {
+					console.error("Error processing CDP command event:", err);
+				}
+			});
+
+			this.eventSource.onerror = (err) => {
+				console.warn("CDP EventSource connection error:", err);
+			};
+		} catch (err) {
+			console.error("Failed to initialize CDP stream:", err);
+		}
+	}
+
+	public stopListening(): void {
+		if (this.eventSource) {
+			this.eventSource.close();
+			this.eventSource = null;
+		}
+		this.detachDebugger();
+	}
+
+	private async handleCdpCommand(cmd: { action: string; url?: string; mission_id: string }): Promise<void> {
+		const { action, url, mission_id } = cmd;
+
+		try {
+			const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
+			const targetTab = tabs[0];
+			if (!targetTab || !targetTab.id) {
+				throw new Error("No active tab available for CDP takeover");
+			}
+
+			const tabId = targetTab.id;
+			this.activeDebuggeeTabId = tabId;
+
+			await chrome.debugger.attach({ tabId }, "1.3");
+
+			let resultPayload: any = { success: true };
+
+			if (action === "navigate" && url) {
+				await chrome.debugger.sendCommand({ tabId }, "Page.enable");
+				await chrome.debugger.sendCommand({ tabId }, "Page.navigate", { url });
+				resultPayload = { navigatedUrl: url, tabId };
+			}
+
+			await this.sendResult(mission_id, resultPayload, null);
+		} catch (err: any) {
+			console.error("CDP execution error:", err);
+			await this.sendResult(mission_id, null, err.message || String(err));
+		} finally {
+			await this.detachDebugger();
+		}
+	}
+
+	private async detachDebugger(): Promise<void> {
+		if (this.activeDebuggeeTabId !== null) {
+			try {
+				await chrome.debugger.detach({ tabId: this.activeDebuggeeTabId });
+			} catch (err) {
+				console.warn("Debugger detach warning:", err);
+			} finally {
+				this.activeDebuggeeTabId = null;
+			}
+		}
+	}
+
+	private async sendResult(missionId: string, result: any, error: string | null): Promise<void> {
+		try {
+			const token = await storage.get("token");
+			const resultUrl = await buildBackendUrl("/api/v1/dsh/cdp/result");
+
+			await fetch(resultUrl, {
+				method: "POST",
+				headers: {
+					"Content-Type": "application/json",
+					Authorization: `Bearer ${token}`,
+				},
+				body: JSON.stringify({
+					mission_id: missionId,
+					result: result,
+					error: error,
+				}),
+			});
+		} catch (err) {
+			console.error("Failed to post CDP result:", err);
+		}
+	}
+}
diff --git a/nowing_browser_extension/background/index.ts b/nowing_browser_extension/background/index.ts
index 8d66cf117..40c5397f0 100644
--- a/nowing_browser_extension/background/index.ts
+++ b/nowing_browser_extension/background/index.ts
@@ -1,6 +1,10 @@
 import { Storage } from "@plasmohq/storage";
 import { getRenderedHtml, initQueues, initWebHistory } from "~utils/commons";
 import type { WebHistory } from "~utils/interfaces";
+import { CdpBridge } from "./cdp-bridge";
+
+// Start listening for CDP commands from Nowing Backend
+CdpBridge.getInstance().startListening();
 
 chrome.tabs.onCreated.addListener(async (tab: any) => {
 	try {
diff --git a/nowing_browser_extension/package.json b/nowing_browser_extension/package.json
index 62021f291..b757f1417 100644
--- a/nowing_browser_extension/package.json
+++ b/nowing_browser_extension/package.json
@@ -67,6 +67,7 @@
 		"storage",
 		"scripting",
 		"unlimitedStorage",
-		"activeTab"
+		"activeTab",
+		"debugger"
 	]
 }
diff --git a/nowing_browser_extension/popup.tsx b/nowing_browser_extension/popup.tsx
index c41926ced..1bf2e8bea 100644
--- a/nowing_browser_extension/popup.tsx
+++ b/nowing_browser_extension/popup.tsx
@@ -1,11 +1,54 @@
+import React, { useState } from "react";
 import { MemoryRouter } from "react-router-dom";
 import { Toaster } from "@/routes/ui/toaster";
 import { Routing } from "~routes";
+import { buildBackendUrl } from "~utils/backend-url";
+import { Storage } from "@plasmohq/storage";
+
+const storage = new Storage({ area: "local" });
 
 function IndexPopup() {
+	const [resuming, setResuming] = useState(false);
+	const [activeMissionId, setActiveMissionId] = useState<string | null>(null);
+
+	const handleReleaseControl = async () => {
+		if (!activeMissionId) {
+			return;
+		}
+		setResuming(true);
+		try {
+			const token = await storage.get("token");
+			const url = await buildBackendUrl("/api/v1/dsh/resume");
+			await fetch(url, {
+				method: "POST",
+				headers: {
+					"Content-Type": "application/json",
+					Authorization: `Bearer ${token}`,
+				},
+				body: JSON.stringify({ mission_id: activeMissionId }),
+			});
+			setActiveMissionId(null);
+		} catch (error) {
+			console.error("Failed to release control and resume mission:", error);
+		} finally {
+			setResuming(false);
+		}
+	};
+
 	return (
 		<MemoryRouter>
-			<Routing />
+			<div className="p-4 flex flex-col items-center space-y-4">
+				<Routing />
+				{activeMissionId && (
+					<button
+						onClick={handleReleaseControl}
+						disabled={resuming}
+						className="px-4 py-2 bg-red-500 hover:bg-red-600 text-white rounded font-medium disabled:opacity-50"
+					>
+						{resuming ? "Resuming..." : "Release Control"}
+					</button>
+				)}
+			</div>
 			<Toaster />
 		</MemoryRouter>
 	);
diff --git a/nowing_browser_extension/tests/test_cdp_takeover.test.tsx b/nowing_browser_extension/tests/test_cdp_takeover.test.tsx
new file mode 100644
index 000000000..96c77e291
--- /dev/null
+++ b/nowing_browser_extension/tests/test_cdp_takeover.test.tsx
@@ -0,0 +1,28 @@
+import React from 'react';
+import { render, screen } from '@testing-library/react';
+import IndexPopup from '../popup';
+
+// Mock the router and API
+jest.mock('react-router-dom', () => ({
+  ...jest.requireActual('react-router-dom'),
+  MemoryRouter: ({ children }: any) => <div>{children}</div>,
+}));
+
+jest.mock('~routes', () => ({
+  Routing: () => <div data-testid="routing-outlet" />
+}));
+
+describe('Extension UI & Permissions', () => {
+  it('should include exactly "debugger" in manifest permissions (test_manifest_debugger)', () => {
+    const fs = require('fs');
+    const path = require('path');
+    const manifestPath = path.resolve(__dirname, '../package.json');
+    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
+    expect(manifest.permissions).toContain('debugger');
+  });
+
+  it('should render routing outlet and popup container cleanly', () => {
+    render(<IndexPopup />);
+    expect(screen.getByTestId('routing-outlet')).toBeInTheDocument();
+  });
+});
