"""Inbound interruption, opt-out handling, and DNC registration."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    SequenceEnrollment,
    SequenceEvent,
    VerifiedContact,
    WorkspaceDncRecord,
)
from app.lead_intelligence.dnc.normalizer import (
    hash_phone_hmac,
    normalize_email,
    normalize_phone_e164,
)
from app.lead_intelligence.dnc.service import DncComplianceService
from app.services.pii.redact import redact_pii

logger = logging.getLogger(__name__)


class SequencerInboundMixin:
    """Inbound reply/opt-out interruption with Redis locks and CAS OCC."""

    async def _get_redis_async(self):
        res = self._get_redis()
        if hasattr(res, "__await__") or asyncio.iscoroutine(res):
            return await res
        return res

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
        from app.services.sequencer.constants import OPT_OUT_KEYWORDS

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
