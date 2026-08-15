"""Integration tests for Promo Code Claim and Management Routes (Story 21.7 / AC-5 / AC-7).

Validates REST API endpoints for claiming promo codes, duplicate redemption checks,
and Admin creation routes.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.context import AuthContext
from app.services.promo_code_service import (
    PromoCodeAlreadyRedeemedError,
    PromoCodeExpiredError,
)
from app.users import require_session_context

pytestmark = pytest.mark.integration


@pytest.fixture
def test_app() -> FastAPI:
    """Create test FastAPI application with mounted promo codes router."""
    from app.routes.promo_code_routes import router as promo_router

    app = FastAPI()
    app.include_router(promo_router, prefix="/api/v1")
    return app


@pytest.fixture
def mock_auth() -> AuthContext:
    user = MagicMock()
    user.id = uuid4()
    user.email = "growth@nowing.net"
    user.is_active = True
    user.is_superuser = False
    user.credit_micros_balance = 1_000_000

    auth = MagicMock(spec=AuthContext)
    auth.user = user
    auth.workspace_id = 1
    auth.client_id = None
    return auth


def test_claim_promo_code_success(test_app: FastAPI, mock_auth: AuthContext) -> None:
    """POST /api/v1/credits/promo-code/claim succeeds and returns new balance."""
    test_app.dependency_overrides[require_session_context] = lambda: mock_auth

    mock_res = MagicMock()
    mock_res.code = "WELCOME50"
    mock_res.credit_micros_granted = 2_000_000
    mock_res.new_balance_micros = 3_000_000
    mock_res.message = "Promo code claimed successfully!"

    with patch(
        "app.services.promo_code_service.PromoCodeService.claim_promo_code",
        new=AsyncMock(return_value=mock_res),
    ):
        client = TestClient(test_app)
        response = client.post(
            "/api/v1/credits/promo-code/claim",
            json={"code": "welcome50"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["credit_micros_granted"] == 2_000_000
        assert data["new_balance_micros"] == 3_000_000


def test_claim_promo_code_duplicate_conflict(
    test_app: FastAPI, mock_auth: AuthContext
) -> None:
    """POST /api/v1/credits/promo-code/claim returns 409 when user already claimed code."""
    test_app.dependency_overrides[require_session_context] = lambda: mock_auth

    with patch(
        "app.services.promo_code_service.PromoCodeService.claim_promo_code",
        new=AsyncMock(side_effect=PromoCodeAlreadyRedeemedError("Already redeemed")),
    ):
        client = TestClient(test_app)
        response = client.post(
            "/api/v1/credits/promo-code/claim",
            json={"code": "WELCOME50"},
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "PROMO_CODE_ALREADY_USED"


def test_claim_promo_code_expired_bad_request(
    test_app: FastAPI, mock_auth: AuthContext
) -> None:
    """POST /api/v1/credits/promo-code/claim returns 400 when code is expired."""
    test_app.dependency_overrides[require_session_context] = lambda: mock_auth

    with patch(
        "app.services.promo_code_service.PromoCodeService.claim_promo_code",
        new=AsyncMock(side_effect=PromoCodeExpiredError("Code expired")),
    ):
        client = TestClient(test_app)
        response = client.post(
            "/api/v1/credits/promo-code/claim",
            json={"code": "OLD2024"},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "PROMO_CODE_EXPIRED"
