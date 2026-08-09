"""Red-phase unit tests for the public agent-chat PAT scope dependency.

Story 18.1 — Public Agent-Chat Endpoints.
These tests drive the contract for ``app.auth.agent_chat.require_agent_chat_pat``.
They will fail (red) until ``app/auth/agent_chat.py`` is implemented.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext

pytestmark = pytest.mark.unit

# Sentinel used by _patch_seams when it should not monkeypatch get_user_membership.
_UNSET = object()


def _pat_dep():
    """Import the dependency under test; fails red until it exists."""
    from app.auth.agent_chat import require_agent_chat_pat

    return require_agent_chat_pat


def _make_request(
    workspace_id: int,
    *,
    suffix: str = "/threads",
    token: str = "nw_pat_testtoken",
) -> Request:
    return Request(
        {
            "type": "http",
            "scheme": "http",
            "method": "POST",
            "path": f"/api/v1/workspaces/{workspace_id}/agent-chat{suffix}",
            "path_params": {"workspace_id": workspace_id},
            "query_string": b"",
            "headers": [(b"authorization", f"Bearer {token}".encode())],
            "server": ("test", 80),
        }
    )


def _make_auth(
    *,
    workspace_id: int = 42,
    client_id: str | None = "bdsai.vn",
    agent_id: str | None = "bdsai-listing-assistant",
    scopes: list[str] | None = None,
    token_kind: str = "agent_chat",
) -> AuthContext:
    scopes = scopes or ["agent_chat:thread:create"]
    pat = SimpleNamespace(
        token_kind=token_kind,
        workspace_id=workspace_id,
        client_id=client_id,
        agent_id=agent_id,
        scopes=scopes,
    )
    user = SimpleNamespace(id=uuid4(), is_active=True)
    return AuthContext.pat_auth(user, pat)


def _make_body(
    *,
    client_id: str | None = "bdsai.vn",
    agent_id: str | None = "bdsai-listing-assistant",
) -> SimpleNamespace:
    return SimpleNamespace(client_id=client_id, agent_id=agent_id)


class _FakeResult:
    """Minimal stand-in for SQLAlchemy Result."""

    def __init__(self, item: object | None) -> None:
        self._item = item

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._item)


class _FakeScalars:
    def __init__(self, item: object | None) -> None:
        self._item = item

    def first(self) -> object | None:
        return self._item


class _FakeSession:
    """AsyncSession stand-in that returns canned rows per table name."""

    def __init__(
        self,
        *,
        membership: object | None = None,
        vertical_client: object | None = None,
        agent_config: object | None = None,
    ) -> None:
        self.membership = membership
        self.vertical_client = vertical_client
        self.agent_config = agent_config
        self.execute_calls: list[object] = []

    async def execute(self, stmt: object) -> _FakeResult:
        self.execute_calls.append(stmt)
        sql = str(stmt).lower()
        item = None
        if "workspace_memberships" in sql:
            item = self.membership
        elif "vertical_clients" in sql:
            item = self.vertical_client
        elif "agent_configs" in sql:
            item = self.agent_config
        return _FakeResult(item)


def _patch_seams(
    monkeypatch,
    *,
    auth: AuthContext | HTTPException | None = None,
    membership: object | None | object = _UNSET,
    feature_enabled: bool = True,
) -> SimpleNamespace:
    """Mock the external seams the dependency is expected to call."""
    guc_mock = AsyncMock()
    monkeypatch.setattr(
        "app.canonical.tenant_context.set_request_tenant_context",
        guc_mock,
        raising=False,
    )
    monkeypatch.setattr(
        "app.config.config.AGENT_CHAT_PUBLIC_ENABLED",
        feature_enabled,
        raising=False,
    )

    auth_mock = None
    if auth is not None:
        if isinstance(auth, HTTPException):
            auth_mock = AsyncMock(side_effect=auth)
        else:
            auth_mock = AsyncMock(return_value=auth)
        monkeypatch.setattr("app.users.get_auth_context", auth_mock)

    membership_mock = None
    if membership is not _UNSET:
        membership_mock = AsyncMock(return_value=membership)
        monkeypatch.setattr("app.utils.rbac.get_user_membership", membership_mock)

    return SimpleNamespace(
        set_request_tenant_context=guc_mock,
        get_auth_context=auth_mock,
        get_user_membership=membership_mock,
    )


async def test_valid_agent_chat_pat_succeeds(monkeypatch):
    """AC-3/AC-10: a fully-scoped agent_chat PAT yields the effective context."""
    auth = _make_auth()
    membership = SimpleNamespace(is_owner=False, is_active=True)
    seams = _patch_seams(monkeypatch, auth=auth, membership=membership)

    fake = _FakeSession(
        membership=membership,
        vertical_client=SimpleNamespace(client_id="bdsai.vn", is_active=True),
        agent_config=SimpleNamespace(
            name="bdsai-listing-assistant",
            client_id="bdsai.vn",
            is_active=True,
        ),
    )
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = fake.execute

    request = _make_request(42)
    body = _make_body()

    require_agent_chat_pat = _pat_dep()
    result = await require_agent_chat_pat(request, session, body)

    assert result.effective_client_id == "bdsai.vn"
    assert result.effective_agent_id == "bdsai-listing-assistant"
    seams.get_auth_context.assert_awaited_once_with(request, session)
    seams.set_request_tenant_context.assert_awaited_once_with(
        session, 42, "bdsai.vn", "bdsai-listing-assistant"
    )


async def test_invalid_or_expired_pat_returns_401(monkeypatch):
    """AC-3: resolve_pat failing or an expired token must fail closed with 401."""
    auth_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized",
    )
    _ = _patch_seams(monkeypatch, auth=auth_exc)
    session = AsyncMock(spec=AsyncSession)
    request = _make_request(42)
    body = _make_body()

    require_agent_chat_pat = _pat_dep()
    with pytest.raises(HTTPException) as exc_info:
        await require_agent_chat_pat(request, session, body)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Unauthorized"


async def test_legacy_pat_on_public_route_returns_403_pat_scope_required(
    monkeypatch,
):
    """AC-10: legacy unscoped PAT on /agent-chat/* must fail with pat_scope_required."""
    auth = _make_auth(
        token_kind="legacy",
        workspace_id=None,
        client_id=None,
        scopes=[],
    )
    seams = _patch_seams(monkeypatch, auth=auth, membership=_UNSET)
    session = AsyncMock(spec=AsyncSession)
    request = _make_request(42)
    body = _make_body(client_id=None, agent_id=None)

    require_agent_chat_pat = _pat_dep()
    with pytest.raises(HTTPException) as exc_info:
        await require_agent_chat_pat(request, session, body)

    assert exc_info.value.status_code == 403
    assert "pat_scope_required" in exc_info.value.detail
    if seams.get_user_membership is not None:
        seams.get_user_membership.assert_not_awaited()


async def test_workspace_id_mismatch_returns_403(monkeypatch):
    """AC-10: request workspace_id must equal pat.workspace_id exactly."""
    auth = _make_auth(workspace_id=42)
    membership = SimpleNamespace(is_active=True)
    seams = _patch_seams(monkeypatch, auth=auth, membership=membership)
    session = AsyncMock(spec=AsyncSession)
    request = _make_request(99)  # different from PAT workspace
    body = _make_body()

    require_agent_chat_pat = _pat_dep()
    with pytest.raises(HTTPException) as exc_info:
        await require_agent_chat_pat(request, session, body)

    assert exc_info.value.status_code == 403
    assert "workspace_id" in exc_info.value.detail.lower()
    seams.get_user_membership.assert_not_awaited()


async def test_revoked_membership_returns_403(monkeypatch):
    """AC-3: a revoked workspace membership must fail closed with 403."""
    auth = _make_auth()
    _ = _patch_seams(monkeypatch, auth=auth, membership=None)
    session = AsyncMock(spec=AsyncSession)
    request = _make_request(42)
    body = _make_body()

    require_agent_chat_pat = _pat_dep()
    with pytest.raises(HTTPException) as exc_info:
        await require_agent_chat_pat(request, session, body)

    assert exc_info.value.status_code == 403
    assert "workspace" in exc_info.value.detail.lower()


async def test_client_id_escalation_in_body_rejected(monkeypatch):
    """AC-6/AC-8/AC-10: body client_id may not widen beyond PAT scope."""
    auth = _make_auth(client_id="bdsai.vn")
    membership = SimpleNamespace(is_active=True)
    _ = _patch_seams(monkeypatch, auth=auth, membership=membership)
    session = AsyncMock(spec=AsyncSession)
    request = _make_request(42)
    body = _make_body(client_id="other.vn")  # escalation attempt

    require_agent_chat_pat = _pat_dep()
    with pytest.raises(HTTPException) as exc_info:
        await require_agent_chat_pat(request, session, body)

    assert exc_info.value.status_code in (400, 403)
    assert "client_id" in exc_info.value.detail.lower()


async def test_client_id_not_registered_for_workspace_returns_400(monkeypatch):
    """AC-6: client_id that is not in vertical_clients must fail with 400."""
    auth = _make_auth(client_id="bdsai.vn")
    membership = SimpleNamespace(is_active=True)
    _ = _patch_seams(monkeypatch, auth=auth, membership=membership)
    fake = _FakeSession(
        membership=membership,
        vertical_client=None,
        agent_config=SimpleNamespace(
            name="bdsai-listing-assistant",
            client_id="bdsai.vn",
            is_active=True,
        ),
    )
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = fake.execute
    request = _make_request(42)
    body = _make_body(client_id="bdsai.vn")

    require_agent_chat_pat = _pat_dep()
    with pytest.raises(HTTPException) as exc_info:
        await require_agent_chat_pat(request, session, body)

    assert exc_info.value.status_code == 400
    assert "client_id" in exc_info.value.detail.lower()


async def test_agent_id_missing_returns_404(monkeypatch):
    """AC-5: a non-existent agent_id must fail closed with 404."""
    auth = _make_auth(agent_id=None)
    membership = SimpleNamespace(is_active=True)
    _ = _patch_seams(monkeypatch, auth=auth, membership=membership)
    fake = _FakeSession(
        membership=membership,
        vertical_client=SimpleNamespace(client_id="bdsai.vn", is_active=True),
        agent_config=None,
    )
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = fake.execute
    request = _make_request(42)
    body = _make_body(agent_id="nonexistent")

    require_agent_chat_pat = _pat_dep()
    with pytest.raises(HTTPException) as exc_info:
        await require_agent_chat_pat(request, session, body)

    assert exc_info.value.status_code == 404
    assert "agent" in exc_info.value.detail.lower()


async def test_agent_id_inactive_returns_404(monkeypatch):
    """AC-5: an inactive agent must be treated as missing (404)."""
    auth = _make_auth(agent_id=None)
    membership = SimpleNamespace(is_active=True)
    _ = _patch_seams(monkeypatch, auth=auth, membership=membership)
    fake = _FakeSession(
        membership=membership,
        vertical_client=SimpleNamespace(client_id="bdsai.vn", is_active=True),
        agent_config=SimpleNamespace(
            name="bdsai-listing-assistant",
            client_id="bdsai.vn",
            is_active=False,
        ),
    )
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = fake.execute
    request = _make_request(42)
    body = _make_body(agent_id="bdsai-listing-assistant")

    require_agent_chat_pat = _pat_dep()
    with pytest.raises(HTTPException) as exc_info:
        await require_agent_chat_pat(request, session, body)

    assert exc_info.value.status_code == 404
    assert "agent" in exc_info.value.detail.lower()


async def test_agent_id_for_different_client_returns_403_or_404(monkeypatch):
    """AC-5: agent_id must belong to the effective client_id."""
    auth = _make_auth(client_id="bdsai.vn", agent_id=None)
    membership = SimpleNamespace(is_active=True)
    _ = _patch_seams(monkeypatch, auth=auth, membership=membership)
    fake = _FakeSession(
        membership=membership,
        vertical_client=SimpleNamespace(client_id="bdsai.vn", is_active=True),
        agent_config=SimpleNamespace(
            name="other-assistant",
            client_id="other.vn",
            is_active=True,
        ),
    )
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = fake.execute
    request = _make_request(42)
    body = _make_body(agent_id="other-assistant")

    require_agent_chat_pat = _pat_dep()
    with pytest.raises(HTTPException) as exc_info:
        await require_agent_chat_pat(request, session, body)

    assert exc_info.value.status_code in (403, 404)


async def test_agent_id_omitted_binds_to_pat_agent_id(monkeypatch):
    """AC-5/AC-10: when request omits agent_id, the effective agent is pat.agent_id."""
    auth = _make_auth(client_id="bdsai.vn", agent_id="bdsai-listing-assistant")
    membership = SimpleNamespace(is_active=True)
    _ = _patch_seams(monkeypatch, auth=auth, membership=membership)
    fake = _FakeSession(
        membership=membership,
        vertical_client=SimpleNamespace(client_id="bdsai.vn", is_active=True),
        agent_config=SimpleNamespace(
            name="bdsai-listing-assistant",
            client_id="bdsai.vn",
            is_active=True,
        ),
    )
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = fake.execute
    request = _make_request(42)
    body = _make_body(agent_id=None)

    require_agent_chat_pat = _pat_dep()
    result = await require_agent_chat_pat(request, session, body)

    assert result.effective_agent_id == "bdsai-listing-assistant"
    assert result.effective_client_id == "bdsai.vn"


async def test_permission_missing_from_pat_scopes_returns_403(monkeypatch):
    """AC-10: the PAT scopes list must contain the required route permission."""
    auth = _make_auth(scopes=["agent_chat:thread:read"])  # missing create
    membership = SimpleNamespace(is_active=True)
    _ = _patch_seams(monkeypatch, auth=auth, membership=membership)
    session = AsyncMock(spec=AsyncSession)
    request = _make_request(42, suffix="/threads")
    body = _make_body()

    require_agent_chat_pat = _pat_dep()
    with pytest.raises(HTTPException) as exc_info:
        await require_agent_chat_pat(request, session, body)

    assert exc_info.value.status_code == 403
    assert "permission" in exc_info.value.detail.lower()


async def test_gucs_set_before_any_business_query(monkeypatch):
    """AC-8: tenant context GUCs are set before the dependency returns."""
    auth = _make_auth()
    membership = SimpleNamespace(is_active=True)
    seams = _patch_seams(monkeypatch, auth=auth, membership=membership)
    fake = _FakeSession(
        membership=membership,
        vertical_client=SimpleNamespace(client_id="bdsai.vn", is_active=True),
        agent_config=SimpleNamespace(
            name="bdsai-listing-assistant",
            client_id="bdsai.vn",
            is_active=True,
        ),
    )
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = fake.execute
    request = _make_request(42)
    body = _make_body()

    require_agent_chat_pat = _pat_dep()
    result = await require_agent_chat_pat(request, session, body)

    assert result.effective_client_id == "bdsai.vn"
    # The dependency must set the tenant GUC before it returns; the handler
    # then runs business queries under the already-established context.
    seams.set_request_tenant_context.assert_awaited_once()
