"""Integration tests for Admin Telegram Scraper Account Onboarding API (Story 22.2 / AC-1)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.app import app
from app.auth.context import AuthContext
from app.db import User, get_async_session
from app.users import require_superuser

pytestmark = [
    pytest.mark.unit,
]


@pytest.fixture
def admin_auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer fake-admin-token"}


@pytest.fixture
async def client():
    mock_user = MagicMock(spec=User)
    mock_user.id = 1
    mock_user.is_superuser = True
    mock_db_session = AsyncMock()

    app.dependency_overrides[require_superuser] = lambda: AuthContext.session(
        user=mock_user
    )
    app.dependency_overrides[get_async_session] = lambda: mock_db_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.pop(require_superuser, None)
    app.dependency_overrides.pop(get_async_session, None)


@pytest.mark.asyncio
async def test_admin_request_otp_success(
    client: AsyncClient, admin_auth_headers: dict
) -> None:
    """Test POST /api/admin/scraper-accounts/telegram/request-otp sends code and caches state in Redis (AC-1)."""
    payload = {
        "phone": "+84988123456",
        "api_id": 123456,
        "api_hash": "abcdef0123456789abcdef0123456789",
    }

    with patch(
        "app.routes.admin_scraper_platform_accounts_routes.telethon_request_login_code",
        new_callable=AsyncMock,
    ) as mock_req:
        mock_req.return_value = {"phone_code_hash": "hash_12345"}

        response = await client.post(
            "/api/admin/scraper-accounts/telegram/request-otp",
            json=payload,
            headers=admin_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "otp_sent"
        assert data["phone"] == "+84988123456"


@pytest.mark.asyncio
async def test_admin_verify_otp_success_direct(
    client: AsyncClient, admin_auth_headers: dict
) -> None:
    """Test POST /api/admin/scraper-accounts/telegram/verify-otp without 2FA completes onboarding (AC-1)."""
    payload = {
        "phone": "+84988123456",
        "code": "12345",
    }

    with patch(
        "app.routes.admin_scraper_platform_accounts_routes.telethon_verify_login_code",
        new_callable=AsyncMock,
    ) as mock_verify:
        mock_verify.return_value = {
            "status": "authenticated",
            "account_id": 123,
            "session_string": "1BJWap1wBu8...",
            "user_id": 999888,
            "username": "tg_user_vn",
        }

        response = await client.post(
            "/api/admin/scraper-accounts/telegram/verify-otp",
            json=payload,
            headers=admin_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "authenticated"
        assert data["account_id"] is not None
        assert "session_string" not in data or data.get("session_string") is None


@pytest.mark.asyncio
async def test_admin_verify_otp_returns_2fa_required(
    client: AsyncClient, admin_auth_headers: dict
) -> None:
    """Test POST /api/admin/scraper-accounts/telegram/verify-otp detects 2FA password requirement (AC-1)."""
    payload = {
        "phone": "+84988123456",
        "code": "12345",
    }

    with patch(
        "app.routes.admin_scraper_platform_accounts_routes.telethon_verify_login_code",
        new_callable=AsyncMock,
    ) as mock_verify:
        mock_verify.return_value = {
            "status": "2fa_required",
            "hint": "My 2FA hint",
        }

        response = await client.post(
            "/api/admin/scraper-accounts/telegram/verify-otp",
            json=payload,
            headers=admin_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "2fa_required"
        assert data["hint"] == "My 2FA hint"


@pytest.mark.asyncio
async def test_admin_verify_2fa_success(
    client: AsyncClient, admin_auth_headers: dict
) -> None:
    """Test POST /api/admin/scraper-accounts/telegram/verify-2fa with password saves encrypted session (AC-1)."""
    payload = {
        "phone": "+84988123456",
        "password": "SuperSecret2FAPassword!",
    }

    with patch(
        "app.routes.admin_scraper_platform_accounts_routes.telethon_verify_2fa_password",
        new_callable=AsyncMock,
    ) as mock_2fa:
        mock_2fa.return_value = {
            "status": "authenticated",
            "account_id": 123,
            "session_string": "1BJWap1wBu8...",
            "user_id": 999888,
            "username": "tg_user_vn",
        }

        response = await client.post(
            "/api/admin/scraper-accounts/telegram/verify-2fa",
            json=payload,
            headers=admin_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "authenticated"
        assert data["account_id"] is not None
        assert "session_string" not in data or data.get("session_string") is None


@pytest.mark.asyncio
async def test_admin_verify_otp_expired_flow(
    client: AsyncClient, admin_auth_headers: dict
) -> None:
    """Test POST /api/admin/scraper-accounts/telegram/verify-otp returns 400 when Redis flow expired (AC-1)."""
    payload = {
        "phone": "+84988123456",
        "code": "12345",
    }

    with patch(
        "app.routes.admin_scraper_platform_accounts_routes.telethon_verify_login_code",
        new_callable=AsyncMock,
    ) as mock_verify:
        mock_verify.side_effect = ValueError(
            "Auth flow expired or not found in Redis cache"
        )

        response = await client.post(
            "/api/admin/scraper-accounts/telegram/verify-otp",
            json=payload,
            headers=admin_auth_headers,
        )

        assert response.status_code == 400
        assert "expired" in response.json()["detail"].lower()
