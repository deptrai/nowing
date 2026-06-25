"""
Unit tests for Auth JWT routes — Story 1.2 (P0)

Covers:
  POST /auth/jwt/login        — fastapi-users login (200, 400, 422)
  POST /auth/jwt/refresh      — token refresh (200, 401 invalid, 401 expired, 401 user-not-found, 422)
  POST /auth/jwt/revoke       — single-device logout (200, 200 no-op)
  POST /auth/jwt/logout-all   — all-device logout (200, 401 unauthenticated)

All tests are unit-level: no real DB, no real JWT crypto.
External dependencies are mocked via app.dependency_overrides and pytest-mock.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.app import app
from app.db import User
from app.users import current_active_user

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_user() -> User:
    """Minimal mock User object (sufficient for JWT generation)."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.email = "user@example.com"
    user.is_active = True
    user.is_superuser = False
    user.is_verified = True
    return user


@pytest.fixture
def mock_refresh_token_record(mock_user):
    """Minimal RefreshToken ORM object mock."""
    record = MagicMock()
    record.id = uuid.uuid4()
    record.user_id = mock_user.id
    record.family_id = uuid.uuid4()
    record.is_revoked = False
    record.is_expired = False
    return record


@pytest.fixture
def client(mock_user) -> TestClient:
    """
    TestClient with current_active_user overridden.
    Used for routes that require authentication.
    NOTE: Do NOT use as context manager — avoids event loop conflicts.
    """
    app.dependency_overrides[current_active_user] = lambda: mock_user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.pop(current_active_user, None)


@pytest.fixture
def unauthenticated_client() -> TestClient:
    """
    TestClient with NO dependency overrides.
    Used to verify 401 on protected routes.
    NOTE: Do NOT use as context manager — avoids event loop conflicts.
    """
    app.dependency_overrides.pop(current_active_user, None)
    c = TestClient(app, raise_server_exceptions=False)
    yield c


# ---------------------------------------------------------------------------
# POST /auth/jwt/login
# ---------------------------------------------------------------------------


class TestLoginEndpoint:
    """[P0] Story 1.2 — AC BE-1: JWT issued on valid credentials, 401 on invalid."""

    def test_login_valid_credentials_returns_tokens(self, unauthenticated_client):
        """[P0] Valid username+password → 200 with access_token, token_type."""
        with (
            patch(
                "app.users.UserManager.authenticate",
                new_callable=AsyncMock,
            ) as mock_auth,
            patch(
                "app.users.CustomBearerTransport.get_login_response",
                new_callable=AsyncMock,
            ) as mock_login_resp,
        ):
            from fastapi.responses import JSONResponse

            mock_user_obj = MagicMock()
            mock_user_obj.id = uuid.uuid4()
            mock_user_obj.is_active = True
            mock_auth.return_value = mock_user_obj
            mock_login_resp.return_value = JSONResponse(
                {
                    "access_token": "tok_access",
                    "refresh_token": "tok_refresh",
                    "token_type": "bearer",
                }
            )

            resp = unauthenticated_client.post(
                "/auth/jwt/login",
                data={"username": "user@example.com", "password": "correct_pass"},
            )

        # fastapi-users returns 200 on success
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    def test_login_invalid_password_returns_400(self, unauthenticated_client):
        """[P0] Invalid credentials → 400 (fastapi-users LOGIN_BAD_CREDENTIALS)."""
        with patch(
            "app.users.UserManager.authenticate",
            new_callable=AsyncMock,
            return_value=None,  # None = bad credentials in fastapi-users
        ):
            resp = unauthenticated_client.post(
                "/auth/jwt/login",
                data={"username": "user@example.com", "password": "wrong_pass"},
            )

        # fastapi-users raises 400 LOGIN_BAD_CREDENTIALS when authenticate returns None
        assert resp.status_code == 400

    def test_login_missing_username_returns_422(self, unauthenticated_client):
        """[P1] Missing required field → 422 Unprocessable Entity."""
        resp = unauthenticated_client.post(
            "/auth/jwt/login",
            data={"password": "pass_only"},  # no username
        )
        assert resp.status_code == 422

    def test_login_missing_password_returns_422(self, unauthenticated_client):
        """[P1] Missing password field → 422."""
        resp = unauthenticated_client.post(
            "/auth/jwt/login",
            data={"username": "user@example.com"},
        )
        assert resp.status_code == 422

    def test_login_empty_body_returns_422(self, unauthenticated_client):
        """[P2] Empty body → 422."""
        resp = unauthenticated_client.post("/auth/jwt/login", data={})
        assert resp.status_code == 422

    def test_login_inactive_user_returns_400(self, unauthenticated_client):
        """[P1] Inactive user → 400 (fastapi-users LOGIN_BAD_CREDENTIALS for inactive)."""
        with patch(
            "app.users.UserManager.authenticate",
            new_callable=AsyncMock,
        ) as mock_auth:
            # fastapi-users checks is_active after authenticate; return inactive user
            mock_user_obj = MagicMock()
            mock_user_obj.is_active = False
            mock_auth.return_value = mock_user_obj

            resp = unauthenticated_client.post(
                "/auth/jwt/login",
                data={"username": "inactive@example.com", "password": "pass"},
            )

        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /auth/jwt/refresh
# ---------------------------------------------------------------------------


class TestRefreshEndpoint:
    """[P0] Story 1.2 — token refresh, rotation, and error paths."""

    def test_refresh_valid_token_returns_new_tokens(
        self, unauthenticated_client, mock_user, mock_refresh_token_record
    ):
        """[P0] Valid refresh token → 200 with new access_token + refresh_token."""
        with (
            patch(
                "app.routes.auth_routes.validate_refresh_token",
                new_callable=AsyncMock,
                return_value=mock_refresh_token_record,
            ),
            patch(
                "app.routes.auth_routes.async_session_maker",
            ) as mock_session_maker,
            patch(
                "app.routes.auth_routes.get_jwt_strategy",
            ) as mock_strategy_factory,
            patch(
                "app.routes.auth_routes.rotate_refresh_token",
                new_callable=AsyncMock,
                return_value="new_refresh_tok_abc",
            ),
        ):
            # Mock DB session lookup
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_result = MagicMock()
            mock_result.scalars.return_value.first.return_value = mock_user
            mock_session.execute = AsyncMock(return_value=mock_result)

            # Mock JWT strategy
            mock_strategy = AsyncMock()
            mock_strategy.write_token = AsyncMock(return_value="new_access_tok_xyz")
            mock_strategy_factory.return_value = mock_strategy

            resp = unauthenticated_client.post(
                "/auth/jwt/refresh",
                json={"refresh_token": "valid_refresh_token_value"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["access_token"] == "new_access_tok_xyz"
        assert body["refresh_token"] == "new_refresh_tok_abc"
        assert body["token_type"] == "bearer"

    def test_refresh_invalid_token_returns_401(self, unauthenticated_client):
        """[P0] Invalid/unknown refresh token → 401 Unauthorized."""
        with patch(
            "app.routes.auth_routes.validate_refresh_token",
            new_callable=AsyncMock,
            return_value=None,  # None = invalid token
        ):
            resp = unauthenticated_client.post(
                "/auth/jwt/refresh",
                json={"refresh_token": "totally_invalid_token"},
            )

        assert resp.status_code == 401
        assert "Invalid or expired" in resp.json()["detail"]

    def test_refresh_expired_token_returns_401(self, unauthenticated_client):
        """[P0] Expired refresh token → 401 (validate_refresh_token returns None for expired)."""
        with patch(
            "app.routes.auth_routes.validate_refresh_token",
            new_callable=AsyncMock,
            return_value=None,  # expired → returns None
        ):
            resp = unauthenticated_client.post(
                "/auth/jwt/refresh",
                json={"refresh_token": "expired_token_value"},
            )

        assert resp.status_code == 401

    def test_refresh_user_not_found_returns_401(
        self, unauthenticated_client, mock_refresh_token_record
    ):
        """[P1] Token valid but user deleted from DB → 401."""
        with (
            patch(
                "app.routes.auth_routes.validate_refresh_token",
                new_callable=AsyncMock,
                return_value=mock_refresh_token_record,
            ),
            patch(
                "app.routes.auth_routes.async_session_maker",
            ) as mock_session_maker,
        ):
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_result = MagicMock()
            mock_result.scalars.return_value.first.return_value = None  # user not found
            mock_session.execute = AsyncMock(return_value=mock_result)

            resp = unauthenticated_client.post(
                "/auth/jwt/refresh",
                json={"refresh_token": "valid_token_deleted_user"},
            )

        assert resp.status_code == 401
        assert "User not found" in resp.json()["detail"]

    def test_refresh_missing_body_field_returns_422(self, unauthenticated_client):
        """[P1] Missing refresh_token field → 422 Unprocessable Entity."""
        resp = unauthenticated_client.post(
            "/auth/jwt/refresh",
            json={},  # no refresh_token
        )
        assert resp.status_code == 422

    def test_refresh_non_string_token_returns_422(self, unauthenticated_client):
        """[P2] Non-string refresh_token → 422."""
        resp = unauthenticated_client.post(
            "/auth/jwt/refresh",
            json={"refresh_token": 12345},
        )
        assert resp.status_code == 422

    def test_refresh_rotates_token(
        self, unauthenticated_client, mock_user, mock_refresh_token_record
    ):
        """[P1] Successful refresh calls rotate_refresh_token (old token invalidated)."""
        with (
            patch(
                "app.routes.auth_routes.validate_refresh_token",
                new_callable=AsyncMock,
                return_value=mock_refresh_token_record,
            ),
            patch(
                "app.routes.auth_routes.async_session_maker",
            ) as mock_session_maker,
            patch(
                "app.routes.auth_routes.get_jwt_strategy",
            ) as mock_strategy_factory,
            patch(
                "app.routes.auth_routes.rotate_refresh_token",
                new_callable=AsyncMock,
                return_value="rotated_token",
            ) as mock_rotate,
        ):
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_result = MagicMock()
            mock_result.scalars.return_value.first.return_value = mock_user
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_strategy = AsyncMock()
            mock_strategy.write_token = AsyncMock(return_value="new_access_tok")
            mock_strategy_factory.return_value = mock_strategy

            unauthenticated_client.post(
                "/auth/jwt/refresh",
                json={"refresh_token": "old_token"},
            )

            mock_rotate.assert_awaited_once_with(mock_refresh_token_record)


# ---------------------------------------------------------------------------
# POST /auth/jwt/revoke
# ---------------------------------------------------------------------------


class TestRevokeEndpoint:
    """[P1] Story 1.2 — single-device logout via refresh token revocation."""

    def test_revoke_valid_token_returns_200(self, unauthenticated_client):
        """[P1] Valid refresh token → 200 with detail message."""
        with patch(
            "app.routes.auth_routes.revoke_refresh_token",
            new_callable=AsyncMock,
            return_value=True,
        ):
            resp = unauthenticated_client.post(
                "/auth/jwt/revoke",
                json={"refresh_token": "some_refresh_token"},
            )

        assert resp.status_code == 200
        assert "logged out" in resp.json()["detail"].lower()

    def test_revoke_unknown_token_still_returns_200(self, unauthenticated_client):
        """[P2] Unknown/already-revoked token → 200 (no-op, idempotent)."""
        with patch(
            "app.routes.auth_routes.revoke_refresh_token",
            new_callable=AsyncMock,
            return_value=False,  # token not found
        ):
            resp = unauthenticated_client.post(
                "/auth/jwt/revoke",
                json={"refresh_token": "nonexistent_token"},
            )

        assert resp.status_code == 200

    def test_revoke_missing_token_field_returns_422(self, unauthenticated_client):
        """[P1] Missing refresh_token → 422."""
        resp = unauthenticated_client.post(
            "/auth/jwt/revoke",
            json={},
        )
        assert resp.status_code == 422

    def test_revoke_calls_revoke_refresh_token(self, unauthenticated_client):
        """[P1] Verifies revoke_refresh_token is called with the provided token value."""
        with patch(
            "app.routes.auth_routes.revoke_refresh_token",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_revoke:
            unauthenticated_client.post(
                "/auth/jwt/revoke",
                json={"refresh_token": "specific_token_xyz"},
            )

            mock_revoke.assert_awaited_once_with("specific_token_xyz")


# ---------------------------------------------------------------------------
# POST /auth/jwt/logout-all
# ---------------------------------------------------------------------------


class TestLogoutAllEndpoint:
    """[P1] Story 1.2 — logout all devices (requires valid access token)."""

    def test_logout_all_authenticated_returns_200(self, client, mock_user):
        """[P1] Authenticated user → 200 with detail message."""
        with patch(
            "app.routes.auth_routes.revoke_all_user_tokens",
            new_callable=AsyncMock,
        ) as mock_revoke_all:
            resp = client.post("/auth/jwt/logout-all")

        assert resp.status_code == 200
        assert "all devices" in resp.json()["detail"].lower()
        mock_revoke_all.assert_awaited_once_with(mock_user.id)

    def test_logout_all_unauthenticated_returns_401(self, unauthenticated_client):
        """[P0] No access token → 401 Unauthorized."""
        resp = unauthenticated_client.post("/auth/jwt/logout-all")
        assert resp.status_code == 401

    def test_logout_all_revokes_all_user_tokens(self, client, mock_user):
        """[P1] Verifies revoke_all_user_tokens is called with current user's ID."""
        with patch(
            "app.routes.auth_routes.revoke_all_user_tokens",
            new_callable=AsyncMock,
        ) as mock_revoke_all:
            client.post("/auth/jwt/logout-all")

        mock_revoke_all.assert_awaited_once_with(mock_user.id)
