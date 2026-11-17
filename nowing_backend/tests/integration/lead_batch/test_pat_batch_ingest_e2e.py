"""Story 42.1 — PAT-scoped REST batch ingest (API-level e2e).

Exercises the REAL auth path end-to-end: ``Authorization: Bearer nw_pat_…``
→ ``resolve_pat`` → ``AuthContext.pat_auth`` → ``RequirePermission``
(membership + ``api_access_enabled`` gate) → ``RequirePatScope`` (workspace
binding + ``leads:write``) → service → PAT attribution ledger → 422 shape.

Rides on the Story 26.1 harness in this directory (``db_session``,
``db_user``, ``db_workspace``, ``lead_batch_payload``).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app, limiter
from app.db import (
    Lead,
    LeadActivityLog,
    PersonalAccessToken,
    User,
    Workspace,
    get_async_session,
)
from app.routes.workspaces_routes import create_default_roles_and_membership
from app.utils.pat import generate_pat, hash_pat

pytestmark = [pytest.mark.integration]

limiter.enabled = False


@pytest_asyncio.fixture
async def pat_workspace(
    db_session: AsyncSession, db_workspace: Workspace
) -> Workspace:
    """The Story 26.1 workspace with ``api_access_enabled`` turned on —
    required before any gated (PAT) principal passes ``check_permission``.
    """
    db_workspace.api_access_enabled = True
    await db_session.flush()
    return db_workspace


@pytest_asyncio.fixture
async def db_pat(
    db_session: AsyncSession, db_user: User, pat_workspace: Workspace
) -> tuple[PersonalAccessToken, str]:
    """A valid PAT bound to ``pat_workspace`` carrying ``leads:write``."""
    token = generate_pat()
    pat = PersonalAccessToken(
        user_id=db_user.id,
        token_hash=hash_pat(token),
        token_prefix=token[:12],
        label="story-42-1-e2e",
        workspace_id=pat_workspace.id,
        scopes=["leads:write"],
        token_kind="legacy",
    )
    db_session.add(pat)
    await db_session.flush()
    return pat, token


@pytest_asyncio.fixture
async def client_real_auth(
    db_session: AsyncSession,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """AsyncClient with the session store overridden but REAL
    ``get_auth_context`` — Bearer PATs resolve through ``resolve_pat``.
    """

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_async_session] = override_session

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


def _headers(token: str, **extra: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", **extra}


# ---------------------------------------------------------------------------
# PAT_OK: happy path — lead persisted + attribution ledger row
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pat_ingest_persists_lead_and_writes_ledger(
    client_real_auth, db_session, db_workspace, pat_workspace, db_pat,
    lead_batch_payload,
):
    pat, token = db_pat
    resp = await client_real_auth.post(
        f"/api/v1/workspaces/{pat_workspace.id}/leads/batch-ingest",
        headers=_headers(token, **{"Idempotency-Key": "e2e-idem-1"}),
        json=lead_batch_payload,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ingested_count"] == 1
    assert len(body["lead_ids"]) == 1

    logs = (
        (
            await db_session.execute(
                select(LeadActivityLog).where(
                    LeadActivityLog.workspace_id == pat_workspace.id,
                    LeadActivityLog.lead_id == uuid.UUID(body["lead_ids"][0]),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(logs) == 1
    row = logs[0]
    assert row.activity_type == "batch_ingested"
    assert row.details["actor_pat_token_id"] == pat.id
    assert row.details["pat_token_prefix"] == pat.token_prefix
    assert row.details["idempotency_key"] == "e2e-idem-1"
    assert row.details["source"] == "batch_ingest"


# ---------------------------------------------------------------------------
# PAT_NO_SCOPE / PAT_WRONG_WS / api_access gate: 403s, nothing persisted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pat_without_leads_write_scope_gets_403(
    client_real_auth, db_session, db_user, pat_workspace, lead_batch_payload
):
    token = generate_pat()
    db_session.add(
        PersonalAccessToken(
            user_id=db_user.id,
            token_hash=hash_pat(token),
            token_prefix=token[:12],
            label="no-scope",
            workspace_id=pat_workspace.id,
            scopes=[],  # legacy / empty scope set → fail-closed
            token_kind="legacy",
        )
    )
    await db_session.flush()

    resp = await client_real_auth.post(
        f"/api/v1/workspaces/{pat_workspace.id}/leads/batch-ingest",
        headers=_headers(token),
        json=lead_batch_payload,
    )
    assert resp.status_code == 403
    assert "leads:write" in resp.json()["detail"]

    count = (
        await db_session.execute(
            select(func.count(Lead.id)).where(Lead.workspace_id == pat_workspace.id)
        )
    ).scalar_one()
    assert count == 0


@pytest.mark.asyncio
async def test_pat_bound_to_other_workspace_gets_403(
    client_real_auth, db_session, db_user, db_workspace, pat_workspace,
    db_pat, lead_batch_payload,
):
    """PAT bound to workspace A may not ingest into workspace B.

    Workspace B needs membership + api_access_enabled=True so the request
    passes the permission gate and reaches the PAT scope seam — otherwise a
    403 surfaces for an earlier, unrelated reason.
    """
    other = Workspace(
        name="Other Space", user_id=db_user.id, api_access_enabled=True
    )
    db_session.add(other)
    await db_session.flush()
    await create_default_roles_and_membership(db_session, other.id, db_user.id)
    await db_session.flush()

    _, token = db_pat
    resp = await client_real_auth.post(
        f"/api/v1/workspaces/{other.id}/leads/batch-ingest",
        headers=_headers(token),
        json=lead_batch_payload,
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "workspace_id outside pat scope"


@pytest.mark.asyncio
async def test_pat_on_api_access_disabled_workspace_gets_403(
    client_real_auth, db_session, db_user, db_pat, lead_batch_payload
):
    """api_access_enabled=False → 403 at the permission gate, before scope."""
    disabled_ws = Workspace(name="No API Space", user_id=db_user.id)
    db_session.add(disabled_ws)
    await db_session.flush()
    await create_default_roles_and_membership(db_session, disabled_ws.id, db_user.id)
    await db_session.flush()

    # PAT bound TỚI disabled_ws — binding-first (AI-42.4) check pass rồi mới
    # tới api-access gate (dùng db_pat bound pat_workspace sẽ 403 binding).
    token = generate_pat()
    db_session.add(
        PersonalAccessToken(
            user_id=db_user.id,
            token_hash=hash_pat(token),
            token_prefix=token[:12],
            label="e2e-disabled-ws-pat",
            workspace_id=disabled_ws.id,
            scopes=["leads:write"],
            token_kind="legacy",
        )
    )
    await db_session.flush()

    resp = await client_real_auth.post(
        f"/api/v1/workspaces/{disabled_ws.id}/leads/batch-ingest",
        headers=_headers(token),
        json=lead_batch_payload,
    )
    assert resp.status_code == 403
    assert "API access" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# DEGENERATE_BATCH: structured 422 reject-all
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_degenerate_batch_returns_structured_422_and_rolls_back(
    client_real_auth, db_session, pat_workspace, db_pat, lead_batch_payload
):
    _, token = db_pat
    payload = {
        "leads": [
            lead_batch_payload["leads"][0],
            {"company_name": ""},  # degenerate: all contact fields empty
            {"domain": ""},
        ]
    }
    resp = await client_real_auth.post(
        f"/api/v1/workspaces/{pat_workspace.id}/leads/batch-ingest",
        headers=_headers(token),
        json=payload,
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["status"] == "failed"
    assert body["rejected_indexes"] == [1, 2]
    assert set(body["reason_map"].keys()) == {"1", "2"}

    count = (
        await db_session.execute(
            select(func.count(Lead.id)).where(Lead.workspace_id == pat_workspace.id)
        )
    ).scalar_one()
    assert count == 0  # reject-all: nothing persisted


# ---------------------------------------------------------------------------
# REPUSH_IDEMPOTENT: dedupe holds; ledger records every call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pat_repush_idempotent_dedup_and_ledger_per_call(
    client_real_auth, db_session, pat_workspace, db_pat, lead_batch_payload
):
    _, token = db_pat
    for _ in range(2):
        resp = await client_real_auth.post(
            f"/api/v1/workspaces/{pat_workspace.id}/leads/batch-ingest",
            headers=_headers(token, **{"Idempotency-Key": "e2e-idem-2"}),
            json=lead_batch_payload,
        )
        assert resp.status_code == 200

    leads = (
        await db_session.execute(
            select(func.count(Lead.id)).where(Lead.workspace_id == pat_workspace.id)
        )
    ).scalar_one()
    assert leads == 1  # uq_leads_workspace_value_hmac dedupe

    logs = (
        await db_session.execute(
            select(func.count(LeadActivityLog.id)).where(
                LeadActivityLog.workspace_id == pat_workspace.id
            )
        )
    ).scalar_one()
    assert logs == 2  # attribution ledger records one row per call (by design)
