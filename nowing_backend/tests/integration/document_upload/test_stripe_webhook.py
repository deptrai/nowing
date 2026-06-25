"""Integration tests for Stripe webhook fulfillment."""

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


async def _get_user_id(email: str) -> str:
    row = await _fetchrow('SELECT id FROM "user" WHERE email = $1', email)
    assert row is not None, f"User {email!r} not found"
    return str(row["id"])


async def _get_pages_limit(email: str) -> int:
    row = await _fetchrow('SELECT pages_limit FROM "user" WHERE email = $1', email)
    assert row is not None, f"User {email!r} not found"
    return row["pages_limit"]


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


class _FakeWebhookStripeClient:
    def __init__(self, event):
        self.event = event
        self.last_payload = None
        self.last_signature = None
        self.last_secret = None

    def construct_event(self, payload, signature, secret):
        self.last_payload = payload
        self.last_signature = signature
        self.last_secret = secret
        return self.event


class TestStripeWebhookFulfillment:
    async def test_webhook_grants_pages_once(
        self,
        client,
        headers,
        search_space_id: int,
        page_limits,
        monkeypatch,
    ):
        await page_limits.set(pages_used=0, pages_limit=100)

        checkout_session = SimpleNamespace(
            id="cs_test_webhook_123",
            url="https://checkout.stripe.test/cs_test_webhook_123",
            payment_intent=None,
            amount_total=None,
            currency=None,
        )
        create_client = _FakeCreateStripeClient(checkout_session)

        monkeypatch.setattr(stripe_routes, "get_stripe_client", lambda: create_client)
        monkeypatch.setattr(stripe_routes.config, "STRIPE_PRICE_ID", "price_pages_1000")
        monkeypatch.setattr(
            stripe_routes.config, "NEXT_FRONTEND_URL", "http://localhost:3000"
        )
        monkeypatch.setattr(stripe_routes.config, "STRIPE_PAGES_PER_UNIT", 1000)

        create_response = await client.post(
            "/api/v1/stripe/create-checkout-session",
            headers=headers,
            json={"quantity": 3, "search_space_id": search_space_id},
        )
        assert create_response.status_code == 200, create_response.text

        initial_limit = await _get_pages_limit(TEST_EMAIL)
        assert initial_limit == 100

        user_id = await _get_user_id(TEST_EMAIL)
        webhook_checkout_session = SimpleNamespace(
            id=checkout_session.id,
            payment_status="paid",
            payment_intent="pi_test_123",
            amount_total=300,
            currency="usd",
            metadata={
                "user_id": user_id,
                "quantity": "3",
                "pages_per_unit": "1000",
            },
        )
        event = SimpleNamespace(
            type="checkout.session.completed",
            data=SimpleNamespace(object=webhook_checkout_session),
        )
        webhook_client = _FakeWebhookStripeClient(event)

        monkeypatch.setattr(stripe_routes, "get_stripe_client", lambda: webhook_client)
        monkeypatch.setattr(stripe_routes.config, "STRIPE_WEBHOOK_SECRET", "whsec_test")

        first_response = await client.post(
            "/api/v1/stripe/webhook",
            headers={"Stripe-Signature": "sig_test"},
            content=b"{}",
        )
        assert first_response.status_code == 200, first_response.text

        updated_limit = await _get_pages_limit(TEST_EMAIL)
        assert updated_limit == 3100

        purchase = await _fetchrow(
            """
            SELECT status, amount_total, currency, stripe_payment_intent_id
            FROM page_purchases
            WHERE stripe_checkout_session_id = $1
            """,
            checkout_session.id,
        )
        assert purchase is not None
        assert purchase["status"] == "COMPLETED"
        assert purchase["amount_total"] == 300
        assert purchase["currency"] == "usd"
        assert purchase["stripe_payment_intent_id"] == "pi_test_123"

        second_response = await client.post(
            "/api/v1/stripe/webhook",
            headers={"Stripe-Signature": "sig_test"},
            content=b"{}",
        )
        assert second_response.status_code == 200, second_response.text

        assert await _get_pages_limit(TEST_EMAIL) == 3100
