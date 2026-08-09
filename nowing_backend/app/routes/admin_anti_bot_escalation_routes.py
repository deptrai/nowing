"""Admin routes for anti-bot / CAPTCHA screenshot escalations.

Apache-2.0. Platform and workspace admins can list, inspect, resolve, and retry
escalations created when a scraper capability hits an anti-bot block.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.context import AuthContext
from app.capabilities.core.async_runner import start_async_run
from app.capabilities.core.store import get_capability
from app.db import (
    AntiBotEscalation,
    Run,
    WorkspaceMembership,
    WorkspaceRole,
    get_async_session,
)
from app.file_storage.factory import get_storage_backend
from app.schemas.anti_bot_escalation import (
    AntiBotEscalationListResponse,
    AntiBotEscalationRead,
    AntiBotEscalationResolveRequest,
    AntiBotEscalationRetryResponse,
)
from app.services.anti_bot_escalation import (
    get_escalation,
    list_escalations,
    resolve_escalation,
)
from app.users import get_auth_context

router = APIRouter(prefix="/admin/anti-bot-escalations")
logger = logging.getLogger(__name__)


async def _has_workspace_admin_access(
    session: AsyncSession,
    auth: AuthContext,
    workspace_id: int,
) -> bool:
    """Return True if the principal is superuser, workspace owner, or editor."""
    if auth.user.is_superuser:
        return True
    membership = await session.execute(
        select(WorkspaceMembership)
        .where(
            WorkspaceMembership.user_id == auth.user.id,
            WorkspaceMembership.workspace_id == workspace_id,
        )
        .options(selectinload(WorkspaceMembership.role))
    )
    membership = membership.scalar_one_or_none()
    if membership is None:
        return False
    return membership.is_owner or (
        membership.role is not None and membership.role.name in {"Owner", "Editor"}
    )


async def _admin_workspace_ids(
    session: AsyncSession,
    auth: AuthContext,
) -> list[int]:
    """Return workspace ids the principal can admin."""
    if auth.user.is_superuser:
        return []
    result = await session.execute(
        select(WorkspaceMembership.workspace_id)
        .where(WorkspaceMembership.user_id == auth.user.id)
        .join(WorkspaceMembership.role)
        .where(
            (WorkspaceMembership.is_owner.is_(True))
            | (WorkspaceRole.name.in_(["Owner", "Editor"]))
        )
    )
    return list(result.scalars().all())


async def _to_read(escalation: AntiBotEscalation) -> AntiBotEscalationRead:
    return AntiBotEscalationRead.model_validate(escalation)


@router.get("", response_model=AntiBotEscalationListResponse)
async def list_anti_bot_escalations(
    workspace_id: int | None = Query(None),
    domain: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> AntiBotEscalationListResponse:
    """List escalations with optional filters."""
    admin_workspace_ids: list[int] = []
    if workspace_id is not None:
        if not await _has_workspace_admin_access(session, auth, workspace_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this workspace",
            )
    elif not auth.user.is_superuser:
        admin_workspace_ids = await _admin_workspace_ids(session, auth)
        if not admin_workspace_ids:
            return AntiBotEscalationListResponse(items=[], total=0)

    filters: list = []
    if workspace_id is not None:
        filters.append(AntiBotEscalation.workspace_id == workspace_id)
    elif admin_workspace_ids:
        filters.append(AntiBotEscalation.workspace_id.in_(admin_workspace_ids))
    if domain is not None:
        filters.append(AntiBotEscalation.domain == domain)
    if status is not None:
        filters.append(AntiBotEscalation.status == status)

    total_result = await session.execute(
        select(func.count(AntiBotEscalation.id)).where(*filters)
    )
    total = total_result.scalar() or 0

    items = await list_escalations(
        session,
        workspace_id=workspace_id,
        domain=domain,
        status=status,
        limit=limit,
        offset=offset,
    )
    return AntiBotEscalationListResponse(
        items=[await _to_read(item) for item in items],
        total=total,
    )


@router.get("/{escalation_id}", response_model=AntiBotEscalationRead)
async def get_anti_bot_escalation(
    escalation_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> AntiBotEscalation:
    escalation = await get_escalation(session, escalation_id)
    if escalation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Escalation not found",
        )
    if not await _has_workspace_admin_access(session, auth, escalation.workspace_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this escalation",
        )
    return escalation


@router.post("/{escalation_id}/resolve", response_model=AntiBotEscalationRead)
async def resolve_anti_bot_escalation(
    escalation_id: int,
    body: AntiBotEscalationResolveRequest | None = None,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> AntiBotEscalation:
    escalation = await get_escalation(session, escalation_id)
    if escalation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Escalation not found",
        )
    if not await _has_workspace_admin_access(session, auth, escalation.workspace_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this escalation",
        )
    # Audit trail uses the authenticated principal, not the optional body field.
    user_id = body.user_id if body and body.user_id else auth.user.id
    escalation = await resolve_escalation(session, escalation_id, user_id=user_id)
    await session.commit()
    return escalation


@router.post("/{escalation_id}/retry", response_model=AntiBotEscalationRetryResponse)
async def retry_anti_bot_escalation(
    escalation_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> AntiBotEscalationRetryResponse:
    escalation = await get_escalation(session, escalation_id)
    if escalation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Escalation not found",
        )
    if not await _has_workspace_admin_access(session, auth, escalation.workspace_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this escalation",
        )

    escalation.status = "retry"
    retry_run_id: str | None = None
    message = "Retry requested; run will be re-enqueued."

    run = await session.get(Run, escalation.run_id)
    if run is None:
        message = "Retry requested but original run not found."
    else:
        try:
            capability = get_capability(run.capability)
            input_data = run.input or {}
            payload = capability.input_schema(**input_data)
            retry_run_id = await start_async_run(
                session=session,
                workspace_id=run.workspace_id,
                capability=capability,
                payload=payload,
                origin="retry",
                user_id=run.user_id,
                thread_id=run.thread_id,
                parent_run_id=escalation.run_id,
            )
            if retry_run_id is None:
                message = "Retry requested but run could not be scheduled."
            else:
                message = f"Retry scheduled as run_{retry_run_id}."
        except (KeyError, ValidationError, TypeError) as exc:
            logger.warning(
                "Could not retry escalation %s for capability %s: %s",
                escalation_id,
                run.capability,
                exc,
            )
            message = (
                "Retry requested but could not be enqueued; "
                "manual re-run may be required."
            )
        except Exception as exc:
            logger.exception("Retry failed for escalation %s", escalation_id)
            message = f"Retry scheduling failed: {exc}"

    escalation_metadata = (
        dict(escalation.escalation_metadata) if escalation.escalation_metadata else {}
    )
    if retry_run_id is not None:
        escalation_metadata["retry_run_id"] = retry_run_id
    else:
        escalation_metadata["retry_error"] = message
    escalation_metadata["retried_by"] = str(auth.user.id)
    escalation_metadata["retried_at"] = datetime.now(UTC).isoformat()
    escalation.escalation_metadata = escalation_metadata

    logger.info(
        "Anti-bot escalation retried: escalation_id=%s user_id=%s retry_run_id=%s",
        escalation_id,
        auth.user.id,
        retry_run_id,
    )

    await session.commit()

    return AntiBotEscalationRetryResponse(
        id=escalation.id,
        status=escalation.status,
        retry_run_id=retry_run_id,
        message=message,
    )


@router.get("/{escalation_id}/screenshot")
async def get_anti_bot_escalation_screenshot(
    escalation_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> StreamingResponse:
    """Stream the screenshot for an escalation. RBAC-protected admin-only path."""
    escalation = await get_escalation(session, escalation_id)
    if escalation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Escalation not found",
        )
    if not await _has_workspace_admin_access(session, auth, escalation.workspace_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this escalation",
        )

    escalation_metadata = escalation.escalation_metadata or {}
    storage_key = escalation_metadata.get("storage_key")
    if not storage_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No screenshot stored for this escalation",
        )

    async def _stream() -> AsyncIterator[bytes]:
        backend = get_storage_backend()
        async for chunk in backend.open_stream(storage_key):
            yield chunk

    return StreamingResponse(
        _stream(),
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="escalation_{escalation_id}.png"'
        },
    )
