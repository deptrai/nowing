"""
Unit tests for Stripe route helpers.

Tests isolated business logic without real Stripe or DB.
Uses pytest-mock and FastAPI dependency overrides.

Markers: @pytest.mark.unit
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.routes.stripe_routes import (
    _check_verify_session_rate_limit,
    _get_price_id_for_plan,
    _normalize_optional_string,
    _resolve_plan_price_id,
    _verify_session_calls,
)
from app.schemas.stripe import PlanId

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _check_verify_session_rate_limit
# ---------------------------------------------------------------------------


class TestCheckVerifySessionRateLimit:
    """Unit tests for the in-memory rate limiter."""

    def setup_method(self) -> None:
        # Clear the shared state before each test
        _verify_session_calls.clear()

    def test_first_call_is_allowed(self) -> None:
        """First call for a user must not raise."""
        _check_verify_session_rate_limit("user-001")  # Should not raise

    def test_calls_within_limit_are_allowed(self) -> None:
        """19 calls (< 20) must all succeed."""
        for _ in range(19):
            _check_verify_session_rate_limit("user-002")

    def test_exactly_at_limit_raises_429(self) -> None:
        """21st call within window must raise HTTP 429."""
        user_id = "user-rate-limit"
        for _ in range(20):
            _check_verify_session_rate_limit(user_id)

        with pytest.raises(HTTPException) as exc_info:
            _check_verify_session_rate_limit(user_id)

        assert exc_info.value.status_code == 429

    def test_old_calls_outside_window_are_evicted(self) -> None:
        """Calls older than 60 s should not count toward the limit."""
        user_id = "user-evict"
        now = datetime.now(UTC).timestamp()
        # Inject 20 calls 61 seconds in the past
        _verify_session_calls[user_id] = [now - 61] * 20

        # This should not raise — old calls are outside the 60-second window
        _check_verify_session_rate_limit(user_id)

    def test_different_users_have_independent_counters(self) -> None:
        """Rate limit is per user_id — different users don't share counters."""
        for _ in range(20):
            _check_verify_session_rate_limit("user-A")

        # user-B should still be allowed
        _check_verify_session_rate_limit("user-B")  # Should not raise


# ---------------------------------------------------------------------------
# _resolve_plan_price_id / _get_price_id_for_plan
# ---------------------------------------------------------------------------


class TestGetPriceIdForPlan:
    """Unit tests for plan → Stripe Price ID mapping."""

    def test_configured_plan_returns_price_id(self) -> None:
        """When the env var is set, return the price ID string."""
        fake_price_id = "price_test_pro_monthly_123"

        with patch("app.routes.stripe_routes.config") as mock_config:
            mock_config.STRIPE_PRO_MONTHLY_PRICE_ID = fake_price_id
            mock_config.STRIPE_PRO_YEARLY_PRICE_ID = None
            mock_config.STRIPE_MAX_MONTHLY_PRICE_ID = None
            mock_config.STRIPE_MAX_YEARLY_PRICE_ID = None

            price_id = _resolve_plan_price_id(PlanId.pro_monthly)

        assert price_id == fake_price_id

    def test_unconfigured_plan_returns_none(self) -> None:
        """When env var is not set, _resolve_plan_price_id returns None."""
        with patch("app.routes.stripe_routes.config") as mock_config:
            mock_config.STRIPE_PRO_MONTHLY_PRICE_ID = None
            mock_config.STRIPE_PRO_YEARLY_PRICE_ID = None
            mock_config.STRIPE_MAX_MONTHLY_PRICE_ID = None
            mock_config.STRIPE_MAX_YEARLY_PRICE_ID = None

            price_id = _resolve_plan_price_id(PlanId.pro_yearly)

        assert price_id is None

    def test_get_price_id_raises_503_when_not_configured(self) -> None:
        """_get_price_id_for_plan raises HTTP 503 when price ID is missing."""
        with patch("app.routes.stripe_routes.config") as mock_config:
            mock_config.STRIPE_PRO_MONTHLY_PRICE_ID = None
            mock_config.STRIPE_PRO_YEARLY_PRICE_ID = None
            mock_config.STRIPE_MAX_MONTHLY_PRICE_ID = None
            mock_config.STRIPE_MAX_YEARLY_PRICE_ID = None

            with pytest.raises(HTTPException) as exc_info:
                _get_price_id_for_plan(PlanId.pro_monthly)

        assert exc_info.value.status_code == 503

    def test_get_price_id_returns_value_when_configured(self) -> None:
        """_get_price_id_for_plan returns the configured price ID."""
        with patch("app.routes.stripe_routes.config") as mock_config:
            mock_config.STRIPE_PRO_MONTHLY_PRICE_ID = "price_live_monthly"
            mock_config.STRIPE_PRO_YEARLY_PRICE_ID = None
            mock_config.STRIPE_MAX_MONTHLY_PRICE_ID = None
            mock_config.STRIPE_MAX_YEARLY_PRICE_ID = None

            result = _get_price_id_for_plan(PlanId.pro_monthly)

        assert result == "price_live_monthly"


# ---------------------------------------------------------------------------
# _normalize_optional_string
# ---------------------------------------------------------------------------


class TestNormalizeOptionalString:
    """Unit tests for the Stripe object → str normaliser."""

    def test_none_returns_none(self) -> None:
        assert _normalize_optional_string(None) is None

    def test_plain_string_returned_as_is(self) -> None:
        assert _normalize_optional_string("cus_abc123") == "cus_abc123"

    def test_object_with_id_attribute_returns_id(self) -> None:
        obj = MagicMock()
        obj.id = "cus_from_object"
        assert _normalize_optional_string(obj) == "cus_from_object"

    def test_integer_returns_string(self) -> None:
        result = _normalize_optional_string(42)
        assert result == "42"
