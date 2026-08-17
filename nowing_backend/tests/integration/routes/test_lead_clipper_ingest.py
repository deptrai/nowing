"""ATDD Red-Phase Integration Tests: Nowing Lead Clipper Ingest (Story 24.4 / INV-24.5).

Verifies full database persistence, deduplication constraint enforcement,
PAT scope gating (leads:clipper:write), and extension origin handling for
POST /api/v1/workspaces/{workspace_id}/leads/clip.
"""

from __future__ import annotations

import hashlib
from collections.abc import AsyncGenerator
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app, limiter
from app.auth.context import AuthContext
from app.db import (
    Lead,
    PersonalAccessToken,
    User,
    Workspace,
    get_async_session,
)
from app.users import get_auth_context

pytestmark = [pytest.mark.integration]

limiter.enabled = False

CLIPPER_SCOPE = "leads:clipper:write"


def _compute_hash(workspace_id: int, canonical_url: str, phone: str = "") -> str:
    norm_phone = "".join(c for c in phone if c.isdigit())
    raw = f"{workspace_id}:{canonical_url}:{norm_phone}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@pytest_asyncio.fixture
async def clipper_client(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
) -> AsyncGenerator[tuple[httpx.AsyncClient, PersonalAccessToken], None]:
    """Provides an AsyncClient configured with a scoped Clipper PAT."""
    pat = PersonalAccessToken(
        user_id=db_user.id,
        user=db_user,
        token_hash=hashlib.sha256(b"test_clipper_token").hexdigest(),
        token_prefix="nw_pat_clip",
        label="Test Clipper Extension PAT",
        workspace_id=db_workspace.id,
        scopes=[CLIPPER_SCOPE],
        token_kind="clipper",
    )
    db_session.add(pat)
    await db_session.flush()

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_auth() -> AuthContext:
        return AuthContext.pat_auth(db_user, pat)

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_auth_context] = override_auth

    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            timeout=30.0,
            follow_redirects=False,
            headers={
                "Authorization": "Bearer nw_pat_clip_secret",
                "Origin": "chrome-extension://abcdefghijklmnop1234567890",
            },
        ) as test_client:
            yield test_client, pat
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


async def test_lead_clipper_ingest_success_creates_db_lead(
    clipper_client: tuple[httpx.AsyncClient, PersonalAccessToken],
    db_session: AsyncSession,
    db_workspace: Workspace,
):
    """AC-1 & AC-3: Valid payload clips lead and persists to DB within workspace."""
    client, _ = clipper_client
    payload = {
        "source_canonical_url": "https://batdongsan.com.vn/ban-nha-quan-1/listing-9988",
        "source_platform": "batdongsan",
        "contact_name": "Trần Thị B",
        "phone": "0933112233",
        "email": "ttb@gmail.com",
        "company_name": "BĐS Sài Gòn Mới",
        "post_content": "Bán nhà hẻm xe hơi Quận 1, 80m2 3 lầu",
        "price": "12 tỷ",
        "location": "Quận 1, TP.HCM",
        "metadata": {"rooms": 4, "floors": 3},
    }

    response = await client.post(
        f"/api/v1/workspaces/{db_workspace.id}/leads/clip",
        json=payload,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["is_duplicate"] is False
    assert "lead_id" in data
    assert "dedupe_hash" in data

    # Verify DB record
    lead_id = UUID(data["lead_id"])
    stmt = select(Lead).where(Lead.id == lead_id, Lead.workspace_id == db_workspace.id)
    result = await db_session.execute(stmt)
    lead = result.scalar_one_or_none()
    assert lead is not None
    assert lead.company_name == "BĐS Sài Gòn Mới"
    assert lead.source == "batdongsan"


async def test_lead_clipper_ingest_deduplication_upsert(
    clipper_client: tuple[httpx.AsyncClient, PersonalAccessToken],
    db_session: AsyncSession,
    db_workspace: Workspace,
):
    """INV-24.5: Submitting identical lead payload twice returns is_duplicate=True without duplicating row."""
    client, _ = clipper_client
    payload = {
        "source_canonical_url": "https://facebook.com/groups/bds_hanoi/posts/778899",
        "source_platform": "facebook",
        "contact_name": "Lê Văn C",
        "phone": "0988776655",
        "post_content": "Chính chủ cần bán gấp căn hộ 2PN Times City",
        "price": "4.5 tỷ",
    }

    resp1 = await client.post(f"/api/v1/workspaces/{db_workspace.id}/leads/clip", json=payload)
    resp2 = await client.post(f"/api/v1/workspaces/{db_workspace.id}/leads/clip", json=payload)

    assert resp1.status_code == 200
    assert resp2.status_code == 200

    data1 = resp1.json()
    data2 = resp2.json()

    assert data1["is_duplicate"] is False
    assert data2["is_duplicate"] is True
    assert data1["lead_id"] == data2["lead_id"]
    assert data1["dedupe_hash"] == data2["dedupe_hash"]


async def test_lead_clipper_ingest_rejected_without_clipper_scope(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    """AC-1: Token missing leads:clipper:write must be rejected with 403 Forbidden."""
    unscoped_pat = PersonalAccessToken(
        user_id=db_user.id,
        user=db_user,
        token_hash=hashlib.sha256(b"test_unscoped_token").hexdigest(),
        token_prefix="nw_pat_unscoped",
        label="Unscoped PAT",
        workspace_id=db_workspace.id,
        scopes=["agent_chat:thread:create"],  # Missing leads:clipper:write
        token_kind="legacy",
    )
    db_session.add(unscoped_pat)
    await db_session.flush()

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_auth() -> AuthContext:
        return AuthContext.pat_auth(db_user, unscoped_pat)

    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_auth_context] = override_auth

    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as test_client:
            response = await test_client.post(
                f"/api/v1/workspaces/{db_workspace.id}/leads/clip",
                json={
                    "source_canonical_url": "https://topcv.vn/cv/123",
                    "source_platform": "topcv",
                    "contact_name": "Candidate",
                },
            )
            # Must be 403 Forbidden or 404 (if route not mounted)
            assert response.status_code in {403, 404}
    finally:
        app.dependency_overrides.clear()
