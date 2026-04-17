"""Stripe routes for subscriptions and token top-up purchases."""

from __future__ import annotations

import logging
import secrets
import string
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from stripe import SignatureVerificationError, StripeClient, StripeError

from app.config import config
from app.db import (
    GiftCode,
    GiftCodeStatus,
    GiftRequest,
    GiftRequestStatus,
    SubscriptionRequest,
    SubscriptionRequestStatus,
    SubscriptionStatus,
    User,
    get_async_session,
)
from app.schemas.stripe import (
    BillingPortalResponse,
    CreateGiftCheckoutRequest,
    CreateGiftCheckoutResponse,
    CreateSubscriptionCheckoutRequest,
    CreateSubscriptionCheckoutResponse,
    CreateTokenTopupRequest,
    CreateTokenTopupResponse,
    GiftCodeItem,
    GiftCodesResponse,
    PlanId,
    RedeemGiftRequest,
    RedeemGiftResponse,
    RequestGiftRequest,
    RequestGiftResponse,
    StripeStatusResponse,
    StripeWebhookResponse,
)
from app.users import current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stripe", tags=["stripe"])

# ---------------------------------------------------------------------------
# Simple in-memory rate limiter for verify-checkout-session (20 calls/60 s)
# Not persistent across workers — acceptable for the low-risk, low-volume
# nature of this endpoint.
# ---------------------------------------------------------------------------
_VERIFY_SESSION_WINDOW_SECS = 60
_VERIFY_SESSION_MAX_CALLS = 20
_verify_session_calls: dict[str, list[float]] = defaultdict(list)


def _check_verify_session_rate_limit(user_id: str) -> None:
    now = datetime.now(UTC).timestamp()
    cutoff = now - _VERIFY_SESSION_WINDOW_SECS
    calls = [t for t in _verify_session_calls[user_id] if t > cutoff]
    if len(calls) >= _VERIFY_SESSION_MAX_CALLS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Try again later.",
        )
    calls.append(now)
    _verify_session_calls[user_id] = calls


def get_stripe_client() -> StripeClient:
    """Return a configured Stripe client or raise if Stripe is disabled."""
    if not config.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe checkout is not configured.",
        )
    return StripeClient(config.STRIPE_SECRET_KEY)


def _get_token_topup_urls(search_space_id: int) -> tuple[str, str]:
    if not config.NEXT_FRONTEND_URL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NEXT_FRONTEND_URL is not configured.",
        )
    base_url = config.NEXT_FRONTEND_URL.rstrip("/")
    success_url = f"{base_url}/dashboard/{search_space_id}/purchase-success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base_url}/dashboard/{search_space_id}/purchase-cancel"
    return success_url, cancel_url


def _get_gift_urls(search_space_id: int) -> tuple[str, str]:
    """Return (success_url, cancel_url) for gift checkout."""
    if not config.NEXT_FRONTEND_URL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NEXT_FRONTEND_URL is not configured.",
        )
    base_url = config.NEXT_FRONTEND_URL.rstrip("/")
    success_url = f"{base_url}/dashboard/{search_space_id}/purchase-success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base_url}/dashboard/{search_space_id}/purchase-cancel"
    return success_url, cancel_url


def _normalize_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return getattr(value, "id", str(value))


def _get_subscription_urls() -> tuple[str, str]:
    """Return (success_url, cancel_url) for subscription checkout."""
    if not config.NEXT_FRONTEND_URL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NEXT_FRONTEND_URL is not configured.",
        )
    base = config.NEXT_FRONTEND_URL.rstrip("/")
    success_url = f"{base}/subscription-success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base}/pricing"
    return success_url, cancel_url


def _resolve_plan_price_id(plan_id: PlanId) -> str | None:
    """Return the Stripe Price ID for a plan, or None if not configured."""
    mapping = {
        PlanId.pro_monthly: config.STRIPE_PRO_MONTHLY_PRICE_ID,
        PlanId.pro_yearly: config.STRIPE_PRO_YEARLY_PRICE_ID,
        PlanId.max_monthly: config.STRIPE_MAX_MONTHLY_PRICE_ID,
        PlanId.max_yearly: config.STRIPE_MAX_YEARLY_PRICE_ID,
    }
    return mapping.get(plan_id) or None


def _get_price_id_for_plan(plan_id: PlanId) -> str:
    """Map a plan_id enum to the corresponding Stripe Price ID from env vars.

    Raises HTTP 503 if the price ID is not configured.
    """
    price_id = _resolve_plan_price_id(plan_id)
    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Stripe price ID for plan '{plan_id.value}' is not configured.",
        )
    return price_id


async def _get_or_create_stripe_customer(
    stripe_client: StripeClient,
    user: User,
    db_session: AsyncSession,
) -> str:
    """Return existing Stripe customer ID or create a new one and persist it.

    Uses SELECT ... FOR UPDATE to prevent duplicate customer creation under
    concurrent requests for the same user.
    """
    if user.stripe_customer_id:
        return user.stripe_customer_id

    locked_user = (
        (
            await db_session.execute(
                select(User).where(User.id == user.id).with_for_update()
            )
        )
        .unique()
        .scalar_one()
    )

    # Re-check after acquiring the lock — another request may have created it.
    if locked_user.stripe_customer_id:
        return locked_user.stripe_customer_id

    try:
        customer = stripe_client.v1.customers.create(
            params={
                "email": locked_user.email,
                "metadata": {"user_id": str(locked_user.id)},
            }
        )
    except StripeError as exc:
        logger.exception("Failed to create Stripe customer for user %s", locked_user.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to create Stripe customer.",
        ) from exc

    locked_user.stripe_customer_id = str(customer.id)
    await db_session.commit()
    return locked_user.stripe_customer_id


def _get_metadata(checkout_session: Any) -> dict[str, str]:
    metadata = getattr(checkout_session, "metadata", None) or {}
    if isinstance(metadata, dict):
        return {str(key): str(value) for key, value in metadata.items()}
    return dict(metadata)


async def _fulfill_token_topup(
    db_session: AsyncSession, checkout_session: Any
) -> StripeWebhookResponse:
    """Add purchased tokens to the user after a confirmed Stripe payment.

    Uses SELECT ... FOR UPDATE on the User row to prevent double-granting
    when Stripe retries the webhook concurrently.
    """
    metadata = _get_metadata(checkout_session)
    user_id_str = metadata.get("user_id")
    tokens_granted_str = metadata.get("tokens_granted")

    if not user_id_str or not tokens_granted_str:
        logger.warning(
            "Token topup webhook missing metadata for session %s", checkout_session.id
        )
        return StripeWebhookResponse()

    try:
        tokens_to_add = int(tokens_granted_str)
    except ValueError:
        logger.error(
            "Invalid tokens_granted '%s' in webhook for session %s",
            tokens_granted_str,
            checkout_session.id,
        )
        return StripeWebhookResponse()

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        logger.error(
            "Invalid user_id '%s' in token topup metadata for session %s",
            user_id_str,
            checkout_session.id,
        )
        return StripeWebhookResponse()

    user = (
        (
            await db_session.execute(
                select(User).where(User.id == user_id).with_for_update(of=User)
            )
        )
        .unique()
        .scalar_one_or_none()
    )
    if user is None:
        logger.error(
            "User %s not found for token topup session %s", user_id, checkout_session.id
        )
        return StripeWebhookResponse()

    # Idempotency: check if this checkout session was already fulfilled.
    # Stripe metadata is immutable, so we store a marker on the user's row
    # by checking against the checkout session ID stored in a simple log.
    checkout_id = str(checkout_session.id)
    fulfilled_sessions = set(
        (user.fulfilled_topup_sessions or "").split(",")
    )
    if checkout_id in fulfilled_sessions:
        logger.info(
            "Token topup already fulfilled for session %s, skipping", checkout_id
        )
        return StripeWebhookResponse()

    user.purchased_tokens = (user.purchased_tokens or 0) + tokens_to_add

    # Track fulfilled session for idempotency
    fulfilled_sessions.discard("")
    fulfilled_sessions.add(checkout_id)
    user.fulfilled_topup_sessions = ",".join(fulfilled_sessions)

    logger.info(
        "Granted %d tokens to user %s via topup (session %s)",
        tokens_to_add,
        user.id,
        checkout_session.id,
    )
    await db_session.commit()
    return StripeWebhookResponse()


# ---------------------------------------------------------------------------
# Gift code fulfillment
# ---------------------------------------------------------------------------

_GIFT_CODE_CHARS = string.ascii_uppercase + string.digits


def _generate_gift_code() -> str:
    """Generate a random gift code in format GIFT-XXXX-XXXX-XXXX."""
    groups = [
        "".join(secrets.choice(_GIFT_CODE_CHARS) for _ in range(4)) for _ in range(3)
    ]
    return "GIFT-" + "-".join(groups)


def _mask_gift_code(code: str) -> str:
    """Return a log-safe representation of a gift code (prefix + last 4)."""
    if not code or len(code) < 4:
        return "GIFT-****"
    return f"GIFT-****-****-{code[-4:]}"


async def _mint_gift_code(
    db_session: AsyncSession,
    *,
    plan_id: str,
    duration_months: int,
    amount_paid: int,
    purchaser_id: uuid.UUID,
    stripe_payment_intent_id: str | None = None,
    expires_at: datetime | None = None,
) -> GiftCode:
    """Mint a new GiftCode with unique code, flushing to DB but NOT committing.

    Retries up to 3 times on code collision. Caller must commit the session.
    Raises IntegrityError after max_attempts if collisions persist, or on
    other constraint violations (FK, payment_intent unique).
    """
    if expires_at is None:
        expires_at = datetime.now(UTC) + timedelta(days=365)

    max_attempts = 3
    last_exc: IntegrityError | None = None
    for attempt in range(1, max_attempts + 1):
        code = _generate_gift_code()
        gift = GiftCode(
            code=code,
            plan_id=plan_id,
            duration_months=duration_months,
            amount_paid=amount_paid,
            purchaser_id=purchaser_id,
            stripe_payment_intent_id=stripe_payment_intent_id,
            status=GiftCodeStatus.ACTIVE,
            expires_at=expires_at,
        )
        try:
            async with db_session.begin_nested():
                db_session.add(gift)
                await db_session.flush()
            return gift
        except IntegrityError as exc:
            last_exc = exc
            constraint = getattr(getattr(exc, "orig", None), "diag", None)
            constraint_name = getattr(constraint, "constraint_name", "") or ""
            is_code_collision = constraint_name == "uq_gift_codes_code"
            if not is_code_collision:
                # FK violation / payment_intent unique — retry won't help.
                raise
            if attempt < max_attempts:
                logger.warning(
                    "Gift code collision on attempt %d for purchaser %s, retrying",
                    attempt,
                    purchaser_id,
                )
    assert last_exc is not None
    raise last_exc


async def _fulfill_gift_purchase(
    db_session: AsyncSession, checkout_session: Any
) -> StripeWebhookResponse:
    """Create a gift code record after a confirmed Stripe gift payment.

    Idempotency: always returns 200 to Stripe so redeliveries are not retried
    indefinitely. If a gift code for this payment_intent_id already exists,
    skip insert and return success. On unrecoverable errors (invalid metadata,
    FK violation, collision retries exhausted) we log and return 200 — Stripe
    has already captured the payment, so an admin must reconcile manually.
    """
    metadata = _get_metadata(checkout_session)
    purchaser_id_str = metadata.get("purchaser_id")
    plan_id = metadata.get("plan_id")
    duration_months_str = metadata.get("duration_months")
    amount_cents_str = metadata.get("amount_cents")

    if not all([purchaser_id_str, plan_id, duration_months_str, amount_cents_str]):
        logger.error(
            "Gift webhook missing metadata for session %s: %s — payment captured, manual reconciliation required",
            checkout_session.id,
            metadata,
        )
        return StripeWebhookResponse()

    try:
        purchaser_id = uuid.UUID(purchaser_id_str)
        duration_months = int(duration_months_str)
        amount_paid = int(amount_cents_str)
    except (ValueError, TypeError) as exc:
        logger.error(
            "Gift webhook invalid metadata for session %s: %s — payment captured, manual reconciliation required",
            checkout_session.id,
            exc,
        )
        return StripeWebhookResponse()

    # Cross-verify amount against server-side pricing to detect tampering
    plan_pricing = config.GIFT_PRICING.get(plan_id)
    expected_amount = plan_pricing.get(duration_months) if plan_pricing else None
    if expected_amount is None or expected_amount != amount_paid:
        logger.error(
            "Gift webhook pricing mismatch for session %s: plan=%s duration=%s metadata_amount=%s expected=%s — manual reconciliation required",
            checkout_session.id,
            plan_id,
            duration_months,
            amount_paid,
            expected_amount,
        )
        return StripeWebhookResponse()

    if duration_months <= 0 or amount_paid <= 0:
        logger.error(
            "Gift webhook non-positive values for session %s: duration=%s amount=%s",
            checkout_session.id,
            duration_months,
            amount_paid,
        )
        return StripeWebhookResponse()

    payment_intent = getattr(checkout_session, "payment_intent", None)
    if hasattr(payment_intent, "id"):
        payment_intent_id = str(payment_intent.id)
    elif payment_intent:
        payment_intent_id = str(payment_intent)
    else:
        payment_intent_id = ""

    # Idempotency pre-check: Stripe redeliveries reuse payment_intent_id,
    # so bail out early instead of hitting the partial unique index
    # (uq_gift_codes_stripe_payment_intent_id) and burning retry attempts.
    if payment_intent_id:
        existing_stmt = select(GiftCode.id).where(
            GiftCode.stripe_payment_intent_id == payment_intent_id
        )
        existing = (await db_session.execute(existing_stmt)).scalar_one_or_none()
        if existing is not None:
            logger.info(
                "Gift webhook already fulfilled for payment_intent %s (session %s) — skipping",
                payment_intent_id,
                checkout_session.id,
            )
            return StripeWebhookResponse()

    expires_at = datetime.now(UTC) + timedelta(days=365)

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        code = _generate_gift_code()
        gift = GiftCode(
            code=code,
            plan_id=plan_id,
            duration_months=duration_months,
            amount_paid=amount_paid,
            purchaser_id=purchaser_id,
            stripe_payment_intent_id=payment_intent_id or None,
            status=GiftCodeStatus.ACTIVE,
            expires_at=expires_at,
        )
        db_session.add(gift)
        try:
            await db_session.commit()
            logger.info(
                "Gift code %s created for user %s (session %s)",
                _mask_gift_code(code),
                purchaser_id,
                checkout_session.id,
            )
            return StripeWebhookResponse()
        except IntegrityError as exc:
            await db_session.rollback()
            constraint = getattr(getattr(exc, "orig", None), "diag", None)
            constraint_name = getattr(constraint, "constraint_name", "") or ""
            # Only retry on gift code collision; other integrity errors
            # (FK violation, payment_intent unique) won't be fixed by retry.
            is_code_collision = "code" in constraint_name and "pkey" not in constraint_name
            if not is_code_collision:
                logger.error(
                    "Gift webhook integrity error for session %s (constraint=%s): %s — manual reconciliation required",
                    checkout_session.id,
                    constraint_name or "unknown",
                    exc,
                )
                return StripeWebhookResponse()
            if attempt < max_attempts:
                logger.warning(
                    "Gift code collision on attempt %d for session %s, retrying",
                    attempt,
                    checkout_session.id,
                )
            else:
                logger.error(
                    "Failed to create gift code after %d attempts for session %s — manual reconciliation required",
                    max_attempts,
                    checkout_session.id,
                )
                return StripeWebhookResponse()

    return StripeWebhookResponse()


# ---------------------------------------------------------------------------
# Subscription event helpers
# ---------------------------------------------------------------------------


async def _get_user_by_stripe_customer_id(
    db_session: AsyncSession, customer_id: str
) -> User | None:
    """Fetch the User row for a given Stripe customer ID (with FOR UPDATE lock)."""
    return (
        (
            await db_session.execute(
                select(User)
                .where(User.stripe_customer_id == customer_id)
                .with_for_update(of=User)
            )
        )
        .unique()
        .scalar_one_or_none()
    )


def _period_end_from_subscription(subscription: Any) -> datetime | None:
    """Extract current_period_end timestamp from a Stripe subscription object."""
    ts = getattr(subscription, "current_period_end", None)
    if ts is None:
        return None
    return datetime.fromtimestamp(int(ts), tz=UTC)


async def _handle_subscription_event(
    db_session: AsyncSession, subscription: Any
) -> StripeWebhookResponse:
    """Handle customer.subscription.created / updated / deleted.

    Idempotency: compares stripe_subscription_id + current_period_end so
    duplicate events for the same billing period are no-ops.
    """
    customer_id = _normalize_optional_string(getattr(subscription, "customer", None))
    subscription_id = _normalize_optional_string(getattr(subscription, "id", None))
    sub_status = str(getattr(subscription, "status", "")).lower()
    period_end = _period_end_from_subscription(subscription)

    # Determine plan from the first subscription item's price ID
    plan_id: str = "free"
    try:
        items = getattr(subscription, "items", None)
        if items:
            item_data = getattr(items, "data", None) or []
            if item_data:
                price_id = str(getattr(item_data[0].price, "id", ""))
                if price_id == config.STRIPE_PRO_YEARLY_PRICE_ID:
                    plan_id = "pro_yearly"
                elif price_id == config.STRIPE_PRO_MONTHLY_PRICE_ID:
                    plan_id = "pro_monthly"
                else:
                    logger.warning(
                        "Subscription %s has unrecognized price ID %s; defaulting to free limits",
                        subscription_id,
                        price_id,
                    )
    except Exception:
        logger.warning("Could not parse plan from subscription %s", subscription_id)

    if not customer_id:
        logger.error(
            "Subscription event missing customer ID for subscription %s",
            subscription_id,
        )
        return StripeWebhookResponse()

    # Safety: never silently downgrade an active subscription to "free" due to
    # an unrecognized price ID. Return early without modifying the user.
    if (
        plan_id == "free"
        and str(getattr(subscription, "status", "")).lower() == "active"
    ):
        logger.error(
            "Subscription %s is active but price ID is unrecognized — skipping update to avoid downgrade",
            subscription_id,
        )
        return StripeWebhookResponse()

    user = await _get_user_by_stripe_customer_id(db_session, customer_id)
    if user is None:
        logger.warning(
            "No user found for Stripe customer %s; skipping subscription event",
            customer_id,
        )
        return StripeWebhookResponse()

    # Map Stripe status → SubscriptionStatus enum
    if sub_status == "active":
        new_status = SubscriptionStatus.ACTIVE
    elif sub_status in {"canceled", "incomplete_expired"}:
        new_status = SubscriptionStatus.CANCELED
        plan_id = "free"
    elif sub_status == "past_due":
        new_status = SubscriptionStatus.PAST_DUE
    else:
        # incomplete, trialing, unpaid → leave current status unchanged
        logger.info(
            "Ignoring subscription %s with unhandled Stripe status '%s'",
            subscription_id,
            sub_status,
        )
        return StripeWebhookResponse()

    # Idempotency: skip if nothing meaningful changed
    if (
        user.stripe_subscription_id == subscription_id
        and user.subscription_status == new_status
        and user.plan_id == plan_id
        and user.subscription_current_period_end == period_end
    ):
        logger.info("Subscription %s already up-to-date; skipping", subscription_id)
        return StripeWebhookResponse()

    # Update subscription fields
    user.stripe_subscription_id = subscription_id
    user.subscription_status = new_status
    user.plan_id = plan_id
    # Guard against out-of-order webhook delivery: only advance period_end forward
    if period_end is not None and (
        user.subscription_current_period_end is None
        or period_end > user.subscription_current_period_end
    ):
        user.subscription_current_period_end = period_end

    # Update limits from plan config
    limits = config.PLAN_LIMITS.get(plan_id, config.PLAN_LIMITS["free"])
    user.monthly_token_limit = limits["monthly_token_limit"]

    # Upgrade pages_limit on activation; reset token counter date
    if new_status == SubscriptionStatus.ACTIVE:
        user.pages_limit = max(user.pages_used, limits["pages_limit"])
        if user.token_reset_date is None:
            user.token_reset_date = datetime.now(UTC).date()

    # Downgrade pages_limit when canceling
    if new_status == SubscriptionStatus.CANCELED:
        free_limits = config.PLAN_LIMITS["free"]
        user.pages_limit = max(user.pages_used, free_limits["pages_limit"])

    logger.info(
        "Updated subscription for user %s: status=%s plan=%s subscription=%s",
        user.id,
        new_status,
        plan_id,
        subscription_id,
    )
    await db_session.commit()
    return StripeWebhookResponse()


async def _handle_invoice_payment_succeeded(
    db_session: AsyncSession, invoice: Any
) -> StripeWebhookResponse:
    """Reset tokens_used_this_month and advance token_reset_date on billing renewal."""
    customer_id = _normalize_optional_string(getattr(invoice, "customer", None))
    billing_reason = str(getattr(invoice, "billing_reason", "")).lower()

    if not customer_id:
        return StripeWebhookResponse()

    # Reset tokens on subscription renewals and initial subscription creation
    if billing_reason not in {"subscription_cycle", "subscription_create"}:
        logger.info(
            "invoice.payment_succeeded billing_reason=%s; not resetting tokens",
            billing_reason,
        )
        return StripeWebhookResponse()

    user = await _get_user_by_stripe_customer_id(db_session, customer_id)
    if user is None:
        logger.warning(
            "No user found for Stripe customer %s; skipping token reset", customer_id
        )
        return StripeWebhookResponse()

    user.tokens_used_this_month = 0
    user.purchased_tokens = 0
    user.token_reset_date = datetime.now(UTC).date()

    logger.info(
        "Reset tokens_used_this_month and purchased_tokens for user %s on subscription renewal", user.id
    )
    await db_session.commit()
    return StripeWebhookResponse()


async def _handle_invoice_payment_failed(
    db_session: AsyncSession, invoice: Any
) -> StripeWebhookResponse:
    """Mark subscription as past_due when a renewal invoice payment fails."""
    customer_id = _normalize_optional_string(getattr(invoice, "customer", None))
    if not customer_id:
        return StripeWebhookResponse()

    user = await _get_user_by_stripe_customer_id(db_session, customer_id)
    if user is None:
        logger.warning(
            "No user found for Stripe customer %s; skipping past_due update",
            customer_id,
        )
        return StripeWebhookResponse()

    if user.subscription_status == SubscriptionStatus.ACTIVE:
        user.subscription_status = SubscriptionStatus.PAST_DUE
        logger.info("Set subscription to PAST_DUE for user %s", user.id)
        await db_session.commit()
    else:
        logger.info(
            "invoice.payment_failed for user %s already in status %s; no change",
            user.id,
            user.subscription_status,
        )

    return StripeWebhookResponse()


async def _activate_subscription_from_checkout(
    db_session: AsyncSession, checkout_session: Any
) -> StripeWebhookResponse:
    """Activate subscription when checkout.session.completed fires for mode='subscription'.

    The full subscription lifecycle will also be handled by customer.subscription.created,
    but we activate immediately here so the user sees Pro access right after checkout.
    """
    customer_id = _normalize_optional_string(
        getattr(checkout_session, "customer", None)
    )
    subscription_id = _normalize_optional_string(
        getattr(checkout_session, "subscription", None)
    )
    metadata = _get_metadata(checkout_session)
    plan_id_str = metadata.get("plan_id", "")

    if not customer_id:
        logger.error(
            "Subscription checkout session missing customer ID: %s",
            getattr(checkout_session, "id", ""),
        )
        return StripeWebhookResponse()

    user = await _get_user_by_stripe_customer_id(db_session, customer_id)
    if user is None:
        logger.warning(
            "No user found for Stripe customer %s; skipping subscription activation",
            customer_id,
        )
        return StripeWebhookResponse()

    # Idempotency: already activated
    if (
        user.subscription_status == SubscriptionStatus.ACTIVE
        and user.stripe_subscription_id == subscription_id
    ):
        logger.info(
            "Subscription already active for user %s; skipping activation", user.id
        )
        return StripeWebhookResponse()

    plan_id = (
        plan_id_str
        if plan_id_str in {"pro_monthly", "pro_yearly", "max_monthly", "max_yearly"}
        else "pro_monthly"
    )
    limits = config.PLAN_LIMITS.get(plan_id, config.PLAN_LIMITS["pro_monthly"])

    user.subscription_status = SubscriptionStatus.ACTIVE
    user.plan_id = plan_id
    user.stripe_subscription_id = subscription_id
    user.monthly_token_limit = limits["monthly_token_limit"]
    user.pages_limit = max(user.pages_used, limits["pages_limit"])
    user.tokens_used_this_month = 0
    user.token_reset_date = datetime.now(UTC).date()

    # Retrieve subscription object to set period_end (best-effort)
    if subscription_id:
        try:
            stripe_client = get_stripe_client()
            sub_obj = stripe_client.v1.subscriptions.retrieve(subscription_id)
            user.subscription_current_period_end = _period_end_from_subscription(
                sub_obj
            )
        except Exception:
            logger.warning(
                "Could not retrieve subscription %s for period_end", subscription_id
            )

    logger.info(
        "Activated subscription for user %s: plan=%s subscription=%s",
        user.id,
        plan_id,
        subscription_id,
    )
    await db_session.commit()
    return StripeWebhookResponse()


# Token rate: $1 USD = 100,000 tokens
_TOKENS_PER_USD = 100_000


@router.post("/create-token-topup-checkout", response_model=CreateTokenTopupResponse)
async def create_token_topup_checkout(
    body: CreateTokenTopupRequest,
    user: User = Depends(current_active_user),
) -> CreateTokenTopupResponse:
    """Create a Stripe Checkout Session for buying additional LLM tokens.

    Uses Stripe price_data so no pre-created price IDs are required.
    Rate: $1 USD = 100,000 tokens.
    When Stripe is not configured (no STRIPE_SECRET_KEY), returns admin_approval_mode=True
    so the user knows to contact an admin to have tokens added manually.
    """
    # Admin-approval mode: Stripe not configured — inform user to contact admin
    if not config.STRIPE_SECRET_KEY:
        logger.info(
            "Token topup admin-approval mode: no Stripe key, user %s requested %.2f USD",
            user.id,
            body.amount_usd,
        )
        return CreateTokenTopupResponse(checkout_url="", admin_approval_mode=True)

    stripe_client = get_stripe_client()

    amount_cents = max(100, round(body.amount_usd * 100))  # minimum $1
    tokens_granted = round(body.amount_usd * _TOKENS_PER_USD)

    success_url, cancel_url = _get_token_topup_urls(body.search_space_id)

    try:
        checkout_session = stripe_client.v1.checkout.sessions.create(
            params={
                "mode": "payment",
                "success_url": success_url,
                "cancel_url": cancel_url,
                "line_items": [
                    {
                        "price_data": {
                            "currency": "usd",
                            "unit_amount": amount_cents,
                            "product_data": {
                                "name": f"Token Top-up — {tokens_granted:,} tokens",
                                "description": (
                                    f"Add {tokens_granted:,} LLM tokens to your Nowing account."
                                    " Tokens expire at the end of your current billing period."
                                ),
                            },
                        },
                        "quantity": 1,
                    }
                ],
                "client_reference_id": str(user.id),
                "customer_email": user.email,
                "metadata": {
                    "user_id": str(user.id),
                    "tokens_granted": str(tokens_granted),
                    "purchase_type": "token_topup",
                },
            }
        )
    except (StripeError, HTTPException) as exc:
        logger.warning(
            "Stripe token topup failed for user %s, falling back to admin-approval: %s",
            user.id,
            exc,
        )
        return CreateTokenTopupResponse(checkout_url="", admin_approval_mode=True)

    checkout_url = getattr(checkout_session, "url", None)
    if not checkout_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Stripe checkout session did not return a URL.",
        )

    return CreateTokenTopupResponse(checkout_url=checkout_url)


@router.post("/create-gift-checkout", response_model=CreateGiftCheckoutResponse)
async def create_gift_checkout(
    body: CreateGiftCheckoutRequest,
    user: User = Depends(current_active_user),
) -> CreateGiftCheckoutResponse:
    """Create a Stripe Checkout Session for purchasing a gift subscription.

    Uses Stripe price_data so no pre-created price IDs are required.
    Returns admin_approval_mode=True when Stripe is not configured (no
    STRIPE_SECRET_KEY) or when Stripe raises an error during session creation.
    """
    # Validate plan_id and duration_months against GIFT_PRICING config
    plan_pricing = config.GIFT_PRICING.get(body.plan_id)
    if not plan_pricing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid plan_id '{body.plan_id}'. "
                f"Valid plans: {list(config.GIFT_PRICING)}"
            ),
        )
    amount_cents = plan_pricing.get(body.duration_months)
    if amount_cents is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid duration_months {body.duration_months} for plan "
                f"'{body.plan_id}'. Valid durations: {sorted(plan_pricing)}"
            ),
        )

    # Admin-approval fallback: Stripe not configured
    if not config.STRIPE_SECRET_KEY:
        logger.info(
            "Gift checkout admin-approval mode: no Stripe key, user %s requested %s x%d months",
            user.id,
            body.plan_id,
            body.duration_months,
        )
        return CreateGiftCheckoutResponse(checkout_url="", admin_approval_mode=True)

    stripe_client = get_stripe_client()

    # Gift purchases are not tied to a specific search space — use 0 placeholder
    # in success/cancel URLs. Frontend (Story 6.6) handles redirect.
    success_url, cancel_url = _get_gift_urls(0)

    plan_label = body.plan_id.replace("_", " ").title()

    try:
        checkout_session = stripe_client.v1.checkout.sessions.create(
            params={
                "mode": "payment",
                "success_url": success_url,
                "cancel_url": cancel_url,
                "line_items": [
                    {
                        "price_data": {
                            "currency": "usd",
                            "unit_amount": amount_cents,
                            "product_data": {
                                "name": (
                                    f"Nowing Gift — {plan_label} × "
                                    f"{body.duration_months} month(s)"
                                ),
                                "description": (
                                    f"Gift subscription: {plan_label} for "
                                    f"{body.duration_months} month(s). "
                                    "The recipient can redeem this gift code "
                                    "in their account settings."
                                ),
                            },
                        },
                        "quantity": 1,
                    }
                ],
                "client_reference_id": str(user.id),
                "customer_email": user.email,
                "metadata": {
                    "purchase_type": "gift",
                    "purchaser_id": str(user.id),
                    "plan_id": body.plan_id,
                    "duration_months": str(body.duration_months),
                    "amount_cents": str(amount_cents),
                },
            }
        )
    except StripeError as exc:
        logger.warning(
            "Stripe gift checkout failed for user %s, falling back to admin-approval: %s",
            user.id,
            exc,
        )
        return CreateGiftCheckoutResponse(checkout_url="", admin_approval_mode=True)

    checkout_url = getattr(checkout_session, "url", None)
    if not checkout_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Stripe checkout session did not return a URL.",
        )

    return CreateGiftCheckoutResponse(checkout_url=checkout_url)


@router.post("/redeem-gift", response_model=RedeemGiftResponse)
async def redeem_gift(
    body: RedeemGiftRequest,
    user: User = Depends(current_active_user),
    db_session: AsyncSession = Depends(get_async_session),
) -> RedeemGiftResponse:
    """Redeem a gift code and extend the user's subscription.

    The gift code must be active, not expired, and not already redeemed.
    Extension formula: new_expiry = max(current_period_end, now()) + 30 * duration_months days.

    If the user has an active Stripe-managed subscription, only the period end
    is extended — plan/limits stay under Stripe's control to avoid state drift.
    Otherwise the gift's plan/limits are applied to the user.
    """
    normalized_code = body.code.strip().upper()
    if not normalized_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gift code không hợp lệ hoặc đã được sử dụng",
        )

    gift = (
        await db_session.execute(
            select(GiftCode)
            .where(GiftCode.code == normalized_code)
            .with_for_update()
        )
    ).scalar_one_or_none()

    if (
        gift is None
        or gift.status != GiftCodeStatus.ACTIVE
        or gift.redeemer_id is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gift code không hợp lệ hoặc đã được sử dụng",
        )

    now = datetime.now(UTC)

    if gift.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gift code đã hết hạn",
        )

    if gift.duration_months <= 0:
        logger.error(
            "Gift code %s has invalid duration_months=%s — refusing redeem",
            _mask_gift_code(gift.code),
            gift.duration_months,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gift code không hợp lệ hoặc đã được sử dụng",
        )

    if gift.plan_id not in config.PLAN_LIMITS:
        logger.error(
            "Gift code %s targets unknown plan_id=%s (not in PLAN_LIMITS) — refusing redeem",
            _mask_gift_code(gift.code),
            gift.plan_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gói của gift code không còn được hỗ trợ, vui lòng liên hệ support.",
        )

    # Re-lock user row to serialize concurrent redemptions from the same user
    locked_user = (
        await db_session.execute(
            select(User).where(User.id == user.id).with_for_update()
        )
    ).scalar_one()

    base_expiry = (
        locked_user.subscription_current_period_end
        if locked_user.subscription_current_period_end
        and locked_user.subscription_current_period_end > now
        else now
    )
    new_expiry = base_expiry + timedelta(days=30 * gift.duration_months)

    # Preserve plan for any user on an active paid plan (Stripe-backed OR
    # admin-seeded). Gift is a time extension, not a tier change — never
    # downgrade a paying/seeded PRO/MAX user to the gift's plan_id.
    has_active_paid_plan = (
        locked_user.subscription_status
        in {SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE}
        and locked_user.plan_id in config.PLAN_LIMITS
        and locked_user.plan_id != "free"
    )

    locked_user.subscription_current_period_end = new_expiry

    if has_active_paid_plan:
        logger.info(
            "Gift %s redeemed by active-paid user %s (plan=%s) — period extended to %s, plan unchanged",
            _mask_gift_code(gift.code),
            locked_user.id,
            locked_user.plan_id,
            new_expiry,
        )
    else:
        limits = config.PLAN_LIMITS[gift.plan_id]
        locked_user.plan_id = gift.plan_id
        locked_user.subscription_status = SubscriptionStatus.ACTIVE
        locked_user.monthly_token_limit = limits["monthly_token_limit"]
        locked_user.pages_limit = max(locked_user.pages_used, limits["pages_limit"])
        locked_user.tokens_used_this_month = 0
        locked_user.purchased_tokens = 0
        locked_user.token_reset_date = now.date()

    gift.status = GiftCodeStatus.REDEEMED
    gift.redeemed_at = now
    gift.redeemer_id = locked_user.id

    await db_session.commit()

    logger.info(
        "Gift code %s redeemed by user %s, new expiry: %s",
        _mask_gift_code(gift.code),
        locked_user.id,
        new_expiry,
    )

    return RedeemGiftResponse(new_expiry=new_expiry, plan_id=gift.plan_id)


@router.get("/gift-codes", response_model=GiftCodesResponse)
async def get_gift_codes(
    user: User = Depends(current_active_user),
    db_session: AsyncSession = Depends(get_async_session),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> GiftCodesResponse:
    """List all gift codes purchased by the current user."""
    result = await db_session.execute(
        select(GiftCode)
        .where(GiftCode.purchaser_id == user.id)
        .order_by(GiftCode.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    gifts = result.scalars().all()
    items = [
        GiftCodeItem(
            id=g.id,
            code=g.code,
            plan_id=g.plan_id,
            duration_months=g.duration_months,
            status=g.status.value,
            created_at=g.created_at,
            expires_at=g.expires_at,
            redeemed_at=g.redeemed_at,
        )
        for g in gifts
    ]
    return GiftCodesResponse(items=items, count=len(items))


@router.post("/request-gift", response_model=RequestGiftResponse)
async def request_gift(
    body: RequestGiftRequest,
    user: User = Depends(current_active_user),
    db_session: AsyncSession = Depends(get_async_session),
) -> RequestGiftResponse:
    """Create an admin-approval gift request when Stripe is unavailable.

    Used as fallback when create-gift-checkout returns admin_approval_mode=True
    (either because STRIPE_SECRET_KEY is unset or because Stripe raised an
    error during session creation).
    """
    plan_id_str = body.plan_id.value
    plan_pricing = config.GIFT_PRICING.get(plan_id_str)
    if not plan_pricing or body.duration_months not in plan_pricing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid plan_id or duration_months.",
        )

    # Serialize concurrent request_gift calls for the same user to prevent
    # duplicate PENDING rows from racing double-submits.
    await db_session.execute(
        select(User.id).where(User.id == user.id).with_for_update()
    )

    existing = await db_session.execute(
        select(GiftRequest)
        .where(GiftRequest.user_id == user.id)
        .where(GiftRequest.plan_id == plan_id_str)
        .where(GiftRequest.duration_months == body.duration_months)
        .where(GiftRequest.status == GiftRequestStatus.PENDING)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bạn đã có yêu cầu đang chờ xử lý cho gói này.",
        )

    req = GiftRequest(
        user_id=user.id,
        plan_id=plan_id_str,
        duration_months=body.duration_months,
    )
    db_session.add(req)
    await db_session.commit()
    await db_session.refresh(req)

    logger.info(
        "Gift request created for user %s (plan=%s, months=%d)",
        user.id,
        plan_id_str,
        body.duration_months,
    )

    return RequestGiftResponse(
        request_id=req.id,
        message="Yêu cầu của bạn đang chờ admin xử lý.",
    )


async def _queue_subscription_approval_request(
    user: User,
    plan_id: str,
    db_session: AsyncSession,
) -> CreateSubscriptionCheckoutResponse:
    """Queue a subscription upgrade request for admin approval.

    Raises HTTP 409 if user already has active subscription or pending request,
    HTTP 429 if recently rejected within 24-hour cooldown.
    """
    if user.subscription_status == SubscriptionStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an active subscription.",
        )
    existing = await db_session.execute(
        select(SubscriptionRequest)
        .where(SubscriptionRequest.user_id == user.id)
        .where(SubscriptionRequest.status == SubscriptionRequestStatus.PENDING)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a pending subscription request.",
        )
    cooldown_cutoff = datetime.now(UTC) - timedelta(hours=24)
    recently_rejected = await db_session.execute(
        select(SubscriptionRequest)
        .where(SubscriptionRequest.user_id == user.id)
        .where(SubscriptionRequest.status == SubscriptionRequestStatus.REJECTED)
        .where(SubscriptionRequest.created_at >= cooldown_cutoff)
    )
    if recently_rejected.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Your previous request was rejected. Please wait 24 hours before resubmitting.",
        )
    req = SubscriptionRequest(user_id=user.id, plan_id=plan_id)
    db_session.add(req)
    await db_session.commit()
    logger.info(
        "Admin-approval subscription request created for user %s (plan=%s)",
        user.id,
        plan_id,
    )
    return CreateSubscriptionCheckoutResponse(checkout_url="", admin_approval_mode=True)


@router.post(
    "/create-subscription-checkout",
    response_model=CreateSubscriptionCheckoutResponse,
)
async def create_subscription_checkout(
    body: CreateSubscriptionCheckoutRequest,
    user: User = Depends(current_active_user),
    db_session: AsyncSession = Depends(get_async_session),
) -> CreateSubscriptionCheckoutResponse:
    """Create a Stripe Checkout Session for a recurring subscription.

    Falls back to admin-approval mode when:
    - STRIPE_SECRET_KEY is not configured, or
    - The plan's price ID is not configured, or
    - The Stripe API call fails (invalid/test credentials).
    """
    price_id = _resolve_plan_price_id(body.plan_id)

    # Fast path: Stripe clearly not configured → queue approval request
    if not config.STRIPE_SECRET_KEY or not price_id:
        return await _queue_subscription_approval_request(
            user, body.plan_id.value, db_session
        )

    # Prevent duplicate subscriptions before hitting Stripe
    if user.subscription_status == SubscriptionStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an active subscription.",
        )

    stripe_client = get_stripe_client()
    success_url, cancel_url = _get_subscription_urls()

    try:
        customer_id = await _get_or_create_stripe_customer(stripe_client, user, db_session)
        checkout_session = stripe_client.v1.checkout.sessions.create(
            params={
                "mode": "subscription",
                "customer": customer_id,
                "success_url": success_url,
                "cancel_url": cancel_url,
                "line_items": [{"price": price_id, "quantity": 1}],
                "metadata": {
                    "user_id": str(user.id),
                    "plan_id": body.plan_id.value,
                },
            }
        )
    except (StripeError, HTTPException) as exc:
        # Stripe credentials invalid or API unreachable → fall back to admin-approval
        logger.warning(
            "Stripe checkout failed for user %s (plan=%s), falling back to admin-approval: %s",
            user.id,
            body.plan_id.value,
            exc,
        )
        return await _queue_subscription_approval_request(
            user, body.plan_id.value, db_session
        )

    checkout_url = getattr(checkout_session, "url", None)
    if not checkout_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Stripe subscription checkout session did not return a URL.",
        )

    return CreateSubscriptionCheckoutResponse(checkout_url=checkout_url)


@router.get("/verify-checkout-session")
async def verify_checkout_session(
    session_id: str,
    user: User = Depends(current_active_user),
) -> dict:
    """Verify a Stripe Checkout Session belongs to the user and is paid."""
    _check_verify_session_rate_limit(str(user.id))
    stripe_client = get_stripe_client()
    try:
        session = stripe_client.v1.checkout.sessions.retrieve(session_id)
    except StripeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid checkout session.",
        ) from exc

    metadata = getattr(session, "metadata", None) or {}
    if metadata.get("user_id") != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session does not belong to this user.",
        )

    payment_status = getattr(session, "payment_status", None)
    return {
        "verified": payment_status in {"paid", "no_payment_required"},
        "payment_status": payment_status,
    }


@router.get("/status", response_model=StripeStatusResponse)
async def get_stripe_status() -> StripeStatusResponse:
    """Return Stripe availability for frontend feature gating."""
    return StripeStatusResponse(stripe_enabled=bool(config.STRIPE_SECRET_KEY))


@router.post("/webhook", response_model=StripeWebhookResponse)
async def stripe_webhook(
    request: Request,
    db_session: AsyncSession = Depends(get_async_session),
) -> StripeWebhookResponse:
    """Handle Stripe webhooks and grant purchased pages after payment."""
    if not config.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe webhook handling is not configured.",
        )

    stripe_client = get_stripe_client()
    payload = await request.body()
    signature = request.headers.get("Stripe-Signature")

    if not signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe-Signature header.",
        )

    try:
        event = stripe_client.construct_event(
            payload,
            signature,
            config.STRIPE_WEBHOOK_SECRET,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe webhook payload.",
        ) from exc
    except SignatureVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe webhook signature.",
        ) from exc

    logger.info("Received Stripe webhook event: %s", event.type)

    # --- Checkout session events ---
    if event.type in {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
    }:
        checkout_session = event.data.object
        payment_status = getattr(checkout_session, "payment_status", None)
        session_mode = str(getattr(checkout_session, "mode", "payment")).lower()

        if event.type == "checkout.session.completed" and payment_status not in {
            "paid",
            "no_payment_required",
        }:
            logger.info(
                "Received checkout.session.completed for unpaid session %s; waiting for async success.",
                checkout_session.id,
            )
            return StripeWebhookResponse()

        if session_mode == "subscription":
            return await _activate_subscription_from_checkout(
                db_session, checkout_session
            )

        metadata = _get_metadata(checkout_session)
        if metadata.get("purchase_type") == "gift":
            return await _fulfill_gift_purchase(db_session, checkout_session)
        if metadata.get("purchase_type") in {"token_packs", "token_topup"}:
            return await _fulfill_token_topup(db_session, checkout_session)

        logger.warning(
            "Unrecognized payment-mode checkout session %s with purchase_type=%s",
            checkout_session.id,
            metadata.get("purchase_type"),
        )
        return StripeWebhookResponse()

    if event.type in {
        "checkout.session.async_payment_failed",
        "checkout.session.expired",
    }:
        logger.info("Payment session failed/expired: %s", event.type)
        return StripeWebhookResponse()

    # --- Subscription lifecycle events ---
    if event.type in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        subscription = event.data.object
        return await _handle_subscription_event(db_session, subscription)

    # --- Invoice events ---
    if event.type == "invoice.payment_succeeded":
        invoice = event.data.object
        return await _handle_invoice_payment_succeeded(db_session, invoice)

    if event.type == "invoice.payment_failed":
        invoice = event.data.object
        return await _handle_invoice_payment_failed(db_session, invoice)

    logger.info("Unhandled Stripe event type: %s", event.type)
    return StripeWebhookResponse()


@router.get("/billing-portal", response_model=BillingPortalResponse)
async def get_billing_portal(
    user: User = Depends(current_active_user),
) -> BillingPortalResponse:
    """Create a Stripe Customer Portal session for subscription management."""
    stripe_client = get_stripe_client()
    if not user.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Stripe customer found for your account.",
        )

    return_url = config.STRIPE_BILLING_PORTAL_RETURN_URL or (
        (config.NEXT_FRONTEND_URL.rstrip("/") + "/dashboard")
        if config.NEXT_FRONTEND_URL
        else ""
    )
    if not return_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing portal return URL is not configured.",
        )

    try:
        portal_session = stripe_client.v1.billing_portal.sessions.create(
            params={"customer": user.stripe_customer_id, "return_url": return_url}
        )
    except StripeError as exc:
        logger.exception(
            "Failed to create Stripe billing portal session for user %s", user.id
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to create billing portal session.",
        ) from exc

    return BillingPortalResponse(url=portal_session.url)
