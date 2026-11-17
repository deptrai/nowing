"""AI-42.4: unified PAT seam — scope = permission string, enforced ngay trong
`check_permission` (mọi `RequirePermission` caller) + workspace binding trong
`check_workspace_access`. Test gọi trực tiếp 2 hàm với session/membership giả —
không cần mount router.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from app.auth.context import AuthContext
from app.utils import rbac


class _FakeResult:
    def __init__(self, row: Any) -> None:
        self._row = row

    def scalars(self) -> "_FakeResult":
        return self

    def first(self) -> Any:
        return self._row


class _FakeSession:
    """Session giả — `execute(...)` trả workspace cho api-access gate."""

    def __init__(self, workspace: Any) -> None:
        self.workspace = workspace

    async def execute(self, _stmt: Any) -> _FakeResult:
        return _FakeResult(self.workspace)


def _membership() -> Any:
    role = SimpleNamespace(permissions=["members:view", "leads:read"])
    return SimpleNamespace(is_owner=False, role=role)


def _pat_auth(
    *,
    scopes: list[str],
    workspace_id: int = 1,
    token_kind: str = "legacy",
) -> AuthContext:
    user = SimpleNamespace(id=uuid.uuid4(), is_active=True)
    pat = SimpleNamespace(
        id=7,
        scopes=scopes,
        workspace_id=workspace_id,
        token_kind=token_kind,
    )
    return AuthContext.pat_auth(user, pat)


def _session_auth() -> AuthContext:
    return AuthContext.session(SimpleNamespace(id=uuid.uuid4(), is_active=True))


@pytest.fixture(autouse=True)
def _fake_membership(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake(*_args: Any, **_kwargs: Any) -> Any:
        return _membership()

    monkeypatch.setattr(rbac, "get_user_membership", _fake)


def _ws(enabled: bool = True) -> _FakeSession:
    return _FakeSession(SimpleNamespace(id=1, api_access_enabled=enabled))


# --- check_permission unified seam -----------------------------------------


@pytest.mark.anyio
async def test_pat_with_required_scope_allowed() -> None:
    """PAT có scope đúng perm → pass, trả membership."""
    auth = _pat_auth(scopes=["members:view"])
    membership = await rbac.check_permission(_ws(), auth, 1, "members:view")
    assert membership is not None


@pytest.mark.anyio
async def test_pat_missing_scope_403_non_leads_perm() -> None:
    """PAT leads-scope nhưng endpoint cần members:view → 403 (non-leads domain
    giờ cũng fail-closed nhờ unified check)."""
    auth = _pat_auth(scopes=["leads:write"])
    with pytest.raises(HTTPException) as exc:
        await rbac.check_permission(_ws(), auth, 1, "members:view")
    assert exc.value.status_code == 403
    assert "permission missing: members:view" in str(exc.value.detail)


@pytest.mark.anyio
async def test_pat_wrong_workspace_binding_first() -> None:
    """PAT bound ws-999 gọi ws-1 → 403 binding (trước api-access gate)."""
    auth = _pat_auth(scopes=["members:view"], workspace_id=999)
    with pytest.raises(HTTPException) as exc:
        await rbac.check_permission(_ws(enabled=False), auth, 1, "members:view")
    assert exc.value.status_code == 403
    assert "outside pat scope" in str(exc.value.detail)


@pytest.mark.anyio
async def test_self_host_pat_exempt() -> None:
    """self_host key scopes=[] nhưng owner-minted full-access → exempt."""
    auth = _pat_auth(scopes=[], token_kind="self_host")
    membership = await rbac.check_permission(_ws(), auth, 1, "members:view")
    assert membership is not None


@pytest.mark.anyio
async def test_session_unchanged() -> None:
    """Session user không bị scope check (is_gated=False)."""
    auth = _session_auth()
    membership = await rbac.check_permission(_ws(), auth, 1, "members:view")
    assert membership is not None


@pytest.mark.anyio
async def test_legacy_empty_scopes_fail_closed() -> None:
    """legacy PAT scopes=[] → 403 dù membership có perm."""
    auth = _pat_auth(scopes=[])
    with pytest.raises(HTTPException) as exc:
        await rbac.check_permission(_ws(), auth, 1, "members:view")
    assert exc.value.status_code == 403
    assert "permission missing: members:view" in str(exc.value.detail)


# --- check_workspace_access binding ----------------------------------------


@pytest.mark.anyio
async def test_workspace_access_pat_wrong_ws_403() -> None:
    """PAT bound ws-999 → check_workspace_access(1) 403 (binding-only)."""
    auth = _pat_auth(scopes=[], workspace_id=999)
    with pytest.raises(HTTPException) as exc:
        await rbac.check_workspace_access(_ws(), auth, 1)
    assert exc.value.status_code == 403
    assert "outside pat scope" in str(exc.value.detail)


@pytest.mark.anyio
async def test_workspace_access_pat_bound_passes() -> None:
    """PAT bound đúng ws → pass (membership-level, không scope check)."""
    auth = _pat_auth(scopes=[], workspace_id=1)
    membership = await rbac.check_workspace_access(_ws(), auth, 1)
    assert membership is not None


@pytest.mark.anyio
async def test_workspace_access_self_host_unbound_exempt() -> None:
    """self_host bound ws-B vẫn access ws-A (owner-minted full-access)."""
    auth = _pat_auth(scopes=[], workspace_id=999, token_kind="self_host")
    membership = await rbac.check_workspace_access(_ws(), auth, 1)
    assert membership is not None
