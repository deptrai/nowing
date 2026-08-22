"""REST routes for Sequence Bounded Context (Story 24.1 / AD-39 / AD-41 / AD-43)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.context import AuthContext
from app.db import (
    Sequence,
    SequenceEnrollment,
    SequenceEvent,
    SequenceStep,
    get_async_session,
)
from app.schemas.sequence import (
    ChannelBreakdown,
    SequenceAnalyticsResponse,
    SequenceCreate,
    SequenceDetailRead,
    SequenceEnrollmentRead,
    SequenceEnrollRequest,
    SequenceEventRead,
    SequenceRead,
    SequenceUpdate,
)
from app.services.sequencer_service import (
    DeferredChannelError,
    SequencerService,
)
from app.tenant_context import set_request_tenant_context
from app.users import get_auth_context
from app.utils.rbac import check_workspace_access

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/workspaces/{workspace_id}/sequences",
    tags=["sequences"],
)


@router.post("", response_model=SequenceDetailRead, status_code=status.HTTP_201_CREATED)
async def create_sequence(
    workspace_id: int,
    payload: SequenceCreate,
    session: AsyncSession = Depends(get_async_session),
    auth_ctx: AuthContext = Depends(get_auth_context),
) -> SequenceDetailRead:
    """Create a new outreach Sequence with ordered steps (AD-39, AD-41)."""
    await check_workspace_access(session, auth_ctx, workspace_id)
    await set_request_tenant_context(session, workspace_id=workspace_id)

    sequencer = SequencerService()

    # Validate channels for each step, duplicate step_order, and entry_step_order
    step_orders = [s.step_order for s in payload.steps]
    if len(step_orders) != len(set(step_orders)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="step_order values must be unique within a sequence",
        )
    if payload.steps and payload.entry_step_order not in step_orders:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="entry_step_order must match one of the provided step_order values",
        )
    for s in payload.steps:
        try:
            await sequencer.validate_step_channel(s.channel)
        except DeferredChannelError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

    sequence = Sequence(
        id=uuid4(),
        workspace_id=workspace_id,
        client_id=getattr(auth_ctx.user, "client_id", None) or "default",
        name=payload.name,
        description=payload.description,
        status=payload.status,
        shared=payload.shared,
        created_by_user_id=auth_ctx.user.id,
        entry_step_order=payload.entry_step_order,
        created_at=datetime.now(UTC),
    )
    session.add(sequence)
    await session.flush()

    for step_data in payload.steps:
        step = SequenceStep(
            id=uuid4(),
            workspace_id=workspace_id,
            client_id=getattr(auth_ctx.user, "client_id", None) or "default",
            sequence_id=sequence.id,
            step_order=step_data.step_order,
            step_type=step_data.step_type,
            channel=step_data.channel,
            fallback_channels=step_data.fallback_channels or [],
            template=step_data.template,
            wait_duration_seconds=step_data.wait_duration_seconds,
            condition_config=step_data.condition_config,
            is_enabled=step_data.is_enabled,
            created_at=datetime.now(UTC),
        )
        session.add(step)
        await session.flush()

    await session.commit()
    stmt = select(Sequence).where(Sequence.id == sequence.id, Sequence.workspace_id == workspace_id).options(selectinload(Sequence.steps))
    sequence = (await session.execute(stmt)).scalar_one()

    res = SequenceDetailRead.model_validate(sequence)
    return res


@router.get("", response_model=list[SequenceRead])
async def list_sequences(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth_ctx: AuthContext = Depends(get_auth_context),
) -> list[SequenceRead]:
    """List all sequences in the workspace."""
    await check_workspace_access(session, auth_ctx, workspace_id)
    await set_request_tenant_context(session, workspace_id=workspace_id)

    stmt = (
        select(Sequence)
        .where(
            Sequence.workspace_id == workspace_id,
            Sequence.status != "archived",
        )
        .order_by(Sequence.created_at.desc())
    )
    results = (await session.execute(stmt)).scalars().all()
    return [SequenceRead.model_validate(s) for s in results]


@router.get("/{sequence_id}", response_model=SequenceDetailRead)
async def get_sequence(
    workspace_id: int,
    sequence_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth_ctx: AuthContext = Depends(get_auth_context),
) -> SequenceDetailRead:
    """Get sequence details including all configured steps."""
    await check_workspace_access(session, auth_ctx, workspace_id)
    await set_request_tenant_context(session, workspace_id=workspace_id)

    sequence = (
        await session.execute(
            select(Sequence)
            .where(
                Sequence.id == sequence_id,
                Sequence.workspace_id == workspace_id,
            )
            .options(selectinload(Sequence.steps))
        )
    ).scalar_one_or_none()
    if not sequence:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sequence not found")

    return SequenceDetailRead.model_validate(sequence)


@router.put("/{sequence_id}", response_model=SequenceDetailRead)
async def update_sequence(
    workspace_id: int,
    sequence_id: UUID,
    payload: SequenceUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth_ctx: AuthContext = Depends(get_auth_context),
) -> SequenceDetailRead:
    """Update sequence name, description, status, and/or replace steps."""
    await check_workspace_access(session, auth_ctx, workspace_id)
    await set_request_tenant_context(session, workspace_id=workspace_id)

    sequence = (
        await session.execute(
            select(Sequence).where(
                Sequence.id == sequence_id,
                Sequence.workspace_id == workspace_id,
            )
        )
    ).scalar_one_or_none()
    if not sequence:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sequence not found")

    if payload.name is not None:
        sequence.name = payload.name
    if payload.description is not None:
        sequence.description = payload.description
    if payload.status is not None:
        sequence.status = payload.status
    if payload.shared is not None:
        sequence.shared = payload.shared
    if payload.entry_step_order is not None:
        sequence.entry_step_order = payload.entry_step_order

    sequencer = SequencerService()

    if payload.steps is not None:
        # Validate all new steps
        step_orders = [s.step_order for s in payload.steps]
        if len(step_orders) != len(set(step_orders)):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="step_order values must be unique within a sequence",
            )
        if payload.entry_step_order is not None and payload.entry_step_order not in step_orders:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="entry_step_order must match one of the provided step_order values",
            )
        for s in payload.steps:
            try:
                await sequencer.validate_step_channel(s.channel)
            except DeferredChannelError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(exc),
                ) from exc

        # Remove existing steps
        existing_steps = (
            await session.execute(
                select(SequenceStep).where(
                    SequenceStep.sequence_id == sequence_id,
                    SequenceStep.workspace_id == workspace_id,
                )
            )
        ).scalars().all()
        for es in existing_steps:
            await session.delete(es)
        await session.flush()

        # Insert new steps
        for step_data in payload.steps:
            step = SequenceStep(
                workspace_id=workspace_id,
                client_id=getattr(auth_ctx.user, "client_id", None) or "default",
                sequence_id=sequence.id,
                step_order=step_data.step_order,
                step_type=step_data.step_type,
                channel=step_data.channel,
                fallback_channels=step_data.fallback_channels or [],
                template=step_data.template,
                wait_duration_seconds=step_data.wait_duration_seconds,
                condition_config=step_data.condition_config,
                is_enabled=step_data.is_enabled,
            )
            session.add(step)

    await session.commit()
    sequence = (
        await session.execute(
            select(Sequence)
            .where(
                Sequence.id == sequence_id,
                Sequence.workspace_id == workspace_id,
            )
            .options(selectinload(Sequence.steps))
        )
    ).scalar_one()

    return SequenceDetailRead.model_validate(sequence)


@router.delete("/{sequence_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sequence(
    workspace_id: int,
    sequence_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth_ctx: AuthContext = Depends(get_auth_context),
) -> None:
    """Soft-delete / archive a sequence."""
    await check_workspace_access(session, auth_ctx, workspace_id)
    await set_request_tenant_context(session, workspace_id=workspace_id)

    sequence = (
        await session.execute(
            select(Sequence).where(
                Sequence.id == sequence_id,
                Sequence.workspace_id == workspace_id,
            )
        )
    ).scalar_one_or_none()
    if not sequence:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sequence not found")

    sequence.status = "archived"
    await session.commit()


@router.post("/{sequence_id}/enroll", response_model=list[SequenceEnrollmentRead])
async def enroll_leads(
    workspace_id: int,
    sequence_id: UUID,
    payload: SequenceEnrollRequest,
    session: AsyncSession = Depends(get_async_session),
    auth_ctx: AuthContext = Depends(get_auth_context),
) -> list[SequenceEnrollmentRead]:
    """Enroll leads into the outreach sequence after validating consent (AC-4 / AD-25)."""
    await check_workspace_access(session, auth_ctx, workspace_id)
    await set_request_tenant_context(session, workspace_id=workspace_id)

    sequencer = SequencerService()
    try:
        enrollments = await sequencer.enroll_leads(
            session=session,
            workspace_id=workspace_id,
            sequence_id=sequence_id,
            lead_ids=payload.lead_ids,
            user_id=auth_ctx.user.id,
        )
        await session.commit()
        return [SequenceEnrollmentRead.model_validate(e) for e in enrollments]
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{sequence_id}/pause", response_model=SequenceRead)
async def pause_sequence(
    workspace_id: int,
    sequence_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth_ctx: AuthContext = Depends(get_auth_context),
) -> SequenceRead:
    """Pause an active sequence."""
    await check_workspace_access(session, auth_ctx, workspace_id)
    await set_request_tenant_context(session, workspace_id=workspace_id)
    sequence = await session.get(Sequence, (sequence_id, workspace_id))
    if not sequence:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sequence not found")
    sequence.status = "paused"
    await session.commit()
    await session.refresh(sequence)
    return SequenceRead.model_validate(sequence)


@router.post("/{sequence_id}/resume", response_model=SequenceRead)
async def resume_sequence(
    workspace_id: int,
    sequence_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth_ctx: AuthContext = Depends(get_auth_context),
) -> SequenceRead:
    """Resume a paused sequence."""
    await check_workspace_access(session, auth_ctx, workspace_id)
    await set_request_tenant_context(session, workspace_id=workspace_id)
    sequence = await session.get(Sequence, (sequence_id, workspace_id))
    if not sequence:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sequence not found")
    sequence.status = "active"
    await session.commit()
    await session.refresh(sequence)
    return SequenceRead.model_validate(sequence)


@router.get("/{sequence_id}/analytics", response_model=SequenceAnalyticsResponse)
async def get_sequence_analytics(
    workspace_id: int,
    sequence_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth_ctx: AuthContext = Depends(get_auth_context),
) -> SequenceAnalyticsResponse:
    """Get real-time aggregated metrics for a sequence (AC-8)."""
    await check_workspace_access(session, auth_ctx, workspace_id)
    await set_request_tenant_context(session, workspace_id=workspace_id)

    sequencer = SequencerService()
    metrics = await sequencer.get_sequence_analytics(session, workspace_id, sequence_id)

    return SequenceAnalyticsResponse(
        sequence_id=sequence_id,
        total_enrolled=metrics.total_enrolled,
        active_scheduled=metrics.active_scheduled,
        delivered_count=metrics.delivered_count,
        responded_count=metrics.responded_count,
        unsubscribed_count=metrics.unsubscribed_count,
        failed_count=metrics.failed_count,
        total_cost_micros=metrics.total_cost_micros,
        channel_breakdown=[
            ChannelBreakdown(
                channel=cb.channel,
                sent=cb.sent,
                delivered=cb.delivered,
                opened=cb.opened,
                replied=cb.replied,
                bounced=cb.bounced,
                failed=cb.failed,
                skipped=cb.skipped,
                cost_micros=cb.cost_micros,
            )
            for cb in metrics.channel_breakdown
        ],
    )


@router.get("/{sequence_id}/enrollments", response_model=list[SequenceEnrollmentRead])
async def list_sequence_enrollments(
    workspace_id: int,
    sequence_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth_ctx: AuthContext = Depends(get_auth_context),
) -> list[SequenceEnrollmentRead]:
    """List all lead enrollments for a sequence."""
    await check_workspace_access(session, auth_ctx, workspace_id)
    await set_request_tenant_context(session, workspace_id=workspace_id)

    stmt = (
        select(SequenceEnrollment)
        .where(
            SequenceEnrollment.sequence_id == sequence_id,
            SequenceEnrollment.workspace_id == workspace_id,
        )
        .order_by(SequenceEnrollment.created_at.desc())
    )
    results = (await session.execute(stmt)).scalars().all()
    return [SequenceEnrollmentRead.model_validate(e) for e in results]


@router.get("/{sequence_id}/events", response_model=list[SequenceEventRead])
async def list_sequence_events(
    workspace_id: int,
    sequence_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth_ctx: AuthContext = Depends(get_auth_context),
) -> list[SequenceEventRead]:
    """List all delivery and interaction events for a sequence."""
    await check_workspace_access(session, auth_ctx, workspace_id)
    await set_request_tenant_context(session, workspace_id=workspace_id)

    stmt = (
        select(SequenceEvent)
        .where(
            SequenceEvent.sequence_id == sequence_id,
            SequenceEvent.workspace_id == workspace_id,
        )
        .order_by(SequenceEvent.created_at.desc())
    )
    results = (await session.execute(stmt)).scalars().all()
    return [SequenceEventRead.model_validate(e) for e in results]
