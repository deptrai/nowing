"""REST routes for intent signal detection (Story 21.1)."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import (
    Permission,
    SignalEvent,
    Workspace,
    get_async_session,
)
from app.lead_intelligence.signals.schemas import (
    SignalDetectInput,
    SignalEventRead,
    SignalInput,
    SignalListResponse,
    SignalOutput,
)
from app.lead_intelligence.signals.service import SIGNAL_TYPES, SignalDetectionService
from app.users import get_auth_context
from app.utils.rbac import check_permission

router = APIRouter()


async def require_workspace_member(
    session: AsyncSession,
    auth: AuthContext,
    workspace_id: int,
) -> AuthContext:
    """Ensure the caller is a member of the workspace."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.FULL_ACCESS.value,
        error_message="You don't have access to this workspace",
    )
    return auth


@router.post(
    "/{workspace_id}/signals/detect",
    response_model=SignalOutput,
    status_code=status.HTTP_200_OK,
)
async def detect_signals(
    workspace_id: int,
    body: SignalDetectInput,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> SignalOutput:
    """Run a one-time signal detection for a company."""
    await require_workspace_member(session, auth, workspace_id)

    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    if body.signal_type not in SIGNAL_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown signal_type: {body.signal_type}",
        )

    client_id = auth.pat.client_id if auth.pat is not None else None
    ctx = SimpleNamespace(
        session=session,
        workspace_id=workspace_id,
        run_id=None,
        client_id=client_id,
        user_id=auth.user.id,
    )
    service = SignalDetectionService()
    signal_input = SignalInput(
        company_name=body.company_name,
        domain=body.domain,
        lookback_days=body.lookback_days,
        confidence_threshold=body.confidence_threshold,
        signal_types=body.signal_types,
    )
    return await service.detect(
        session,
        ctx,
        signal_input,
        body.signal_type,
    )


@router.get(
    "/{workspace_id}/signals",
    response_model=SignalListResponse,
)
async def list_signals(
    workspace_id: int,
    signal_type: str | None = None,
    company_name: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    confidence_min: float = Query(default=0.0, ge=0.0, le=100.0),
    sort: str = Query(default="detected_at_desc"),
    limit: int = Query(default=20, ge=1),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> SignalListResponse:
    """List signal events for a workspace."""
    await require_workspace_member(session, auth, workspace_id)

    if limit > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="limit exceeds max 100",
        )
    if from_date is not None and to_date is not None and from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from_date must be before to_date",
        )

    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    stmt: Select = select(SignalEvent).where(SignalEvent.workspace_id == workspace_id)
    count_stmt = select(func.count(SignalEvent.id)).where(
        SignalEvent.workspace_id == workspace_id
    )

    if signal_type is not None:
        stmt = stmt.where(SignalEvent.signal_type == signal_type)
        count_stmt = count_stmt.where(SignalEvent.signal_type == signal_type)
    if company_name is not None:
        stmt = stmt.where(SignalEvent.company_name.ilike(f"%{company_name}%"))
        count_stmt = count_stmt.where(
            SignalEvent.company_name.ilike(f"%{company_name}%")
        )
    if from_date is not None:
        stmt = stmt.where(SignalEvent.detected_at >= from_date)
        count_stmt = count_stmt.where(SignalEvent.detected_at >= from_date)
    if to_date is not None:
        stmt = stmt.where(SignalEvent.detected_at <= to_date)
        count_stmt = count_stmt.where(SignalEvent.detected_at <= to_date)
    if confidence_min > 0:
        stmt = stmt.where(SignalEvent.confidence >= confidence_min)
        count_stmt = count_stmt.where(SignalEvent.confidence >= confidence_min)

    if sort == "detected_at_asc":
        stmt = stmt.order_by(SignalEvent.detected_at)
    elif sort == "confidence_desc":
        stmt = stmt.order_by(desc(SignalEvent.confidence))
    elif sort == "confidence_asc":
        stmt = stmt.order_by(SignalEvent.confidence)
    else:
        stmt = stmt.order_by(desc(SignalEvent.detected_at))

    stmt = stmt.offset(offset).limit(limit)

    rows = list((await session.execute(stmt)).scalars().all())
    total = (await session.execute(count_stmt)).scalar() or 0

    return SignalListResponse(
        items=[SignalEventRead.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{workspace_id}/signals/{signal_id}",
    response_model=SignalEventRead,
)
async def get_signal(
    workspace_id: int,
    signal_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> SignalEventRead:
    """Return a single signal event by ID."""
    await require_workspace_member(session, auth, workspace_id)

    row = (
        await session.execute(
            select(SignalEvent).where(
                SignalEvent.workspace_id == workspace_id,
                SignalEvent.id == signal_id,
            )
        )
    ).scalar_one_or_none()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signal not found",
        )

    return SignalEventRead.model_validate(row)
