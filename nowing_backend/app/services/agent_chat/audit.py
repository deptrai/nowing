"""Audit logging for public agent-chat API calls (Story 18.1, AC-11)."""

from __future__ import annotations

import logging
import uuid

from app.observability import metrics

logger = logging.getLogger(__name__)


async def log_public_call(
    *,
    actor_user_id: str,
    pat_id: int | str,
    workspace_id: int,
    client_id: str | None,
    agent_id: str | None,
    route: str,
    status: int,
    run_id: uuid.UUID | str | None = None,
    content: str | None = None,
) -> None:
    """Log a public agent-chat call and emit a low-cardinality metric.

    The message body is never written to the audit record or metric labels.
    """
    # Build an explicit extra dict; do not attach the untrusted request body.
    extra = {
        "actor_user_id": actor_user_id,
        "pat_id": pat_id,
        "workspace_id": workspace_id,
        "client_id": client_id,
        "agent_id": agent_id,
        "route": route,
        "status": status,
        "run_id": run_id,
    }

    try:
        logger.info("agent_chat.public_call", extra=extra)
    except Exception:
        # Audit logging must never break the response path. Metrics still fire.
        logger.exception("agent_chat.audit_log_failed")

    metrics.record_agent_chat_public_call(
        workspace_id=workspace_id,
        client_id=client_id or "",
        agent_id=agent_id or "",
        route=route,
        status=status,
    )
