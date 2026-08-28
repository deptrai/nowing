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
import hashlib
import logging
import random
import re
from dataclasses import dataclass, field
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
from app.gateway.accounts import account_token, get_or_create_system_telegram_account
from app.gateway.telegram.adapter import TelegramAdapter
from app.gateway.zalo.zns_client import ZnsClient
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
OPT_OUT_KEYWORDS = {
    "stop",
    "huy",
    "hủy",
    "ngung",
    "ngưng",
    "unsubscribe",
    "optout",
    "opt-out",
}


class DeferredChannelError(Exception):
    """Raised when an outreach channel is not supported in the MVP release (AD-41 / DEF-102)."""


@dataclass
class ChannelAnalytics:
    """Per-channel metrics for a sequence."""

    channel: str = "email"
    sent: int = 0
    delivered: int = 0
    opened: int = 0
    replied: int = 0
    bounced: int = 0
    failed: int = 0
    skipped: int = 0
    cost_micros: int = 0


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
    channel_breakdown: list[ChannelAnalytics] = field(default_factory=list)


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

    delay_seconds = max(delay_seconds, 0)
    target_dt = from_dt + timedelta(seconds=delay_seconds)
    current_minute = target_dt.hour * 60 + target_dt.minute
    start_minute = 8 * 60  # 08:00
    end_minute = 21 * 60 + 30  # 21:30

    if start_minute <= current_minute <= end_minute:
        return target_dt

    jitter_seconds = random.randint(0, 1800)
    if current_minute < start_minute:
        next_send = datetime.combine(
            target_dt.date(), time(hour=8, minute=5), tzinfo=VN_TZ
        )
    else:
        next_day = target_dt.date() + timedelta(days=1)
        next_send = datetime.combine(next_day, time(hour=8, minute=5), tzinfo=VN_TZ)

    return next_send + timedelta(seconds=jitter_seconds)


def interpolate_template_variables(
    template_str: str, variables: dict[str, Any], fallback_blank: bool = True
) -> str:
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


def evaluate_condition_step(
    condition_config: dict[str, Any], context: dict[str, Any]
) -> int | None:
    """Evaluate condition predicate (e.g. has_replied, opened) and return next step order or None."""
    predicate = condition_config.get("predicate", "has_replied")
    if_true_step = condition_config.get("if_true_step")
    if_false_step = condition_config.get("if_false_step")

    is_matched = bool(context.get(predicate, False))
    return if_true_step if is_matched else if_false_step


class SequencerService:
    """Orchestration service for automated multi-step sequences."""

    # AD-25 / AD-49: lead consent statuses that allow outbound communication
    ENROLLABLE_CONSENT_STATUSES = {"granted", "confirmed", "opted_in"}

    def __init__(self) -> None:
        self.encryption = VerifiedContactEncryption()
        self.billing_service = BillingEventService()

    def _get_redis(self):
        return get_redis_client()

    async def _get_redis_async(self):
        res = self._get_redis()
        if hasattr(res, "__await__") or asyncio.iscoroutine(res):
            return await res
        return res

    async def validate_step_channel(self, channel: str) -> bool:
        """Validate outreach channel against allowed MVP channels (AD-41)."""
        allowed = getattr(
            config, "SEQUENCER_OUTBOUND_CHANNELS", ALLOWED_OUTBOUND_CHANNELS
        )
        if isinstance(allowed, str):
            allowed = [c.strip() for c in allowed.split(",") if c.strip()]
        allowed_lower = {c.lower() for c in allowed}
        if channel.lower() not in allowed_lower:
            raise DeferredChannelError(
                f"Channel '{channel}' is deferred out of MVP (AD-41 / DEF-102). Only {allowed} supported."
            )
        # AD-41 / DEF-102 legal gate: Zalo requires explicit re-activation.
        if channel.lower() == "zalo" and not getattr(
            config, "AD_41_REACTIVATED", False
        ):
            raise DeferredChannelError(
                "Channel 'zalo' is gated by AD-41 / DEF-102. Set AD_41_REACTIVATED=true after SCP sign-off."
            )
        return True

    def calculate_step_eta(
        self,
        target_dt: datetime | None = None,
        delay_seconds: int = 0,
        from_dt: datetime | None = None,
    ) -> datetime:
        """AC-3: Calculate step ETA respecting quiet hours (08:00 - 21:30 VN Time) & jitter."""
        base_dt = target_dt or from_dt or datetime.now(VN_TZ)
        return calculate_step_eta(delay_seconds=delay_seconds, from_dt=base_dt)

    async def check_outbound_compliance(
        self,
        session: AsyncSession,
        workspace_id: int,
        phone: str | None,
        channel: str,
        consent_status: str | None,
        legal_basis: str | None,
        external_chat_ids: dict[str, Any] | None = None,
    ) -> bool:
        """AC-4 / INV-24.2: Verify Consent & DNC Pre-check fail-closed."""
        if not legal_basis or not str(legal_basis).strip():
            return False
        if consent_status not in self.ENROLLABLE_CONSENT_STATUSES:
            return False

        external_chat_ids = external_chat_ids or {}

        # Fail-closed if the required channel identifier is missing.
        if channel == "zalo" and (not phone or not str(phone).strip()):
            return False
        if channel == "telegram" and not external_chat_ids.get("telegram_chat_id"):
            return False

        dnc_key = getattr(config, "SECRET_KEY", None)
        if not dnc_key:
            logger.error(
                "[SequencerService] SECRET_KEY is not configured — failing closed for DNC pre-check"
            )
            return False

        dnc_svc = DncComplianceService(secret_key=dnc_key)

        # Check DNC by email/phone domain/tax when available.
        if phone and str(phone).strip():
            normalized = normalize_phone_e164(str(phone).strip())
            if not normalized:
                return False
            dnc_result = await dnc_svc.is_blocked(
                workspace_id=workspace_id,
                phone=normalized,
                session=session,
            )
            if dnc_result.is_blocked:
                return False

        return True

    def get_billing_event_for_step(
        self, channel: str, event_type: str = "sent"
    ) -> dict[str, Any]:
        """AD-42 / AD-48 / AC-7: Return billing event specification."""
        if event_type == "meeting_booked":
            return {
                "event_type": "outcome_meeting_booked",
                "event_entity_type": "outcome_event",
                "cost_micros": 0,
            }

        channel_type_map = {
            "email": "email_send",
            "zalo": "zns_send",
            "telegram": "telegram_send",
        }
        cost_map = {
            "email": getattr(config, "SEQUENCE_EMAIL_COST_MICROS", 500),
            "zalo": getattr(config, "SEQUENCE_ZNS_COST_MICROS", 300),
            "telegram": getattr(config, "SEQUENCE_TELEGRAM_COST_MICROS", 0),
        }
        return {
            "event_type": channel_type_map.get(channel, f"{channel}_send"),
            "event_entity_type": "sequence_event",
            "cost_micros": cost_map.get(channel, 0),
        }

    async def _send_email_dispatch(
        self,
        *,
        to_email: str,
        subject: str,
        body: str,
    ) -> str:
        """Dispatch email via SMTP and return provider message id."""
        return await self._send_email_async(
            to_email=to_email, subject=subject, body=body
        )

    async def _send_telegram_dispatch(
        self,
        session: AsyncSession,
        workspace_id: int,
        chat_id: str,
        text: str,
        parse_mode: str | None = None,
    ) -> str:
        """Dispatch Telegram bot message for a workspace."""
        account = await get_or_create_system_telegram_account(session)
        token = account_token(account)
        if not token:
            if not getattr(config, "TELEGRAM_SHARED_BOT_TOKEN", None):
                raise RuntimeError("missing_telegram_token")
            token = str(config.TELEGRAM_SHARED_BOT_TOKEN)
        adapter = TelegramAdapter(token)
        result = await adapter.send_message(
            external_peer_id=chat_id,
            text=text,
            parse_mode=parse_mode,
        )
        return result.external_message_id or f"tg_{uuid4().hex[:12]}"

    async def _send_zns_dispatch(
        self,
        session: AsyncSession,
        *,
        workspace_id: int,
        user_id: UUID | None,
        phone: str,
        template_id: str,
        template_data: dict[str, Any],
        lead_id: UUID,
    ) -> str:
        """Dispatch Zalo ZNS template for a workspace."""
        cost_micros = int(getattr(config, "SEQUENCE_ZNS_COST_MICROS", 300))
        client = ZnsClient()
        res = await client.send_zns_template(
            session,
            workspace_id=workspace_id,
            phone=phone,
            template_id=template_id,
            template_data=template_data,
            user_id=user_id,
            lead_id=lead_id,
            cost_micros=cost_micros,
        )
        return res.get("msg_id") or f"zns_{uuid4().hex[:12]}"

    async def _handle_send_step(
        self,
        session: AsyncSession,
        sequence: Sequence,
        step: SequenceStep,
        enrollment: SequenceEnrollment,
        lead: Lead,
    ) -> SequenceEvent:
        """AC-5 / AC-6 / AC-7: Multi-channel send step with fallback orchestration."""
        await self.validate_step_channel(step.channel)

        # 1. Resolve verified contact with external chat IDs for the primary channel.
        contact = await self._resolve_verified_contact(
            session, lead, channel=step.channel
        )
        if not contact or not contact.consent or not contact.is_valid:
            logger.info(
                "Skipping send step for lead %s: no consented contact for %s",
                lead.id,
                step.channel,
            )
            return await self._skip_step(
                session,
                sequence,
                step,
                enrollment,
                reason="no_consent",
                channel=step.channel,
            )

        # 2. Contact identifiers per channel
        raw_email = None
        raw_phone = None
        telegram_chat_id = None
        if step.channel == "email":
            try:
                raw_email = (
                    self.encryption.decrypt(contact.email)
                    if self.encryption.is_encrypted(contact.email)
                    else contact.email
                )
            except Exception:
                raw_email = contact.email
            if not raw_email:
                return await self._skip_step(
                    session,
                    sequence,
                    step,
                    enrollment,
                    reason="missing_email",
                    channel=step.channel,
                )
        else:
            try:
                raw_phone = (
                    self.encryption.decrypt(contact.phone)
                    if self.encryption.is_encrypted(contact.phone)
                    else contact.phone
                )
            except Exception:
                raw_phone = contact.phone
            if step.channel == "telegram":
                telegram_chat_id = (contact.external_chat_ids or {}).get(
                    "telegram_chat_id"
                )
                if not telegram_chat_id and raw_phone:
                    # Best-effort fallback: normalize phone is not a chat id, so fail.
                    pass
                if not telegram_chat_id:
                    return await self._skip_step(
                        session,
                        sequence,
                        step,
                        enrollment,
                        reason="missing_telegram_chat_id",
                        channel=step.channel,
                    )
            if step.channel == "zalo" and (not raw_phone or not str(raw_phone).strip()):
                return await self._skip_step(
                    session,
                    sequence,
                    step,
                    enrollment,
                    reason="missing_phone",
                    channel=step.channel,
                )

        # 3. Compliance & DNC pre-check
        is_allowed = await self.check_outbound_compliance(
            session,
            workspace_id=enrollment.workspace_id,
            phone=raw_phone,
            channel=step.channel,
            consent_status=lead.consent_status,
            legal_basis=lead.legal_basis,
            external_chat_ids=contact.external_chat_ids or {},
        )
        if not is_allowed:
            return await self._skip_step(
                session,
                sequence,
                step,
                enrollment,
                reason="compliance_or_dnc",
                channel=step.channel,
            )

        # 4. Wallet pre-check
        billing_spec = self.get_billing_event_for_step(step.channel)
        cost_micros = int(billing_spec["cost_micros"])
        attributed_user_id = sequence.created_by_user_id
        if not attributed_user_id:
            ws = await session.get(Workspace, enrollment.workspace_id)
            attributed_user_id = ws.user_id if ws else None

        if cost_micros > 0 and attributed_user_id:
            try:
                await wallet_credit.check_balance(
                    session, attributed_user_id, cost_micros
                )
            except wallet_credit.InsufficientCreditsError:
                return await self._fail_step(
                    session,
                    sequence,
                    step,
                    enrollment,
                    reason="insufficient_credits",
                    channel=step.channel,
                    detail=f"requires {cost_micros} micros",
                )

        # 5. Template interpolation
        template_data = step.template or {}
        context_vars = {
            "customer_name": getattr(lead, "contact_name", None)
            or getattr(lead, "company_name", None)
            or "Quý khách",
            "company": getattr(lead, "company_name", None) or "Doanh nghiệp",
            "property_title": (lead.custom_fields or {}).get("property_title", "")
            if lead.custom_fields
            else "",
            "consultant_phone": getattr(config, "CONSULTANT_PHONE", "0901234567"),
        }

        # 6. Dispatch with fallback
        primary_channel = step.channel
        fallback_channels = step.fallback_channels or []
        channels_to_try = [primary_channel, *list(fallback_channels)]
        channels_to_try = list(
            dict.fromkeys(
                [c.strip().lower() for c in channels_to_try if c and c.strip()]
            )
        )

        last_error: str | None = None
        for channel in channels_to_try:
            try:
                await self.validate_step_channel(channel)
                msg_id, used_channel = await self._dispatch_single_channel(
                    session=session,
                    sequence=sequence,
                    step=step,
                    enrollment=enrollment,
                    lead=lead,
                    contact=contact,
                    channel=channel,
                    template_data=template_data,
                    context_vars=context_vars,
                    attributed_user_id=attributed_user_id,
                    cost_micros=cost_micros,
                )

                # 7. Success -> record event, advance, bill
                event = SequenceEvent(
                    workspace_id=enrollment.workspace_id,
                    client_id=enrollment.client_id,
                    enrollment_id=enrollment.id,
                    sequence_id=sequence.id,
                    step_id=step.id,
                    event_type="sent",
                    channel=used_channel,
                    cost_micros=cost_micros,
                    event_metadata={
                        "template_id": template_data.get("template_id"),
                        "fallback_used": used_channel != primary_channel,
                    },
                    provider_msg_id=msg_id,
                )
                session.add(event)
                await session.flush()

                await self._advance_to_next_step(session, sequence, step, enrollment)

                billing_spec = self.get_billing_event_for_step(used_channel)
                cost_micros = int(billing_spec["cost_micros"])
                event.cost_micros = cost_micros
                await self.billing_service.record_sequence_send(
                    session=session,
                    sequence_event_id=event.id,
                    event_type=billing_spec["event_type"],
                    workspace_id=enrollment.workspace_id,
                    client_id=enrollment.client_id,
                    user_id=attributed_user_id,
                    cost_micros=cost_micros,
                )

                # Ensure final commit for zero-cost sends and staged state.
                await session.commit()
                return event
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "Channel %s failed for lead %s: %s. Trying fallback...",
                    channel,
                    lead.id,
                    exc,
                )

        # All channels failed
        event = SequenceEvent(
            workspace_id=enrollment.workspace_id,
            client_id=enrollment.client_id,
            enrollment_id=enrollment.id,
            sequence_id=sequence.id,
            step_id=step.id,
            event_type="failed",
            event_subtype="all_channels_unavailable",
            channel=step.channel,
            cost_micros=0,
            event_metadata={"error": last_error or "all_channels_unavailable"},
        )
        session.add(event)
        enrollment.status = "failed"
        await session.commit()
        return event

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
            raise ValueError(
                f"Active sequence {sequence_id} not found in workspace {workspace_id}"
            )

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

    # AD-25 / AD-49: lead consent statuses that allow outbound communication
    ENROLLABLE_CONSENT_STATUSES = {"granted", "confirmed", "opted_in"}

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
            lead_obj = (
                await session.execute(
                    select(Lead).where(
                        Lead.id == lead, Lead.workspace_id == workspace_id
                    )
                )
            ).scalar_one_or_none()
        else:
            lead_obj = lead

        if not lead_obj:
            logger.warning(
                "Enrollment rejected: Lead %s not found in workspace %s",
                lead,
                workspace_id,
            )
            return None

        if lead_obj.workspace_id != workspace_id:
            logger.warning(
                "Enrollment rejected: Lead %s workspace mismatch", lead_obj.id
            )
            return None

        # AC-4: Consent & Legal Basis gate
        if (
            lead_obj.consent_status not in self.ENROLLABLE_CONSENT_STATUSES
            or not lead_obj.legal_basis
        ):
            logger.info(
                "Rejecting enrollment: Lead %s lacks consent (%s) or legal basis",
                lead_obj.id,
                lead_obj.consent_status,
            )
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

    async def get_due_enrollments(
        self,
        session: AsyncSession,
        workspace_id: int | None = None,
    ) -> list[SequenceEnrollment]:
        """Query enrollments due for execution, scoped to a workspace if provided."""
        now_dt = datetime.now(UTC)
        filters = [
            SequenceEnrollment.status == "scheduled",
            SequenceEnrollment.scheduled_at <= now_dt,
        ]
        if workspace_id is not None:
            filters.append(SequenceEnrollment.workspace_id == workspace_id)
        stmt = select(SequenceEnrollment).where(*filters)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def evaluate_pending_enrollments(self, session: AsyncSession) -> int:
        """Celery Beat worker dispatcher: query due enrollments and enqueue tasks (AC-3)."""
        now_dt = datetime.now(UTC)
        workspace_stmt = (
            select(SequenceEnrollment.workspace_id)
            .where(
                SequenceEnrollment.status == "scheduled",
                SequenceEnrollment.scheduled_at <= now_dt,
            )
            .distinct()
        )
        workspace_result = await session.execute(workspace_stmt)
        workspace_ids = list(workspace_result.scalars().all())

        dispatched_count = 0
        for ws_id in workspace_ids:
            due_enrollments = await self.get_due_enrollments(
                session, workspace_id=ws_id
            )
            for enrollment in due_enrollments:
                try:
                    from app.automations.tasks.sequence_tasks import (
                        execute_sequence_step,
                    )

                    execute_sequence_step.delay(
                        enrollment_id=str(enrollment.id),
                        workspace_id=ws_id,
                    )
                    dispatched_count += 1
                except Exception:
                    logger.exception(
                        "Failed to dispatch Celery task for enrollment %s",
                        enrollment.id,
                    )

        return dispatched_count

    async def execute_enrollment_step(
        self,
        session: AsyncSession,
        enrollment_id: UUID,
        workspace_id: int,
    ) -> SequenceEvent | None:
        """Execute the current step for an enrollment under Redis distributed lock (AC-5, AC-6)."""
        from app.tenant_context import set_request_tenant_context

        redis_client = await get_redis_client()
        lock_key = f"sequence:lock:enrollment:{workspace_id}:{enrollment_id}"

        async with redis_client.lock(
            lock_key, timeout=10.0, blocking=True, blocking_timeout=3.0
        ):
            # Fetch enrollment with fresh data. Celery worker must bypass RLS for the initial
            # read because client_id is not known until the row is loaded.
            enrollment = (
                await session.execute(
                    select(SequenceEnrollment).where(
                        SequenceEnrollment.id == enrollment_id,
                        SequenceEnrollment.workspace_id == workspace_id,
                    )
                )
            ).scalar_one_or_none()

            if enrollment:
                await set_request_tenant_context(
                    session,
                    workspace_id=workspace_id,
                    client_id=enrollment.client_id,
                )

            if not enrollment or enrollment.status not in ("scheduled", "executing"):
                logger.info(
                    "Enrollment %s not eligible for execution (status=%s)",
                    enrollment_id,
                    getattr(enrollment, "status", None),
                )
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
                logger.info(
                    "CAS check failed on enrollment %s; skipping concurrent execution",
                    enrollment_id,
                )
                return None

            enrollment.version = current_version + 1
            enrollment.status = "executing"

            # Load sequence and current step
            sequence = await session.get(
                Sequence, (enrollment.sequence_id, workspace_id)
            )
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
            if step.step_type in ("send_email", "send_zalo", "send_telegram"):
                return await self._handle_send_step(
                    session, sequence, step, enrollment, lead
                )
            elif step.step_type == "wait":
                return await self._handle_wait_step(session, sequence, step, enrollment)
            elif step.step_type == "condition":
                return await self._handle_condition_step(
                    session, sequence, step, enrollment, lead
                )
            else:
                logger.warning(
                    "Unsupported step type %s; skipping to next step", step.step_type
                )
                await self._advance_to_next_step(session, sequence, step, enrollment)
                await session.commit()
                return None

    async def _fail_step(
        self,
        session: AsyncSession,
        sequence: Sequence,
        step: SequenceStep,
        enrollment: SequenceEnrollment,
        *,
        reason: str,
        channel: str,
        detail: str | None = None,
    ) -> SequenceEvent:
        """Record a failed send step and stop the enrollment."""
        event = SequenceEvent(
            workspace_id=enrollment.workspace_id,
            client_id=enrollment.client_id,
            enrollment_id=enrollment.id,
            sequence_id=sequence.id,
            step_id=step.id,
            event_type="failed",
            event_subtype=reason,
            channel=channel,
            cost_micros=0,
            event_metadata={"reason": reason, "detail": detail},
        )
        session.add(event)
        enrollment.status = "failed"
        enrollment.scheduled_at = None
        enrollment.updated_at = datetime.now(UTC)
        await session.commit()
        return event

    async def _skip_step(
        self,
        session: AsyncSession,
        sequence: Sequence,
        step: SequenceStep,
        enrollment: SequenceEnrollment,
        *,
        reason: str,
        channel: str,
        detail: str | None = None,
    ) -> SequenceEvent:
        """Record a skipped send step and advance enrollment."""
        event = SequenceEvent(
            workspace_id=enrollment.workspace_id,
            client_id=enrollment.client_id,
            enrollment_id=enrollment.id,
            sequence_id=sequence.id,
            step_id=step.id,
            event_type="skipped",
            event_subtype=reason,
            channel=channel,
            cost_micros=0,
            event_metadata={"reason": reason, "detail": detail},
        )
        session.add(event)
        if reason == "dnc_blocked":
            enrollment.status = "unsubscribed"
        await self._advance_to_next_step(session, sequence, step, enrollment)
        await session.commit()
        return event

    async def _dispatch_single_channel(
        self,
        *,
        session: AsyncSession,
        sequence: Sequence,
        step: SequenceStep,
        enrollment: SequenceEnrollment,
        lead: Lead,
        contact: VerifiedContact,
        channel: str,
        template_data: dict[str, Any],
        context_vars: dict[str, Any],
        attributed_user_id: UUID | None,
        cost_micros: int,
    ) -> tuple[str, str]:
        """Dispatch one channel and return (provider_msg_id, used_channel)."""
        if channel == "email":
            raw_email = contact.email
            if not raw_email:
                raise ValueError("missing_email")
            if self.encryption.is_encrypted(raw_email):
                raw_email = self.encryption.decrypt(raw_email)
            norm_email = normalize_email(raw_email) or ""

            dnc_key = (
                getattr(config, "SECRET_KEY", None)
                or "nowing-secret-key-for-dnc-compliance-32"
            )
            dnc_svc = DncComplianceService(secret_key=dnc_key)
            dnc_result = await dnc_svc.is_blocked(
                workspace_id=enrollment.workspace_id,
                email=norm_email,
                session=session,
            )
            if dnc_result.is_blocked:
                raise ValueError("dnc_blocked")

            subject = interpolate_template_variables(
                template_data.get("subject", "Cơ hội hợp tác từ Nowing"),
                context_vars,
            )
            body = interpolate_template_variables(
                template_data.get("body", ""), context_vars
            )
            msg_id = await self._send_email_dispatch(
                to_email=norm_email, subject=subject, body=body
            )
            return msg_id, "email"

        if channel == "zalo":
            raw_phone = contact.phone
            if not raw_phone:
                raise ValueError("missing_phone")
            if self.encryption.is_encrypted(raw_phone):
                raw_phone = self.encryption.decrypt(raw_phone)
            phone = normalize_phone_e164(raw_phone) or raw_phone

            dnc_key = (
                getattr(config, "SECRET_KEY", None)
                or "nowing-secret-key-for-dnc-compliance-32"
            )
            dnc_svc = DncComplianceService(secret_key=dnc_key)
            dnc_result = await dnc_svc.is_blocked(
                workspace_id=enrollment.workspace_id,
                phone=phone,
                session=session,
            )
            if dnc_result.is_blocked:
                raise ValueError("dnc_blocked")

            zalo_template = template_data.get("template_id") or template_data.get(
                "zalo_template_id"
            )
            zalo_data = (
                template_data.get("template_data")
                or template_data.get("zalo_template_data")
                or {}
            )
            if not zalo_template:
                raise ValueError("missing_zalo_template_id")

            msg_id = await self._send_zns_dispatch(
                session=session,
                workspace_id=enrollment.workspace_id,
                user_id=attributed_user_id,
                phone=phone,
                template_id=str(zalo_template),
                template_data=zalo_data,
                lead_id=lead.id,
            )
            return msg_id, "zalo"

        if channel == "telegram":
            chat_id = (contact.external_chat_ids or {}).get("telegram_chat_id")
            if not chat_id:
                raise ValueError("missing_telegram_chat_id")

            dnc_key = (
                getattr(config, "SECRET_KEY", None)
                or "nowing-secret-key-for-dnc-compliance-32"
            )
            dnc_svc = DncComplianceService(secret_key=dnc_key)

            if contact.phone:
                raw_phone = contact.phone
                if self.encryption.is_encrypted(raw_phone):
                    raw_phone = self.encryption.decrypt(raw_phone)
                phone = normalize_phone_e164(raw_phone) or raw_phone
                dnc_result = await dnc_svc.is_blocked(
                    workspace_id=enrollment.workspace_id,
                    phone=phone,
                    session=session,
                )
                if dnc_result.is_blocked:
                    raise ValueError("dnc_blocked")

            if contact.email:
                raw_email = contact.email
                if self.encryption.is_encrypted(raw_email):
                    raw_email = self.encryption.decrypt(raw_email)
                norm_email = normalize_email(raw_email) or ""
                if norm_email:
                    dnc_result = await dnc_svc.is_blocked(
                        workspace_id=enrollment.workspace_id,
                        email=norm_email,
                        session=session,
                    )
                    if dnc_result.is_blocked:
                        raise ValueError("dnc_blocked")

            text = interpolate_template_variables(
                template_data.get("body", ""), context_vars
            )
            parse_mode = template_data.get("parse_mode")
            msg_id = await self._send_telegram_dispatch(
                session=session,
                workspace_id=enrollment.workspace_id,
                chat_id=str(chat_id),
                text=text,
                parse_mode=parse_mode,
            )
            return msg_id, "telegram"

        raise ValueError(f"unsupported_channel:{channel}")

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

        await self._advance_to_next_step(
            session, sequence, step, enrollment, next_eta=next_eta
        )
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
            "opened": enrollment.status
            in (
                "responded",
                "executing",
            ),  # opened/delivered are not tracked per-event yet
            "delivered": enrollment.status in ("responded", "executing", "scheduled"),
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
            (
                await session.execute(
                    select(SequenceStep)
                    .where(
                        SequenceStep.sequence_id == sequence.id,
                        SequenceStep.workspace_id == sequence.workspace_id,
                        SequenceStep.step_order > current_step.step_order,
                        SequenceStep.is_enabled.is_(True),
                    )
                    .order_by(SequenceStep.step_order.asc())
                )
            )
            .scalars()
            .first()
        )

        if next_step:
            enrollment.current_step = next_step.step_order
            enrollment.status = "scheduled"
            delay = (
                next_step.wait_duration_seconds or 0
                if next_step.step_type == "wait"
                else 0
            )
            enrollment.scheduled_at = next_eta or calculate_step_eta(delay)
        else:
            enrollment.status = "completed"
            enrollment.scheduled_at = None

        enrollment.version += 1
        enrollment.last_event_at = datetime.now(UTC)
        enrollment.updated_at = datetime.now(UTC)

    async def _resolve_inbound_contact(
        self,
        session: AsyncSession,
        workspace_id: int,
        *,
        phone: str | None = None,
        email: str | None = None,
        telegram_chat_id: str | None = None,
        zalo_user_id: str | None = None,
    ) -> VerifiedContact | None:
        """Resolve a consented VerifiedContact from inbound identifiers (AC-5 / AD-49)."""
        if email:
            norm_email = normalize_email(email)
            stmt = (
                select(VerifiedContact)
                .where(
                    VerifiedContact.workspace_id == workspace_id,
                    VerifiedContact.email == norm_email,
                    VerifiedContact.consent.is_(True),
                    VerifiedContact.is_valid.is_(True),
                )
                .order_by(
                    VerifiedContact.confidence.desc(), VerifiedContact.created_at.desc()
                )
            )
            return (await session.execute(stmt)).scalars().first()

        if phone:
            e164 = normalize_phone_e164(phone)
            if e164:
                stmt = (
                    select(VerifiedContact)
                    .where(
                        VerifiedContact.workspace_id == workspace_id,
                        VerifiedContact.phone == e164,
                        VerifiedContact.consent.is_(True),
                        VerifiedContact.is_valid.is_(True),
                    )
                    .order_by(
                        VerifiedContact.confidence.desc(),
                        VerifiedContact.created_at.desc(),
                    )
                )
                return (await session.execute(stmt)).scalars().first()

        if telegram_chat_id:
            stmt = (
                select(VerifiedContact)
                .where(
                    VerifiedContact.workspace_id == workspace_id,
                    VerifiedContact.external_chat_ids.contains(
                        {"telegram_chat_id": telegram_chat_id}
                    ),
                    VerifiedContact.consent.is_(True),
                    VerifiedContact.is_valid.is_(True),
                )
                .order_by(
                    VerifiedContact.confidence.desc(),
                    VerifiedContact.created_at.desc(),
                )
            )
            return (await session.execute(stmt)).scalars().first()

        if zalo_user_id:
            stmt = (
                select(VerifiedContact)
                .where(
                    VerifiedContact.workspace_id == workspace_id,
                    VerifiedContact.external_chat_ids.contains(
                        {"zalo_user_id": zalo_user_id}
                    ),
                    VerifiedContact.consent.is_(True),
                    VerifiedContact.is_valid.is_(True),
                )
                .order_by(
                    VerifiedContact.confidence.desc(),
                    VerifiedContact.created_at.desc(),
                )
            )
            return (await session.execute(stmt)).scalars().first()

        return None

    async def handle_inbound_interruption(
        self,
        workspace_id: int,
        session: AsyncSession | None = None,
        *,
        enrollment_id: int | None = None,
        reason: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        telegram_chat_id: str | None = None,
        zalo_user_id: str | None = None,
        text: str | None = None,
        channel: str | None = None,
    ) -> SequenceEnrollment | bool | None:
        """Handle incoming reply/opt-out, lock enrollment, CAS update status and cancel future steps (AC-6 / INV-24.7)."""
        redis_client = await self._get_redis_async()
        raw_lock_id = (
            f"enrollment:{enrollment_id}"
            if enrollment_id is not None
            else (email or phone or telegram_chat_id or zalo_user_id or "inbound")
        )
        lock_id = hashlib.sha256(str(raw_lock_id).encode()).hexdigest()[:16]
        lock_key = (
            f"sequence:lock:enrollment:{workspace_id}:{enrollment_id}"
            if enrollment_id is not None
            else f"sequence:lock:inbound:{workspace_id}:{lock_id}"
        )

        # Fast path without a DB session: just acquire a short-lived Redis lock.
        if session is None:
            acquired = await redis_client.set(lock_key, "1", ex=10, nx=True)
            return bool(acquired)

        async with redis_client.lock(
            lock_key, timeout=10.0, blocking=True, blocking_timeout=2.0
        ):
            # Check opt-out keyword
            is_opt_out = False
            if text:
                words = re.findall(r"\w+", text.lower())
                is_opt_out = any(w in OPT_OUT_KEYWORDS for w in words)

            # Resolve the contact that this inbound message belongs to
            contact = await self._resolve_inbound_contact(
                session,
                workspace_id,
                phone=phone,
                email=email,
                telegram_chat_id=telegram_chat_id,
                zalo_user_id=zalo_user_id,
            )
            if not contact:
                logger.info(
                    "No consented verified contact found for inbound %s",
                    email or phone or telegram_chat_id or zalo_user_id,
                )
                return None

            # Find the most recently scheduled active enrollment for this lead
            stmt = (
                select(SequenceEnrollment)
                .where(
                    SequenceEnrollment.workspace_id == workspace_id,
                    SequenceEnrollment.lead_id == contact.lead_id,
                    SequenceEnrollment.status.in_(["scheduled", "executing", "paused"]),
                )
                .order_by(
                    SequenceEnrollment.scheduled_at.desc().nulls_last(),
                    SequenceEnrollment.created_at.desc(),
                )
            )
            enrollments = (await session.execute(stmt)).scalars().all()
            if not enrollments:
                return None

            enrollment = enrollments[0]
            current_version = enrollment.version

            new_status = "unsubscribed" if is_opt_out else "responded"
            new_scheduled_at = None if is_opt_out else enrollment.scheduled_at

            # CAS update to prevent lost updates from concurrent step execution.
            update_stmt = (
                update(SequenceEnrollment)
                .where(
                    SequenceEnrollment.id == enrollment.id,
                    SequenceEnrollment.workspace_id == workspace_id,
                    SequenceEnrollment.version == current_version,
                )
                .values(
                    status=new_status,
                    scheduled_at=new_scheduled_at,
                    version=current_version + 1,
                    updated_at=datetime.now(UTC),
                )
            )
            res = await session.execute(update_stmt)
            if res.rowcount == 0:
                logger.info(
                    "CAS check failed on enrollment %s for inbound interruption",
                    enrollment.id,
                )
                return None

            enrollment.status = new_status
            enrollment.scheduled_at = new_scheduled_at
            enrollment.version = current_version + 1

            # Cancel future scheduled steps when opting out.
            if is_opt_out:
                await self._cancel_future_steps(session, enrollment)

                # Register DNC
                await self._register_opt_out_dnc(
                    session,
                    workspace_id,
                    phone=phone or contact.phone,
                    email=email or contact.email,
                )

            event = SequenceEvent(
                workspace_id=workspace_id,
                client_id=enrollment.client_id,
                enrollment_id=enrollment.id,
                sequence_id=enrollment.sequence_id,
                event_type="skipped" if is_opt_out else "replied",
                event_subtype="opt_out" if is_opt_out else None,
                channel=channel or "email",
                cost_micros=0,
                event_metadata={"text": redact_pii(text or "").text},
            )
            session.add(event)

            await session.commit()
            return enrollment

    async def _cancel_future_steps(
        self,
        session: AsyncSession,
        enrollment: SequenceEnrollment,
    ) -> None:
        """Mark any future scheduled steps as skipped for this enrollment."""
        # Mark the enrollment itself as unsubscribed already; future events are
        # implicitly skipped because the enrollment will no longer be scheduled.
        # We also log a bulk skipped event for audit clarity.
        event = SequenceEvent(
            workspace_id=enrollment.workspace_id,
            client_id=enrollment.client_id,
            enrollment_id=enrollment.id,
            sequence_id=enrollment.sequence_id,
            event_type="skipped",
            event_subtype="future_steps_cancelled",
            channel="email",
            cost_micros=0,
            event_metadata={"reason": "opt_out"},
        )
        session.add(event)

    async def _register_opt_out_dnc(
        self,
        session: AsyncSession,
        workspace_id: int,
        phone: str | None = None,
        email: str | None = None,
    ) -> None:
        """Register opt-out contact to WorkspaceDncRecord and invalidate cache."""
        dnc_key = (
            getattr(config, "SECRET_KEY", None)
            or "nowing-secret-key-for-dnc-compliance-32"
        )
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
            # ponytail: hash_phone_hmac is a deterministic HMAC helper; it is used
            # for any normalized value (phone or email) in this codebase.
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
        """Resolve highest-confidence consented VerifiedContact for given lead and channel."""
        stmt = (
            select(VerifiedContact)
            .where(
                VerifiedContact.lead_id == lead.id,
                VerifiedContact.workspace_id == lead.workspace_id,
                VerifiedContact.consent.is_(True),
                VerifiedContact.is_valid.is_(True),
            )
            .order_by(
                VerifiedContact.confidence.desc(), VerifiedContact.created_at.desc()
            )
        )
        contact = (await session.execute(stmt)).scalars().first()
        if not contact:
            return None

        if channel == "email" and not contact.email:
            return None
        if channel == "telegram" and not (contact.external_chat_ids or {}).get(
            "telegram_chat_id"
        ):
            # Fallback: if phone-based chat id exists in the lead, accept it later.
            return None
        if channel == "zalo" and not contact.phone:
            return None

        return contact

    async def _send_email_async(self, to_email: str, subject: str, body: str) -> str:
        """Asynchronous wrapper around synchronous SMTP sender."""
        await asyncio.to_thread(
            _send_email_smtp, to_email=to_email, subject=subject, body=body
        )
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
            func.count().filter(
                SequenceEnrollment.status.in_(["scheduled", "executing"])
            ),
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

        # Per-channel breakdown: aggregate raw events in Python for driver safety.
        cb_stmt = select(
            SequenceEvent.channel, SequenceEvent.event_type, SequenceEvent.cost_micros
        ).where(
            SequenceEvent.sequence_id == sequence_id,
            SequenceEvent.workspace_id == workspace_id,
        )
        cb_res = await session.execute(cb_stmt)
        breakdown: dict[str, dict[str, int]] = {}
        for row in cb_res.all():
            channel = row[0] or "email"
            event_type = row[1] or "sent"
            cost = row[2] or 0
            entry = breakdown.setdefault(
                channel,
                {
                    "sent": 0,
                    "delivered": 0,
                    "opened": 0,
                    "replied": 0,
                    "bounced": 0,
                    "failed": 0,
                    "skipped": 0,
                    "cost_micros": 0,
                },
            )
            if event_type in entry:
                entry[event_type] += 1
            entry["cost_micros"] += cost
        for channel, metrics in breakdown.items():
            analytics.channel_breakdown.append(
                ChannelAnalytics(
                    channel=channel,
                    sent=metrics["sent"],
                    delivered=metrics["delivered"],
                    opened=metrics["opened"],
                    replied=metrics["replied"],
                    bounced=metrics["bounced"],
                    failed=metrics["failed"],
                    skipped=metrics["skipped"],
                    cost_micros=metrics["cost_micros"],
                )
            )

        return analytics
