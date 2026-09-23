"""VietQR / Napas 24/7 dynamic top-up checkout (Story 37.7 / AC-2).

Flow: the dashboard creates a *top-up intent* — a PENDING ``CreditPurchase``
row whose ``stripe_checkout_session_id`` column carries the unique transfer
memo (``NOWING <8-hex>``; the column's unique index doubles as the memo
uniqueness guarantee). The buyer has ``VIETQR_TOPUP_EXPIRES_MINUTES`` (10 min)
to complete the bank transfer. When the Napas bank-transfer webhook arrives we
verify the HMAC signature, match the memo + amount, and credit the wallet in
the same transaction — well inside the 5-second crediting SLA.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import CreditPurchase, CreditPurchaseStatus, User
from app.services.vietqr_payout_client import VietQRPayoutClient

logger = logging.getLogger(__name__)

# The dev placeholder shipped in vietqr_payout_client.py is publicly known —
# a webhook endpoint that accepts it can be forged by anyone to credit
# arbitrary wallets, so fulfilment refuses to run while it is in effect.
_DEV_WEBHOOK_SECRET = "test_webhook_secret_key_123"

# 1 dashboard credit == $0.01 == 10_000 micro-USD (matches the buy-credits UI).
MICROS_PER_CREDIT = 10_000

# Hybrid pricing packages (Story 37.7 / AC-1). Server-authoritative: clients
# send only the tier id so credit amounts can never be forged.
HYBRID_PRICING_TIERS: dict[str, dict[str, Any]] = {
    "starter": {
        "id": "starter",
        "name": "Starter",
        "price_vnd": 990_000,
        "credits": 1_000,
        "seats": 1,
        "highlighted": False,
    },
    "professional": {
        "id": "professional",
        "name": "Professional",
        "price_vnd": 2_490_000,
        "credits": 3_500,
        "seats": 3,
        "highlighted": True,
    },
    "business": {
        "id": "business",
        "name": "Business",
        "price_vnd": 5_990_000,
        "credits": 10_000,
        "seats": None,  # unlimited
        "highlighted": False,
    },
}

# Minimum ad-hoc (non-tier) VietQR top-up: 10.000đ.
MIN_CUSTOM_TOPUP_VND = 10_000

# Transfer-memo pattern emitted into the QR payload / copy block. Bank apps
# frequently mangle whitespace, so matching tolerates separators.
_MEMO_RE = re.compile(r"NOWING[\s\-]*([0-9A-F]{8})")

# Payload keys scanned (in order) for the credited amount, in VND.
_AMOUNT_KEYS = (
    "amount_vnd",
    "amount",
    "transferAmount",
    "creditAmount",
    "value",
    "amountIn",
)


def pricing_tiers() -> list[dict[str, Any]]:
    """Return the hybrid tier catalogue for the packaging UI."""
    return [
        {
            **tier,
            "credit_micros": tier["credits"] * MICROS_PER_CREDIT,
        }
        for tier in HYBRID_PRICING_TIERS.values()
    ]


def build_transfer_memo(purchase_id: UUID) -> str:
    """Deterministic transfer memo for a top-up intent: ``NOWING <8-hex>``."""
    return f"NOWING {purchase_id.hex[:8].upper()}"


def build_qr_url(*, amount_vnd: int, memo: str) -> str:
    """Dynamic VietQR image URL encoding the beneficiary account + memo."""
    return (
        "https://img.vietqr.io/image/"
        f"{config.VIETQR_BANK_BIN}-{config.VIETQR_ACCOUNT_NUMBER}-compact2.png"
        f"?amount={amount_vnd}"
        f"&addInfo={quote(memo)}"
        f"&accountName={quote(config.VIETQR_ACCOUNT_NAME)}"
    )


def _intent_expires_at(purchase: CreditPurchase) -> datetime:
    created_at = purchase.created_at or datetime.now(UTC)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return created_at + timedelta(minutes=config.VIETQR_TOPUP_EXPIRES_MINUTES)


def _intent_dict(
    purchase: CreditPurchase, *, now: datetime | None = None
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    expires_at = _intent_expires_at(purchase)
    memo = purchase.stripe_checkout_session_id
    status_value = (
        purchase.status.value
        if isinstance(purchase.status, CreditPurchaseStatus)
        else str(purchase.status)
    ).lower()
    # A PENDING intent past its window reads "expired"; EXPIRED stays expired
    # but remains webhook-creditable (funds may still arrive). FAILED is a
    # real payment failure and stays terminal.
    expired = (
        status_value == CreditPurchaseStatus.PENDING.value and now >= expires_at
    ) or status_value == CreditPurchaseStatus.EXPIRED.value
    return {
        "intent_id": str(purchase.id),
        "status": "expired" if expired else status_value,
        "amount_vnd": purchase.amount_total or 0,
        "credit_micros": purchase.credit_micros_granted,
        "credits": purchase.credit_micros_granted // MICROS_PER_CREDIT,
        "transfer_memo": memo,
        "bank_bin": config.VIETQR_BANK_BIN,
        "bank_name": config.VIETQR_BANK_NAME,
        "bank_account_number": config.VIETQR_ACCOUNT_NUMBER,
        "bank_account_name": config.VIETQR_ACCOUNT_NAME,
        "qr_url": build_qr_url(amount_vnd=purchase.amount_total or 0, memo=memo or ""),
        "expires_at": expires_at.isoformat(),
        "created_at": purchase.created_at.isoformat() if purchase.created_at else None,
    }


async def create_topup_intent(
    session: AsyncSession,
    *,
    user_id: UUID,
    tier_id: str | None = None,
    amount_vnd: int | None = None,
) -> dict[str, Any]:
    """Create a PENDING VietQR top-up intent for the user's wallet.

    ``tier_id`` purchases a hybrid package at the server-authoritative price;
    ``amount_vnd`` buys ad-hoc credit at ``VIETQR_VND_PER_USD``. Exactly one is
    required — the client never supplies the credit amount.
    """
    if not config.VIETQR_TOPUP_ENABLED:
        raise ValueError("VietQR top-ups are disabled")
    if tier_id is not None and amount_vnd is not None:
        raise ValueError("Provide either tier_id or amount_vnd, not both")
    if tier_id is not None:
        tier = HYBRID_PRICING_TIERS.get(tier_id)
        if tier is None:
            raise ValueError(f"Unknown pricing tier: {tier_id}")
        final_amount_vnd = int(tier["price_vnd"])
        credit_micros = int(tier["credits"]) * MICROS_PER_CREDIT
    elif amount_vnd is not None:
        if amount_vnd < MIN_CUSTOM_TOPUP_VND:
            raise ValueError(f"Minimum VietQR top-up is {MIN_CUSTOM_TOPUP_VND:,} VND")
        vnd_per_usd = int(config.VIETQR_VND_PER_USD)
        if vnd_per_usd <= 0:
            raise ValueError("VIETQR_VND_PER_USD must be positive")
        final_amount_vnd = int(amount_vnd)
        credit_micros = round(final_amount_vnd / vnd_per_usd * 1_000_000)
    else:
        raise ValueError("Either tier_id or amount_vnd is required")

    # A uuid/memo collision is effectively impossible, but the unique index
    # must never surface as a 500 — retry a few times on IntegrityError.
    for _attempt in range(3):
        purchase_id = uuid.uuid4()
        purchase = CreditPurchase(
            id=purchase_id,
            user_id=user_id,
            # The unique session-id column doubles as the memo store so webhook
            # matching is a single indexed equality lookup.
            stripe_checkout_session_id=build_transfer_memo(purchase_id),
            stripe_payment_intent_id=None,
            quantity=credit_micros // MICROS_PER_CREDIT,
            credit_micros_granted=credit_micros,
            amount_total=final_amount_vnd,
            currency="vnd",
            source="vietqr",
            status=CreditPurchaseStatus.PENDING,
        )
        session.add(purchase)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            continue
        await session.refresh(purchase)
        return _intent_dict(purchase)
    raise ValueError("Could not allocate a unique transfer memo; retry")


async def get_topup_intent(
    session: AsyncSession, *, intent_id: UUID, user_id: UUID
) -> dict[str, Any] | None:
    """Return intent status; lazily expires stale PENDING intents."""
    purchase = await session.get(CreditPurchase, intent_id)
    if purchase is None or purchase.user_id != user_id or purchase.source != "vietqr":
        return None

    now = datetime.now(UTC)
    if purchase.status == CreditPurchaseStatus.PENDING and now >= _intent_expires_at(
        purchase
    ):
        # Conditional UPDATE — can never clobber a concurrently COMPLETED row,
        # and EXPIRED stays webhook-creditable for late transfers.
        await session.execute(
            update(CreditPurchase)
            .where(
                CreditPurchase.id == intent_id,
                CreditPurchase.status == CreditPurchaseStatus.PENDING,
            )
            .values(status=CreditPurchaseStatus.EXPIRED)
        )
        await session.commit()
        await session.refresh(purchase)

    return _intent_dict(purchase, now=now)


def _extract_memo(payload: Any) -> str | None:
    """Find a ``NOWING XXXXXXXX`` transfer memo anywhere in the payload."""
    text = ""
    if isinstance(payload, dict):
        parts: list[str] = []
        for value in payload.values():
            if isinstance(value, (dict, list)):
                nested = _extract_memo(value)
                if nested:
                    return nested
            elif isinstance(value, str):
                parts.append(value)
        text = " ".join(parts)
    elif isinstance(payload, list):
        for item in payload:
            nested = _extract_memo(item)
            if nested:
                return nested
    else:
        text = str(payload)

    match = _MEMO_RE.search(text.upper())
    return f"NOWING {match.group(1)}" if match else None


def _coerce_amount(value: Any) -> int | None:
    """Coerce a candidate amount field; 0/empty/unparseable reads as absent."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value) if value > 0 else None
    if isinstance(value, str):
        digits = re.sub(r"[^\d]", "", value)
        if digits:
            amount = int(digits)
            return amount if amount > 0 else None
    return None


def _extract_amount_vnd(payload: Any) -> int | None:
    """Best-effort VND amount extraction across common Napas payload shapes.

    A present-but-empty/zero candidate key must not shadow a valid amount in
    another key — falsy values are skipped, not returned.
    """
    if isinstance(payload, dict):
        for key in _AMOUNT_KEYS:
            amount = _coerce_amount(payload.get(key))
            if amount is not None:
                return amount
        for value in payload.values():
            if isinstance(value, (dict, list)):
                nested = _extract_amount_vnd(value)
                if nested is not None:
                    return nested
    elif isinstance(payload, list):
        for item in payload:
            nested = _extract_amount_vnd(item)
            if nested is not None:
                return nested
    return None


def _extract_tx_reference(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in ("tx_reference", "transaction_id", "reference", "ref", "ft"):
        value = payload.get(key)
        if value:
            return str(value)[:255]
    return None


async def process_transfer_webhook(
    session: AsyncSession,
    *,
    raw_body: bytes,
    signature: str | None,
) -> dict[str, Any]:
    """Fulfil a Napas bank-transfer webhook (AC-2: credit within 5 seconds).

    Verifies the HMAC-SHA256 signature, matches the transfer memo to a
    non-terminal intent (PENDING or EXPIRED — a late transfer still means the
    money arrived), then credits the wallet in a single short transaction.
    """
    if not config.VIETQR_TOPUP_ENABLED:
        return {"status": "disabled"}

    # Read the secret at call time so env changes/tests take effect, and
    # refuse outright when it is unset or still the public dev placeholder —
    # forging a valid signature would otherwise be trivial.
    secret = os.environ.get("VIETQR_WEBHOOK_SECRET", "")
    if not secret or secret == _DEV_WEBHOOK_SECRET:
        logger.error("VietQR webhook refused: VIETQR_WEBHOOK_SECRET unconfigured")
        return {"status": "webhook_unconfigured"}

    if not VietQRPayoutClient.verify_webhook_signature(
        raw_body, signature or "", secret=secret
    ):
        return {"status": "invalid_signature"}

    try:
        payload = json.loads(raw_body)
    except (ValueError, TypeError):
        return {"status": "invalid_payload"}

    memo = _extract_memo(payload)
    if memo is None:
        return {"status": "no_memo"}

    purchase = (
        await session.execute(
            select(CreditPurchase)
            .where(
                CreditPurchase.stripe_checkout_session_id == memo,
                CreditPurchase.source == "vietqr",
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if purchase is None:
        return {"status": "no_matching_intent"}

    if purchase.status == CreditPurchaseStatus.COMPLETED:
        return {"status": "already_completed", "intent_id": str(purchase.id)}
    # EXPIRED is still creditable — the transfer genuinely arrived, just late.
    if purchase.status not in (
        CreditPurchaseStatus.PENDING,
        CreditPurchaseStatus.EXPIRED,
    ):
        return {"status": "not_pending", "intent_id": str(purchase.id)}

    amount_vnd = _extract_amount_vnd(payload)
    if amount_vnd is None:
        # Unrecognized payload shape — do NOT credit, leave the intent
        # PENDING/EXPIRED so a corrected webhook delivery can still settle it.
        logger.warning(
            "VietQR webhook for intent %s carried no parseable amount",
            purchase.id,
        )
        return {"status": "amount_unknown", "intent_id": str(purchase.id)}
    if amount_vnd < (purchase.amount_total or 0):
        logger.warning(
            "VietQR webhook underpaid for intent %s: got %s, expected %s",
            purchase.id,
            amount_vnd,
            purchase.amount_total,
        )
        return {"status": "amount_mismatch", "intent_id": str(purchase.id)}

    if datetime.now(UTC) >= _intent_expires_at(purchase):
        # The money still arrived — credit it (we owe the balance) but flag it
        # so late payments are visible in logs.
        logger.warning(
            "VietQR webhook arrived after intent expiry for %s; crediting anyway",
            purchase.id,
        )

    user = (
        await session.execute(
            select(User).where(User.id == purchase.user_id).with_for_update(of=User)
        )
    ).scalar_one_or_none()
    if user is None:
        # The wallet owner is gone — close the intent so it never stays
        # PENDING forever waiting for a retry that can't credit anyone.
        logger.error(
            "VietQR intent %s references missing user %s", purchase.id, purchase.user_id
        )
        purchase.status = CreditPurchaseStatus.FAILED
        await session.commit()
        return {"status": "user_not_found", "intent_id": str(purchase.id)}

    purchase.status = CreditPurchaseStatus.COMPLETED
    purchase.completed_at = datetime.now(UTC)
    tx_ref = _extract_tx_reference(payload)
    if tx_ref:
        purchase.stripe_payment_intent_id = tx_ref
    user.credit_micros_balance = (
        user.credit_micros_balance + purchase.credit_micros_granted
    )
    await session.commit()

    logger.info(
        "VietQR top-up credited: intent=%s user=%s micros=%s amount_vnd=%s",
        purchase.id,
        user.id,
        purchase.credit_micros_granted,
        amount_vnd,
    )
    return {
        "status": "credited",
        "intent_id": str(purchase.id),
        "credit_micros": purchase.credit_micros_granted,
    }
