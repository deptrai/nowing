"""Telephony Compliance Gate (Story 38.4 / Decree 91 / Decree 13 PDPD).

Centralized 4-layer pre-flight compliance evaluator for autonomous Voice AI SDR:
1. Curfew Scheduler: Prohibits outbound dialing outside Mon-Fri 09:00-11:30 and
   13:30-17:00 ICT (Decree 91/2020/NĐ-CP). Reuses scheduling.py constants.
2. 24h Frequency Cap: Max 1 call per 24 hours per normalized E.164 phone per
   workspace. Enforced via Redis distributed lock (SET NX EX 86400).
3. National DNC 5656 & Workspace DNC: Pre-flight blacklist check via
   DncComplianceService. Blocked numbers cannot be called and incur 0 charges.
4. Pre-call Wallet Soft-lock: Reserves 7,500,000 micros (3-minute buffer at
   2,500 VND/min) via wallet_credit.reserve_credit before placing the call.
   Fails closed (HTTP 402 equivalent) if spendable balance is insufficient.

Runtime In-Call Features:
- Recording disclosure announcement within first 3 seconds of customer answer.
- Immediate opt-out handling (< 2s hangup + register_contact_opt_out).
"""

from __future__ import annotations

import enum
import logging
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.config.voice import (
    VOICE_PRECALL_SOFT_LOCK_MICROS,
)
from app.lead_intelligence.dnc.normalizer import (
    hash_phone_hmac,
    normalize_phone_e164,
)
from app.lead_intelligence.dnc.service import (
    DncComplianceService,
    get_redis,
)
from app.services.sequencer.scheduling import is_voice_curfew

logger = logging.getLogger(__name__)

# Redis frequency lock TTL: 24 hours in seconds (Decree 91 frequency cap)
_FREQUENCY_LOCK_TTL_SECONDS = 86400

# Opt-out detection phrases in Vietnamese (Story 38.4 / Decree 91)
OPTOUT_KEYPHRASES = (
    "đừng gọi",
    "dung goi",
    "không có nhu cầu",
    "khong co nhu cau",
    "làm phiền quá",
    "lam phien qua",
    "phiền quá",
    "phien qua",
    "xóa số",
    "xoa so",
    "bỏ số",
    "bo so",
    "gọi lại sau",  # soft objection vs hard optout
    "không quan tâm",
    "khong quan tam",
    "tắt máy",
    "tat may",
)

# Hard rejection triggers that MUST register permanent DNC immediately
HARD_OPTOUT_KEYPHRASES = (
    "đừng gọi",
    "dung goi",
    "không có nhu cầu",
    "khong co nhu cau",
    "làm phiền",
    "lam phien",
    "phiền quá",
    "phien qua",
    "xóa số",
    "xoa so",
    "bỏ số",
    "bo so",
    "không quan tâm",
    "khong quan tam",
)


class ComplianceVerdict(enum.StrEnum):
    """Result status of the 4-layer telephony pre-flight compliance check."""

    APPROVED = "APPROVED"
    CURFEW_BLOCKED = "CURFEW_BLOCKED"
    FREQUENCY_CAPPED = "FREQUENCY_CAPPED"
    DNC_BLOCKED = "DNC_BLOCKED"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    INVALID_PHONE = "INVALID_PHONE"


@dataclass(frozen=True)
class ComplianceCheckResult:
    """Outcome of pre-flight compliance check."""

    allowed: bool
    verdict: ComplianceVerdict
    reason: str
    phone_e164: str | None = None
    lock_key: str | None = None
    reserved_micros: int = 0

    @classmethod
    def allow(
        cls,
        phone_e164: str,
        lock_key: str | None = None,
        reserved_micros: int = 0,
    ) -> ComplianceCheckResult:
        return cls(
            allowed=True,
            verdict=ComplianceVerdict.APPROVED,
            reason="All 4 telephony compliance layers passed",
            phone_e164=phone_e164,
            lock_key=lock_key,
            reserved_micros=reserved_micros,
        )

    @classmethod
    def reject(
        cls,
        verdict: ComplianceVerdict,
        reason: str,
        phone_e164: str | None = None,
    ) -> ComplianceCheckResult:
        return cls(
            allowed=False,
            verdict=verdict,
            reason=reason,
            phone_e164=phone_e164,
        )


class TelephonyComplianceGate:
    """4-layer compliance gate protecting telephony dispatch from legal violations."""

    def __init__(
        self,
        *,
        secret_key: str | None = None,
        soft_lock_micros: int = VOICE_PRECALL_SOFT_LOCK_MICROS,
    ) -> None:
        self.secret_key = (
            secret_key
            or getattr(config, "SECRET_KEY", None)
            # Must match the DncComplianceService fallback so HMAC digests
            # agree between opt-out registration and pre-flight checks.
            or "default_dnc_secret_key"
        )
        self.soft_lock_micros = soft_lock_micros

    # ------------------------------------------------------------------
    # Layer 1: Decree 91 Curfew Window Check
    # ------------------------------------------------------------------

    @staticmethod
    def is_curfew(now: datetime | None = None) -> bool:
        """Return True if current time is outside legal calling hours (Decree 91)."""
        return is_voice_curfew(now)

    # ------------------------------------------------------------------
    # Layer 2: 24h Frequency Cap (Redis Distributed Lock)
    # ------------------------------------------------------------------

    def _get_frequency_key(self, workspace_id: int, phone_e164: str) -> str:
        vh = hash_phone_hmac(phone_e164, secret_key=self.secret_key)
        return f"voice:freq:{workspace_id}:{vh}"

    async def acquire_frequency_lock(
        self, workspace_id: int, phone_e164: str
    ) -> bool:
        """Atomically acquire 24-hour calling lock on the target phone.

        Returns True if acquired (first call in 24h), False if frequency capped.
        Fail-closed: returns False if Redis is unreachable to avoid spam fines.
        """
        redis_client = get_redis()
        if redis_client is None:
            logger.error(
                "[ComplianceGate] Redis unavailable for frequency lock — failing closed"
            )
            return False

        key = self._get_frequency_key(workspace_id, phone_e164)
        try:
            # SET key "1" EX 86400 NX
            acquired = await redis_client.set(
                key, "1", ex=_FREQUENCY_LOCK_TTL_SECONDS, nx=True
            )
            return bool(acquired)
        except Exception as exc:
            logger.error(
                "[ComplianceGate] Redis frequency lock check failed: %s — failing closed",
                exc,
            )
            return False

    async def release_frequency_lock(
        self, workspace_id: int, phone_e164: str
    ) -> None:
        """Release the 24h lock if a call was cancelled before dialing."""
        redis_client = get_redis()
        if redis_client is None:
            return
        key = self._get_frequency_key(workspace_id, phone_e164)
        try:
            await redis_client.delete(key)
        except Exception as exc:
            logger.warning("[ComplianceGate] Failed to release frequency lock: %s", exc)

    # ------------------------------------------------------------------
    # Layer 3: National DNC 5656 & Workspace Blacklist Check
    # ------------------------------------------------------------------

    async def check_dnc(
        self,
        workspace_id: int,
        phone_e164: str,
        session: AsyncSession | None = None,
    ) -> bool:
        """Return True if phone is on National or Workspace DNC blacklist."""
        try:
            dnc_svc = DncComplianceService(secret_key=self.secret_key)
            result = await dnc_svc.check_phone(
                workspace_id=workspace_id,
                phone=phone_e164,
                session=session,
            )
            return result.is_blocked
        except Exception as exc:
            logger.error("[ComplianceGate] DNC check failed: %s — failing closed", exc)
            return True  # Fail-closed to protect legal compliance

    # ------------------------------------------------------------------
    # Layer 4: Pre-call Wallet Soft-lock (Deposit)
    # ------------------------------------------------------------------

    async def reserve_deposit(
        self,
        session: AsyncSession,
        user_id: str | UUID,
        amount_micros: int | None = None,
    ) -> int:
        """Soft-lock pre-call funds in the caller's wallet."""
        from app.services.wallet_credit import reserve_credit

        amount = (
            amount_micros if amount_micros is not None else self.soft_lock_micros
        )
        return await reserve_credit(session, user_id, amount)

    @staticmethod
    async def release_deposit(
        session: AsyncSession,
        user_id: str | UUID,
        amount_micros: int,
    ) -> int:
        """Release soft-locked funds back to spendable balance upon call failure."""
        from app.services.wallet_credit import release_credit

        return await release_credit(session, user_id, amount_micros)

    # ------------------------------------------------------------------
    # Pre-flight Orchestrator
    # ------------------------------------------------------------------

    async def evaluate_preflight(
        self,
        session: AsyncSession,
        workspace_id: int,
        raw_phone: str,
        *,
        user_id: str | UUID | None = None,
        now: datetime | None = None,
    ) -> ComplianceCheckResult:
        """Execute the 4 compliance layers in strict order.

        Layers:
        1. Curfew check (Nghị định 91)
        2. E.164 normalization
        3. DNC 5656 check (National + Workspace DNC)
        4. 24h frequency cap check (Redis NX lock)
        5. Wallet soft-lock deposit (if user_id provided)

        Returns:
            :class:`ComplianceCheckResult` detailing allowed status and verdict.
        """
        # 1. Curfew
        if self.is_curfew(now):
            logger.info(
                "[ComplianceGate] Rejected ws=%s: outside Decree 91 calling window",
                workspace_id,
            )
            return ComplianceCheckResult.reject(
                ComplianceVerdict.CURFEW_BLOCKED,
                "Outside Decree 91 calling window (09:00-11:30 or 13:30-17:00 ICT Mon-Fri)",
            )

        # 2. Normalization
        phone_e164 = normalize_phone_e164(raw_phone)
        if not phone_e164:
            return ComplianceCheckResult.reject(
                ComplianceVerdict.INVALID_PHONE,
                f"Failed to normalize phone number: {raw_phone!r}",
            )

        # 3. DNC 5656
        is_blocked = await self.check_dnc(workspace_id, phone_e164, session=session)
        if is_blocked:
            logger.info(
                "[ComplianceGate] Rejected ws=%s: phone %s is on DNC list",
                workspace_id,
                phone_e164[:6] + "...",
            )
            return ComplianceCheckResult.reject(
                ComplianceVerdict.DNC_BLOCKED,
                "Phone is registered on National DNC 5656 or Workspace DNC blacklist",
                phone_e164=phone_e164,
            )

        # 4. 24h Frequency Cap
        locked = await self.acquire_frequency_lock(workspace_id, phone_e164)
        if not locked:
            logger.info(
                "[ComplianceGate] Rejected ws=%s: phone %s called within last 24h",
                workspace_id,
                phone_e164[:6] + "...",
            )
            return ComplianceCheckResult.reject(
                ComplianceVerdict.FREQUENCY_CAPPED,
                "Phone has already been called within the last 24 hours in this workspace",
                phone_e164=phone_e164,
            )

        # 5. Pre-call Deposit Soft-lock (if user_id present)
        reserved_amount = 0
        if user_id is not None and self.soft_lock_micros > 0:
            try:
                await self.reserve_deposit(
                    session, user_id, self.soft_lock_micros
                )
                reserved_amount = self.soft_lock_micros
            except Exception as exc:
                # Release frequency lock if deposit fails
                await self.release_frequency_lock(workspace_id, phone_e164)
                logger.warning(
                    "[ComplianceGate] Deposit reservation failed for user=%s: %s",
                    user_id,
                    exc,
                )
                return ComplianceCheckResult.reject(
                    ComplianceVerdict.INSUFFICIENT_FUNDS,
                    f"Insufficient funds to reserve 3-minute pre-call deposit: {exc}",
                    phone_e164=phone_e164,
                )

        lock_key = self._get_frequency_key(workspace_id, phone_e164)
        logger.info(
            "[ComplianceGate] APPROVED ws=%s phone=%s (lock=%s reserved=%s)",
            workspace_id,
            phone_e164[:6] + "...",
            lock_key,
            reserved_amount,
        )
        return ComplianceCheckResult.allow(
            phone_e164=phone_e164,
            lock_key=lock_key,
            reserved_micros=reserved_amount,
        )


def is_opt_out_utterance(text: str) -> bool:
    """Return True if *text* contains explicit customer opt-out phrases."""
    if not text or not text.strip():
        return False
    # NFC-normalize so STT-emitted combining diacritics still match the
    # precomposed Vietnamese keyphrases above.
    norm = unicodedata.normalize("NFC", text).lower().strip()
    return any(phrase in norm for phrase in HARD_OPTOUT_KEYPHRASES)


def is_dtmf_opt_out(key: str | int) -> bool:
    """Return True if DTMF keypress signifies an opt-out (keys 0 or 9)."""
    return str(key).strip() in {"0", "9"}
