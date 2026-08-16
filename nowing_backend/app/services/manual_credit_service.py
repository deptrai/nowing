"""Manual workspace credit adjustment service with dual-audit ledger."""

from __future__ import annotations

import hashlib
import logging
import struct
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AuditEvent, CreditTransaction, Workspace
from app.redis_client import get_redis_client

logger = logging.getLogger(__name__)

# 1 credit = $0.01 = 10_000 micro-USD. 500 credits = $5.00.
CREDIT_TO_MICROS = 10_000

# Daily manual adjustment quota: $10 = 1_000 credits.
DAILY_CREDIT_QUOTA = 1_000

# Redis lock TTL for the workspace wallet (seconds).
WORKSPACE_WALLET_LOCK_TTL = 10

# Postgres lock timeout for credit adjustment operations (seconds).
WORKSPACE_WALLET_POSTGRES_LOCK_TIMEOUT = 5

RELEASE_LOCK_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


class ManualCreditQuotaExceededError(Exception):
    """Raised when an admin exceeds the daily manual adjustment quota."""

    def __init__(self, limit_credits: int, used_credits: int) -> None:
        self.limit_credits = limit_credits
        self.used_credits = used_credits
        super().__init__(
            "Daily manual adjustment quota exceeded. Manager approval required."
        )


class ManualCreditValidationError(Exception):
    """Raised when adjustment payload fails validation."""


class ManualCreditAdjustmentService:
    """Atomic manual credit adjustment with Redis + Postgres 2-tier locks."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _micros_from_credits(self, amount_credits: int) -> int:
        return amount_credits * CREDIT_TO_MICROS

    def _credits_from_micros(self, amount_micros: int) -> int:
        return amount_micros // CREDIT_TO_MICROS

    @staticmethod
    def _admin_advisory_lock_key(actor_admin_id: uuid.UUID) -> int:
        """Deterministic signed 64-bit key for pg_advisory_xact_lock.

        ponytail: we only need one advisory lock per admin per transaction.
        Hash the UUID to a 64-bit value; collisions across the full UUID space
        are astronomically unlikely for the manual-credit volume.
        """
        digest = hashlib.sha256(str(actor_admin_id).encode()).digest()[:8]
        (value,) = struct.unpack(">q", digest)
        return value

    async def _daily_credit_total(self, actor_admin_id: uuid.UUID) -> int:
        """Total credits (CREDIT direction) created by this admin today (UTC)."""
        today = datetime.now(UTC).date()
        start_of_day = datetime.combine(today, datetime.min.time(), tzinfo=UTC)
        stmt = select(
            func.coalesce(func.sum(CreditTransaction.amount_micros), 0)
        ).where(
            CreditTransaction.actor_admin_id == actor_admin_id,
            CreditTransaction.direction == "CREDIT",
            CreditTransaction.created_at >= start_of_day,
        )
        result = await self.session.execute(stmt)
        micros = result.scalar_one()
        return self._credits_from_micros(micros)

    def _validate_payload(
        self,
        amount_credits: int,
        direction: str,
        reason: str,
        ticket_ref: str,
    ) -> None:
        if not isinstance(amount_credits, int) or amount_credits <= 0:
            raise ManualCreditValidationError(
                "amount_credits must be a positive integer"
            )
        if direction not in {"CREDIT", "DEBIT"}:
            raise ManualCreditValidationError("direction must be 'CREDIT' or 'DEBIT'")
        if not isinstance(reason, str) or len(reason) < 10:
            raise ManualCreditValidationError(
                "reason is required and must be at least 10 characters"
            )
        if not isinstance(ticket_ref, str) or not ticket_ref.strip():
            raise ManualCreditValidationError("ticket_ref is required")

    @asynccontextmanager
    async def _workspace_redis_lock(self, workspace_id: int):
        """Try to acquire a Redis lock for the workspace wallet.

        ponytail: Redis is a best-effort guard. If Redis is unavailable in a
        test environment, we fall back to the Postgres FOR UPDATE lock alone.
        Upgrading to a redlock-style multi-node lock is unnecessary for the
        current single-primary Postgres architecture.
        """
        redis_client = await get_redis_client()
        key = f"lock:workspace_wallet:{workspace_id}"
        token = uuid.uuid4().hex
        acquired = False

        if redis_client is not None:
            try:
                acquired = bool(
                    await redis_client.set(
                        key,
                        token,
                        nx=True,
                        ex=WORKSPACE_WALLET_LOCK_TTL,
                    )
                )
            except Exception as exc:
                logger.warning(
                    "Redis workspace wallet lock unavailable for %s: %s", key, exc
                )

        try:
            yield acquired
        finally:
            if acquired and redis_client is not None:
                try:
                    await redis_client.eval(RELEASE_LOCK_LUA, 1, key, token)
                except Exception as exc:
                    logger.warning(
                        "Failed to release workspace wallet lock %s: %s", key, exc
                    )

    async def adjust_credits(
        self,
        *,
        workspace_id: int,
        amount_credits: int,
        direction: str,
        reason: str,
        ticket_ref: str,
        actor_admin_id: uuid.UUID,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Apply a manual credit or debit adjustment to a workspace wallet.

        Enforces 2-tier locking (Redis + Postgres FOR UPDATE), idempotency,
        immutable ledger insertion and a daily per-admin credit grant quota.
        """
        self._validate_payload(amount_credits, direction, reason, ticket_ref)

        # Idempotency: return existing transaction for this key without taking
        # any locks. If two requests race, the unique index plus the re-check
        # under the workspace lock keeps the ledger single-writer per workspace.
        existing = await self.session.execute(
            select(CreditTransaction).where(
                CreditTransaction.idempotency_key == idempotency_key
            )
        )
        existing_tx = existing.scalar_one_or_none()
        if existing_tx is not None:
            return self._to_result(existing_tx)

        amount_micros = self._micros_from_credits(amount_credits)

        # Fail fast if a Postgres row/advisory lock is held too long.
        await self.session.execute(
            text(f"SET LOCAL lock_timeout = '{WORKSPACE_WALLET_POSTGRES_LOCK_TIMEOUT}s'")
        )

        # Tier-2a: advisory lock on the admin id. This serializes all manual
        # credit adjustments by the same admin across workspaces, preventing
        # the daily quota from being bypassed by concurrent requests.
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": self._admin_advisory_lock_key(actor_admin_id)},
        )

        # Daily quota applies to the sum of CREDIT adjustments made today.
        # It runs inside the admin advisory lock, so the sum is exact.
        if direction == "CREDIT":
            daily_credits = await self._daily_credit_total(actor_admin_id)
            if daily_credits + amount_credits > DAILY_CREDIT_QUOTA:
                self._record_audit(
                    action="manual_credit_quota_exceeded",
                    actor_admin_id=actor_admin_id,
                    ticket_ref=ticket_ref,
                )
                raise ManualCreditQuotaExceededError(DAILY_CREDIT_QUOTA, daily_credits)

        async with self._workspace_redis_lock(workspace_id):
            # Tier-2b: Postgres row lock on the workspace wallet.
            workspace_result = await self.session.execute(
                select(Workspace).where(Workspace.id == workspace_id).with_for_update()
            )
            workspace = workspace_result.scalar_one_or_none()
            if workspace is None:
                raise ManualCreditValidationError(f"Workspace {workspace_id} not found")

            # Idempotency re-check under DB lock.
            existing = await self.session.execute(
                select(CreditTransaction).where(
                    CreditTransaction.idempotency_key == idempotency_key
                )
            )
            existing_tx = existing.scalar_one_or_none()
            if existing_tx is not None:
                return self._to_result(existing_tx)

            if direction == "DEBIT":
                if workspace.credit_micros_balance < amount_micros:
                    raise ManualCreditValidationError(
                        "Insufficient workspace credit balance for debit"
                    )
                workspace.credit_micros_balance -= amount_micros
            else:
                workspace.credit_micros_balance += amount_micros

            transaction = CreditTransaction(
                workspace_id=workspace_id,
                actor_admin_id=actor_admin_id,
                direction=direction,
                amount_micros=amount_micros,
                reason=reason,
                ticket_ref=ticket_ref,
                idempotency_key=idempotency_key,
            )
            self.session.add(transaction)
            await self.session.flush()

        return self._to_result(transaction)

    def _record_audit(
        self,
        *,
        action: str,
        actor_admin_id: uuid.UUID,
        ticket_ref: str,
    ) -> None:
        event = AuditEvent(
            action=action,
            actor_id=actor_admin_id,
            subject_id=None,
            ticket_ref=ticket_ref,
        )
        self.session.add(event)

    def _to_result(self, transaction: CreditTransaction) -> dict[str, Any]:
        return {
            "transaction_id": transaction.id,
            "workspace_id": transaction.workspace_id,
            "actor_admin_id": str(transaction.actor_admin_id),
            "direction": transaction.direction,
            "amount_credits": self._credits_from_micros(transaction.amount_micros),
            "amount_micros": transaction.amount_micros,
            "reason": transaction.reason,
            "ticket_ref": transaction.ticket_ref,
            "idempotency_key": transaction.idempotency_key,
            "created_at": transaction.created_at.isoformat()
            if transaction.created_at
            else None,
        }
