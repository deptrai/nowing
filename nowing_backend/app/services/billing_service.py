"""Billing service for credit transactions and Auto-Refund SLA (Story 21.3 / AD-42).

Provides:
- auto_refund_lead: 24-hour Auto-Refund SLA when a resolved phone number is invalid or unreachable.
- Reverts 100% of credits to the user's wallet, records lead_refund BillingEvent,
  marks VerifiedContact as invalid, and updates PhoneWaterfallLog.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import desc, select
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
        except Exception as exc:
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
        lead = await self.session.get(Lead, lead_id)
        if not lead or lead.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lead not found in this workspace",
            )

        # 2. Find latest successful PhoneWaterfallLog
        stmt = (
            select(PhoneWaterfallLog)
            .where(
                PhoneWaterfallLog.workspace_id == workspace_id,
                PhoneWaterfallLog.lead_id == lead_id,
                PhoneWaterfallLog.status.in_(["success", "refunded"]),
            )
            .order_by(desc(PhoneWaterfallLog.created_at))
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
            refund_micros = 1_500_000  # Fallback default 1.5 credits

        # 5. Restore credits to User's wallet
        if user_id is not None:
            user = await self.session.get(User, user_id)
            if user:
                user.credit_micros_balance += refund_micros
                self.session.add(user)

        # 6. Record negative refund BillingEvent
        refund_event = BillingEvent(
            workspace_id=workspace_id,
            client_id=lead.client_id,
            user_id=user_id,
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
            except Exception as e:
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
