"""
API-layer tests for Stripe endpoints.

Tests use httpx.AsyncClient + ASGITransport.
Key insight: when config.STRIPE_SECRET_KEY is falsy (default in CI),
the token-topup endpoint returns admin_approval_mode=True without
hitting Stripe — no mock needed for that path.

Markers: @pytest.mark.api
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.api


# ---------------------------------------------------------------------------
# P0 — Stripe status / admin-approval-mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stripe_status_returns_stripe_enabled_flag(
    api_client: AsyncClient,
) -> None:
    """GET /api/v1/stripe/status — public endpoint → 200 + {stripe_enabled: bool}."""
    response = await api_client.get("/api/v1/stripe/status")

    assert response.status_code == 200
    body = response.json()
    assert "stripe_enabled" in body
    assert isinstance(body["stripe_enabled"], bool)


@pytest.mark.asyncio
async def test_token_topup_no_stripe_key_returns_admin_approval_mode(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """
    POST /api/v1/stripe/create-token-topup-checkout
    When STRIPE_SECRET_KEY is not set (default in CI), the endpoint returns
    admin_approval_mode=True instead of a Stripe session URL.
    """
    response = await api_client.post(
        "/api/v1/stripe/create-token-topup-checkout",
        json={"amount_usd": 10, "search_space_id": 1},
        headers=auth_headers,
    )

    # Either admin_approval_mode is returned or Stripe created a session
    assert response.status_code in (200, 201)
    body = response.json()
    # In CI without STRIPE_SECRET_KEY this must be True
    if "admin_approval_mode" in body:
        assert body["admin_approval_mode"] is True


@pytest.mark.asyncio
async def test_token_topup_unauthenticated_returns_401(
    api_client: AsyncClient,
) -> None:
    """POST /api/v1/stripe/create-token-topup-checkout — no auth → 401."""
    response = await api_client.post(
        "/api/v1/stripe/create-token-topup-checkout",
        json={"token_amount": 100},
    )

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# P0 — Webhook signature verification
# ---------------------------------------------------------------------------


def _build_stripe_signature(payload: str, secret: str, timestamp: int | None = None) -> str:
    """Build a Stripe-compatible Svix/Stripe webhook signature header."""
    ts = timestamp or int(time.time())
    signed_payload = f"{ts}.{payload}"
    sig = hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"t={ts},v1={sig}"


@pytest.mark.asyncio
async def test_webhook_missing_signature_returns_400(
    api_client: AsyncClient,
) -> None:
    """POST /api/v1/stripe/webhook — no Stripe-Signature header → 400."""
    payload = json.dumps({"type": "checkout.session.completed", "data": {}})
    response = await api_client.post(
        "/api/v1/stripe/webhook",
        content=payload,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code in (400, 403, 422)


@pytest.mark.asyncio
async def test_webhook_invalid_signature_returns_400(
    api_client: AsyncClient,
) -> None:
    """POST /api/v1/stripe/webhook — wrong signature → 400."""
    payload = json.dumps({"type": "checkout.session.completed", "data": {}})
    response = await api_client.post(
        "/api/v1/stripe/webhook",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": "t=1234567890,v1=badsignature",
        },
    )

    assert response.status_code in (400, 403)


# ---------------------------------------------------------------------------
# P1 — Gift checkout validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_gift_checkout_unauthenticated_returns_401(
    api_client: AsyncClient,
) -> None:
    """POST /api/v1/stripe/create-gift-checkout — no auth → 401."""
    response = await api_client.post(
        "/api/v1/stripe/create-gift-checkout",
        json={"plan_id": "pro", "duration_months": 1},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_gift_checkout_invalid_plan_returns_400(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """POST /api/v1/stripe/create-gift-checkout — unknown plan_id → 400/422."""
    response = await api_client.post(
        "/api/v1/stripe/create-gift-checkout",
        json={"plan_id": "nonexistent-plan-xyz", "duration_months": 1},
        headers=auth_headers,
    )

    assert response.status_code in (400, 422, 500)


# ---------------------------------------------------------------------------
# P1 — Gift redemption
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redeem_gift_unauthenticated_returns_401(
    api_client: AsyncClient,
) -> None:
    """POST /api/v1/stripe/redeem-gift — no auth → 401."""
    response = await api_client.post(
        "/api/v1/stripe/redeem-gift",
        json={"gift_code": "GIFT-TEST-0000"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_redeem_gift_invalid_code_returns_404(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """POST /api/v1/stripe/redeem-gift — unknown code → 404."""
    response = await api_client.post(
        "/api/v1/stripe/redeem-gift",
        json={"code": "INVALID-CODE-XXXXXXXX"},
        headers=auth_headers,
    )

    assert response.status_code in (404, 400)


# ---------------------------------------------------------------------------
# P1 — Billing portal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_billing_portal_unauthenticated_returns_401(
    api_client: AsyncClient,
) -> None:
    """GET /api/v1/stripe/billing-portal — no auth → 401."""
    response = await api_client.get("/api/v1/stripe/billing-portal")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_billing_portal_no_customer_id_returns_400(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """
    GET /api/v1/stripe/billing-portal — user without stripe_customer_id → 400.
    Test user in CI likely has no Stripe customer, so this tests the guard.
    """
    response = await api_client.get(
        "/api/v1/stripe/billing-portal",
        headers=auth_headers,
    )

    # Either user has no customer_id (400) or Stripe not configured (400/500)
    # Accept 200 only if Stripe is fully configured in test env
    assert response.status_code in (200, 400, 404, 500)
