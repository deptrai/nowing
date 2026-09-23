"""Billing service for credit transactions and Auto-Refund SLA (Story 21.3 / AD-42).

Provides:
- auto_refund_lead: 24-hour Auto-Refund SLA when a resolved phone number is invalid or unreachable.
- auto_refund_invalid_contact: objective technical refund SLA (Story 37.7 / AD-121)
  triggered strictly by programmatic telco/Zalo error codes, with the AD-110
  15% monthly circuit breaker routing excess requests to the Admin Desk.
- Reverts 100% of credits to the user's wallet, records refund BillingEvents,
  marks VerifiedContact as invalid, and updates PhoneWaterfallLog.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import desc, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    BillingEvent,
    Lead,
    PhoneWaterfallLog,
    User,
    VerifiedContact,
)

logger = logging.getLogger(__name__)

REFUND_SLA_HOURS = 24
_redis_client: aioredis.Redis | None = None

# AD-121: auto-refund fires strictly on programmatic telco/Zalo error codes —
# never on manual user claims.
INVALID_CONTACT_ERROR_CODES = frozenset(
    {"ZALO_USER_NOT_FOUND", "TELCO_NUMBER_UNALLOCATED"}
)

# PhoneWaterfallLog.status values for the Admin Desk review queue (AD-110).
# ``status`` is String(20), so keep these short.
REFUND_REVIEW_STATUS = "refund_review"
REFUND_REJECTED_STATUS = "refund_rejected"

# BillingEvent.event_type values written by the invalid-contact refund path.
REFUND_INVALID_CONTACT_EVENT = "credit_refund_invalid_contact"
REFUND_ADMIN_DESK_EVENT = "credit_refund_admin_desk"

# Event types counted for the 15% monthly circuit breaker: everything that
# represents a paid lead unlock vs every automatic credit return issued by
# THIS path. Manual-report refunds ("lead_refund", "contact_unlock_refund")
# are governed by their own 24h SLA, not AD-110 — counting them here would
# let unrelated refund activity silently disable the programmatic SLA.
_UNLOCK_EVENT_TYPES = ("contact_enrichment", "contact_unlock")
_AUTO_REFUND_EVENT_TYPES = (REFUND_INVALID_CONTACT_EVENT,)


def extract_invalid_contact_error_code(payload: Any) -> str | None:
    """Return a canonical AD-121 invalid-contact code found in ``payload``.

    Accepts provider raw_response dicts, plain strings, or nested envelopes.
    Word-boundary matching keeps prefixed/suffixed variants like
    ``ZALO_USER_NOT_FOUND_RESOLVED`` from triggering a refund.

    ponytail: str() on a dict/list renders nested envelopes recursively, so a
    single regex scan covers {"error": {"code": "..."}} shapes without a
    walker. Remaining ceiling: an exact code quoted inside an unrelated field
    (e.g. a ``previous_errors`` history string) still matches.
    """
    if payload is None:
        return None
    haystack = str(payload).upper()
    for code in INVALID_CONTACT_ERROR_CODES:
        if re.search(rf"(?<![A-Z0-9_]){re.escape(code)}(?![A-Z0-9_])", haystack):
            return code
    return None


def _month_bounds(now: datetime) -> tuple[datetime, datetime]:
    """Return (start, end) of the current calendar month in UTC."""
    start = datetime(now.year, now.month, 1, tzinfo=UTC)
    if now.month == 12:
        end = datetime(now.year + 1, 1, 1, tzinfo=UTC)
    else:
        end = datetime(now.year, now.month + 1, 1, tzinfo=UTC)
    return start, end


def get_redis() -> aioredis.Redis | None:
    """Return singleton async Redis client for invalidating cache on refund."""
    global _redis_client
    if not getattr(config, "REDIS_APP_URL", None):
        return None
    if _redis_client is None:
        try:
            _redis_client = aioredis.from_url(
                config.REDIS_APP_URL, decode_responses=True
            )
        except Exception as exc:  # Redis init is best-effort; client stays None
            logger.warning("Failed to initialize async Redis client: %s", exc)
            return None
    return _redis_client


class BillingService:
    """Enterprise billing service for lead intelligence and auto-refund SLA."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def auto_refund_lead(
        self,
        *,
        workspace_id: int,
        lead_id: UUID,
        user_id: UUID | None,
        reason: str = "reported_invalid_phone",
    ) -> dict[str, Any]:
        """Process 100% auto-refund for an invalid/unreachable lead phone within 24h SLA.

        Raises:
            HTTPException: If lead not found, no successful resolution, SLA expired (>24h),
                           or already refunded.
        """
        # 1. Fetch Lead
        lead = await self.session.get(Lead, (lead_id, workspace_id))
        if not lead or lead.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lead not found in this workspace",
            )

        # 2. Find latest successful PhoneWaterfallLog with row lock for update
        stmt = (
            select(PhoneWaterfallLog)
            .where(
                PhoneWaterfallLog.workspace_id == workspace_id,
                PhoneWaterfallLog.lead_id == lead_id,
                PhoneWaterfallLog.status.in_(["success", "refunded"]),
            )
            .order_by(desc(PhoneWaterfallLog.created_at))
            .with_for_update()
            .limit(1)
        )
        res = await self.session.execute(stmt)
        log_entry = res.scalar_one_or_none()

        if not log_entry:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No successful phone resolution found for this lead to refund",
            )

        # 3. Guard: Check if already refunded
        if log_entry.status == "refunded":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Lead phone resolution was already refunded on {log_entry.refunded_at}",
            )

        # 4. Guard: Check 24-hour SLA window
        now = datetime.now(UTC)
        created_at = log_entry.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)

        age = now - created_at
        if age > timedelta(hours=REFUND_SLA_HOURS):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Auto-refund SLA expired: reported after {age.total_seconds() / 3600:.1f} hours "
                    f"(maximum allowed SLA is {REFUND_SLA_HOURS} hours)"
                ),
            )

        refund_micros = log_entry.cost_micros
        if refund_micros <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This phone resolution incurred no charges; cannot process a refund.",
            )

        # 5. Determine original payer and restore credits to User's wallet
        original_event_stmt = (
            select(BillingEvent.user_id)
            .where(
                BillingEvent.workspace_id == workspace_id,
                BillingEvent.event_entity_type == "contact_enrichment",
                BillingEvent.event_id == log_entry.id,
            )
            .limit(1)
        )
        payer_user_id = (
            await self.session.execute(original_event_stmt)
        ).scalar_one_or_none()
        target_refund_user_id = payer_user_id or user_id

        if target_refund_user_id is not None:
            user = await self.session.get(User, target_refund_user_id)
            if user:
                user.credit_micros_balance += refund_micros
                self.session.add(user)

        # 6. Record negative refund BillingEvent
        refund_event = BillingEvent(
            workspace_id=workspace_id,
            client_id=lead.client_id,
            user_id=target_refund_user_id,
            event_entity_type="lead_refund",
            event_type="lead_refund",
            event_id=lead_id,
            cost_micros=-refund_micros,
            currency="USD",
            cost_basis="actual",
        )
        self.session.add(refund_event)

        # 7. Update PhoneWaterfallLog status
        log_entry.status = "refunded"
        log_entry.refunded_at = now
        log_entry.refund_reason = reason
        self.session.add(log_entry)

        # 8. Mark VerifiedContact as invalid
        contacts_stmt = select(VerifiedContact).where(
            VerifiedContact.workspace_id == workspace_id,
            VerifiedContact.lead_id == lead_id,
        )
        contacts_res = await self.session.execute(contacts_stmt)
        for contact in contacts_res.scalars().all():
            contact.is_valid = False
            contact.verification_status = "invalid"
            contact.refunded_at = now
            contact.invalid_reason = reason
            self.session.add(contact)

        # 9. Invalidate Redis phone cache
        redis = get_redis()
        if redis:
            try:
                await redis.delete(f"enrich:phone:lead:{lead_id}")
                if log_entry.phone_hash:
                    await redis.delete(f"enrich:phone:{log_entry.phone_hash}")
            except (
                Exception
            ) as e:  # best-effort cache cleanup; refund already committed
                logger.warning("Failed deleting Redis cache during refund: %s", e)

        await self.session.commit()

        logger.info(
            "Auto-refund processed for lead %s (refund_micros=%s, user_id=%s)",
            lead_id,
            refund_micros,
            user_id,
        )

        return {
            "lead_id": str(lead_id),
            "refunded": True,
            "refund_micros": refund_micros,
            "refund_credits": refund_micros / 1_000_000,
            "refunded_at": now.isoformat(),
            "reason": reason,
            "status": "refunded",
        }

    async def _count_workspace_events(
        self,
        *,
        workspace_id: int,
        event_types: tuple[str, ...],
        since: datetime,
        until: datetime,
    ) -> int:
        """Count BillingEvent rows of the given types in a workspace window.

        ponytail: selects rows and counts in Python (same approach as
        ``billing_event_service._count_workspace_events``) so unit tests with
        fake sessions don't need a real ``func.count()`` evaluation.
        """
        result = await self.session.execute(
            select(BillingEvent).where(
                BillingEvent.workspace_id == workspace_id,
                BillingEvent.event_type.in_(event_types),
                BillingEvent.created_at >= since,
                BillingEvent.created_at < until,
            )
        )
        return len(list(result.scalars().all()))

    async def auto_refund_invalid_contact(
        self,
        *,
        workspace_id: int,
        lead_id: UUID,
        user_id: UUID | None,
        error_code: str,
        waterfall_log_id: UUID | None = None,
        bypass_cap: bool = False,
    ) -> dict[str, Any]:
        """Objective technical refund SLA for invalid contacts (Story 37.7 / AD-121).

        Fires strictly when a programmatic telco/Zalo check on an unlocked
        phone returns ``ZALO_USER_NOT_FOUND`` or ``TELCO_NUMBER_UNALLOCATED``.
        Immediately re-credits the deducted micros to the original payer's
        wallet and writes an audited ``credit_refund_invalid_contact`` ledger
        entry.

        Circuit breaker (AD-110): when the month's auto-refund volume reaches
        15% of the month's unlocked leads for the workspace, the request is
        NOT auto-refunded — the PhoneWaterfallLog is queued at
        ``refund_review`` status for the manual Admin Desk instead.
        """
        code = (error_code or "").strip().upper()
        if code not in INVALID_CONTACT_ERROR_CODES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Auto-refund requires a programmatic invalid-contact error "
                    f"code ({', '.join(sorted(INVALID_CONTACT_ERROR_CODES))}); "
                    "manual claims are not eligible."
                ),
            )

        lead = await self.session.get(Lead, (lead_id, workspace_id))
        if not lead or lead.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lead not found in this workspace",
            )

        if waterfall_log_id is not None:
            # Exact-log refund: two concurrent resolutions on the same lead
            # must never cross-refund each other's log rows.
            res = await self.session.execute(
                select(PhoneWaterfallLog)
                .where(PhoneWaterfallLog.id == waterfall_log_id)
                .with_for_update()
            )
            log_entry = res.scalar_one_or_none()
            if log_entry is None or log_entry.workspace_id != workspace_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Refund target log not found in this workspace",
                )
        else:
            stmt = (
                select(PhoneWaterfallLog)
                .where(
                    PhoneWaterfallLog.workspace_id == workspace_id,
                    PhoneWaterfallLog.lead_id == lead_id,
                    PhoneWaterfallLog.status.in_(
                        ["success", "refunded", REFUND_REVIEW_STATUS]
                    ),
                )
                .order_by(desc(PhoneWaterfallLog.created_at))
                .with_for_update()
                .limit(1)
            )
            res = await self.session.execute(stmt)
            log_entry = res.scalar_one_or_none()

        if not log_entry or log_entry.status not in (
            "success",
            "refunded",
            REFUND_REVIEW_STATUS,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No successful phone resolution found for this lead to refund",
            )

        now = datetime.now(UTC)

        # Idempotent: a programmatic verification callback may be retried by
        # the provider; report the existing state instead of raising.
        if log_entry.status == "refunded":
            return {
                "lead_id": str(lead_id),
                "refunded": True,
                "already_refunded": True,
                "refund_micros": log_entry.cost_micros,
                "refund_credits": log_entry.cost_micros / 1_000_000,
                "refunded_at": log_entry.refunded_at.isoformat()
                if log_entry.refunded_at
                else None,
                "reason": log_entry.refund_reason or code,
                "status": "refunded",
            }
        if log_entry.status == REFUND_REVIEW_STATUS and not bypass_cap:
            return {
                "lead_id": str(lead_id),
                "refunded": False,
                "routed_to_admin_desk": True,
                "status": REFUND_REVIEW_STATUS,
                "reason": log_entry.refund_reason or code,
            }

        refund_micros = log_entry.cost_micros
        if refund_micros <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This phone resolution incurred no charges; cannot process a refund.",
            )

        # AD-110 circuit breaker: monthly auto-refund volume capped at 15% of
        # total unlocked leads for the workspace.
        if not bypass_cap:
            # Serialize the cap check per workspace: two concurrent refunds
            # on different leads must not both pass the count check before
            # either commits. Transaction-scoped, released on commit/rollback.
            lock_key = int.from_bytes(
                hashlib.sha256(str(workspace_id).encode()).digest()[:8],
                "big",
                signed=True,
            )
            await self.session.execute(
                text("SELECT pg_advisory_xact_lock(:k)"), {"k": lock_key}
            )
            cycle_start, cycle_end = _month_bounds(now)
            unlock_count = await self._count_workspace_events(
                workspace_id=workspace_id,
                event_types=_UNLOCK_EVENT_TYPES,
                since=cycle_start,
                until=cycle_end,
            )
            refund_count = await self._count_workspace_events(
                workspace_id=workspace_id,
                event_types=_AUTO_REFUND_EVENT_TYPES,
                since=cycle_start,
                until=cycle_end,
            )
            cap_pct = float(getattr(config, "AUTO_REFUND_MONTHLY_CAP_PCT", 0.15))
            cap_pct = max(0.0, min(cap_pct, 1.0))
            if refund_count >= math.ceil(unlock_count * cap_pct):
                log_entry.status = REFUND_REVIEW_STATUS
                log_entry.refund_reason = code
                self.session.add(log_entry)
                # Audited escalation marker so the Admin Desk queue is visible
                # in the billing ledger, not just in the waterfall log.
                self.session.add(
                    BillingEvent(
                        workspace_id=workspace_id,
                        client_id=lead.client_id,
                        user_id=user_id,
                        event_entity_type="contact_enrichment",
                        event_type=REFUND_ADMIN_DESK_EVENT,
                        event_id=log_entry.id,
                        cost_micros=0,
                        currency="USD",
                        cost_basis="actual",
                    )
                )
                await self.session.commit()
                logger.info(
                    "Auto-refund cap reached for workspace %s; lead %s routed to "
                    "Admin Desk (error_code=%s, refunds=%s, unlocks=%s)",
                    workspace_id,
                    lead_id,
                    code,
                    refund_count,
                    unlock_count,
                )
                return {
                    "lead_id": str(lead_id),
                    "refunded": False,
                    "routed_to_admin_desk": True,
                    "status": REFUND_REVIEW_STATUS,
                    "reason": code,
                }

        # Determine the original payer — constrained to the actual unlock
        # charge event (deterministic order), never the requester. The admin
        # approving at the Desk must not receive the credits.
        payer_user_id = (
            await self.session.execute(
                select(BillingEvent.user_id)
                .where(
                    BillingEvent.workspace_id == workspace_id,
                    BillingEvent.event_entity_type == "contact_enrichment",
                    BillingEvent.event_type == "contact_enrichment",
                    BillingEvent.event_id == log_entry.id,
                )
                .order_by(BillingEvent.created_at.asc())
                .limit(1)
            )
        ).scalar_one_or_none()

        if payer_user_id is None:
            # No identifiable payer — routing to review beats silently
            # crediting the wrong wallet or emitting a false ledger event.
            log_entry.status = REFUND_REVIEW_STATUS
            log_entry.refund_reason = f"payer_unresolved:{code}"
            self.session.add(log_entry)
            await self.session.commit()
            logger.warning(
                "Auto-refund payer unresolved; lead %s log %s routed to "
                "Admin Desk (workspace=%s)",
                lead_id,
                log_entry.id,
                workspace_id,
            )
            return {
                "lead_id": str(lead_id),
                "refunded": False,
                "routed_to_admin_desk": True,
                "status": REFUND_REVIEW_STATUS,
                "reason": "payer_unresolved",
            }
        target_refund_user_id = payer_user_id

        # Stage all mutations; apply_credit's commit persists them atomically.
        log_entry.status = "refunded"
        log_entry.refunded_at = now
        log_entry.refund_reason = code
        self.session.add(log_entry)

        self.session.add(
            BillingEvent(
                workspace_id=workspace_id,
                client_id=lead.client_id,
                user_id=target_refund_user_id,
                event_entity_type="contact_enrichment",
                event_type=REFUND_INVALID_CONTACT_EVENT,
                event_id=log_entry.id,
                cost_micros=-refund_micros,
                currency="USD",
                cost_basis="actual",
            )
        )

        contacts_res = await self.session.execute(
            select(VerifiedContact).where(
                VerifiedContact.workspace_id == workspace_id,
                VerifiedContact.lead_id == lead_id,
            )
        )
        for contact in contacts_res.scalars().all():
            contact.is_valid = False
            contact.verification_status = "invalid"
            contact.refunded_at = now
            contact.invalid_reason = code
            self.session.add(contact)

        from app.services import wallet_credit

        await wallet_credit.apply_credit(
            self.session, target_refund_user_id, refund_micros
        )

        # Best-effort: drop the cached phone so the bad number isn't re-served.
        redis = get_redis()
        if redis:
            try:
                await redis.delete(f"enrich:phone:lead:{lead_id}")
                if log_entry.phone_hash:
                    await redis.delete(f"enrich:phone:{log_entry.phone_hash}")
            except Exception as e:  # cache cleanup failure; refund already committed
                logger.warning(
                    "Failed deleting Redis cache during invalid-contact refund: %s", e
                )

        logger.info(
            "Invalid-contact auto-refund processed for lead %s "
            "(refund_micros=%s, error_code=%s, user_id=%s)",
            lead_id,
            refund_micros,
            code,
            target_refund_user_id,
        )

        return {
            "lead_id": str(lead_id),
            "refunded": True,
            "refund_micros": refund_micros,
            "refund_credits": refund_micros / 1_000_000,
            "refunded_at": now.isoformat(),
            "reason": code,
            "status": "refunded",
        }

    async def resolve_admin_desk_refund(
        self,
        *,
        log_id: UUID,
        approve: bool,
        admin_user_id: UUID | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Resolve a queued invalid-contact refund from the Admin Desk (AD-110).

        ``approve`` executes the refund bypassing the 15% circuit breaker (the
        breaker's whole point is to defer the decision to a human). ``reject``
        marks the entry ``refund_rejected`` so it leaves the queue.
        """
        stmt = (
            select(PhoneWaterfallLog)
            .where(PhoneWaterfallLog.id == log_id)
            .with_for_update()
        )
        log_entry = (await self.session.execute(stmt)).scalar_one_or_none()
        if log_entry is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Refund review entry not found",
            )
        if log_entry.status != REFUND_REVIEW_STATUS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Entry is not awaiting review (status={log_entry.status})",
            )

        if not approve:
            log_entry.status = REFUND_REJECTED_STATUS
            if note:
                log_entry.refund_reason = (
                    f"{log_entry.refund_reason or ''}|rejected:{note}"[:255]
                )
            self.session.add(log_entry)
            await self.session.commit()
            return {
                "log_id": str(log_id),
                "lead_id": str(log_entry.lead_id),
                "status": REFUND_REJECTED_STATUS,
                "refunded": False,
            }

        # refund_reason may carry a prefix (``payer_unresolved:CODE``) or the
        # bare code — extract the whitelisted code robustly.
        code = extract_invalid_contact_error_code(log_entry.refund_reason)
        if code is None:
            code = "TELCO_NUMBER_UNALLOCATED"
        result = await self.auto_refund_invalid_contact(
            workspace_id=log_entry.workspace_id,
            lead_id=log_entry.lead_id,
            # Admin identity is audit-only — never a wallet destination.
            user_id=None,
            error_code=code,
            waterfall_log_id=log_entry.id,
            bypass_cap=True,
        )
        result["log_id"] = str(log_id)
        if result.get("refunded"):
            approval_meta = f"{code}|approved_by:{admin_user_id}"
            if note:
                approval_meta += f"|{note}"
            log_entry.refund_reason = approval_meta[:255]
            self.session.add(log_entry)
            await self.session.commit()
        return result
