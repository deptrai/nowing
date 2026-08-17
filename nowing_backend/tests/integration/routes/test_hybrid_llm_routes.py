"""Integration tests for Hybrid LLM REST routes (Story 26.3 / AD-103).

Requires Postgres + Redis.
All tests are ATDD red-phase scaffolds and are skipped until implementation.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app
from app.auth.context import AuthContext
from app.db import PersonalAccessToken, User, Workspace, get_async_session
from app.users import get_auth_context

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skip(
        reason="ATDD red phase — Story 26.3 Hybrid LLM routes not yet implemented"
    ),
]


@pytest_asyncio.fixture
async def pat_workspace_client(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """PAT-authenticated client scoped to db_workspace."""
    pat = PersonalAccessToken(
        user_id=db_user.id,
        user=db_user,
        token_hash="0" * 64,
        token_prefix="nw_pat_test",
        label="Test PAT",
        workspace_id=db_workspace.id,
    )
    auth = AuthContext.pat_auth(db_user, pat)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_auth() -> AuthContext:
        return auth

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


@pytest.fixture
def dsh_worker_secret(monkeypatch) -> str:
    """Predictable sidecar secret for worker route tests."""
    from app.config import config

    monkeypatch.setattr(config, "DSH_WORKER_SECRET", "test-dsh-secret")
    return "test-dsh-secret"


def _hybrid_request() -> dict[str, Any]:
    return {
        "task_type": "fast_extraction",
        "sensitivity": "public",
        "messages": [{"role": "user", "content": "extract company name"}],
        "response_model": {
            "type": "object",
            "properties": {"company_name": {"type": "string"}},
            "required": ["company_name"],
        },
    }


class TestHybridLLMPublicRoute:
    """POST /api/v1/workspaces/{workspace_id}/hybrid-llm/invoke"""

    async def test_invoke_returns_200_when_authenticated_and_authorized(
        self, client_as_regular_user, db_workspace
    ) -> None:
        resp = await client_as_regular_user.post(
            f"/api/v1/workspaces/{db_workspace.id}/hybrid-llm/invoke",
            json=_hybrid_request(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "content" in body
        assert "tier" in body

    async def test_invoke_rejects_missing_permission(
        self, client_as_regular_user, db_workspace, monkeypatch
    ) -> None:
        with patch(
            "app.routes.hybrid_llm_routes.check_permission",
            new=AsyncMock(side_effect=Exception("forbidden")),
        ):
            resp = await client_as_regular_user.post(
                f"/api/v1/workspaces/{db_workspace.id}/hybrid-llm/invoke",
                json=_hybrid_request(),
            )
        assert resp.status_code == 403

    async def test_invoke_rejects_invalid_request_body(
        self, client_as_regular_user, db_workspace
    ) -> None:
        bad = _hybrid_request()
        del bad["task_type"]
        resp = await client_as_regular_user.post(
            f"/api/v1/workspaces/{db_workspace.id}/hybrid-llm/invoke",
            json=bad,
        )
        assert resp.status_code == 422

    async def test_invoke_records_token_usage_for_workspace_owner(
        self, client_as_regular_user, db_workspace, db_session
    ) -> None:
        resp = await client_as_regular_user.post(
            f"/api/v1/workspaces/{db_workspace.id}/hybrid-llm/invoke",
            json=_hybrid_request(),
        )
        assert resp.status_code == 200

        from app.db import TokenUsage

        usage = (
            await db_session.execute(
                select(TokenUsage).where(TokenUsage.workspace_id == db_workspace.id)
            )
        ).scalar_one_or_none()
        assert usage is not None
        assert usage.user_id == db_workspace.user_id


class TestHybridLLMInternalRoute:
    """POST /v1/hybrid-llm/invoke (DSH worker only)."""

    async def test_internal_invoke_requires_dsh_secret(
        self, pat_workspace_client, db_workspace
    ) -> None:
        resp = await pat_workspace_client.post(
            "/v1/hybrid-llm/invoke",
            json={"workspace_id": db_workspace.id, **_hybrid_request()},
        )
        assert resp.status_code == 403

    async def test_internal_invoke_rejects_global_pat(
        self, client_as_regular_user, db_workspace, dsh_worker_secret
    ) -> None:
        resp = await client_as_regular_user.post(
            "/v1/hybrid-llm/invoke",
            json={"workspace_id": db_workspace.id, **_hybrid_request()},
            headers={"X-Dsh-Worker-Secret": dsh_worker_secret},
        )
        assert resp.status_code == 403

    async def test_internal_invoke_accepts_workspace_pat_and_secret(
        self, pat_workspace_client, db_workspace, dsh_worker_secret
    ) -> None:
        resp = await pat_workspace_client.post(
            "/v1/hybrid-llm/invoke",
            json={"workspace_id": db_workspace.id, **_hybrid_request()},
            headers={"X-Dsh-Worker-Secret": dsh_worker_secret},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "content" in body
        assert body.get("tier") is not None

    async def test_internal_invoke_rejects_workspace_mismatch(
        self, pat_workspace_client, db_session, db_user, db_workspace
    ) -> None:
        # Create a second workspace and PAT scoped to it.
        other = Workspace(name="Other Space", user_id=db_user.id)
        db_session.add(other)
        await db_session.flush()

        other_pat = PersonalAccessToken(
            user_id=db_user.id,
            user=db_user,
            token_hash="1" * 64,
            token_prefix="nw_pat_test",
            label="Other PAT",
            workspace_id=other.id,
        )

        async def override_auth() -> AuthContext:
            return AuthContext.pat_auth(db_user, other_pat)

        app.dependency_overrides[get_auth_context] = override_auth

        resp = await pat_workspace_client.post(
            "/v1/hybrid-llm/invoke",
            json={"workspace_id": db_workspace.id, **_hybrid_request()},
            headers={"X-Dsh-Worker-Secret": "test-dsh-secret"},
        )
        assert resp.status_code == 403
