"""Unit tests for ``app.routes.self_host_research``.

Tests the metered ``POST /v1/self-host/research`` endpoint end-to-end with
monkeypatched auth, executor, wallet, and token-tracking seams.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_async_session

pytestmark = pytest.mark.unit


class _FakeUser(SimpleNamespace):
    """Minimal User stand-in for self-host route tests."""

    id = uuid.uuid4()
    is_active = True
    credit_micros_balance = 1_000_000
    credit_micros_reserved = 0


class _FakePAT(SimpleNamespace):
    """Minimal PersonalAccessToken stand-in."""

    id = 1
    token_kind = "self_host"
    workspace_id = 42
    user = _FakeUser()
    label = "self-host-test"
    token_prefix = "nw_pat_t"
    expires_at = None
    last_used_at = None


def _make_run_app() -> FastAPI:
    """Build a small FastAPI app with only the self-host research router."""
    from app.routes.self_host_research import router

    app = FastAPI()
    app.include_router(router, prefix="/v1")
    return app


@pytest.fixture
def fake_session():
    """AsyncSession stand-in that tracks commits and executes."""

    class _FakeResult:
        def __init__(self, value: Any = None):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

        def scalar(self):
            return self._value

        def scalars(self):
            return self

        def first(self):
            return self._value

        def all(self):
            return [self._value] if self._value is not None else []

    class _FakeSession:
        def __init__(self):
            self.committed = False
            self.added: list[Any] = []
            self._execute_result: Any = None

        def set_execute_result(self, value: Any) -> None:
            self._execute_result = value

        async def execute(self, _stmt: Any) -> _FakeResult:
            return _FakeResult(self._execute_result)

        def add(self, obj: Any) -> None:
            self.added.append(obj)

        async def commit(self) -> None:
            self.committed = True

        async def refresh(self, _obj: Any) -> None:
            pass

        async def flush(self) -> None:
            pass

    return _FakeSession()


@pytest.fixture
def client(monkeypatch, fake_session):
    """TestClient with auth, executor, wallet, and tracking seams patched."""
    import app.routes.self_host_research as sh_mod

    app = _make_run_app()
    app.dependency_overrides[get_async_session] = lambda: fake_session

    # Default: valid self-host PAT
    async def _resolve_pat(_session: Any, token: str) -> Any:
        if token == "valid-self-host-key":
            return _FakePAT()
        if token == "legacy-key":
            return SimpleNamespace(
                id=2,
                token_kind="legacy",
                workspace_id=42,
                user=_FakeUser(),
            )
        return None

    monkeypatch.setattr(sh_mod, "resolve_pat", _resolve_pat)
    monkeypatch.setattr(sh_mod, "maybe_touch_last_used", lambda _pat: None)

    # Wallet tracking
    calls: dict[str, list[Any]] = {"check": [], "debit": []}

    async def _check_balance(_session: Any, user_id: Any, required_micros: int) -> None:
        calls["check"].append({"user_id": user_id, "required_micros": required_micros})
        if required_micros > _FakeUser.credit_micros_balance:
            from app.services.wallet_credit import InsufficientCreditsError

            raise InsufficientCreditsError(
                message="short",
                balance_micros=_FakeUser.credit_micros_balance,
                required_micros=required_micros,
            )

    async def _apply_debit(_session: Any, user_id: Any, cost_micros: int) -> int:
        calls["debit"].append({"user_id": user_id, "cost_micros": cost_micros})
        _FakeUser.credit_micros_balance -= cost_micros
        return _FakeUser.credit_micros_balance

    monkeypatch.setattr(sh_mod, "check_balance", _check_balance)
    monkeypatch.setattr(sh_mod, "apply_debit", _apply_debit)
    sh_mod._debit_calls = calls  # type: ignore[attr-defined]

    # Token usage tracking
    recorded: list[dict[str, Any]] = []

    async def _record_token_usage(session: Any, **kwargs: Any) -> Any:
        recorded.append(kwargs)
        return SimpleNamespace(id=1)

    monkeypatch.setattr(sh_mod, "record_token_usage", _record_token_usage)
    sh_mod._recorded = recorded  # type: ignore[attr-defined]

    # Default: ChainLens configured
    class _FakeAuth:
        configured = True

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

    monkeypatch.setattr(sh_mod, "ChainLensServiceAuth", _FakeAuth)

    # Default: successful research executor
    async def _fake_executor(payload: Any, ctx: Any = None) -> Any:
        from app.capabilities.chainlens.research.schemas import ResearchOutput, Source

        return ResearchOutput(
            status="complete",
            answer="answer",
            sources=[Source(title="s", url="https://example.com")],
            cost_micros=48200,
            cost_dollars=0.0482,
            cost_basis="actual",
            resolved_mode="balanced",
            mode_requested="balanced",
            tokens_total=7950,
            tokens_prompt=4273,
            tokens_completion=3677,
            duration_ms=1000,
            first_token_time_ms=100,
            degraded=False,
            degradation_reason=None,
        )

    monkeypatch.setattr(sh_mod, "build_research_executor", lambda: _fake_executor)

    # Disable Redis for rate-limit by forcing in-memory path.
    monkeypatch.setattr(sh_mod, "_redis_client", Mock(side_effect=Exception("no redis")))

    test_client = TestClient(app)
    test_client._sh_mod = sh_mod  # type: ignore[attr-defined]
    return test_client


def _call(client: TestClient, token: str = "valid-self-host-key", json_body: dict[str, Any] | None = None) -> Any:
    json_body = json_body or {"query": "test"}
    return client.post(
        "/v1/self-host/research",
        json=json_body,
        headers={"Authorization": f"Bearer {token}"},
    )


def test_self_host_research_happy_path_cost_parse(client):
    response = _call(client)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "complete"
    assert body["answer"] == "answer"

    sh_mod = client._sh_mod
    debit_calls = sh_mod._debit_calls
    recorded = sh_mod._recorded

    # cost_micros 48200 * 1.5 = 72300 floored
    assert debit_calls["debit"][0]["cost_micros"] == 72300
    assert recorded[0]["cost_micros"] == 72300
    assert recorded[0]["usage_type"] == "deep_research"
    assert recorded[0]["call_details"]["cost_micros"] == 48200
    assert recorded[0]["call_details"]["billed_micros"] == 72300
    assert recorded[0]["call_details"]["multiplier"] == 1.5


def test_self_host_research_missing_key_401(client):
    response = client.post("/v1/self-host/research", json={"query": "test"})
    assert response.status_code == 401


def test_self_host_research_invalid_key_401(client):
    response = _call(client, token="nope")
    assert response.status_code == 401


def test_self_host_research_wrong_token_kind_401(client):
    response = _call(client, token="legacy-key")
    assert response.status_code == 401
    assert "self-host" in response.text.lower()


def test_self_host_research_out_of_credit_402(client, monkeypatch):
    import app.routes.self_host_research as sh_mod
    from app.services.wallet_credit import InsufficientCreditsError

    user = _FakeUser()
    user.credit_micros_balance = 0
    user.credit_micros_reserved = 0

    async def _resolve_pat(_session: Any, token: str) -> Any:
        return SimpleNamespace(
            id=1,
            token_kind="self_host",
            workspace_id=42,
            user=user,
            last_used_at=None,
        )

    monkeypatch.setattr(sh_mod, "resolve_pat", _resolve_pat)

    # Make the pre-flight balance check fail for this user.
    async def _check_balance_short(_session: Any, _user_id: Any, required_micros: int) -> None:
        raise InsufficientCreditsError(
            message="short",
            balance_micros=0,
            required_micros=required_micros,
        )

    monkeypatch.setattr(sh_mod, "check_balance", _check_balance_short)

    response = _call(client)
    assert response.status_code == 402
    body = response.json()
    assert body["detail"]["error_code"] == "insufficient_credits"


def test_self_host_research_rate_limit_429(client, monkeypatch):
    import app.routes.self_host_research as sh_mod

    # Speed up rate-limit fill by shrinking the window and cap.
    monkeypatch.setattr(sh_mod, "_SELF_HOST_RATE_LIMIT_PER_MINUTE", 1)
    monkeypatch.setattr(sh_mod, "_SELF_HOST_WINDOW_SECONDS", 1)

    _call(client)  # first call OK
    response = _call(client)
    assert response.status_code == 429
    assert "Retry-After" in response.headers


def test_self_host_research_engine_not_configured_degrades(client, monkeypatch):
    import app.routes.self_host_research as sh_mod

    class _NoAuth:
        configured = False

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

    monkeypatch.setattr(sh_mod, "ChainLensServiceAuth", _NoAuth)

    response = _call(client)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "engine_unavailable"
    assert body["degradation_reason"] == "not_configured"
    assert body["next_action"] is not None

    # No debit on not_configured.
    assert len(sh_mod._debit_calls["debit"]) == 0


def test_self_host_research_missing_cost_fallback(client, monkeypatch):
    import app.routes.self_host_research as sh_mod
    from app.capabilities.chainlens.research.schemas import ResearchOutput, Source

    async def _fake_executor(payload: Any, ctx: Any = None) -> Any:
        return ResearchOutput(
            status="complete",
            answer="answer",
            sources=[Source(title="s", url="https://example.com")],
            cost_micros=None,
            cost_dollars=None,
            cost_basis=None,
            resolved_mode="balanced",
            mode_requested="balanced",
            tokens_total=None,
            tokens_prompt=None,
            tokens_completion=None,
            duration_ms=1000,
            first_token_time_ms=100,
            degraded=False,
            degradation_reason=None,
        )

    monkeypatch.setattr(sh_mod, "build_research_executor", lambda: _fake_executor)

    response = _call(client)
    assert response.status_code == 200

    # Fallback 60000 micros * 1.5 = 90000
    assert sh_mod._debit_calls["debit"][0]["cost_micros"] == 90000
    assert sh_mod._recorded[0]["call_details"]["cost_basis"] == "fallback"
    assert sh_mod._recorded[0]["call_details"]["cost_micros"] == 60000
    assert sh_mod._recorded[0]["call_details"]["billed_micros"] == 90000


def test_self_host_research_zero_cost_no_debit(client, monkeypatch):
    import app.routes.self_host_research as sh_mod
    from app.capabilities.chainlens.research.schemas import ResearchOutput, Source

    async def _fake_executor(payload: Any, ctx: Any = None) -> Any:
        return ResearchOutput(
            status="complete",
            answer="answer",
            sources=[Source(title="s", url="https://example.com")],
            cost_micros=0,
            cost_dollars=0.0,
            cost_basis="actual",
            resolved_mode="balanced",
            mode_requested="balanced",
            tokens_total=None,
            tokens_prompt=None,
            tokens_completion=None,
            duration_ms=1000,
            first_token_time_ms=100,
            degraded=False,
            degradation_reason=None,
        )

    monkeypatch.setattr(sh_mod, "build_research_executor", lambda: _fake_executor)

    response = _call(client)
    assert response.status_code == 200
    assert len(sh_mod._debit_calls["debit"]) == 0
    assert sh_mod._recorded[0]["cost_micros"] == 0


def test_self_host_research_engine_unavailable_no_content_no_debit(client, monkeypatch):
    import app.routes.self_host_research as sh_mod
    from app.capabilities.chainlens.research.schemas import ResearchOutput

    async def _fake_executor(payload: Any, ctx: Any = None) -> Any:
        return ResearchOutput(
            status="engine_unavailable",
            answer="",
            sources=[],
            cost_micros=None,
            cost_dollars=None,
            cost_basis=None,
            resolved_mode=None,
            mode_requested="balanced",
            tokens_total=None,
            tokens_prompt=None,
            tokens_completion=None,
            duration_ms=1000,
            first_token_time_ms=100,
            degraded=True,
            degradation_reason="upstream_error",
        )

    monkeypatch.setattr(sh_mod, "build_research_executor", lambda: _fake_executor)

    response = _call(client)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "engine_unavailable"
    assert body["degradation_reason"] == "upstream_error"
    assert len(sh_mod._debit_calls["debit"]) == 0
