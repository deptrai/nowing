from __future__ import annotations

import asyncio
import json
import logging
import time

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.auth.context import AuthContext
from app.db import DshMission, get_async_session
from app.redis_client import get_redis_client
from app.routes.dsh import dsh_public_router
from app.routes.dsh.deps import _require_mission_access
from app.schemas.dsh import CdpResultPayload
from app.services.browser_operator_audit_service import (
    BrowserOperatorAuditService,
    validate_session_token,
)
from app.services.pii.redact import redact_pii
from app.users import get_auth_context

logger = logging.getLogger(__name__)


@dsh_public_router.get("/dsh/cdp/stream")
async def cdp_stream(request: Request, auth: AuthContext = Depends(get_auth_context)):
    """SSE stream for the Chrome extension to receive CDP commands."""
    redis = await get_redis_client()
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

    pubsub = redis.pubsub()
    try:
        await pubsub.subscribe(channel)
    except (
        BaseException
    ):  # cleanup pubsub and release stream lock on subscription failure
        try:
            await redis.delete(stream_lock_key)
        except (Exception, asyncio.CancelledError) as exc:
            logger.warning(
                "Failed to delete CDP stream lock %s: %s", stream_lock_key, exc
            )
        try:
            await pubsub.close()
        except (Exception, asyncio.CancelledError) as exc:
            logger.warning(
                "Failed to close pubsub for CDP channel %s: %s", channel, exc
            )
        raise

    async def event_generator():
        last_heartbeat = time.monotonic()
        try:
            while True:
                if await request.is_disconnected():
                    break

                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                now = time.monotonic()
                if message and message["type"] == "message":
                    raw_data = message["data"]
                    data = (
                        raw_data.decode("utf-8")
                        if isinstance(raw_data, bytes)
                        else str(raw_data)
                    )
                    yield {
                        "event": "cdp_command",
                        "data": data,
                    }
                    last_heartbeat = now
                elif now - last_heartbeat >= 15.0:
                    # Story 35.3: Emit keep-alive comment every 15s to keep idle SSE active
                    yield {
                        "comment": "ping",
                    }
                    last_heartbeat = now
        except asyncio.CancelledError:
            raise
        finally:
            try:
                await pubsub.unsubscribe(channel)
            except (Exception, asyncio.CancelledError) as exc:
                logger.warning(
                    "Failed to unsubscribe from CDP channel %s: %s", channel, exc
                )
            try:
                await pubsub.close()
            except (Exception, asyncio.CancelledError) as exc:
                logger.warning(
                    "Failed to close pubsub for CDP channel %s: %s", channel, exc
                )
            try:
                await redis.delete(stream_lock_key)
            except (Exception, asyncio.CancelledError) as exc:
                logger.warning(
                    "Failed to delete CDP stream lock %s: %s", stream_lock_key, exc
                )

    return EventSourceResponse(event_generator())


def _redact_cdp_result_value(value):
    """Recursively redact PII from CDP result values before Redis storage.

    Fail-soft: if redaction fails, log the incident and replace the value with
    a marker rather than aborting the CDP result pipeline.
    """
    if isinstance(value, str):
        try:
            return redact_pii(value, context="lead_enrichment").text
        except Exception as exc:  # best-effort PII redaction; fallback to placeholder
            logger.warning("PII redaction failed for CDP result value: %s", exc)
            return "<redaction_failed>"
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
    """Receive result from extension's CDP execution with session token validation.

    Fail-closed: audit log is committed BEFORE the result is pushed to Redis,
    so a failed audit write prevents the worker from consuming an un-audited result.
    """
    mission = await session.get(DshMission, payload.mission_id)
    if mission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mission not found",
        )
    _require_mission_access(auth, mission)

    redis = await get_redis_client()

    # Validate CDP session token (required; missing or invalid → 401)
    session_token = payload.session_token
    valid, err = await validate_session_token(
        session_token,
        str(payload.mission_id),
        str(auth.user.id),
        redis_client=redis,
    )
    if not valid:
        # Log failed auth attempt as audit event
        await BrowserOperatorAuditService.log_event(
            session,
            mission_id=payload.mission_id,
            workspace_id=mission.workspace_id,
            user_id=auth.user.id,
            command_id=payload.command_id or "unknown",
            action="auth_failure",
            success=False,
            error_message=f"Session token validation failed: {err}",
            metadata={"event_type": "auth_failure"},
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid CDP session token: {err}",
        )

    key = f"cdp_result:{auth.user.id}:{payload.mission_id}"

    redacted_result = (
        _redact_cdp_result_value(payload.result) if payload.result is not None else None
    )
    command_id = payload.command_id or (
        payload.result.get("command_id")
        if isinstance(payload.result, dict)
        else "unknown"
    )
    result_data = {
        "result": redacted_result,
        "error": payload.error,
        "command_id": command_id,
        "requires_human": payload.requires_human,
        "challenge": payload.challenge,
    }

    # Extract action and target_url from result payload if present
    result_dict = payload.result if isinstance(payload.result, dict) else {}
    action = result_dict.get("action", "cdp_result")
    target_url = result_dict.get("navigatedUrl") or result_dict.get("url")

    # Fail-closed: commit audit log BEFORE pushing to Redis.
    success = payload.error is None and not payload.requires_human
    await BrowserOperatorAuditService.log_command_result(
        session,
        mission_id=payload.mission_id,
        workspace_id=mission.workspace_id,
        user_id=auth.user.id,
        command_id=command_id,
        action=action,
        target_url=target_url,
        success=success,
        error_message=payload.error,
        challenge=payload.challenge,
        requires_human=payload.requires_human,
    )
    await session.commit()

    # Only push to Redis after the audit event is durably committed.
    pipe = redis.pipeline()
    pipe.rpush(key, json.dumps(result_data))
    pipe.expire(key, 300)
    pipe.ltrim(key, -5, -1)
    await pipe.execute()

    return {"status": "ok"}


__all__ = [
    "_redact_cdp_result_value",
    "cdp_result",
    "cdp_stream",
]
