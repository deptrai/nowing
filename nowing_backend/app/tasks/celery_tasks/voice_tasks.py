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


async def _async_process_post_call_qa(
    *,
    workspace_id: int,
    lead_id: str,
    user_id: str | None,
    call_session_id: str,
    duration_seconds: float,
    transcript: str = "",
    campaign_id: str | None = None,
    hangup_cause: str = "completed",
    room_name: str | None = None,
) -> dict[str, Any]:
    """Post-call reconciliation: billing, BANT scoring, and CRM timeline sync."""
    from uuid import UUID

    from app.services.voice.billing import (
        calculate_telecom_block_charge,
        evaluate_bant_score,
        evaluate_hangup_protection,
        finalize_call_billing,
        sync_call_to_lead_activity_log,
    )

    parsed_lead_id = UUID(lead_id)
    parsed_user_id = UUID(user_id) if user_id else None

    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        # 1. Calculate telecom charge (6s + 1s block)
        billed_seconds, base_cost_micros = calculate_telecom_block_charge(
            duration_seconds
        )

        # 2. Evaluate Hang-up Protection (100% free if < 10s within quota)
        protection_applied = await evaluate_hangup_protection(
            campaign_id, duration_seconds
        )
        actual_cost_micros = 0 if protection_applied else base_cost_micros

        # 3. Reconcile wallet: commit actual cost, release unused deposit
        committed = 0
        if parsed_user_id:
            committed = await finalize_call_billing(
                session,
                parsed_user_id,
                reserved_micros=7_500_000,
                actual_cost_micros=actual_cost_micros,
            )

        # 4. Evaluate BANT scorecard
        bant_score, bant_breakdown = evaluate_bant_score(transcript)

        # 5. Sync results into LeadActivityLog (CRM timeline)
        log_entry = None
        if parsed_lead_id:
            log_entry = await sync_call_to_lead_activity_log(
                session,
                workspace_id=workspace_id,
                lead_id=parsed_lead_id,
                actor_user_id=parsed_user_id,
                call_duration_seconds=duration_seconds,
                billed_seconds=billed_seconds,
                cost_micros=actual_cost_micros,
                bant_score=bant_score,
                bant_breakdown=bant_breakdown,
                transcript_summary=transcript[:500],
                hangup_cause=hangup_cause,
                room_name=room_name,
            )

        await session.commit()

        return {
            "status": "processed",
            "billed_seconds": billed_seconds,
            "base_cost_micros": base_cost_micros,
            "actual_cost_micros": actual_cost_micros,
            "hangup_protection_applied": protection_applied,
            "committed_micros": committed,
            "bant_score": bant_score,
            "bant_breakdown": bant_breakdown,
            "activity_log_id": str(log_entry.id) if log_entry else None,
        }


@celery_app.task(name="process_post_call_qa_task")
def process_post_call_qa_task(
    *,
    workspace_id: int,
    lead_id: str,
    user_id: str | None = None,
    call_session_id: str = "",
    duration_seconds: float = 0.0,
    transcript: str = "",
    campaign_id: str | None = None,
    hangup_cause: str = "completed",
    room_name: str | None = None,
) -> dict[str, Any]:
    """Celery task: post-call billing reconciliation + BANT QA + CRM sync."""
    return run_async_celery_task(
        lambda: _async_process_post_call_qa(
            workspace_id=workspace_id,
            lead_id=lead_id,
            user_id=user_id,
            call_session_id=call_session_id,
            duration_seconds=duration_seconds,
            transcript=transcript,
            campaign_id=campaign_id,
            hangup_cause=hangup_cause,
            room_name=room_name,
        )
    )
