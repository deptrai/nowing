"""Public (unauthenticated) pitch-portal endpoints (Story 37.5/37.6).

These back ``pitch.nowing.ai/{workspace_slug}/{lead_id}``:

- ``GET .../meta`` — sanitized portal metadata + generated content for the
  SSR page (Story 37.5).
- ``POST .../beacon`` — cookieless ``navigator.sendBeacon`` telemetry.  Per
  AD-120 the beacon always answers ``204`` for well-formed payloads (including
  filtered preview pings and unknown leads) so the endpoint never leaks whether
  a lead exists; the unguessable lead UUID in the URL is the capability.
- ``POST .../opt-out`` — Decree 13 self-serve "xóa thông tin" (Story 37.5
  AC-4).  Answers ``200`` for any well-formed request — including unknown
  leads — so it cannot be probed for lead existence either.
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
@limiter.limit("120/minute")
async def get_pitch_meta(
    request: Request,
    workspace_ref: str,
    lead_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    redis_client: Any = Depends(get_redis_client),
) -> PitchPortalMetaResponse:
    """Sanitized portal metadata; 404 hides existence (unguessable lead UUID)."""
    from app.services.pitch_portal import get_portal_content, sanitize_text

    workspace_id = await _resolve_workspace_id(session, workspace_ref)
    if workspace_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pitch link invalid"
        )
    lead = await _get_public_lead(session, workspace_id, lead_id)
    if lead is None or lead.consent_status == "withdrawn":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pitch link invalid"
        )

    workspace = await session.get(Workspace, workspace_id)
    # Story 37.5: generated content is cached per lead; a cold cache rebuilds
    # the deterministic artifact so the portal always renders complete.
    try:
        content = await get_portal_content(session, redis_client, lead)
    except Exception:  # generation failure must not 500 the public page
        logger.exception("pitch meta: content build failed lead=%s", lead_id)
        content = {}
    return PitchPortalMetaResponse(
        lead_id=lead.id,
        workspace_id=workspace_id,
        company_name=sanitize_text(lead.company_name, 200) or "Doanh nghiệp",
        industry=sanitize_text(lead.industry, 100) or None,
        location=sanitize_text(lead.location, 100) or None,
        workspace_name=sanitize_text(
            workspace.name if workspace is not None else "Nowing", 100
        )
        or "Nowing",
        booking_path=f"/book/{workspace_id}/{lead.id}",
        opt_out_path=f"/pitch/{workspace_ref}/{lead.id}/opt-out",
        headline=content.get("headline"),
        exec_summary=content.get("exec_summary"),
        exec_cards=content.get("exec_cards") or [],
        logo_url=content.get("logo_url"),
        roi=content.get("roi"),
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
    from app.services.pitch_engagement import (
        dispatch_prepared_pitch_alert,
        is_crawler_user_agent,
        mark_pitch_beacon_alerted,
        pitch_beacon_lock_key,
        record_pitch_beacon,
    )

    # AC-3: drop preview pings before touching the DB — they are nearly free.
    user_agent = request.headers.get("user-agent")
    if is_crawler_user_agent(user_agent):
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # Reject oversized bodies via Content-Length before buffering; the body
    # read below is the fallback for chunked/missing headers.
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > _MAX_BEACON_BODY_BYTES:
                return Response(status_code=status.HTTP_204_NO_CONTENT)
        except ValueError:
            return Response(status_code=status.HTTP_204_NO_CONTENT)

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

    result = await record_pitch_beacon(
        session,
        redis_client,
        lead=lead,
        dwell_seconds=payload.dwell_seconds,
        sections_viewed=payload.sections_viewed,
        device_type=payload.device_type,
        session_id=payload.session_id,
        event=payload.event,
        user_agent=user_agent,
    )
    if not result.outcome.startswith("recorded"):
        await session.rollback()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # Commit the timeline row BEFORE the Telegram send — the network call must
    # not hold the DB transaction open (review 37.6).
    await session.commit()
    if result.alert is not None:
        sent = await dispatch_prepared_pitch_alert(result.alert)
        if sent:
            if result.activity_log is not None:
                try:
                    await mark_pitch_beacon_alerted(
                        session, result.activity_log
                    )
                    await session.commit()
                except Exception:  # alert delivered; flag is display-only
                    logger.warning(
                        "pitch beacon: alert flag update failed lead=%s",
                        lead_id,
                    )
                    await session.rollback()
        else:
            # Transient failure — release the cooldown so the next beacon can
            # retry instead of being suppressed for the full 30 minutes.
            try:
                await redis_client.delete(pitch_beacon_lock_key(lead.id))
            except Exception:
                logger.warning(
                    "pitch beacon: failed to release lock for lead %s",
                    lead_id,
                )
    logger.debug(
        "pitch beacon %s lead=%s ws=%s outcome=%s",
        payload.event,
        lead_id,
        workspace_id,
        result.outcome,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{workspace_ref}/{lead_id}/opt-out")
@limiter.limit("30/minute")
async def pitch_opt_out(
    request: Request,
    workspace_ref: str,
    lead_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    redis_client: Any = Depends(get_redis_client),
) -> dict[str, Any]:
    """Decree 13 self-serve opt-out behind the portal footer link (AC-4).

    Always answers a generic ``{"status": "ok"}`` — including for unknown
    workspaces/leads — so the endpoint cannot be probed for existence; the
    unguessable lead UUID is the capability, same as ``/meta``.
    """
    from app.services.pitch_engagement import is_crawler_user_agent
    from app.services.pitch_portal import process_pitch_opt_out

    if is_crawler_user_agent(request.headers.get("user-agent")):
        return {"status": "ok"}

    workspace_id = await _resolve_workspace_id(session, workspace_ref)
    if workspace_id is None:
        return {"status": "ok"}
    lead = await _get_public_lead(session, workspace_id, lead_id)
    if lead is None:
        return {"status": "ok"}

    # The SSR host forwards the real prospect IP (same convention as the other
    # public lead endpoints); fall back to the socket peer only when absent.
    client_ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or request.headers.get("x-real-ip", "").strip()
        or (request.client.host if request.client else None)
        or None
    )
    try:
        purged = await process_pitch_opt_out(
            session, redis_client, lead=lead, ip_address=client_ip
        )
        await session.commit()
    except Exception:  # opt-out must not surface internals; log + generic ok
        await session.rollback()
        logger.exception(
            "pitch opt-out failed lead=%s ws=%s", lead_id, workspace_id
        )
        return {"status": "ok"}

    logger.info(
        "pitch opt-out lead=%s ws=%s purged=%s", lead_id, workspace_id, purged
    )
    return {"status": "ok"}


_FAVICON_CACHE_PREFIX = "pitch_favicon"
_FAVICON_CACHE_TTL_SECONDS = 7 * 24 * 3600
_FAVICON_TIMEOUT_SECONDS = 5.0
_FAVICON_MAX_BYTES = 64 * 1024


@router.get("/favicon")
@limiter.limit("120/minute")
async def pitch_favicon(
    request: Request,
    domain: str,
    redis_client: Any = Depends(get_redis_client),
) -> Response:
    """Server-side favicon proxy for portal prospect logos (Story 37.5).

    Rendering ``google.com/s2/favicons`` directly in the portal would disclose
    the viewer's IP and the lead's domain to a third party on a page that
    advertises Decree-13 compliance. The backend fetches instead; the lead's
    domain is still sent to Google but is never correlated with the viewer.
    The ``domain`` param is strictly validated — only google.com is ever
    contacted, so this cannot be used as an open proxy/SSRF.
    """
    import base64

    import httpx

    from app.services.pitch_portal import _DOMAIN_RE, sanitize_text

    d = sanitize_text(domain, 255).lower()
    if not d or not _DOMAIN_RE.match(d):
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    cache_key = f"{_FAVICON_CACHE_PREFIX}:{d}"
    if redis_client is not None:
        try:
            raw = await redis_client.get(cache_key)
            if raw:
                cached = json.loads(raw)
                return Response(
                    content=base64.b64decode(cached["b64"]),
                    media_type=cached.get("ct") or "image/png",
                )
        except Exception:  # degraded cache → fetch upstream
            logger.warning("pitch favicon: cache read failed for %s", d)

    try:
        async with httpx.AsyncClient(
            timeout=_FAVICON_TIMEOUT_SECONDS
        ) as client:
            upstream = await client.get(
                "https://www.google.com/s2/favicons",
                params={"domain": d, "sz": "128"},
            )
    except Exception:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    if upstream.status_code != 200 or not upstream.content:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    body = upstream.content[:_FAVICON_MAX_BYTES]
    content_type = (
        upstream.headers.get("content-type", "image/png").split(";")[0].strip()
        or "image/png"
    )
    if not content_type.startswith("image/"):
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    if redis_client is not None:
        try:
            await redis_client.set(
                cache_key,
                json.dumps(
                    {"ct": content_type, "b64": base64.b64encode(body).decode()}
                ),
                ex=_FAVICON_CACHE_TTL_SECONDS,
            )
        except Exception:  # cache write failure is non-fatal
            logger.warning("pitch favicon: cache write failed for %s", d)
    return Response(content=body, media_type=content_type)
