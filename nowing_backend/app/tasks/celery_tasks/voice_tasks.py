"""Celery background tasks for Voice AI SDR call dispatch (Story 38.7)."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.celery_app import celery_app
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

logger = logging.getLogger(__name__)


async def _async_dispatch_voice_call(
    *,
    workspace_id: int,
    phone_e164: str,
    user_id: str | None = None,
    lead_id: str | None = None,
) -> dict[str, Any]:
    """Execute pre-flight compliance check and dispatch outbound voice call."""
    from app.services.voice.compliance_gate import TelephonyComplianceGate
    from app.services.voice.sip_manager import SipTrunkManager
    from app.services.voice.telephony_client import LiveKitTelephonyClient

    parsed_user_id = UUID(user_id) if user_id else None

    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        gate = TelephonyComplianceGate()
        check = await gate.evaluate_preflight(
            session,
            workspace_id=workspace_id,
            raw_phone=phone_e164,
            user_id=parsed_user_id,
        )

        if not check.allowed:
            logger.warning(
                "[voice_task] Compliance rejected call ws=%s phone=%s: %s",
                workspace_id,
                phone_e164[:6] + "...",
                check.verdict.value,
            )
            return {
                "status": "rejected",
                "verdict": check.verdict.value,
                "reason": check.reason,
            }

        trunk = await SipTrunkManager().resolve_workspace_trunk(session, workspace_id)

        from uuid import uuid4

        room_name = f"call_{uuid4().hex}"

        try:
            async with LiveKitTelephonyClient() as telephony:
                part_info = await telephony.dispatch_call(
                    phone_number=check.phone_e164 or phone_e164,
                    trunk_id=trunk.trunk_id,
                    room_name=room_name,
                    participant_identity=f"sip_{check.phone_e164 or phone_e164}",
                )
            return {
                "status": "dispatched",
                "room_name": room_name,
                "sip_call_id": part_info.sip_call_id,
                "trunk_id": trunk.trunk_id,
                "reserved_micros": check.reserved_micros,
            }
        except Exception as exc:
            logger.error("[voice_task] Call dispatch failed: %s", exc)
            # Release 24h frequency lock and soft-lock on infrastructure error
            if check.phone_e164:
                await gate.release_frequency_lock(workspace_id, check.phone_e164)
            if parsed_user_id and check.reserved_micros > 0:
                await gate.release_deposit(
                    session, parsed_user_id, check.reserved_micros
                )
            return {"status": "error", "error": str(exc)}


@celery_app.task(
    name="dispatch_voice_call_task",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def dispatch_voice_call_task(
    self: Any,
    *,
    workspace_id: int,
    phone_e164: str,
    user_id: str | None = None,
    lead_id: str | None = None,
) -> dict[str, Any]:
    """Celery task to dispatch an outbound Voice AI SDR call asynchronously."""
    return run_async_celery_task(
        lambda: _async_dispatch_voice_call(
            workspace_id=workspace_id,
            phone_e164=phone_e164,
            user_id=user_id,
            lead_id=lead_id,
        )
    )
