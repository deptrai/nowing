"""SequencerService: Multi-Channel Drip Outreach Campaign Engine (Story 24.1 / AD-39 / AD-41 / AD-42 / AD-43 / AD-49).

Handles:
- Sequence & Step CRUD and execution
- Quiet Hours (08:00 - 21:30 Asia/Ho_Chi_Minh) & anti-thundering herd jitter calculation
- Strict Consent & Legal Basis gate (AD-25, AD-49)
- Email-first MVP channel enforcement (AD-41)
- Inbound opt-out/reply interruption with Redis lock & CAS OCC (INV-24.2, INV-24.7)
- Transactional billing & wallet debit integration (AD-42, AD-48)
- Sequence analytics aggregation
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.engine.notify import _send_email_smtp
from app.config import config
from app.db import (
    Lead,
    Sequence,
    SequenceEnrollment,
    SequenceEvent,
    SequenceRun,
    SequenceStep,
    VerifiedContact,
    Workspace,
    WorkspaceDncRecord,
)
from app.lead_intelligence.dnc.normalizer import (
    hash_phone_hmac,
    normalize_email,
    normalize_phone_e164,
)
from app.lead_intelligence.dnc.service import DncComplianceService
from app.redis_client import get_redis_client
from app.services import wallet_credit
from app.services.billing_event_service import BillingEventService
from app.services.pii.redact import redact_pii
from app.services.pii.verified_contact_encryption import VerifiedContactEncryption

logger = logging.getLogger(__name__)

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# Default allowed channels in MVP (Story 24.1 / AD-41)
ALLOWED_OUTBOUND_CHANNELS = ["email"]

# Opt-out trigger keywords
OPT_OUT_KEYWORDS = {"stop", "huy", "hủy", "ngung", "ngưng", "unsubscribe", "optout", "opt-out"}


class DeferredChannelError(Exception):
    """Raised when an outreach channel is not supported in the MVP release (AD-41 / DEF-102)."""


@dataclass
class SequenceAnalytics:
    """Aggregated metrics for a sequence."""

    total_enrolled: int = 0
    active_scheduled: int = 0
    delivered_count: int = 0
    responded_count: int = 0
    unsubscribed_count: int = 0
    failed_count: int = 0
    total_cost_micros: int = 0


def calculate_step_eta(delay_seconds: int, from_dt: datetime | None = None) -> datetime:
    """Calculate the next execution timestamp respecting Vietnam quiet hours (08:00 - 21:30 VN Time).

    If target timestamp falls outside the sending window:
    - Before 08:00 -> push to 08:05 today + random jitter (0-1800s).
    - After 21:30 -> push to 08:05 tomorrow + random jitter (0-1800s).
    """
    if from_dt is None:
        from_dt = datetime.now(VN_TZ)
    elif from_dt.tzinfo is None:
        from_dt = from_dt.replace(tzinfo=UTC).astimezone(VN_TZ)
    else:
        from_dt = from_dt.astimezone(VN_TZ)

    target_dt = from_dt + timedelta(seconds=delay_seconds)
    current_minute = target_dt.hour * 60 + target_dt.minute
    start_minute = 8 * 60  # 08:00
    end_minute = 21 * 60 + 30  # 21:30

    if start_minute <= current_minute <= end_minute:
        return target_dt

    jitter_seconds = random.randint(0, 1800)
    if current_minute < start_minute:
        next_send = datetime.combine(target_dt.date(), time(hour=8, minute=5), tzinfo=VN_TZ)
    else:
        next_day = target_dt.date() + timedelta(days=1)
        next_send = datetime.combine(next_day, time(hour=8, minute=5), tzinfo=VN_TZ)

    return next_send + timedelta(seconds=jitter_seconds)


def interpolate_template_variables(template_str: str, variables: dict[str, Any], fallback_blank: bool = True) -> str:
    """Replace template variables like {customer_name}, {company}, {property_title}."""
    if not template_str:
        return ""

    def _replace(match: re.Match) -> str:
        key = match.group(1).strip()
        val = variables.get(key)
        if val is not None:
            return str(val)
        return "" if fallback_blank else match.group(0)

    return re.sub(r"\{([a-zA-Z0-9_]+)\}", _replace, template_str)


def evaluate_condition_step(condition_config: dict[str, Any], context: dict[str, Any]) -> int | None:
    """Evaluate condition predicate (e.g. has_replied, opened) and return next step order or None."""
    predicate = condition_config.get("predicate", "has_replied")
    if_true_step = condition_config.get("if_true_step")
    if_false_step = condition_config.get("if_false_step")

    is_matched = bool(context.get(predicate, False))
    return if_true_step if is_matched else if_false_step


class SequencerService:
    """Orchestration service for automated multi-step sequences."""

    def __init__(self) -> None:
        self.encryption = VerifiedContactEncryption()
        self.billing_service = BillingEventService()

    async def validate_step_channel(self, channel: str) -> None:
        """Validate outreach channel against allowed MVP channels (AD-41)."""
        allowed = getattr(config, "SEQUENCER_OUTBOUND_CHANNELS", ALLOWED_OUTBOUND_CHANNELS)
        if isinstance(allowed, str):
            allowed = [c.strip() for c in allowed.split(",")]
        if channel.lower() not in [c.lower() for c in allowed]:
            raise DeferredChannelError(
                f"Channel '{channel}' is deferred out of MVP (AD-41 / DEF-102). Only {allowed} supported."
            )

    async def enroll_leads(
        self,
        session: AsyncSession,
        workspace_id: int,
        sequence_id: UUID,
        lead_ids: list[UUID],
        *,
        triggered_by_alert_rule_id: UUID | None = None,
        user_id: UUID | None = None,
    ) -> list[SequenceEnrollment]:
        """Enroll multiple leads into a sequence, creating a SequenceRun if needed."""
        sequence = (
            await session.execute(
                select(Sequence).where(
                    Sequence.id == sequence_id,
                    Sequence.workspace_id == workspace_id,
                    Sequence.status == "active",
                )
            )
        ).scalar_one_or_none()
        if not sequence:
            raise ValueError(f"Active sequence {sequence_id} not found in workspace {workspace_id}")

        run = SequenceRun(
            workspace_id=workspace_id,
            client_id=sequence.client_id,
            sequence_id=sequence_id,
            triggering_alert_rule_id=triggered_by_alert_rule_id,
            status="running",
        )
        session.add(run)
        await session.flush()

        enrollments: list[SequenceEnrollment] = []
        for lead_id in lead_ids:
            lead = await session.get(Lead, lead_id)
            if not lead:
                continue
            enr = await self.enroll_lead(
                session=session,
                workspace_id=workspace_id,
                sequence_id=sequence_id,
                lead=lead,
                triggering_alert_rule_id=triggered_by_alert_rule_id,
                sequence_run_id=run.id,
            )
            if enr:
                enrollments.append(enr)

        return enrollments

    async def enroll_lead(
        self,
        session: AsyncSession,
        workspace_id: int,
        sequence_id: UUID,
        lead: Lead | UUID,
        *,
        triggering_alert_rule_id: UUID | None = None,
        sequence_run_id: UUID | None = None,
        client_id: str | None = None,
    ) -> tuple[SequenceRun, SequenceEnrollment] | SequenceEnrollment | None:
        """Enroll a single lead into a sequence after verifying consent (AC-4 / AD-25 / AD-49)."""
        if isinstance(lead, (UUID, str)):
            lead_obj = await session.get(Lead, lead)
        else:
            lead_obj = lead

        if not lead_obj:
            logger.warning("Enrollment rejected: Lead %s not found", lead)
            return None

        # AC-4: Consent & Legal Basis gate
        if lead_obj.consent_status == "none" or not lead_obj.legal_basis:
            logger.info("Rejecting enrollment: Lead %s lacks consent (%s) or legal basis", lead_obj.id, lead_obj.consent_status)
            return None

        # Check existing active enrollment
        existing = (
            await session.execute(
                select(SequenceEnrollment).where(
                    SequenceEnrollment.sequence_id == sequence_id,
                    SequenceEnrollment.lead_id == lead_obj.id,
                    SequenceEnrollment.workspace_id == workspace_id,
                    SequenceEnrollment.status.in_(["scheduled", "executing", "paused"]),
                )
            )
        ).scalar_one_or_none()
        if existing:
            return existing

        # Create run if not provided and alert rule triggered
        created_run: SequenceRun | None = None
        if not sequence_run_id:
            created_run = SequenceRun(
                workspace_id=workspace_id,
                client_id=lead_obj.client_id or client_id,
                sequence_id=sequence_id,
                triggering_alert_rule_id=triggering_alert_rule_id,
                status="running",
            )
            session.add(created_run)
            await session.flush()
            sequence_run_id = created_run.id

        # Calculate initial scheduled_at
        initial_eta = calculate_step_eta(delay_seconds=0)

        enrollment = SequenceEnrollment(
            workspace_id=workspace_id,
            client_id=lead_obj.client_id or client_id,
            sequence_id=sequence_id,
            lead_id=lead_obj.id,
            sequence_run_id=sequence_run_id,
            current_step=1,
            status="scheduled",
            scheduled_at=initial_eta,
            version=0,
        )
        session.add(enrollment)
        await session.flush()

        if created_run:
            return (created_run, enrollment)
        return enrollment

    async def get_due_enrollments(self, session: AsyncSession) -> list[SequenceEnrollment]:
        """Query all enrollments due for execution."""
        now_dt = datetime.now(UTC)
        stmt = select(SequenceEnrollment).where(
            SequenceEnrollment.status == "scheduled",
            SequenceEnrollment.scheduled_at <= now_dt,
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def evaluate_pending_enrollments(self, session: AsyncSession) -> int:
        """Celery Beat worker dispatcher: query due enrollments and enqueue tasks (AC-3)."""
        due_enrollments = await self.get_due_enrollments(session)
        dispatched_count = 0

        for enrollment in due_enrollments:
            try:
                from app.automations.tasks.sequence_tasks import execute_sequence_step

                execute_sequence_step.delay(
                    enrollment_id=str(enrollment.id),
                    workspace_id=enrollment.workspace_id,
                )
                dispatched_count += 1
            except Exception:
                logger.exception("Failed to dispatch Celery task for enrollment %s", enrollment.id)

        return dispatched_count

    async def execute_enrollment_step(
        self,
        session: AsyncSession,
        enrollment_id: UUID,
        workspace_id: int,
    ) -> SequenceEvent | None:
        """Execute the current step for an enrollment under Redis distributed lock (AC-5, AC-6)."""
        redis_client = await get_redis_client()
        lock_key = f"sequence:lock:enrollment:{workspace_id}:{enrollment_id}"

        async with redis_client.lock(lock_key, timeout=10.0, blocking=True, blocking_timeout=3.0):
            # Fetch enrollment with fresh data
            enrollment = (
                await session.execute(
                    select(SequenceEnrollment).where(
                        SequenceEnrollment.id == enrollment_id,
                        SequenceEnrollment.workspace_id == workspace_id,
                    )
                )
            ).scalar_one_or_none()

            if not enrollment or enrollment.status not in ("scheduled", "executing"):
                logger.info("Enrollment %s not eligible for execution (status=%s)", enrollment_id, getattr(enrollment, "status", None))
                return None

            current_version = enrollment.version

            # CAS transition to executing
            stmt = (
                update(SequenceEnrollment)
                .where(
                    SequenceEnrollment.id == enrollment_id,
                    SequenceEnrollment.workspace_id == workspace_id,
                    SequenceEnrollment.version == current_version,
                )
                .values(
                    status="executing",
                    version=current_version + 1,
                    updated_at=datetime.now(UTC),
                )
            )
            res = await session.execute(stmt)
            if res.rowcount == 0:
                logger.info("CAS check failed on enrollment %s; skipping concurrent execution", enrollment_id)
                return None

            enrollment.version = current_version + 1
            enrollment.status = "executing"

            # Load sequence and current step
            sequence = await session.get(Sequence, (enrollment.sequence_id, workspace_id))
            if not sequence or sequence.status != "active":
                enrollment.status = "paused"
                await session.commit()
                return None

            step = (
                await session.execute(
                    select(SequenceStep).where(
                        SequenceStep.sequence_id == enrollment.sequence_id,
                        SequenceStep.workspace_id == workspace_id,
                        SequenceStep.step_order == enrollment.current_step,
                        SequenceStep.is_enabled.is_(True),
                    )
                )
            ).scalar_one_or_none()

            if not step:
                # No more steps -> mark sequence completed
                enrollment.status = "completed"
                enrollment.scheduled_at = None
                enrollment.updated_at = datetime.now(UTC)
                await session.commit()
                return None

            lead = await session.get(Lead, enrollment.lead_id)
            if not lead:
                enrollment.status = "failed"
                await session.commit()
                return None

            # Route by step_type
            if step.step_type == "send_email":
                return await self._handle_send_email_step(session, sequence, step, enrollment, lead)
            elif step.step_type == "wait":
                return await self._handle_wait_step(session, sequence, step, enrollment)
            elif step.step_type == "condition":
                return await self._handle_condition_step(session, sequence, step, enrollment, lead)
            else:
                logger.warning("Unsupported step type %s; skipping to next step", step.step_type)
                await self._advance_to_next_step(session, sequence, step, enrollment)
                await session.commit()
                return None

    async def _handle_send_email_step(
        self,
        session: AsyncSession,
        sequence: Sequence,
        step: SequenceStep,
        enrollment: SequenceEnrollment,
        lead: Lead,
    ) -> SequenceEvent:
        """Handle send_email step: DNC check, consent check, balance check, SMTP send, billing debit."""
        await self.validate_step_channel(step.channel)

        # 1. Resolve VerifiedContact & consent check (AC-4)
        contact = await self._resolve_verified_contact(session, lead, channel="email")
        if not contact or not contact.consent or not contact.is_valid:
            logger.info("Skipping send step for lead %s: no consented contact", lead.id)
            event = SequenceEvent(
                workspace_id=enrollment.workspace_id,
                client_id=enrollment.client_id,
                enrollment_id=enrollment.id,
                sequence_id=sequence.id,
                step_id=step.id,
                event_type="skipped",
                event_subtype="no_consent",
                channel="email",
                cost_micros=0,
                event_metadata={"reason": "unconsented_or_invalid_contact"},
            )
            session.add(event)
            await self._advance_to_next_step(session, sequence, step, enrollment)
            await session.commit()
            return event

        # Decrypt contact email
        try:
            raw_email = self.encryption.decrypt(contact.email) if self.encryption.is_encrypted(contact.email) else contact.email
        except Exception:
            raw_email = contact.email

        norm_email = normalize_email(raw_email) if raw_email else ""

        # 2. DNC fail-closed check (INV-24.2)
        dnc_key = getattr(config, "SECRET_KEY", None) or "nowing-secret-key-for-dnc-compliance-32"
        dnc_svc = DncComplianceService(secret_key=dnc_key)
        dnc_result = await dnc_svc.is_blocked(
            workspace_id=enrollment.workspace_id,
            email=norm_email,
            session=session,
        )
        if dnc_result.is_blocked:
            logger.info("Lead %s email %s is on DNC list; skipping step", lead.id, redact_pii(norm_email).text)
            event = SequenceEvent(
                workspace_id=enrollment.workspace_id,
                client_id=enrollment.client_id,
                enrollment_id=enrollment.id,
                sequence_id=sequence.id,
                step_id=step.id,
                event_type="skipped",
                event_subtype="dnc_blocked",
                channel="email",
                cost_micros=0,
            )
            session.add(event)
            enrollment.status = "unsubscribed"
            await session.commit()
            return event

        # 3. Determine attributed user & pre-check wallet credit (AC-6 / AD-42)
        cost_micros = int(getattr(config, "SEQUENCE_EMAIL_COST_MICROS", 500))
        attributed_user_id = sequence.created_by_user_id
        if not attributed_user_id:
            ws = await session.get(Workspace, enrollment.workspace_id)
            attributed_user_id = ws.user_id if ws else None

        if cost_micros > 0 and attributed_user_id:
            try:
                await wallet_credit.check_balance(session, attributed_user_id, cost_micros)
            except wallet_credit.InsufficientCreditsError:
                logger.warning("Insufficient credits for user %s to send sequence email", attributed_user_id)
                event = SequenceEvent(
                    workspace_id=enrollment.workspace_id,
                    client_id=enrollment.client_id,
                    enrollment_id=enrollment.id,
                    sequence_id=sequence.id,
                    step_id=step.id,
                    event_type="failed",
                    event_subtype="insufficient_credits",
                    channel="email",
                    cost_micros=0,
                    event_metadata={"reason": f"requires {cost_micros} micros"},
                )
                session.add(event)
                enrollment.status = "paused"
                await session.commit()
                return event

        # 4. Prepare message & send SMTP
        template_data = step.template or {}
        subject_template = template_data.get("subject", "Cơ hội hợp tác từ Nowing")
        body_template = template_data.get("body", "")

        context_vars = {
            "customer_name": getattr(lead, "contact_name", None) or getattr(lead, "company_name", None) or "Quý khách",
            "company": getattr(lead, "company_name", None) or "Doanh nghiệp",
            "property_title": (lead.custom_fields or {}).get("property_title", "") if lead.custom_fields else "",
            "consultant_phone": getattr(config, "CONSULTANT_PHONE", "0901234567"),
        }

        subject = interpolate_template_variables(subject_template, context_vars)
        body = interpolate_template_variables(body_template, context_vars)

        msg_id: str | None = None
        try:
            msg_id = await self._send_email_async(to_email=norm_email, subject=subject, body=body)
        except Exception as exc:
            logger.exception("Failed to send sequence email to %s: %s", redact_pii(norm_email).text, exc)
            event = SequenceEvent(
                workspace_id=enrollment.workspace_id,
                client_id=enrollment.client_id,
                enrollment_id=enrollment.id,
                sequence_id=sequence.id,
                step_id=step.id,
                event_type="failed",
                event_subtype="smtp_error",
                channel="email",
                cost_micros=0,
                event_metadata={"error": str(exc)},
            )
            session.add(event)
            enrollment.status = "failed"
            await session.commit()
            return event

        # 5. Success -> Record SequenceEvent & advance enrollment
        event = SequenceEvent(
            workspace_id=enrollment.workspace_id,
            client_id=enrollment.client_id,
            enrollment_id=enrollment.id,
            sequence_id=sequence.id,
            step_id=step.id,
            event_type="sent",
            channel="email",
            cost_micros=cost_micros,
            event_metadata={
                "template_id": template_data.get("template_id"),
                "recipient": redact_pii(norm_email).text,
            },
            provider_msg_id=msg_id,
        )
        session.add(event)
        await session.flush()

        await self._advance_to_next_step(session, sequence, step, enrollment)

        # 6. Record BillingEvent & debit user wallet (Final step before commit)
        await self.billing_service.record_sequence_send(
            session=session,
            sequence_event_id=event.id,
            workspace_id=enrollment.workspace_id,
            client_id=enrollment.client_id,
            user_id=attributed_user_id,
            cost_micros=cost_micros,
        )

        return event

    async def _handle_wait_step(
        self,
        session: AsyncSession,
        sequence: Sequence,
        step: SequenceStep,
        enrollment: SequenceEnrollment,
    ) -> SequenceEvent:
        """Handle wait step: calculate delay ETA and advance."""
        delay = step.wait_duration_seconds or 86400  # Default 1 day
        next_eta = calculate_step_eta(delay)

        event = SequenceEvent(
            workspace_id=enrollment.workspace_id,
            client_id=enrollment.client_id,
            enrollment_id=enrollment.id,
            sequence_id=sequence.id,
            step_id=step.id,
            event_type="delivered",
            event_subtype="wait_scheduled",
            channel=step.channel,
            cost_micros=0,
        )
        session.add(event)

        await self._advance_to_next_step(session, sequence, step, enrollment, next_eta=next_eta)
        await session.commit()
        return event

    async def _handle_condition_step(
        self,
        session: AsyncSession,
        sequence: Sequence,
        step: SequenceStep,
        enrollment: SequenceEnrollment,
        lead: Lead,
    ) -> SequenceEvent:
        """Handle condition branching step."""
        context = {
            "has_replied": enrollment.status == "responded",
            "lead_status": getattr(lead, "status", ""),
        }
        next_step_order = evaluate_condition_step(step.condition_config or {}, context)

        event = SequenceEvent(
            workspace_id=enrollment.workspace_id,
            client_id=enrollment.client_id,
            enrollment_id=enrollment.id,
            sequence_id=sequence.id,
            step_id=step.id,
            event_type="delivered",
            event_subtype="condition_evaluated",
            channel=step.channel,
            cost_micros=0,
            event_metadata={"next_step_order": next_step_order},
        )
        session.add(event)

        if next_step_order is not None:
            enrollment.current_step = next_step_order
            enrollment.status = "scheduled"
            enrollment.scheduled_at = calculate_step_eta(0)
        else:
            enrollment.status = "completed"
            enrollment.scheduled_at = None

        enrollment.version += 1
        enrollment.updated_at = datetime.now(UTC)
        await session.commit()
        return event

    async def _advance_to_next_step(
        self,
        session: AsyncSession,
        sequence: Sequence,
        current_step: SequenceStep,
        enrollment: SequenceEnrollment,
        next_eta: datetime | None = None,
    ) -> None:
        """Advance enrollment to next step or mark completed."""
        next_step = (
            await session.execute(
                select(SequenceStep).where(
                    SequenceStep.sequence_id == sequence.id,
                    SequenceStep.workspace_id == sequence.workspace_id,
                    SequenceStep.step_order > current_step.step_order,
                    SequenceStep.is_enabled.is_(True),
                ).order_by(SequenceStep.step_order.asc())
            )
        ).scalars().first()

        if next_step:
            enrollment.current_step = next_step.step_order
            enrollment.status = "scheduled"
            delay = next_step.wait_duration_seconds or 0 if next_step.step_type == "wait" else 0
            enrollment.scheduled_at = next_eta or calculate_step_eta(delay)
        else:
            enrollment.status = "completed"
            enrollment.scheduled_at = None

        enrollment.version += 1
        enrollment.last_event_at = datetime.now(UTC)
        enrollment.updated_at = datetime.now(UTC)

    async def handle_inbound_interruption(
        self,
        session: AsyncSession,
        workspace_id: int,
        *,
        phone: str | None = None,
        email: str | None = None,
        text: str | None = None,
        channel: str | None = None,
    ) -> SequenceEnrollment | None:
        """Handle incoming reply/opt-out, lock enrollment, update status and register DNC (AC-5)."""
        redis_client = await get_redis_client()
        lock_id = email or phone or "inbound"
        lock_key = f"sequence:lock:inbound:{workspace_id}:{lock_id}"

        async with redis_client.lock(lock_key, timeout=10.0, blocking=True, blocking_timeout=2.0):
            # Check opt-out keyword
            is_opt_out = False
            if text:
                words = re.findall(r"\w+", text.lower())
                is_opt_out = any(w in OPT_OUT_KEYWORDS for w in words)

            # Find matching active enrollment
            stmt = select(SequenceEnrollment).where(
                SequenceEnrollment.workspace_id == workspace_id,
                SequenceEnrollment.status.in_(["scheduled", "executing", "paused"]),
            )
            enrollments = (await session.execute(stmt)).scalars().all()
            if not enrollments:
                return None

            enrollment = enrollments[0]

            if is_opt_out:
                enrollment.status = "unsubscribed"
                enrollment.scheduled_at = None
                enrollment.version += 1
                enrollment.updated_at = datetime.now(UTC)

                # Register DNC
                await self._register_opt_out_dnc(session, workspace_id, phone=phone, email=email)

                # Log opt-out event
                event = SequenceEvent(
                    workspace_id=workspace_id,
                    client_id=enrollment.client_id,
                    enrollment_id=enrollment.id,
                    sequence_id=enrollment.sequence_id,
                    event_type="skipped",
                    event_subtype="opt_out",
                    channel=channel or "email",
                    cost_micros=0,
                    event_metadata={"text": redact_pii(text or "").text},
                )
                session.add(event)
            else:
                enrollment.status = "responded"
                enrollment.version += 1
                enrollment.updated_at = datetime.now(UTC)

                event = SequenceEvent(
                    workspace_id=workspace_id,
                    client_id=enrollment.client_id,
                    enrollment_id=enrollment.id,
                    sequence_id=enrollment.sequence_id,
                    event_type="replied",
                    channel=channel or "email",
                    cost_micros=0,
                    event_metadata={"text": redact_pii(text or "").text},
                )
                session.add(event)

            await session.commit()
            return enrollment

    async def _register_opt_out_dnc(
        self,
        session: AsyncSession,
        workspace_id: int,
        phone: str | None = None,
        email: str | None = None,
    ) -> None:
        """Register opt-out contact to WorkspaceDncRecord and invalidate cache."""
        dnc_key = getattr(config, "SECRET_KEY", None) or "nowing-secret-key-for-dnc-compliance-32"
        dnc_service = DncComplianceService(secret_key=dnc_key)
        if phone:
            e164 = normalize_phone_e164(phone)
            if e164:
                p_hash = hash_phone_hmac(e164, secret_key=dnc_service.secret_key)
                session.add(
                    WorkspaceDncRecord(
                        workspace_id=workspace_id,
                        record_type="phone",
                        value=f"{e164[:4]}****{e164[-3:]}",
                        value_hmac=p_hash,
                        reason="Inbound STOP/HUY opt-out",
                        source="inbound_sequence_opt_out",
                    )
                )
        if email:
            norm_mail = email.strip().lower()
            m_hash = hash_phone_hmac(norm_mail, secret_key=dnc_service.secret_key)
            session.add(
                WorkspaceDncRecord(
                    workspace_id=workspace_id,
                    record_type="email",
                    value=redact_pii(norm_mail).text,
                    value_hmac=m_hash,
                    reason="Inbound STOP/HUY opt-out",
                    source="inbound_sequence_opt_out",
                )
            )
        await session.flush()
        await dnc_service.invalidate_workspace_cache(workspace_id)

    async def _resolve_verified_contact(
        self,
        session: AsyncSession,
        lead: Lead,
        channel: str = "email",
    ) -> VerifiedContact | None:
        """Resolve highest-confidence consented VerifiedContact for given lead."""
        stmt = (
            select(VerifiedContact)
            .where(
                VerifiedContact.lead_id == lead.id,
                VerifiedContact.workspace_id == lead.workspace_id,
                VerifiedContact.consent.is_(True),
                VerifiedContact.is_valid.is_(True),
            )
            .order_by(VerifiedContact.confidence.desc(), VerifiedContact.created_at.desc())
        )
        return (await session.execute(stmt)).scalars().first()

    async def _send_email_async(self, to_email: str, subject: str, body: str) -> str:
        """Asynchronous wrapper around synchronous SMTP sender."""
        await asyncio.to_thread(_send_email_smtp, to_email=to_email, subject=subject, body=body)
        return f"msg_{uuid4().hex[:12]}"

    async def get_sequence_analytics(
        self,
        session: AsyncSession,
        workspace_id: int,
        sequence_id: UUID,
    ) -> SequenceAnalytics:
        """Calculate and return real-time metrics for a sequence (AC-8)."""
        analytics = SequenceAnalytics()

        # Enrollments count
        enr_stmt = select(
            func.count(SequenceEnrollment.id),
            func.count().filter(SequenceEnrollment.status.in_(["scheduled", "executing"])),
            func.count().filter(SequenceEnrollment.status == "responded"),
            func.count().filter(SequenceEnrollment.status == "unsubscribed"),
            func.count().filter(SequenceEnrollment.status == "failed"),
        ).where(
            SequenceEnrollment.sequence_id == sequence_id,
            SequenceEnrollment.workspace_id == workspace_id,
        )
        enr_res = (await session.execute(enr_stmt)).first()
        if enr_res:
            analytics.total_enrolled = enr_res[0] or 0
            analytics.active_scheduled = enr_res[1] or 0
            analytics.responded_count = enr_res[2] or 0
            analytics.unsubscribed_count = enr_res[3] or 0
            analytics.failed_count = enr_res[4] or 0

        # Events count and cost
        ev_stmt = select(
            func.count().filter(SequenceEvent.event_type.in_(["delivered", "sent"])),
            func.coalesce(func.sum(SequenceEvent.cost_micros), 0),
        ).where(
            SequenceEvent.sequence_id == sequence_id,
            SequenceEvent.workspace_id == workspace_id,
        )
        ev_res = (await session.execute(ev_stmt)).first()
        if ev_res:
            analytics.delivered_count = ev_res[0] or 0
            analytics.total_cost_micros = ev_res[1] or 0

        return analytics
