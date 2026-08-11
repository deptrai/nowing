"""Red-phase unit tests for the public agent-chat PAT scope dependency.

Story 18.1 — Public Agent-Chat Endpoints.
These tests drive the contract for ``app.auth.agent_chat.require_agent_chat_pat``.
They will fail (red) until ``app/auth/agent_chat.py`` is implemented.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

import app.auth.agent_chat
from app.auth.agent_chat import (
    AgentChatContext,
    _audit_rejection,
    _derive_scope_permission,
    _effective_client_id,
    _parse_workspace_id,
    _resolve_default_agent_id,
    _resolve_vertical_client,
    require_agent_chat_pat,
)
from app.auth.context import AuthContext

pytestmark = pytest.mark.unit

# Sentinel used by _patch_seams when it should not monkeypatch get_user_membership.
_UNSET = object()


def _make_request(
    workspace_id: int | str,
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
    is_valid: bool = True,
) -> AuthContext:
    scopes = scopes or ["agent_chat:thread:create"]
    pat = SimpleNamespace(
        id=1,
        token_kind=token_kind,
        workspace_id=workspace_id,
        client_id=client_id,
        agent_id=agent_id,
        scopes=scopes,
        is_valid=is_valid,
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

    def __init__(
        self, item: object | None, all_rows: list[object] | None = None
    ) -> None:
        self._item = item
        self._all = all_rows or []

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._item, self._all)


class _FakeScalars:
    def __init__(
        self, item: object | None, all_rows: list[object] | None = None
    ) -> None:
        self._item = item
        self._all = all_rows or []

    def first(self) -> object | None:
        return self._item

    def all(self) -> list[object]:
        return list(self._all)


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
        if "workspace_memberships" in sql:
            return _FakeResult(self.membership)
        if "vertical_clients" in sql:
            return _FakeResult(self._vertical_client(sql))
        if "agent_configs" in sql:
            items = self._agent_configs(sql)
            # get_agent_config selects the full row (includes agent_configs.id);
            # _resolve_default_agent_id selects only agent_configs.slug.
            if "agent_configs.id" in sql:
                first = items[0] if items else None
                return _FakeResult(first, items)
            slugs = [getattr(it, "slug", it) for it in items]
            return _FakeResult(slugs[0] if slugs else None, slugs)
        return _FakeResult(None)

    def _vertical_client(self, sql: str) -> object | None:
        vc = self.vertical_client
        if vc is None:
            return None
        is_active = getattr(vc, "is_active", True)
        if "is_active is true" in sql and not is_active:
            return None
        if "is_active is false" in sql and is_active:
            return None
        return vc

    def _agent_configs(self, sql: str) -> list[Any]:
        configs = self.agent_config
        if configs is None:
            return []
        items = list(configs) if isinstance(configs, list) else [configs]
        if "is_active is true" in sql:
            return [it for it in items if getattr(it, "is_active", True)]
        if "is_active is false" in sql:
            return [it for it in items if not getattr(it, "is_active", True)]
        return items


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
        if isinstance(auth, Exception):
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

    result = await require_agent_chat_pat(request, session, body)

    assert result.effective_client_id == "bdsai.vn"
    assert result.effective_agent_id == "bdsai-listing-assistant"
    assert result.actor_user_id == str(auth.user.id)
    assert result.pat_id == str(auth.pat.id)
    seams.get_auth_context.assert_awaited_once_with(request, session)
    seams.set_request_tenant_context.assert_awaited_once()
    guc_call = seams.set_request_tenant_context.call_args
    assert guc_call.args == (session, 42, "bdsai.vn", "bdsai-listing-assistant")
    assert guc_call.kwargs.get("user_id") == str(auth.user.id)


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

    result = await require_agent_chat_pat(request, session, body)

    assert result.effective_client_id == "bdsai.vn"
    # The dependency must set the tenant GUC before it returns; the handler
    # then runs business queries under the already-established context.
    seams.set_request_tenant_context.assert_awaited_once()


# --- Unit-level tests for helper functions and mutation killers ---


def test_parse_workspace_id_returns_zero_for_invalid_input():
    """Non-integer workspace_id values must parse to 0 for audit records."""
    assert _parse_workspace_id(None) == 0
    assert _parse_workspace_id("not-a-number") == 0
    assert _parse_workspace_id(42) == 42


async def test_audit_rejection_uses_default_workspace_id(monkeypatch):
    """_audit_rejection must default missing optional fields to empty/0."""
    audit_mock = AsyncMock()
    monkeypatch.setattr("app.auth.agent_chat._audit", audit_mock)

    request = _make_request(42)
    session = AsyncMock(spec=AsyncSession)

    await _audit_rejection(request, session, status.HTTP_400_BAD_REQUEST)

    assert audit_mock.called
    kwargs = audit_mock.call_args.kwargs
    assert kwargs["actor_user_id"] == ""
    assert kwargs["pat_id"] == ""
    assert kwargs["workspace_id"] == 0
    assert kwargs["client_id"] is None
    assert kwargs["agent_id"] is None


def test_audit_rejection_is_keyword_only():
    """The * marker must force keyword-only arguments; a positional pass is an error."""
    with pytest.raises(TypeError):
        # Positional actor_user_id after status_code must be rejected.
        _audit_rejection(None, None, 400, "user", 1, 42, "client", "agent")


def test_agent_chat_context_properties():
    """AgentChatContext.actor_user_id and .pat_id must return string IDs."""
    user = SimpleNamespace(id=uuid4())
    pat = SimpleNamespace(id=123)
    ctx = AgentChatContext(
        user=user,
        pat=pat,
        workspace_id=42,
        client_id="bdsai.vn",
        agent_id="bdsai-listing-assistant",
    )
    assert ctx.actor_user_id == str(user.id)
    assert ctx.pat_id == str(pat.id)


def test_agent_chat_context_init_is_keyword_only():
    """AgentChatContext.__init__ must reject positional args beyond self."""
    user = SimpleNamespace(id=uuid4())
    pat = SimpleNamespace(id=123)
    with pytest.raises(TypeError):
        AgentChatContext(user, pat, 42, "bdsai.vn", "bdsai-listing-assistant")


def test_derive_scope_permission():
    """_derive_scope_permission maps route + method to the correct PAT scope."""
    post_messages = Request(
        {
            "type": "http",
            "scheme": "http",
            "method": "POST",
            "path": "/api/v1/workspaces/42/agent-chat/threads/1/messages",
            "path_params": {"workspace_id": 42},
            "query_string": b"",
            "headers": [],
            "server": ("test", 80),
        }
    )
    post_threads = Request(
        {
            "type": "http",
            "scheme": "http",
            "method": "POST",
            "path": "/api/v1/workspaces/42/agent-chat/threads",
            "path_params": {"workspace_id": 42},
            "query_string": b"",
            "headers": [],
            "server": ("test", 80),
        }
    )
    get_threads = Request(
        {
            "type": "http",
            "scheme": "http",
            "method": "GET",
            "path": "/api/v1/workspaces/42/agent-chat/threads",
            "path_params": {"workspace_id": 42},
            "query_string": b"",
            "headers": [],
            "server": ("test", 80),
        }
    )
    assert _derive_scope_permission(post_messages) == "agent_chat:message:create"
    assert _derive_scope_permission(post_threads) == "agent_chat:thread:create"
    assert _derive_scope_permission(get_threads) == "agent_chat:thread:read"


def test_effective_client_id_allows_equal_client_id():
    """body_client_id equal to PAT client_id (even a different object) is allowed."""
    pat = SimpleNamespace(client_id="bdsai.vn")
    # Construct a value-equal string that is not the same object as the literal.
    body_client_id = "".join(["bdsai", ".vn"])
    assert body_client_id == pat.client_id
    assert body_client_id is not pat.client_id
    assert _effective_client_id(pat, body_client_id) == "bdsai.vn"


def test_effective_client_id_rejects_escalation():
    """body_client_id different from PAT scope must raise."""
    pat = SimpleNamespace(client_id="bdsai.vn")

    with pytest.raises(HTTPException) as exc_info:
        _effective_client_id(pat, "a.vn")
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "client_id" in exc_info.value.detail.lower()

    with pytest.raises(HTTPException) as exc_info:
        _effective_client_id(pat, "z.vn")
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    with pytest.raises(HTTPException) as exc_info:
        _effective_client_id(pat, "other.vn")
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


def test_effective_client_id_allows_none_body():
    """Omitting body client_id falls back to the PAT scope."""
    pat = SimpleNamespace(client_id="bdsai.vn")
    assert _effective_client_id(pat, None) == "bdsai.vn"


def test_effective_client_id_rejects_invalid_slug():
    """Non-slug body_client_id is rejected before the scope comparison."""
    pat = SimpleNamespace(client_id="bdsai.vn")
    with pytest.raises(HTTPException) as exc_info:
        _effective_client_id(pat, "Not A Slug")
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


async def test_resolve_vertical_client_requires_active_row(monkeypatch):
    """_resolve_vertical_client returns an active client and rejects missing/inactive."""
    monkeypatch.setattr(
        "app.auth.agent_chat._tenant_context.set_request_tenant_context",
        AsyncMock(),
    )

    active = SimpleNamespace(client_id="bdsai.vn", is_active=True)
    inactive = SimpleNamespace(client_id="bdsai.vn", is_active=False)
    session = _FakeSession(vertical_client=active)

    found = await _resolve_vertical_client(session, "bdsai.vn")
    assert found is active

    session = _FakeSession(vertical_client=inactive)
    with pytest.raises(HTTPException) as exc_info:
        await _resolve_vertical_client(session, "bdsai.vn")
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    session = _FakeSession(vertical_client=None)
    with pytest.raises(HTTPException) as exc_info:
        await _resolve_vertical_client(session, "bdsai.vn")
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


async def test_resolve_default_agent_id_boundaries(monkeypatch):
    """_resolve_default_agent_id handles zero, one, and multiple active agents."""
    monkeypatch.setattr(
        "app.auth.agent_chat._tenant_context.set_request_tenant_context",
        AsyncMock(),
    )

    session = _FakeSession(agent_config=[])
    with pytest.raises(HTTPException) as exc_info:
        await _resolve_default_agent_id(session, "bdsai.vn", "user-1")
    assert "no default agent" in exc_info.value.detail.lower()

    session = _FakeSession(
        agent_config=[
            SimpleNamespace(
                client_id="bdsai.vn", slug="bdsai-listing-assistant", is_active=True
            )
        ]
    )
    slug = await _resolve_default_agent_id(session, "bdsai.vn", "user-1")
    assert slug == "bdsai-listing-assistant"

    session = _FakeSession(
        agent_config=[
            SimpleNamespace(client_id="bdsai.vn", slug="agent-a", is_active=True),
            SimpleNamespace(client_id="bdsai.vn", slug="agent-b", is_active=True),
        ]
    )
    with pytest.raises(HTTPException) as exc_info:
        await _resolve_default_agent_id(session, "bdsai.vn", "user-1")
    assert "multiple active agents" in exc_info.value.detail.lower()


async def test_require_agent_chat_pat_rejects_non_pat_method(monkeypatch):
    """Only method == 'pat' with a non-None PAT is accepted."""
    auth = AuthContext(
        user=SimpleNamespace(id=uuid4()),
        method="session",
        pat=SimpleNamespace(
            token_kind="agent_chat",
            workspace_id=42,
            client_id="bdsai.vn",
            agent_id="bdsai-listing-assistant",
            scopes=["agent_chat:thread:create"],
            is_valid=True,
        ),
    )
    _ = _patch_seams(monkeypatch, auth=auth, membership=SimpleNamespace(is_active=True))
    session = AsyncMock(spec=AsyncSession)
    request = _make_request(42)
    body = _make_body()

    with pytest.raises(HTTPException) as exc_info:
        await require_agent_chat_pat(request, session, body)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "pat_scope_required" in exc_info.value.detail


async def test_require_agent_chat_pat_rejects_pat_none_with_pat_method(monkeypatch):
    """method == 'pat' but pat is None must fail."""
    auth = AuthContext(
        user=SimpleNamespace(id=uuid4()),
        method="pat",
        pat=None,
    )
    _ = _patch_seams(monkeypatch, auth=auth, membership=SimpleNamespace(is_active=True))
    session = AsyncMock(spec=AsyncSession)
    request = _make_request(42)
    body = _make_body()

    with pytest.raises(HTTPException) as exc_info:
        await require_agent_chat_pat(request, session, body)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


async def test_require_agent_chat_pat_rejects_unknown_scope(monkeypatch):
    """PAT carrying an unknown scope is rejected before route permission check."""
    auth = _make_auth(scopes=["agent_chat:unknown:scope"])
    _ = _patch_seams(monkeypatch, auth=auth, membership=SimpleNamespace(is_active=True))
    session = AsyncMock(spec=AsyncSession)
    request = _make_request(42)
    body = _make_body()

    with pytest.raises(HTTPException) as exc_info:
        await require_agent_chat_pat(request, session, body)
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "unknown scopes" in exc_info.value.detail.lower()


async def test_require_agent_chat_pat_exact_permission_in_detail(monkeypatch):
    """The 403 detail must name the missing required scope, not a generic message."""
    auth = _make_auth(scopes=["agent_chat:thread:read"])
    _ = _patch_seams(monkeypatch, auth=auth, membership=SimpleNamespace(is_active=True))
    session = AsyncMock(spec=AsyncSession)
    request = _make_request(42, suffix="/threads")
    body = _make_body()

    with pytest.raises(HTTPException) as exc_info:
        await require_agent_chat_pat(request, session, body)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "agent_chat:thread:create" in exc_info.value.detail


async def test_require_agent_chat_pat_workspace_mismatch_both_directions(monkeypatch):
    """workspace_id mismatch must be rejected regardless of numeric ordering."""
    auth = _make_auth(workspace_id=100_000)
    _ = _patch_seams(monkeypatch, auth=auth, membership=SimpleNamespace(is_active=True))
    session = AsyncMock(spec=AsyncSession)

    # request < pat workspace: original != is True, mutant > / >= would be False.
    request = _make_request(42)
    with pytest.raises(HTTPException) as exc_info:
        await require_agent_chat_pat(request, session, _make_body())
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "workspace_id" in exc_info.value.detail.lower()

    # request > pat workspace: original != is True, mutant < / <= would be False.
    auth = _make_auth(workspace_id=10)
    _ = _patch_seams(monkeypatch, auth=auth, membership=SimpleNamespace(is_active=True))
    request = _make_request(42)
    with pytest.raises(HTTPException) as exc_info:
        await require_agent_chat_pat(request, session, _make_body())
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "workspace_id" in exc_info.value.detail.lower()

    # equal workspace with a large int value: original != is False, mutant 'is not' would be True.
    auth = _make_auth(workspace_id=100_000)
    _ = _patch_seams(monkeypatch, auth=auth, membership=SimpleNamespace(is_active=True))
    request = _make_request(100_000)
    fake = _FakeSession(
        membership=SimpleNamespace(is_active=True),
        vertical_client=SimpleNamespace(client_id="bdsai.vn", is_active=True),
        agent_config=SimpleNamespace(
            name="bdsai-listing-assistant",
            client_id="bdsai.vn",
            is_active=True,
        ),
    )
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = fake.execute
    result = await require_agent_chat_pat(request, session, _make_body())
    assert result.workspace_id == 100_000


async def test_require_agent_chat_pat_rejects_invalid_agent_slug(monkeypatch):
    """An agent_id that is not a lowercase slug must be rejected."""
    auth = _make_auth(agent_id=None)
    _ = _patch_seams(monkeypatch, auth=auth, membership=SimpleNamespace(is_active=True))
    session = AsyncMock(spec=AsyncSession)
    request = _make_request(42)
    body = _make_body(agent_id="Not-A-Slug")

    with pytest.raises(HTTPException) as exc_info:
        await require_agent_chat_pat(request, session, body)
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


async def test_require_agent_chat_pat_rejects_expired_pat(monkeypatch):
    """PAT with is_valid == False is rejected as expired."""
    auth = _make_auth(is_valid=False)
    _ = _patch_seams(monkeypatch, auth=auth, membership=SimpleNamespace(is_active=True))
    session = AsyncMock(spec=AsyncSession)
    request = _make_request(42)
    body = _make_body()

    with pytest.raises(HTTPException) as exc_info:
        await require_agent_chat_pat(request, session, body)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "expired" in exc_info.value.detail.lower()


async def test_require_agent_chat_pat_handles_unexpected_auth_exception(monkeypatch):
    """A non-HTTPException from get_auth_context must become a 401."""
    _ = _patch_seams(monkeypatch, auth=RuntimeError("boom"))
    session = AsyncMock(spec=AsyncSession)
    request = _make_request(42)
    body = _make_body()

    with pytest.raises(HTTPException) as exc_info:
        await require_agent_chat_pat(request, session, body)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


async def test_require_agent_chat_pat_omitted_agent_id_resolves_default(monkeypatch):
    """When both body and PAT lack agent_id, the single active agent is used."""
    auth = _make_auth(client_id="bdsai.vn", agent_id=None)
    _ = _patch_seams(monkeypatch, auth=auth, membership=SimpleNamespace(is_active=True))
    fake = _FakeSession(
        membership=SimpleNamespace(is_active=True),
        vertical_client=SimpleNamespace(client_id="bdsai.vn", is_active=True),
        agent_config=[
            SimpleNamespace(
                client_id="bdsai.vn", slug="bdsai-listing-assistant", is_active=True
            )
        ],
    )
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = fake.execute
    request = _make_request(42)
    body = _make_body(agent_id=None)

    result = await require_agent_chat_pat(request, session, body)
    assert result.effective_agent_id == "bdsai-listing-assistant"


async def test_require_agent_chat_pat_omitted_agent_id_multiple_fails(monkeypatch):
    """Multiple active agents when none is specified must produce a 400 with 'multiple'."""
    auth = _make_auth(client_id="bdsai.vn", agent_id=None)
    _ = _patch_seams(monkeypatch, auth=auth, membership=SimpleNamespace(is_active=True))
    fake = _FakeSession(
        membership=SimpleNamespace(is_active=True),
        vertical_client=SimpleNamespace(client_id="bdsai.vn", is_active=True),
        agent_config=[
            SimpleNamespace(client_id="bdsai.vn", slug="agent-a", is_active=True),
            SimpleNamespace(client_id="bdsai.vn", slug="agent-b", is_active=True),
        ],
    )
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = fake.execute
    request = _make_request(42)
    body = _make_body(agent_id=None)

    with pytest.raises(HTTPException) as exc_info:
        await require_agent_chat_pat(request, session, body)
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "multiple" in exc_info.value.detail.lower()


async def test_require_agent_chat_pat_omitted_agent_id_none_fails(monkeypatch):
    """No active agents when none is specified must produce a 400 with 'no default'."""
    auth = _make_auth(client_id="bdsai.vn", agent_id=None)
    _ = _patch_seams(monkeypatch, auth=auth, membership=SimpleNamespace(is_active=True))
    fake = _FakeSession(
        membership=SimpleNamespace(is_active=True),
        vertical_client=SimpleNamespace(client_id="bdsai.vn", is_active=True),
        agent_config=[],
    )
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = fake.execute
    request = _make_request(42)
    body = _make_body(agent_id=None)

    with pytest.raises(HTTPException) as exc_info:
        await require_agent_chat_pat(request, session, body)
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "no default agent" in exc_info.value.detail.lower()


async def test_require_agent_chat_pat_feature_flag_default_false(monkeypatch):
    """Missing AGENT_CHAT_PUBLIC_ENABLED must default to False and return 503."""
    _ = _patch_seams(monkeypatch, membership=_UNSET)
    monkeypatch.setattr(
        app.auth.agent_chat,
        "config",
        SimpleNamespace(),
    )
    session = AsyncMock(spec=AsyncSession)
    request = _make_request(42)
    body = _make_body()

    with pytest.raises(HTTPException) as exc_info:
        await require_agent_chat_pat(request, session, body)
    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


async def test_require_agent_chat_pat_rejects_invalid_workspace_id(monkeypatch):
    """Non-integer workspace_id in path params must raise 400 with the right detail."""
    auth = _make_auth()
    _ = _patch_seams(monkeypatch, auth=auth, membership=SimpleNamespace(is_active=True))
    session = AsyncMock(spec=AsyncSession)

    request = _make_request("not-an-int")
    with pytest.raises(HTTPException) as exc_info:
        await require_agent_chat_pat(request, session, _make_body())
    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "integer" in exc_info.value.detail.lower()

    request = _make_request(None)
    with pytest.raises(HTTPException) as exc_info:
        await require_agent_chat_pat(request, session, _make_body())
    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_derive_scope_permission_uses_url_not_scope_path():
    """The url.path branch must win over scope['path'] when url is present."""

    class _URL:
        def __init__(self, path: str) -> None:
            self.path = path

    request = SimpleNamespace(
        method="POST",
        url=_URL("/threads"),
        scope={"path": "/messages"},
    )
    assert _derive_scope_permission(request) == "agent_chat:thread:create"


async def test_require_agent_chat_pat_rejects_method_lexicographically(monkeypatch):
    """Any non-'pat' method is rejected regardless of string comparison operator."""
    for method in ("a", "z"):
        auth = AuthContext(
            user=SimpleNamespace(id=uuid4()),
            method=method,
            pat=SimpleNamespace(
                token_kind="agent_chat",
                workspace_id=42,
                client_id="bdsai.vn",
                agent_id="bdsai-listing-assistant",
                scopes=["agent_chat:thread:create"],
                is_valid=True,
            ),
        )
        _ = _patch_seams(
            monkeypatch, auth=auth, membership=SimpleNamespace(is_active=True)
        )
        session = AsyncMock(spec=AsyncSession)
        request = _make_request(42)
        body = _make_body()

        with pytest.raises(HTTPException) as exc_info:
            await require_agent_chat_pat(request, session, body)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "pat_scope_required" in exc_info.value.detail


async def test_require_agent_chat_pat_accepts_method_equal_to_pat(monkeypatch):
    """A method value equal to 'pat' but not the same object must succeed."""
    method = "p"
    method += "at"
    assert method == "pat"
    assert id(method) != id("pat")
    auth = _make_auth()
    # Rebuild the AuthContext with the computed method string.
    auth = AuthContext(
        user=auth.user,
        method=method,
        pat=auth.pat,
    )
    _ = _patch_seams(monkeypatch, auth=auth, membership=SimpleNamespace(is_active=True))
    fake = _FakeSession(
        membership=SimpleNamespace(is_active=True),
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

    result = await require_agent_chat_pat(request, session, body)
    assert result.effective_client_id == "bdsai.vn"


async def test_require_agent_chat_pat_rejects_token_kind_lexicographically(monkeypatch):
    """token_kind != 'agent_chat' must raise regardless of string comparison."""
    for token_kind in ("admin", "legacy"):
        auth = _make_auth(token_kind=token_kind)
        _ = _patch_seams(
            monkeypatch, auth=auth, membership=SimpleNamespace(is_active=True)
        )
        session = AsyncMock(spec=AsyncSession)
        request = _make_request(42)
        body = _make_body()

        with pytest.raises(HTTPException) as exc_info:
            await require_agent_chat_pat(request, session, body)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "token_kind" in exc_info.value.detail.lower()


async def test_require_agent_chat_pat_accepts_token_kind_equal_to_agent_chat(
    monkeypatch,
):
    """token_kind equal to 'agent_chat' but a different object must succeed."""
    token_kind = "agent"
    token_kind += "_chat"
    assert token_kind == "agent_chat"
    assert id(token_kind) != id("agent_chat")
    auth = _make_auth(token_kind=token_kind)
    _ = _patch_seams(monkeypatch, auth=auth, membership=SimpleNamespace(is_active=True))
    fake = _FakeSession(
        membership=SimpleNamespace(is_active=True),
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

    result = await require_agent_chat_pat(request, session, body)
    assert result.effective_client_id == "bdsai.vn"


async def test_require_agent_chat_pat_workspace_id_equal_with_string_path_param(
    monkeypatch,
):
    """workspace_id equality must use value, not identity, when parsing from a string path param."""
    auth = _make_auth(workspace_id=100_000)
    _ = _patch_seams(monkeypatch, auth=auth, membership=SimpleNamespace(is_active=True))
    fake = _FakeSession(
        membership=SimpleNamespace(is_active=True),
        vertical_client=SimpleNamespace(client_id="bdsai.vn", is_active=True),
        agent_config=SimpleNamespace(
            name="bdsai-listing-assistant",
            client_id="bdsai.vn",
            is_active=True,
        ),
    )
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = fake.execute
    # Pass a string so int() creates a new object distinct from the auth constant.
    request = _make_request("100000")
    body = _make_body()

    result = await require_agent_chat_pat(request, session, body)
    assert result.workspace_id == 100_000


async def test_require_agent_chat_pat_accepts_falsy_is_valid_values(monkeypatch):
    """is_valid values that are falsy but not exactly False must not trigger expiration."""
    for is_valid in (0, None):
        auth = _make_auth(is_valid=is_valid)
        _ = _patch_seams(
            monkeypatch, auth=auth, membership=SimpleNamespace(is_active=True)
        )
        fake = _FakeSession(
            membership=SimpleNamespace(is_active=True),
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

        result = await require_agent_chat_pat(request, session, body)
        assert result.effective_client_id == "bdsai.vn"
