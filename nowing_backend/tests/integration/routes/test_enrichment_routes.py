"""Integration tests for contact-enrichment REST routes (Story 21.3, Task 5)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app, limiter
from app.auth.context import AuthContext
from app.db import (
    EnrichmentRequest,
    Lead,
    User,
    VerifiedContact,
    Workspace,
    get_async_session,
)
from app.services.pii.verified_contact_encryption import VerifiedContactEncryption
from app.users import get_auth_context

pytestmark = [pytest.mark.integration]

limiter.enabled = False


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
    db_user: User,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Authenticated as the workspace owner (db_user)."""

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_auth() -> AuthContext:
        return AuthContext.session(db_user)

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_auth_context] = override_auth

    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            timeout=30.0,
            follow_redirects=False,
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


async def _make_lead(
    db_session: AsyncSession,
    db_workspace: Workspace,
    company_name: str = "FPT",
) -> Lead:
    lead = Lead(
        id=uuid4(),
        workspace_id=db_workspace.id,
        client_id=None,
        source="test",
        company_name=company_name,
        domain="fpt.com",
        value_hmac=f"lead-hmac-{uuid4().hex[:8]}",
        industry="software",
        status="open",
    )
    db_session.add(lead)
    await db_session.flush()
    return lead


async def test_enrich_lead_returns_202_with_request(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_workspace: Workspace,
    monkeypatch: Any,
) -> None:
    """POST /leads/{id}/enrich returns 202 and persists an EnrichmentRequest."""
    lead = await _make_lead(db_session, db_workspace)
    from app.lead_intelligence.enrichment.service import EnrichmentService

    monkeypatch.setattr(EnrichmentService, "_enqueue", AsyncMock())

    response = await client.post(
        f"/api/v1/workspaces/{db_workspace.id}/leads/{lead.id}/enrich",
        json={"requested_count": 5},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["lead_id"] == str(lead.id)
    assert body["status"] == "pending"
    assert body["contact_count"] == 0
    assert body["degraded"] is False
    request_id = body["enrichment_request_id"]
    assert request_id

    row = (
        await db_session.execute(
            select(EnrichmentRequest).where(EnrichmentRequest.id == request_id)
        )
    ).scalar_one_or_none()
    assert row is not None
    assert row.lead_id == lead.id
    assert row.requested_count == 5
    assert row.status == "pending"


async def test_enrich_lead_lead_not_found_returns_404(
    client: httpx.AsyncClient,
    db_workspace: Workspace,
) -> None:
    """POST /leads/{id}/enrich maps lead_not_found to 404."""
    response = await client.post(
        f"/api/v1/workspaces/{db_workspace.id}/leads/{uuid4()}/enrich",
        json={},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "lead_not_found"


async def test_enrich_lead_insufficient_wallet_returns_402(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_workspace: Workspace,
    monkeypatch: Any,
) -> None:
    """POST /leads/{id}/enrich maps insufficient_wallet to 402."""
    lead = await _make_lead(db_session, db_workspace)
    from app.lead_intelligence.enrichment.service import EnrichmentService

    monkeypatch.setattr(EnrichmentService, "_enqueue", AsyncMock())

    # Force the service to degrade with insufficient_wallet.
    async def _fail_check(*a, **k):
        from app.services import wallet_credit

        raise wallet_credit.InsufficientCreditsError("insufficient")

    monkeypatch.setattr(
        "app.lead_intelligence.enrichment.service.wallet_credit.check_balance",
        _fail_check,
    )

    response = await client.post(
        f"/api/v1/workspaces/{db_workspace.id}/leads/{lead.id}/enrich",
        json={},
    )
    assert response.status_code == 402
    assert response.json()["detail"] == "insufficient_wallet"


async def test_get_contacts_returns_decrypted_contacts(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
) -> None:
    """GET /leads/{id}/contacts returns decrypted VerifiedContact rows."""
    lead = await _make_lead(db_session, db_workspace)
    request = EnrichmentRequest(
        id=uuid4(),
        workspace_id=db_workspace.id,
        lead_id=lead.id,
        requested_count=5,
        status="completed",
        provider_results={},
        created_at=datetime.now(UTC),
    )
    db_session.add(request)
    await db_session.flush()

    encrypted = VerifiedContactEncryption().encrypt_contact(
        {
            "name": "Alice Nguyen",
            "title": "CTO",
            "email": "alice@fpt.com",
            "phone": "+84123456789",
        }
    )
    contact = VerifiedContact(
        id=uuid4(),
        workspace_id=db_workspace.id,
        lead_id=lead.id,
        enrichment_request_id=request.id,
        name=encrypted["name"],
        title=encrypted["title"],
        email=encrypted["email"],
        phone=encrypted["phone"],
        verification_status="verified",
        confidence=0.95,
        source_provider="cleanlist",
        created_at=datetime.now(UTC),
    )
    db_session.add(contact)
    await db_session.flush()

    response = await client.get(
        f"/api/v1/workspaces/{db_workspace.id}/leads/{lead.id}/contacts",
        params={"limit": 10, "offset": 0},
    )
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["name"] == "Alice Nguyen"
    assert items[0]["email"] == "alice@fpt.com"
    assert items[0]["phone"] == "+84123456789"
    assert items[0]["source_provider"] == "cleanlist"


async def test_get_contacts_scoped_by_client(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
) -> None:
    """GET /leads/{id}/contacts filters out contacts of other clients."""
    from app.auth.context import AuthContext
    from app.db import PersonalAccessToken, VerticalClient

    db_session.add(VerticalClient(client_id="client-a", display_name="Client A"))
    db_session.add(VerticalClient(client_id="client-b", display_name="Client B"))
    await db_session.flush()
    lead = await _make_lead(db_session, db_workspace)
    lead.client_id = "client-a"
    await db_session.flush()
    request = EnrichmentRequest(
        id=uuid4(),
        workspace_id=db_workspace.id,
        client_id="client-a",
        lead_id=lead.id,
        requested_count=5,
        status="completed",
        provider_results={},
        created_at=datetime.now(UTC),
    )
    db_session.add(request)
    await db_session.flush()

    encrypted = VerifiedContactEncryption().encrypt_contact(
        {
            "name": "Alice Nguyen",
            "title": "CTO",
            "email": "alice@fpt.com",
            "phone": "+84123456789",
        }
    )
    contact = VerifiedContact(
        id=uuid4(),
        workspace_id=db_workspace.id,
        client_id="client-a",
        lead_id=lead.id,
        enrichment_request_id=request.id,
        name=encrypted["name"],
        title=encrypted["title"],
        email=encrypted["email"],
        phone=encrypted["phone"],
        verification_status="verified",
        confidence=0.95,
        source_provider="cleanlist",
        created_at=datetime.now(UTC),
    )
    db_session.add(contact)
    await db_session.flush()

    # A client-b PAT must not see client-a's contacts for the same lead.
    pat = PersonalAccessToken(
        user_id=db_user.id,
        token_hash="h" * 64,
        token_prefix="nw_pat_b",
        label="client-b",
        client_id="client-b",
    )
    db_session.add(pat)
    await db_session.flush()

    db_workspace.api_access_enabled = True
    await db_session.flush()

    async def override_auth() -> AuthContext:
        return AuthContext.pat_auth(db_user, pat)

    app.dependency_overrides[get_auth_context] = override_auth
    response = await client.get(
        f"/api/v1/workspaces/{db_workspace.id}/leads/{lead.id}/contacts"
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_get_enrichment_requests_lists_and_paginates(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_workspace: Workspace,
) -> None:
    """GET /leads/{id}/enrichments lists requests newest first."""
    lead = await _make_lead(db_session, db_workspace)
    for status in ("completed", "pending", "failed"):
        db_session.add(
            EnrichmentRequest(
                id=uuid4(),
                workspace_id=db_workspace.id,
                lead_id=lead.id,
                requested_count=5,
                status=status,
                provider_results={},
                created_at=datetime.now(UTC),
            )
        )
    await db_session.flush()

    response = await client.get(
        f"/api/v1/workspaces/{db_workspace.id}/leads/{lead.id}/enrichments",
        params={"limit": 2},
    )
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2
    assert items[0]["status"] == "failed"
    assert items[1]["status"] == "pending"


async def test_bulk_enrich_returns_202_for_each_lead(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_workspace: Workspace,
    monkeypatch: Any,
) -> None:
    """POST /leads/enrich enqueues every listed lead."""
    lead_a = await _make_lead(db_session, db_workspace, company_name="FPT")
    lead_b = await _make_lead(db_session, db_workspace, company_name="VNG")
    from app.lead_intelligence.enrichment.service import EnrichmentService

    monkeypatch.setattr(EnrichmentService, "_enqueue", AsyncMock())

    response = await client.post(
        f"/api/v1/workspaces/{db_workspace.id}/leads/enrich",
        json={"lead_ids": [str(lead_a.id), str(lead_b.id)], "requested_count": 5},
    )
    assert response.status_code == 202
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 2
    assert {item["lead_id"] for item in body} == {str(lead_a.id), str(lead_b.id)}
    assert all(item["status"] == "pending" for item in body)


async def test_enrich_cost_endpoint(
    client: httpx.AsyncClient,
    db_workspace: Workspace,
) -> None:
    """GET /leads/enrich/cost exposes the per-contact pricing."""
    from app.config import config

    response = await client.get(
        f"/api/v1/workspaces/{db_workspace.id}/leads/enrich/cost"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["cost_per_contact_micros"] == config.CONTACT_ENRICHMENT_MICROS_PER_CONTACT
    assert body["estimated_cost_micros"] >= 0
    assert body["lead_count"] == 0
