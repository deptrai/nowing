"""Unit tests for GET /workspaces/{id}/scrapers/health (Story 42.3).

Cover đủ 8 case I/O Matrix trong spec: OK, DEGRADED, DOWN, IDLE, NEVER_RAN,
CROSS_WS, UNAUTH, LEGACY_CAP. Fake session trả rows cho 2 query (window 24h +
latest all-time) theo convention test_leads_routes.py.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.auth.context import AuthContext
from app.db import get_async_session
from app.users import get_auth_context
from app.utils.rbac import check_workspace_access

pytestmark = pytest.mark.unit

_NOW = datetime.now(UTC)
_RECENT = _NOW - timedelta(hours=1)
_OLD = _NOW - timedelta(days=5)


class _FakeResult:
    def __init__(self, rows: list[Any] | None = None) -> None:
        self._rows = rows or []

    def all(self) -> list[Any]:
        return self._rows

    def scalars(self) -> _FakeResult:
        return self


class _FakeSession:
    """Fake AsyncSession: trả window rows cho query 24h, latest rows cho DISTINCT ON."""

    def __init__(
        self,
        *,
        window: list[Any] | None = None,
        latest: list[Any] | None = None,
        errors: list[Any] | None = None,
    ) -> None:
        self._window = window or []
        self._latest = latest or []
        self._errors = errors or []
        self.tenant_guc_calls: list[tuple[str, Any]] = []

    async def execute(self, stmt: Any, *args: Any, **kwargs: Any) -> _FakeResult:
        stmt_str = str(stmt)
        if "set_config" in stmt_str:
            # RLS GUC — ghi lại (stmt, params) để test assert tenant context.
            self.tenant_guc_calls.append((stmt_str, args[0] if args else kwargs))
            return _FakeResult(rows=[])
        params = (
            set(stmt.compile().params.values()) if hasattr(stmt, "compile") else set()
        )
        if "GROUP BY" in stmt_str or "count" in stmt_str.lower():
            return _FakeResult(rows=self._window)
        if "error" in params:
            # Query latest-error (WHERE status='error').
            return _FakeResult(rows=self._errors)
        return _FakeResult(rows=self._latest)

    async def close(self) -> None:
        pass


def _window_row(capability: str, attempts: int, hits: int) -> SimpleNamespace:
    return SimpleNamespace(capability=capability, attempts=attempts, hits=hits, last_24h=_RECENT)


def _latest_row(
    capability: str, status: str, error: str | None, created_at: datetime
) -> SimpleNamespace:
    return SimpleNamespace(
        capability=capability, status=status, error=error, created_at=created_at
    )


def _fake_auth() -> AuthContext:
    return AuthContext.session(SimpleNamespace(id=1, is_active=True))


async def _fake_check_access(session: Any, auth: Any, workspace_id: int) -> None:
    return None


def _client(
    fake_session: _FakeSession,
    monkeypatch: pytest.MonkeyPatch,
    *,
    access: Any = _fake_check_access,
) -> TestClient:
    from app.capabilities.core.access import rest as rest_mod
    from app.capabilities.core.access.rest import build_capabilities_router

    # check_workspace_access được gọi trực tiếp trong endpoint (không qua
    # Depends) → monkeypatch module attr, giống cách test_leads_routes patch
    # check_permission.
    monkeypatch.setattr(rest_mod, "check_workspace_access", access)

    app = FastAPI()
    app.include_router(build_capabilities_router([]))
    app.dependency_overrides[get_async_session] = lambda: fake_session
    app.dependency_overrides[get_auth_context] = _fake_auth
    return TestClient(app)


def test_ok_channel_full_success(monkeypatch):
    """OK: 5/5 success trong 24h → rate 1.0, last_status success, envelope ok."""
    session = _FakeSession(
        window=[_window_row("google.search", 5, 5)],
        latest=[_latest_row("google.search", "success", None, _RECENT)],
    )
    resp = _client(session, monkeypatch).get("/workspaces/1/scrapers/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    row = next(c for c in data["channels"] if c["channel"] == "google.search")
    assert row["success_rate_24h"] == 1.0
    assert row["last_status"] == "success"
    assert row["attempts_24h"] == 5
    assert row["last_seen_at"] is not None
    assert data["checked_at"].endswith("Z")  # ISO 8601 UTC (AC5)


def test_degraded_channel(monkeypatch):
    """DEGRADED: 3/5 success → rate 0.6 → envelope degraded."""
    session = _FakeSession(
        window=[_window_row("google.search", 5, 3)],
        latest=[_latest_row("google.search", "error", "captcha", _RECENT)],
    )
    resp = _client(session, monkeypatch).get("/workspaces/1/scrapers/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "degraded"
    row = next(c for c in data["channels"] if c["channel"] == "google.search")
    assert row["success_rate_24h"] == 0.6


def test_down_channel_with_last_error(monkeypatch):
    """DOWN: 0/3 success → rate 0.0 + last_error từ run fail mới nhất → envelope down."""
    session = _FakeSession(
        window=[_window_row("google.search", 3, 0)],
        latest=[_latest_row("google.search", "error", "boom: 429 rate limit", _RECENT)],
        errors=[_latest_row("google.search", "error", "boom: 429 rate limit", _RECENT)],
    )
    resp = _client(session, monkeypatch).get("/workspaces/1/scrapers/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "down"
    row = next(c for c in data["channels"] if c["channel"] == "google.search")
    assert row["success_rate_24h"] == 0.0
    assert row["last_error"] == "boom: 429 rate limit"
    assert row["last_status"] == "error"


def test_last_error_survives_newer_success(monkeypatch):
    """last_error lấy từ run FAIL mới nhất — không bị run success sau đó phủ mất."""
    session = _FakeSession(
        window=[_window_row("google.search", 5, 3)],
        latest=[_latest_row("google.search", "success", None, _RECENT)],
        errors=[_latest_row("google.search", "error", "quota exceeded", _OLD)],
    )
    resp = _client(session, monkeypatch).get("/workspaces/1/scrapers/health")
    assert resp.status_code == 200
    row = next(
        c for c in resp.json()["channels"] if c["channel"] == "google.search"
    )
    assert row["last_status"] == "success"
    assert row["last_error"] == "quota exceeded"


def test_down_beats_degraded_with_mixed_channels(monkeypatch):
    """Envelope 'down' thắng 'degraded' khi workspace có cả channel chết lẫn yếu."""
    session = _FakeSession(
        window=[
            _window_row("dead.cap", 3, 0),
            _window_row("weak.cap", 5, 3),
        ],
        latest=[
            _latest_row("dead.cap", "error", "boom", _RECENT),
            _latest_row("weak.cap", "success", None, _RECENT),
        ],
    )
    resp = _client(session, monkeypatch).get("/workspaces/1/scrapers/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "down"
    rates = {c["channel"]: c["success_rate_24h"] for c in data["channels"]}
    assert rates["dead.cap"] == 0.0
    assert rates["weak.cap"] == 0.6


def test_idle_channel_rate_null(monkeypatch):
    """IDLE: chỉ có runs cũ >24h → rate null, last_status/last_seen_at all-time."""
    session = _FakeSession(
        window=[],
        latest=[_latest_row("google.search", "success", None, _OLD)],
    )
    resp = _client(session, monkeypatch).get("/workspaces/1/scrapers/health")
    assert resp.status_code == 200
    data = resp.json()
    # Không channel observed → ok.
    assert data["status"] == "ok"
    row = next(c for c in data["channels"] if c["channel"] == "google.search")
    assert row["success_rate_24h"] is None
    assert row["attempts_24h"] == 0
    assert row["last_status"] == "success"
    assert row["last_seen_at"] is not None
    assert row["last_seen_at"].startswith(_OLD.strftime("%Y-%m-%dT%H"))


def test_never_ran_channel_unknown(monkeypatch):
    """NEVER_RAN: channel trong registry, 0 run → last_status unknown, rate null, 200."""
    session = _FakeSession(window=[], latest=[])
    resp = _client(session, monkeypatch).get("/workspaces/1/scrapers/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    # Registry thật (all_capabilities) → mọi channel never-ran: unknown + rate null.
    assert data["channels"]
    assert all(c["last_status"] == "unknown" for c in data["channels"])
    assert all(c["success_rate_24h"] is None for c in data["channels"])


def test_never_ran_registry_channel_reports_unknown(monkeypatch):
    """NEVER_RAN với registry có channel: row unknown nhưng không ảnh hưởng envelope."""
    import app.capabilities.core.access.rest as rest_mod

    class _FakeCap:
        name = "google.search"

    original = rest_mod.all_capabilities
    rest_mod.all_capabilities = lambda: [_FakeCap()]
    try:
        session = _FakeSession(window=[], latest=[])
        resp = _client(session, monkeypatch).get("/workspaces/1/scrapers/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        row = next(c for c in data["channels"] if c["channel"] == "google.search")
        assert row["last_status"] == "unknown"
        assert row["last_seen_at"] is None
        assert row["success_rate_24h"] is None
    finally:
        rest_mod.all_capabilities = original


def test_cross_workspace_not_leaked(monkeypatch):
    """CROSS_WS: fake session chỉ trả runs của workspace caller — query filter workspace_id."""

    class _FilterCaptureSession(_FakeSession):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self.where_params: list[Any] = []

        async def execute(self, stmt: Any, *args: Any, **kwargs: Any) -> _FakeResult:
            self.where_params.append(stmt)
            return await super().execute(stmt, *args, **kwargs)

    session = _FilterCaptureSession(
        window=[_window_row("google.search", 2, 2)],
        latest=[_latest_row("google.search", "success", None, _RECENT)],
    )
    resp = _client(session, monkeypatch).get("/workspaces/7/scrapers/health")
    assert resp.status_code == 200
    # Cả 2 query phải bind workspace_id = 7 vào WHERE (filter + GUC set trước).
    hits = 0
    for stmt in session.where_params:
        if hasattr(stmt, "compile"):
            if 7 in stmt.compile().params.values():
                hits += 1
    assert hits >= 2  # window + latest queries
    assert len(session.where_params) >= 2
    # RLS: GUC app.workspace_id phải được set thành "7" trước khi select
    # (FORCE ROW LEVEL SECURITY trên runs — thiếu GUC là trả rỗng lặng lẽ).
    assert any(
        "app.workspace_id" in stmt_str and params.get("wid") == "7"
        for stmt_str, params in session.tenant_guc_calls
    )


def test_unauth_returns_403(monkeypatch):
    """UNAUTH: check_workspace_access raise 403 → endpoint không trả data."""

    async def _deny(session: Any, auth: Any, workspace_id: int) -> None:
        raise HTTPException(status_code=403, detail="not a member")

    session = _FakeSession()
    resp = _client(session, monkeypatch, access=_deny).get("/workspaces/1/scrapers/health")
    assert resp.status_code == 403


def test_no_auth_returns_401(monkeypatch):
    """UNAUTH 401: không có session/PAT → get_auth_context raise trước khi query."""

    def _no_auth() -> AuthContext:
        raise HTTPException(status_code=401, detail="unauthenticated")

    session = _FakeSession()
    fake_client_app = _client(session, monkeypatch)
    # get_auth_context đã bị override trong _client — thay override sang 401.
    fake_client_app.app.dependency_overrides[get_auth_context] = _no_auth  # type: ignore[attr-defined]
    resp = fake_client_app.get("/workspaces/1/scrapers/health")
    assert resp.status_code == 401


def test_legacy_capability_still_returned(monkeypatch):
    """LEGACY_CAP: capability trong runs nhưng không còn registry → vẫn trả row."""
    import app.capabilities.core.access.rest as rest_mod

    class _FakeCap:
        name = "other.cap"

    original = rest_mod.all_capabilities
    rest_mod.all_capabilities = lambda: [_FakeCap()]
    try:
        session = _FakeSession(
            window=[_window_row("legacy.cap", 4, 2)],
            latest=[_latest_row("legacy.cap", "success", None, _RECENT)],
        )
        resp = _client(session, monkeypatch).get("/workspaces/1/scrapers/health")
        assert resp.status_code == 200
        data = resp.json()
        row = next(c for c in data["channels"] if c["channel"] == "legacy.cap")
        assert row["success_rate_24h"] == 0.5
        assert row["last_status"] == "success"
    finally:
        rest_mod.all_capabilities = original


def test_last_error_truncated_200_chars(monkeypatch):
    """Deviation: last_error truncate 200 chars từ runs.error Text free-form."""
    long_error = "x" * 500
    session = _FakeSession(
        window=[_window_row("google.search", 1, 0)],
        latest=[_latest_row("google.search", "error", long_error, _RECENT)],
        errors=[_latest_row("google.search", "error", long_error, _RECENT)],
    )
    resp = _client(session, monkeypatch).get("/workspaces/1/scrapers/health")
    assert resp.status_code == 200
    row = next(c for c in resp.json()["channels"] if c["channel"] == "google.search")
    assert len(row["last_error"]) == 200