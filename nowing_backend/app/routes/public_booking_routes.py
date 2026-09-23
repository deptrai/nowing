"""Public (unauthenticated) meeting-booking endpoints (Story 37.3).

These back the prospect-facing ``/book/{workspace_id}/{lead_id}`` page that
auto-reply sends after negotiation escalation.  The unguessable lead UUID in
the URL is the capability - knowing it grants booking rights for that lead
only, mirroring how external schedulers (Calendly) treat share links.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Lead, get_async_session
from app.rate_limiter import limiter
from app.redis_client import get_redis_client
from app.schemas.lead_pipeline import (
    MeetingBookRequest,
    MeetingBookResponse,
    MeetingSlotProposal,
    MeetingSlotsResponse,
)
from app.tenant_context import set_request_tenant_context

router = APIRouter(prefix="/public/book", tags=["public-booking"])


async def _get_public_lead(
    session: AsyncSession, workspace_id: int, lead_id: UUID
) -> Lead:
    """Fetch the lead scoped to the URL's workspace; 404 hides existence."""
    await set_request_tenant_context(
        session, workspace_id=workspace_id, is_lead_admin="true"
    )
    lead = await session.get(Lead, (lead_id, workspace_id))
    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Booking link invalid"
        )
    return lead


@router.get(
    "/{workspace_id}/{lead_id}/slots",
    response_model=MeetingSlotsResponse,
)
@limiter.limit("10/minute")
async def list_public_slots(
    request: Request,
    workspace_id: int,
    lead_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    redis_client: Any = Depends(get_redis_client),
) -> MeetingSlotsResponse:
    """Free ICT slots for the workspace calendar, minus soft-locked ones."""
    await _get_public_lead(session, workspace_id, lead_id)

    from app.services.meeting_booking import (
        CalendarAvailabilityService,
        MeetingBookingService,
        select_proposals,
    )

    availability = CalendarAvailabilityService(session)
    free, credentials = await availability.compute_availability(workspace_id)
    if not credentials:
        return MeetingSlotsResponse(slots=[], provider=None)
    owner_id = MeetingBookingService.pick_owner_credential(
        credentials, None
    ).user_id
    proposals = select_proposals(free, count=10)

    available: list[Any] = []
    for slot in proposals:
        key = MeetingBookingService.slot_lock_key(owner_id, slot)
        try:
            if await redis_client.exists(key):
                continue
        except Exception:
            continue  # fail closed: don't advertise a possibly-locked slot
        available.append(slot)

    return MeetingSlotsResponse(
        slots=[
            MeetingSlotProposal(start=s.start, end=s.end, label=s.label_ict())
            for s in available
        ],
        provider=credentials[0].provider,
    )


@router.post(
    "/{workspace_id}/{lead_id}/book",
    response_model=MeetingBookResponse,
)
@limiter.limit("5/minute")
async def book_public_slot(
    request: Request,
    workspace_id: int,
    lead_id: UUID,
    payload: MeetingBookRequest,
    session: AsyncSession = Depends(get_async_session),
) -> MeetingBookResponse:
    """Book a slot for the lead; same lock/create flow as the CRM route."""
    lead = await _get_public_lead(session, workspace_id, lead_id)

    from app.services.meeting_booking import (
        MEETING_SCHEDULED_STATUS,
        CalendarSlot,
        MeetingBookingService,
    )

    service = MeetingBookingService(session)
    credentials = await service.availability.resolve_credentials(workspace_id)
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Calendar not available",
        )
    owner_id = MeetingBookingService.pick_owner_credential(
        credentials, None
    ).user_id

    slot = CalendarSlot(
        start=payload.start,
        end=payload.start + timedelta(minutes=payload.duration_minutes),
    )

    locked, lock_token = await service.soft_lock_slots(owner_id, [slot])
    if not locked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This time slot was just booked by someone else",
        )

    attendee_email = payload.attendee_email
    if attendee_email is None:
        attendee_email = await service._resolve_attendee_email(lead)

    result = await service.book_slot(
        workspace_id,
        owner_id,
        slot,
        lead=lead,
        attendee_email=attendee_email,
        summary=payload.summary,
        credentials=credentials,
        lock_token=lock_token,
    )
    await service.release_slot_locks(owner_id, [slot], lock_token)
    if not result.booked:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to create calendar event: {result.reason}",
        )

    await session.commit()
    return MeetingBookResponse(
        booked=True,
        event_id=result.event_id,
        meeting_link=result.meeting_link,
        lead_status=MEETING_SCHEDULED_STATUS,
    )
