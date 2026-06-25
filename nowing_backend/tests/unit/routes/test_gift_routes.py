"""
Unit tests for Gift system routes — Stories 6.1–6.5 (P2)

Covers:
  POST /api/v1/stripe/create-gift-checkout  — 200 with URL, 200 admin_approval fallback,
                                              400 invalid plan, 401 unauth
  POST /api/v1/stripe/redeem-gift           — 200 success, 400 invalid/used/expired,
                                              401 unauth
  GET  /api/v1/stripe/gift-codes            — 200 list, 401 unauth

All tests are unit-level: no real DB, no real Stripe.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app
from app.db import User, get_async_session
from app.users import current_active_user

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_user() -> User:
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.email = "buyer@example.com"
    user.is_active = True
    user.is_superuser = False
    user.is_verified = True
    user.subscription_status = None
    user.plan_id = "free"
    user.subscription_current_period_end = None
    user.pages_limit = 100
    user.pages_used = 0
    user.monthly_token_limit = 50000
    user.tokens_used_this_month = 0
    user.purchased_tokens = 0
    user.token_reset_date = datetime.now(UTC).date()
    return user


@pytest.fixture
def mock_session():
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def client(mock_user, mock_session) -> TestClient:
    app.dependency_overrides[current_active_user] = lambda: mock_user
    app.dependency_overrides[get_async_session] = lambda: mock_session
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.pop(current_active_user, None)
    app.dependency_overrides.pop(get_async_session, None)


@pytest.fixture
def unauthenticated_client(mock_session) -> TestClient:
    app.dependency_overrides.pop(current_active_user, None)
    app.dependency_overrides[get_async_session] = lambda: mock_session
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.pop(get_async_session, None)


@pytest.fixture
def mock_gift_code(mock_user):
    from app.db import GiftCodeStatus

    g = MagicMock()
    g.id = uuid.uuid4()
    g.code = "GIFT-ABCD-EFGH-IJKL"
    g.plan_id = "pro"
    g.duration_months = 3
    g.status = GiftCodeStatus.ACTIVE
    g.redeemer_id = None
    g.purchaser_id = mock_user.id
    g.expires_at = datetime.now(UTC) + timedelta(days=365)
    g.created_at = datetime.now(UTC)
    g.redeemed_at = None
    return g


# ---------------------------------------------------------------------------
# POST /api/v1/stripe/create-gift-checkout
# ---------------------------------------------------------------------------


class TestCreateGiftCheckout:
    """[P2] Story 6.2 — create gift checkout."""

    def test_unauthenticated_returns_401(self, unauthenticated_client):
        """[P0] No auth → 401."""
        resp = unauthenticated_client.post(
            "/api/v1/stripe/create-gift-checkout",
            json={"plan_id": "pro", "duration_months": 3},
        )
        assert resp.status_code == 401

    def test_invalid_plan_id_returns_400(self, client):
        """[P1] Unknown plan_id → 400."""
        resp = client.post(
            "/api/v1/stripe/create-gift-checkout",
            json={"plan_id": "invalid_plan", "duration_months": 1},
        )
        assert resp.status_code == 400

    def test_no_stripe_key_returns_admin_approval_mode(self, client):
        """[P2] Stripe key absent → 200 with admin_approval_mode=True, empty checkout_url."""
        with (
            patch("app.routes.stripe_routes.config") as mock_cfg,
        ):
            # Valid GIFT_PRICING but no Stripe key
            mock_cfg.GIFT_PRICING = {"pro": {3: 2900}}
            mock_cfg.STRIPE_SECRET_KEY = None

            resp = client.post(
                "/api/v1/stripe/create-gift-checkout",
                json={"plan_id": "pro", "duration_months": 3},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["admin_approval_mode"] is True

    def test_stripe_available_returns_checkout_url(self, client):
        """[P2] Stripe configured → 200 with checkout_url."""
        mock_checkout = MagicMock()
        mock_checkout.url = "https://checkout.stripe.com/pay/test_abc"

        with (
            patch("app.routes.stripe_routes.config") as mock_cfg,
            patch("app.routes.stripe_routes.get_stripe_client") as mock_stripe,
        ):
            mock_cfg.GIFT_PRICING = {"pro": {3: 2900}}
            mock_cfg.STRIPE_SECRET_KEY = "sk_test_abc"
            mock_cfg.BACKEND_URL = "http://localhost:8000"
            mock_cfg.NEXT_FRONTEND_URL = "http://localhost:3000"

            mock_stripe_client = MagicMock()
            mock_stripe_client.v1.checkout.sessions.create.return_value = mock_checkout
            mock_stripe.return_value = mock_stripe_client

            resp = client.post(
                "/api/v1/stripe/create-gift-checkout",
                json={"plan_id": "pro", "duration_months": 3},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["checkout_url"] == "https://checkout.stripe.com/pay/test_abc"
        assert body["admin_approval_mode"] is False

    def test_missing_body_returns_422(self, client):
        """[P2] Missing required fields → 422."""
        resp = client.post("/api/v1/stripe/create-gift-checkout", json={})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/stripe/redeem-gift
# ---------------------------------------------------------------------------


class TestRedeemGift:
    """[P2] Story 6.4 — redeem gift code."""

    def test_unauthenticated_returns_401(self, unauthenticated_client):
        """[P0] No auth → 401."""
        resp = unauthenticated_client.post(
            "/api/v1/stripe/redeem-gift",
            json={"code": "GIFT-ABCD-EFGH-IJKL"},
        )
        assert resp.status_code == 401

    def test_missing_code_returns_422(self, client):
        """[P1] Missing code field → 422."""
        resp = client.post("/api/v1/stripe/redeem-gift", json={})
        assert resp.status_code == 422

    def test_empty_code_returns_422(self, client):
        """[P2] Whitespace-only code → 422 (Pydantic strips then rejects min_length=1)."""
        mock_session = app.dependency_overrides[get_async_session]()
        mock_session.execute = AsyncMock()  # should not be called

        resp = client.post(
            "/api/v1/stripe/redeem-gift",
            json={"code": "   "},
        )
        assert resp.status_code == 422

    def test_invalid_or_used_code_returns_400(self, client):
        """[P1] Gift code not found or already used → 400."""
        mock_session = app.dependency_overrides[get_async_session]()
        # scalar_one_or_none returns None → invalid code
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        resp = client.post(
            "/api/v1/stripe/redeem-gift",
            json={"code": "GIFT-FAKE-CODE-HERE"},
        )
        assert resp.status_code == 400

    def test_expired_code_returns_400(self, client, mock_gift_code):
        """[P1] Expired gift code → 400."""
        mock_gift_code.expires_at = datetime.now(UTC) - timedelta(days=1)  # expired

        mock_session = app.dependency_overrides[get_async_session]()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_gift_code
        mock_session.execute = AsyncMock(return_value=mock_result)

        resp = client.post(
            "/api/v1/stripe/redeem-gift",
            json={"code": mock_gift_code.code},
        )
        assert resp.status_code == 400

    def test_valid_code_returns_200(self, client, mock_user, mock_gift_code):
        """[P1] Valid active code → 200 with new_expiry and plan_id."""
        from app.db import GiftCodeStatus, SubscriptionStatus

        # Set up locked_user mock
        locked_user = MagicMock()
        locked_user.id = mock_user.id
        locked_user.plan_id = "free"
        locked_user.subscription_status = None
        locked_user.subscription_current_period_end = None
        locked_user.pages_used = 0
        locked_user.pages_limit = 100

        mock_session = app.dependency_overrides[get_async_session]()

        # 1st execute: gift code query
        mock_gift_result = MagicMock()
        mock_gift_result.scalar_one_or_none.return_value = mock_gift_code

        # 2nd execute: locked user query
        mock_user_result = MagicMock()
        mock_user_result.scalar_one.return_value = locked_user

        mock_session.execute = AsyncMock(
            side_effect=[mock_gift_result, mock_user_result]
        )
        mock_session.commit = AsyncMock()

        with patch("app.routes.stripe_routes.config") as mock_cfg:
            mock_cfg.PLAN_LIMITS = {
                "pro": {
                    "monthly_token_limit": 500000,
                    "pages_limit": 1000,
                }
            }

            resp = client.post(
                "/api/v1/stripe/redeem-gift",
                json={"code": mock_gift_code.code},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert "new_expiry" in body
        assert body["plan_id"] == "pro"


# ---------------------------------------------------------------------------
# GET /api/v1/stripe/gift-codes
# ---------------------------------------------------------------------------


class TestGetGiftCodes:
    """[P2] Story 6.5 — list gift codes."""

    def test_unauthenticated_returns_401(self, unauthenticated_client):
        """[P0] No auth → 401."""
        resp = unauthenticated_client.get("/api/v1/stripe/gift-codes")
        assert resp.status_code == 401

    def test_authenticated_returns_200_with_items(self, client, mock_gift_code):
        """[P2] Authenticated user → 200 with items list."""
        mock_session = app.dependency_overrides[get_async_session]()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_gift_code]
        mock_session.execute = AsyncMock(return_value=mock_result)

        resp = client.get("/api/v1/stripe/gift-codes")

        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "count" in body
        assert body["count"] == 1

    def test_authenticated_empty_list_returns_200(self, client):
        """[P2] No gift codes → 200 with empty items."""
        mock_session = app.dependency_overrides[get_async_session]()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        resp = client.get("/api/v1/stripe/gift-codes")

        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["count"] == 0
