"""
Unit tests for Admin Gift Request routes — Story 6.8 (P2)

Covers:
  GET  /api/v1/admin/gift-requests                        — list (200, 401, 403 non-admin)
  POST /api/v1/admin/gift-requests/{id}/approve           — approve (200, 404, 409, 401, 403)
  POST /api/v1/admin/gift-requests/{id}/reject            — reject (200, 404, 409, 401, 403)

All tests are unit-level: no real DB.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app
from app.db import User, get_async_session
from app.users import current_active_user, current_superuser

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_admin() -> User:
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.email = "admin@nowing.ai"
    user.is_active = True
    user.is_superuser = True
    user.is_verified = True
    return user


@pytest.fixture
def mock_regular_user() -> User:
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.email = "user@example.com"
    user.is_active = True
    user.is_superuser = False
    user.is_verified = True
    return user


@pytest.fixture
def mock_session():
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def admin_client(mock_admin, mock_session) -> TestClient:
    """Authenticated as superuser."""
    app.dependency_overrides[current_active_user] = lambda: mock_admin
    app.dependency_overrides[current_superuser] = lambda: mock_admin
    app.dependency_overrides[get_async_session] = lambda: mock_session
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.pop(current_active_user, None)
    app.dependency_overrides.pop(current_superuser, None)
    app.dependency_overrides.pop(get_async_session, None)


@pytest.fixture
def regular_client(mock_regular_user, mock_session) -> TestClient:
    """Authenticated as regular (non-superuser) user — current_superuser raises 403."""
    from fastapi import HTTPException

    app.dependency_overrides[current_active_user] = lambda: mock_regular_user
    # Override current_superuser to raise 403 (simulates fastapi-users superuser check)
    def _raise_403():
        raise HTTPException(status_code=403, detail="Forbidden")
    app.dependency_overrides[current_superuser] = _raise_403
    app.dependency_overrides[get_async_session] = lambda: mock_session
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.pop(current_active_user, None)
    app.dependency_overrides.pop(current_superuser, None)
    app.dependency_overrides.pop(get_async_session, None)


@pytest.fixture
def unauthenticated_client(mock_session) -> TestClient:
    app.dependency_overrides.pop(current_active_user, None)
    app.dependency_overrides.pop(current_superuser, None)
    app.dependency_overrides[get_async_session] = lambda: mock_session
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.pop(get_async_session, None)


@pytest.fixture
def mock_gift_request():
    from app.db import GiftRequestStatus

    req = MagicMock()
    req.id = uuid.uuid4()
    req.user_id = uuid.uuid4()
    req.plan_id = "pro"
    req.duration_months = 3
    req.status = GiftRequestStatus.PENDING
    req.gift_code_id = None
    req.created_at = datetime.now(UTC)
    req.updated_at = datetime.now(UTC)
    return req


# ---------------------------------------------------------------------------
# GET /api/v1/admin/gift-requests
# ---------------------------------------------------------------------------


class TestListGiftRequests:
    """[P2] Story 6.8 — list gift requests (admin only)."""

    def test_unauthenticated_returns_401(self, unauthenticated_client):
        """[P0] No auth → 401."""
        resp = unauthenticated_client.get("/api/v1/admin/gift-requests")
        assert resp.status_code == 401

    def test_non_admin_returns_403(self, regular_client):
        """[P1] Non-superuser → 403."""
        resp = regular_client.get("/api/v1/admin/gift-requests")
        assert resp.status_code == 403

    def test_admin_returns_200(self, admin_client):
        """[P2] Superuser → 200 with requests list."""
        mock_session = app.dependency_overrides[get_async_session]()

        # list_gift_requests does execute().all() on result rows
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        resp = admin_client.get("/api/v1/admin/gift-requests")

        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body


# ---------------------------------------------------------------------------
# POST /api/v1/admin/gift-requests/{id}/approve
# ---------------------------------------------------------------------------


class TestApproveGiftRequest:
    """[P2] Story 6.8 — approve gift request."""

    def test_unauthenticated_returns_401(self, unauthenticated_client):
        """[P0] No auth → 401."""
        req_id = uuid.uuid4()
        resp = unauthenticated_client.post(
            f"/api/v1/admin/gift-requests/{req_id}/approve"
        )
        assert resp.status_code == 401

    def test_non_admin_returns_403(self, regular_client):
        """[P1] Non-superuser → 403."""
        req_id = uuid.uuid4()
        resp = regular_client.post(
            f"/api/v1/admin/gift-requests/{req_id}/approve"
        )
        assert resp.status_code == 403

    def test_not_found_returns_404(self, admin_client):
        """[P1] Gift request not found → 404."""
        mock_session = app.dependency_overrides[get_async_session]()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        req_id = uuid.uuid4()
        resp = admin_client.post(
            f"/api/v1/admin/gift-requests/{req_id}/approve"
        )
        assert resp.status_code == 404

    def test_already_processed_returns_409(self, admin_client, mock_gift_request):
        """[P2] Request already approved/rejected → 409 Conflict."""
        from app.db import GiftRequestStatus

        mock_gift_request.status = GiftRequestStatus.APPROVED  # not PENDING

        mock_session = app.dependency_overrides[get_async_session]()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_gift_request
        mock_session.execute = AsyncMock(return_value=mock_result)

        resp = admin_client.post(
            f"/api/v1/admin/gift-requests/{mock_gift_request.id}/approve"
        )
        assert resp.status_code == 409

    def test_approve_returns_200(self, admin_client, mock_gift_request):
        """[P2] Valid pending request → 200 with gift_code and plan info."""
        mock_session = app.dependency_overrides[get_async_session]()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_gift_request
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        mock_gift = MagicMock()
        mock_gift.id = uuid.uuid4()
        mock_gift.code = "GIFT-XXXX-YYYY-ZZZZ"
        mock_gift.plan_id = "pro"
        mock_gift.duration_months = 3

        with (
            patch("app.routes.admin_routes.config") as mock_cfg,
            patch(
                "app.routes.admin_routes._mint_gift_code",
                new_callable=AsyncMock,
                return_value=mock_gift,
            ),
        ):
            mock_cfg.GIFT_PRICING = {"pro": {3: 2900}}

            resp = admin_client.post(
                f"/api/v1/admin/gift-requests/{mock_gift_request.id}/approve"
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["gift_code"] == "GIFT-XXXX-YYYY-ZZZZ"
        assert body["plan_id"] == "pro"


# ---------------------------------------------------------------------------
# POST /api/v1/admin/gift-requests/{id}/reject
# ---------------------------------------------------------------------------


class TestRejectGiftRequest:
    """[P2] Story 6.8 — reject gift request."""

    def test_unauthenticated_returns_401(self, unauthenticated_client):
        """[P0] No auth → 401."""
        req_id = uuid.uuid4()
        resp = unauthenticated_client.post(
            f"/api/v1/admin/gift-requests/{req_id}/reject"
        )
        assert resp.status_code == 401

    def test_non_admin_returns_403(self, regular_client):
        """[P1] Non-superuser → 403."""
        req_id = uuid.uuid4()
        resp = regular_client.post(
            f"/api/v1/admin/gift-requests/{req_id}/reject"
        )
        assert resp.status_code == 403

    def test_not_found_returns_404(self, admin_client):
        """[P1] Gift request not found → 404."""
        mock_session = app.dependency_overrides[get_async_session]()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        req_id = uuid.uuid4()
        resp = admin_client.post(
            f"/api/v1/admin/gift-requests/{req_id}/reject"
        )
        assert resp.status_code == 404

    def test_already_processed_returns_409(self, admin_client, mock_gift_request):
        """[P2] Already rejected → 409 Conflict."""
        from app.db import GiftRequestStatus

        mock_gift_request.status = GiftRequestStatus.REJECTED

        mock_session = app.dependency_overrides[get_async_session]()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_gift_request
        mock_session.execute = AsyncMock(return_value=mock_result)

        resp = admin_client.post(
            f"/api/v1/admin/gift-requests/{mock_gift_request.id}/reject"
        )
        assert resp.status_code == 409

    def test_reject_returns_200(self, admin_client, mock_gift_request):
        """[P2] Valid pending request → 200 with status=rejected."""
        from app.db import GiftRequestStatus

        mock_session = app.dependency_overrides[get_async_session]()

        # 1st execute: gift request query
        mock_req_result = MagicMock()
        mock_req_result.scalar_one_or_none.return_value = mock_gift_request

        # 2nd execute: user query (for email in response)
        mock_requester = MagicMock()
        mock_requester.email = "requester@example.com"
        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = mock_requester

        mock_session.execute = AsyncMock(
            side_effect=[mock_req_result, mock_user_result]
        )
        mock_session.commit = AsyncMock()

        # Simulate status change after commit
        def set_rejected(*args, **kwargs):
            mock_gift_request.status = GiftRequestStatus.REJECTED

        mock_session.refresh = AsyncMock(side_effect=set_rejected)

        resp = admin_client.post(
            f"/api/v1/admin/gift-requests/{mock_gift_request.id}/reject",
            json={"reason": "Insufficient documentation"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "rejected"
