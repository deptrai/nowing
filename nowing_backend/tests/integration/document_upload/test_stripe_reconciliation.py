"""Integration tests for Stripe reconciliation task."""

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
from app.tasks.celery_tasks import stripe_reconciliation_task
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


class _FakeReconciliationStripeClient:
    def __init__(self, checkout_session):
        self.checkout_session = checkout_session
        self.requested_ids = []
        self.v1 = SimpleNamespace(
            checkout=SimpleNamespace(
                sessions=SimpleNamespace(retrieve=self._retrieve_session)
            )
        )

    def _retrieve_session(self, checkout_session_id: str):
        self.requested_ids.append(checkout_session_id)
        return self.checkout_session


class TestStripeReconciliation:
    async def test_reconciliation_fulfills_paid_pending_purchase(
        self,
        client,
        headers,
        search_space_id: int,
        page_limits,
        monkeypatch,
    ):
        await page_limits.set(pages_used=220, pages_limit=150)

        checkout_session = SimpleNamespace(
            id="cs_test_reconcile_paid_123",
            url="https://checkout.stripe.test/cs_test_reconcile_paid_123",
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
        assert await _get_pages_limit(TEST_EMAIL) == 150

        reconciled_session = SimpleNamespace(
            id=checkout_session.id,
            status="complete",
            payment_status="paid",
            payment_intent="pi_test_reconcile_123",
            amount_total=300,
            currency="usd",
            metadata={},
        )
        reconcile_client = _FakeReconciliationStripeClient(reconciled_session)

        monkeypatch.setattr(
            stripe_reconciliation_task, "get_stripe_client", lambda: reconcile_client
        )
        monkeypatch.setattr(
            stripe_reconciliation_task.config,
            "STRIPE_RECONCILIATION_LOOKBACK_MINUTES",
            0,
        )
        monkeypatch.setattr(
            stripe_reconciliation_task.config,
            "STRIPE_RECONCILIATION_BATCH_SIZE",
            20,
        )

        await stripe_reconciliation_task._reconcile_pending_page_purchases()

        assert reconcile_client.requested_ids == [checkout_session.id]
        assert await _get_pages_limit(TEST_EMAIL) == 3220

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
        assert purchase["stripe_payment_intent_id"] == "pi_test_reconcile_123"

    async def test_reconciliation_marks_expired_pending_purchase_failed(
        self,
        client,
        headers,
        search_space_id: int,
        page_limits,
        monkeypatch,
    ):
        await page_limits.set(pages_used=0, pages_limit=500)

        checkout_session = SimpleNamespace(
            id="cs_test_reconcile_expired_123",
            url="https://checkout.stripe.test/cs_test_reconcile_expired_123",
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
            json={"quantity": 1, "search_space_id": search_space_id},
        )
        assert create_response.status_code == 200, create_response.text

        expired_session = SimpleNamespace(
            id=checkout_session.id,
            status="expired",
            payment_status="unpaid",
            payment_intent=None,
            amount_total=100,
            currency="usd",
            metadata={},
        )
        reconcile_client = _FakeReconciliationStripeClient(expired_session)

        monkeypatch.setattr(
            stripe_reconciliation_task, "get_stripe_client", lambda: reconcile_client
        )
        monkeypatch.setattr(
            stripe_reconciliation_task.config,
            "STRIPE_RECONCILIATION_LOOKBACK_MINUTES",
            0,
        )
        monkeypatch.setattr(
            stripe_reconciliation_task.config,
            "STRIPE_RECONCILIATION_BATCH_SIZE",
            20,
        )

        await stripe_reconciliation_task._reconcile_pending_page_purchases()

        assert await _get_pages_limit(TEST_EMAIL) == 500

        purchase = await _fetchrow(
            """
            SELECT status
            FROM page_purchases
            WHERE stripe_checkout_session_id = $1
            """,
            checkout_session.id,
        )
        assert purchase is not None
        assert purchase["status"] == "FAILED"
