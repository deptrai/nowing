"""Story 42.7 — service-level auto-table (API-level e2e).

Qua route thật ``POST /workspaces/{id}/leads/batch-ingest`` + PAT thật +
session Postgres thật: mọi lead ingest đều được link vào ``WorkspaceTable``
get-or-create theo ``key = client_id`` (UNIQUE(workspace_id, key),
ON CONFLICT DO NOTHING + re-select — race-safe). Deleted table →
``table_id`` dangling → recreate + relink vào bảng mới.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.lead_batch_service import LeadBatchService

from app.app import app, limiter
from app.db import (
    Lead,
    PersonalAccessToken,
    User,
    Workspace,
    WorkspaceTable,
    get_async_session,
)
from app.utils.pat import generate_pat, hash_pat

pytestmark = [pytest.mark.integration]

limiter.enabled = False


@pytest_asyncio.fixture
async def pat_workspace(
    db_session: AsyncSession, db_workspace: Workspace
) -> Workspace:
    db_workspace.api_access_enabled = True
    await db_session.flush()
    return db_workspace


@pytest_asyncio.fixture
async def db_pat(
    db_session: AsyncSession, db_user: User, pat_workspace: Workspace
) -> tuple[PersonalAccessToken, str]:
    token = generate_pat()
    pat = PersonalAccessToken(
        user_id=db_user.id,
        token_hash=hash_pat(token),
        token_prefix=token[:12],
        label="story-42-7-e2e",
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


async def _post_leads(
    client: httpx.AsyncClient,
    workspace_id: int,
    token: str,
    leads: list[dict],
) -> httpx.Response:
    return await client.post(
        f"/api/v1/workspaces/{workspace_id}/leads/batch-ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={"leads": leads},
    )


def _tables_query(workspace_id: int):
    return select(WorkspaceTable).where(WorkspaceTable.workspace_id == workspace_id)


async def test_ingest_auto_creates_default_table_and_links(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_pat: tuple[PersonalAccessToken, str],
    client_real_auth: httpx.AsyncClient,
):
    """Batch đầu tiên: auto-create WorkspaceTable(key=client_id, name='Leads')
    và lead.table_id trỏ tới bảng đó."""
    _pat, token = db_pat
    resp = await _post_leads(
        client_real_auth,
        db_workspace.id,
        token,
        [{"company_name": "Acme", "email": "a@acme.io", "client_id": "acme"}],
    )
    assert resp.status_code == 200, resp.text

    tables = (await db_session.execute(_tables_query(db_workspace.id))).scalars().all()
    assert len(tables) == 1
    table = tables[0]
    assert table.key == "acme"
    assert table.name == "acme"  # auto-table đặt tên theo client_id

    lead_ids = resp.json()["lead_ids"]
    lead = (
        await db_session.execute(select(Lead).where(Lead.id.in_(lead_ids)))
    ).scalar_one()
    assert lead.table_id == table.id


async def test_repeated_ingest_same_client_reuses_table(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_pat: tuple[PersonalAccessToken, str],
    client_real_auth: httpx.AsyncClient,
):
    """Hai batch cùng client_id → đúng 1 WorkspaceTable (get-or-create)."""
    _pat, token = db_pat
    for i in range(2):
        resp = await _post_leads(
            client_real_auth,
            db_workspace.id,
            token,
            [{"company_name": f"Acme{i}", "email": f"a{i}@acme.io", "client_id": "acme"}],
        )
        assert resp.status_code == 200, resp.text

    count = (
        await db_session.execute(
            select(func.count()).select_from(
                _tables_query(db_workspace.id).subquery()
            )
        )
    ).scalar_one()
    assert count == 1


async def test_deleted_table_recreated_and_relinked(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_pat: tuple[PersonalAccessToken, str],
    client_real_auth: httpx.AsyncClient,
):
    """Xóa table → lead.table_id dangling/NULL → ingest lại tạo bảng MỚI
    (không reuse id đã xóa) và relink lead mới."""
    _pat, token = db_pat
    resp = await _post_leads(
        client_real_auth,
        db_workspace.id,
        token,
        [{"company_name": "Acme", "email": "a@acme.io", "client_id": "acme"}],
    )
    assert resp.status_code == 200, resp.text
    old_table = (
        await db_session.execute(_tables_query(db_workspace.id))
    ).scalar_one()
    old_id = old_table.id

    await db_session.delete(old_table)
    await db_session.flush()

    resp = await _post_leads(
        client_real_auth,
        db_workspace.id,
        token,
        [{"company_name": "Beta", "email": "b@beta.io", "client_id": "acme"}],
    )
    assert resp.status_code == 200, resp.text

    tables = (await db_session.execute(_tables_query(db_workspace.id))).scalars().all()
    assert len(tables) == 1
    assert tables[0].id != old_id
    assert tables[0].key == "acme"

    lead_ids = resp.json()["lead_ids"]
    lead = (
        await db_session.execute(select(Lead).where(Lead.id.in_(lead_ids)))
    ).scalar_one()
    assert lead.table_id == tables[0].id


async def test_explicit_table_id_still_honored(
    db_session: AsyncSession,
    db_workspace: Workspace,
):
    """table_id explicit (UUID hợp lệ, cùng workspace) → giữ nguyên,
    không bị override sang auto-table.

    REST ``LeadItem`` không expose ``table_id`` — field này đi qua funnel
    ``save_leads`` (agent tool) → service-level test đúng tầng."""
    manual = WorkspaceTable(
        workspace_id=db_workspace.id,
        name="Manual",
        key=None,
    )
    db_session.add(manual)
    await db_session.flush()

    svc = LeadBatchService()
    result = await svc.ingest_batch(
        db_session,
        db_workspace.id,
        [
            {
                "company_name": "Acme",
                "email": "a@acme.io",
                "table_id": str(manual.id),
            }
        ],
    )
    lead_ids = result["lead_ids"]
    lead = (
        await db_session.execute(select(Lead).where(Lead.id.in_(lead_ids)))
    ).scalar_one()
    assert lead.table_id == manual.id
