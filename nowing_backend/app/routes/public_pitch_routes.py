"""Public (unauthenticated) pitch-portal endpoints (Story 37.6).

These back ``pitch.nowing.ai/{workspace_slug}/{lead_id}``:

- ``GET .../meta`` — sanitized portal metadata for the SSR page.
- ``POST .../beacon`` — cookieless ``navigator.sendBeacon`` telemetry.  Per
  AD-120 the beacon always answers ``204`` for well-formed payloads (including
  filtered preview pings and unknown leads) so the endpoint never leaks whether
  a lead exists; the unguessable lead UUID in the URL is the capability.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Lead, Workspace, get_async_session
from app.rate_limiter import limiter
from app.redis_client import get_redis_client
from app.schemas.pitch import PitchBeaconPayload, PitchPortalMetaResponse
from app.tenant_context import set_request_tenant_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/public/pitch", tags=["public-pitch"])

_MAX_BEACON_BODY_BYTES = 16 * 1024


async def _resolve_workspace_id(
    session: AsyncSession, workspace_ref: str
) -> int | None:
    from app.services.pitch_engagement import resolve_pitch_workspace_id

    return await resolve_pitch_workspace_id(session, workspace_ref)


async def _get_public_lead(
    session: AsyncSession, workspace_id: int, lead_id: UUID
) -> Lead | None:
    await set_request_tenant_context(
        session, workspace_id=workspace_id, is_lead_admin="true"
    )
    return await session.get(Lead, (lead_id, workspace_id))


@router.get(
    "/{workspace_ref}/{lead_id}/meta",
    response_model=PitchPortalMetaResponse,
)
@limiter.limit("30/minute")
async def get_pitch_meta(
    request: Request,
    workspace_ref: str,
    lead_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> PitchPortalMetaResponse:
    """Sanitized portal metadata; 404 hides existence (unguessable lead UUID)."""
    workspace_id = await _resolve_workspace_id(session, workspace_ref)
    if workspace_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pitch link invalid"
        )
    lead = await _get_public_lead(session, workspace_id, lead_id)
    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pitch link invalid"
        )

    workspace = await session.get(Workspace, workspace_id)
    return PitchPortalMetaResponse(
        lead_id=lead.id,
        workspace_id=workspace_id,
        company_name=lead.company_name,
        industry=lead.industry,
        location=lead.location,
        workspace_name=workspace.name if workspace is not None else "Nowing",
        booking_path=f"/book/{workspace_id}/{lead.id}",
    )


@router.post("/{workspace_ref}/{lead_id}/beacon", status_code=204)
@limiter.limit("120/minute")
async def pitch_beacon(
    request: Request,
    workspace_ref: str,
    lead_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    redis_client: Any = Depends(get_redis_client),
) -> Response:
    """Ingest a ``sendBeacon`` payload; always 204 for well-formed beacons."""
    body = await request.body()
    if len(body) > _MAX_BEACON_BODY_BYTES:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    try:
        payload = PitchBeaconPayload.model_validate(json.loads(body))
    except (json.JSONDecodeError, ValidationError, UnicodeDecodeError):
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    workspace_id = await _resolve_workspace_id(session, workspace_ref)
    if workspace_id is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    lead = await _get_public_lead(session, workspace_id, lead_id)
    if lead is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    from app.services.pitch_engagement import record_pitch_beacon

    outcome = await record_pitch_beacon(
        session,
        redis_client,
        lead=lead,
        dwell_seconds=payload.dwell_seconds,
        sections_viewed=payload.sections_viewed,
        device_type=payload.device_type,
        session_id=payload.session_id,
        event=payload.event,
        user_agent=request.headers.get("user-agent"),
    )
    if outcome.startswith("recorded"):
        await session.commit()
    else:
        await session.rollback()
    logger.debug(
        "pitch beacon %s lead=%s ws=%s outcome=%s",
        payload.event,
        lead_id,
        workspace_id,
        outcome,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
