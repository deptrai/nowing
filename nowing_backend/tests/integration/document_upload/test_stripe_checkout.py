"""Integration tests for Stripe checkout session creation."""

from __future__ import annotations

from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import asyncpg
import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport

from app.app import app
from app.routes import stripe_routes
from tests.integration.conftest import TEST_DATABASE_URL
from tests.utils.helpers import TEST_EMAIL, TEST_PASSWORD, auth_headers

pytestmark = pytest.mark.integration

_ASYNCPG_URL = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


async def _execute(query: str, *args) -> None:
    conn = await asyncpg.connect(_ASYNCPG_URL)
    try:
        await conn.execute(query, *args)
    finally:
        await conn.close()


async def _fetchrow(query: str, *args):
    conn = await asyncpg.connect(_ASYNCPG_URL)
    try:
        return await conn.fetchrow(query, *args)
    finally:
        await conn.close()


def _extract_access_token(response: httpx.Response) -> str | None:
    if response.status_code == 200:
        return response.json()["access_token"]
    if response.status_code == 302:
        location = response.headers.get("location", "")
        return parse_qs(urlparse(location).query).get("token", [None])[0]
    return None


async def _authenticate_test_user(client: httpx.AsyncClient) -> str:
    response = await client.post(
        "/auth/jwt/login",
        data={"username": TEST_EMAIL, "password": TEST_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token = _extract_access_token(response)
    if token:
        return token

    reg_response = await client.post(
        "/auth/register",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    assert reg_response.status_code == 201, (
        f"Registration failed ({reg_response.status_code}): {reg_response.text}"
    )

    response = await client.post(
        "/auth/jwt/login",
        data={"username": TEST_EMAIL, "password": TEST_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token = _extract_access_token(response)
    assert token, f"Login failed ({response.status_code}): {response.text}"
    return token


@pytest_asyncio.fixture(scope="session")
async def auth_token(_ensure_tables) -> str:
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", timeout=30.0
    ) as client:
        return await _authenticate_test_user(client)


@pytest.fixture(scope="session")
def headers(auth_token: str) -> dict[str, str]:
    return auth_headers(auth_token)


@pytest.fixture(autouse=True)
async def _cleanup_page_purchases():
    await _execute("DELETE FROM page_purchases")
    yield
    await _execute("DELETE FROM page_purchases")


class _FakeCreateStripeClient:
    def __init__(self, checkout_session):
        self.checkout_session = checkout_session
        self.last_params = None
        self.v1 = SimpleNamespace(
            checkout=SimpleNamespace(
                sessions=SimpleNamespace(create=self._create_session)
            )
        )

    def _create_session(self, *, params):
        self.last_params = params
        return self.checkout_session


class TestStripeCheckoutSessionCreation:
    async def test_get_status_reflects_backend_toggle(
        self, client, headers, monkeypatch
    ):
        monkeypatch.setattr(stripe_routes.config, "STRIPE_PAGE_BUYING_ENABLED", False)
        disabled_response = await client.get("/api/v1/stripe/status", headers=headers)
        assert disabled_response.status_code == 200, disabled_response.text
        assert disabled_response.json() == {"page_buying_enabled": False}

        monkeypatch.setattr(stripe_routes.config, "STRIPE_PAGE_BUYING_ENABLED", True)
        enabled_response = await client.get("/api/v1/stripe/status", headers=headers)
        assert enabled_response.status_code == 200, enabled_response.text
        assert enabled_response.json() == {"page_buying_enabled": True}

    async def test_create_checkout_session_records_pending_purchase(
        self,
        client,
        headers,
        search_space_id: int,
        monkeypatch,
    ):
        checkout_session = SimpleNamespace(
            id="cs_test_create_123",
            url="https://checkout.stripe.test/cs_test_create_123",
            payment_intent=None,
            amount_total=None,
            currency=None,
        )
        fake_client = _FakeCreateStripeClient(checkout_session)

        monkeypatch.setattr(stripe_routes, "get_stripe_client", lambda: fake_client)
        monkeypatch.setattr(stripe_routes.config, "STRIPE_PRICE_ID", "price_pages_1000")
        monkeypatch.setattr(
            stripe_routes.config, "NEXT_FRONTEND_URL", "http://localhost:3000"
        )
        monkeypatch.setattr(stripe_routes.config, "STRIPE_PAGES_PER_UNIT", 1000)

        response = await client.post(
            "/api/v1/stripe/create-checkout-session",
            headers=headers,
            json={"quantity": 2, "search_space_id": search_space_id},
        )

        assert response.status_code == 200, response.text
        assert response.json() == {"checkout_url": checkout_session.url}
        assert fake_client.last_params is not None
        assert fake_client.last_params["mode"] == "payment"
        assert fake_client.last_params["line_items"] == [
            {"price": "price_pages_1000", "quantity": 2}
        ]
        assert (
            fake_client.last_params["success_url"]
            == f"http://localhost:3000/dashboard/{search_space_id}/purchase-success"
        )
        assert (
            fake_client.last_params["cancel_url"]
            == f"http://localhost:3000/dashboard/{search_space_id}/purchase-cancel"
        )

        purchase = await _fetchrow(
            """
            SELECT quantity, pages_granted, status
            FROM page_purchases
            WHERE stripe_checkout_session_id = $1
            """,
            checkout_session.id,
        )
        assert purchase is not None
        assert purchase["quantity"] == 2
        assert purchase["pages_granted"] == 2000
        assert purchase["status"] == "PENDING"

    async def test_create_checkout_session_returns_503_when_buying_disabled(
        self,
        client,
        headers,
        search_space_id: int,
        monkeypatch,
    ):
        monkeypatch.setattr(stripe_routes.config, "STRIPE_PAGE_BUYING_ENABLED", False)

        response = await client.post(
            "/api/v1/stripe/create-checkout-session",
            headers=headers,
            json={"quantity": 2, "search_space_id": search_space_id},
        )

        assert response.status_code == 503, response.text
        assert (
            response.json()["detail"] == "Page purchases are temporarily unavailable."
        )

        purchase_count = await _fetchrow("SELECT COUNT(*) AS count FROM page_purchases")
        assert purchase_count is not None
        assert purchase_count["count"] == 0
