"""Admin routes for anti-bot / CAPTCHA screenshot escalations.

Apache-2.0. Platform and workspace admins can list, inspect, resolve, and retry
escalations created when a scraper capability hits an anti-bot block.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.core.async_runner import start_async_run
from app.capabilities.core.store import get_capability
from app.db import AntiBotEscalation, Run, get_async_session
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
from app.users import require_superuser

router = APIRouter(prefix="/admin/anti-bot-escalations")
logger = logging.getLogger(__name__)


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
    _auth=Depends(require_superuser),
) -> AntiBotEscalationListResponse:
    """List escalations with optional filters."""
    filters: list = []
    if workspace_id is not None:
        filters.append(AntiBotEscalation.workspace_id == workspace_id)
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
    _auth=Depends(require_superuser),
) -> AntiBotEscalation:
    escalation = await get_escalation(session, escalation_id)
    if escalation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Escalation not found",
        )
    return escalation


@router.post("/{escalation_id}/resolve", response_model=AntiBotEscalationRead)
async def resolve_anti_bot_escalation(
    escalation_id: int,
    body: AntiBotEscalationResolveRequest | None = None,
    session: AsyncSession = Depends(get_async_session),
    _auth=Depends(require_superuser),
) -> AntiBotEscalation:
    user_id = body.user_id if body else None
    escalation = await resolve_escalation(session, escalation_id, user_id=user_id)
    if escalation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Escalation not found",
        )
    await session.commit()
    return escalation


@router.post("/{escalation_id}/retry", response_model=AntiBotEscalationRetryResponse)
async def retry_anti_bot_escalation(
    escalation_id: int,
    session: AsyncSession = Depends(get_async_session),
    _auth=Depends(require_superuser),
) -> AntiBotEscalationRetryResponse:
    escalation = await get_escalation(session, escalation_id)
    if escalation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Escalation not found",
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
    escalation.escalation_metadata = escalation_metadata

    await session.commit()

    return AntiBotEscalationRetryResponse(
        id=escalation.id,
        status=escalation.status,
        retry_run_id=retry_run_id,
        message=message,
    )
