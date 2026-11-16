"""Story 42.3 — GET /workspaces/{id}/scrapers/health (API-level e2e).

Khác với unit suite (fake session chỉ sniff SQL text): suite này chạy
app thật + session Postgres thật + auth PAT thật — cả 2 aggregate query
(24h window GROUP BY + latest all-time DISTINCT ON) execute trên DB thật,
RLS GUC ``app.workspace_id`` được set thật bởi endpoint.

Rides on the shared integration harness (``db_session``, ``db_user``,
``db_workspace``) — same pattern as ``test_pat_batch_ingest_e2e.py``.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app, limiter
from app.db import (
    PersonalAccessToken,
    User,
    Workspace,
    get_async_session,
)
from app.models.scraper import Run
from app.utils.pat import generate_pat, hash_pat

pytestmark = [pytest.mark.integration]

limiter.enabled = False

_CAP = "e2e.testcap"


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
    """PAT bound tới workspace — health endpoint chỉ cần membership
    (``check_workspace_access``), không cần scope cụ thể."""
    token = generate_pat()
    pat = PersonalAccessToken(
        user_id=db_user.id,
        token_hash=hash_pat(token),
        token_prefix=token[:12],
        label="story-42-3-e2e",
        workspace_id=pat_workspace.id,
        scopes=[],
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


def _run(
    workspace_id: int,
    status: str,
    *,
    capability: str = _CAP,
    created_at: datetime | None = None,
    error: str | None = None,
) -> Run:
    run = Run(
        workspace_id=workspace_id,
        capability=capability,
        origin="agent",
        status=status,
        error=error,
        input={},
        output_text=None,
        item_count=0,
        char_count=0,
        external_metadata={},
    )
    if created_at is not None:
        run.created_at = created_at
    return run


def _channel(data: dict, name: str) -> dict | None:
    return next((c for c in data["channels"] if c["channel"] == name), None)


async def test_health_real_db_aggregates_24h_window(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_pat: tuple[PersonalAccessToken, str],
    client_real_auth: httpx.AsyncClient,
):
    """3 success + 1 error trong 24h → rate 0.75, envelope degraded.

    ``e2e.testcap`` không nằm trong registry → xuất hiện ở phần
    observed-legacy; registry channels vẫn ``unknown`` (rate null).
    """
    _pat, token = db_pat
    now = datetime.now(UTC)
    for i in range(3):
        db_session.add(
            _run(db_workspace.id, "success", created_at=now - timedelta(hours=i + 1))
        )
    db_session.add(
        _run(
            db_workspace.id,
            "error",
            created_at=now - timedelta(minutes=30),
            error="boom",
        )
    )
    # Run cũ hơn 24h — chỉ ảnh hưởng last_status/last_seen_at, không vào rate.
    old = now - timedelta(hours=30)
    db_session.add(
        _run(db_workspace.id, "success", capability="e2e.oldcap", created_at=old)
    )
    await db_session.flush()

    resp = await client_real_auth.get(
        f"/api/v1/workspaces/{db_workspace.id}/scrapers/health",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] in ("degraded", "down")
    assert data["checked_at"].endswith("Z")

    cap = _channel(data, _CAP)
    assert cap is not None
    assert cap["success_rate_24h"] == pytest.approx(0.75)
    assert cap["attempts_24h"] == 4
    assert cap["last_status"] == "error"
    assert cap["last_error"] == "boom"


async def test_health_down_when_recent_runs_all_fail(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_pat: tuple[PersonalAccessToken, str],
    client_real_auth: httpx.AsyncClient,
):
    _pat, token = db_pat
    for _ in range(2):
        db_session.add(_run(db_workspace.id, "error"))
    await db_session.flush()

    resp = await client_real_auth.get(
        f"/api/v1/workspaces/{db_workspace.id}/scrapers/health",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "down"


async def test_health_does_not_leak_other_workspace(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
    db_pat: tuple[PersonalAccessToken, str],
    client_real_auth: httpx.AsyncClient,
):
    """Run của workspace khác không lọt vào response (workspace filter + RLS)."""
    from app.routes.workspaces_routes import create_default_roles_and_membership

    other = Workspace(name="other-ws-e2e", user_id=db_user.id)
    db_session.add(other)
    await db_session.flush()
    await create_default_roles_and_membership(db_session, other.id, db_user.id)
    db_session.add(_run(other.id, "error", capability="e2e.othercap"))
    await db_session.flush()

    _pat, token = db_pat
    resp = await client_real_auth.get(
        f"/api/v1/workspaces/{db_workspace.id}/scrapers/health",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    assert _channel(resp.json(), "e2e.othercap") is None


async def test_health_non_member_gets_403(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
    client_real_auth: httpx.AsyncClient,
):
    """PAT của user KHÔNG phải member workspace → 403."""
    from app.routes.workspaces_routes import create_default_roles_and_membership

    stranger = User(
        email=f"stranger-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(stranger)
    await db_session.flush()
    token = generate_pat()
    pat = PersonalAccessToken(
        user_id=stranger.id,
        token_hash=hash_pat(token),
        token_prefix=token[:12],
        label="non-member",
        workspace_id=db_workspace.id,
        scopes=[],
        token_kind="legacy",
    )
    db_session.add(pat)
    await db_session.flush()

    resp = await client_real_auth.get(
        f"/api/v1/workspaces/{db_workspace.id}/scrapers/health",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
