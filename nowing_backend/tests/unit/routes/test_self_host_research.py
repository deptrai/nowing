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
    sh_mod._memory = sh_mod.defaultdict(list)

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
    assert recorded[0]["call_details"]["cost_dollars"] == 0.0482
    assert recorded[0]["prompt_tokens"] == 4273
    assert recorded[0]["completion_tokens"] == 3677
    assert recorded[0]["total_tokens"] == 7950
    assert "degraded" not in recorded[0]["call_details"]


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
    assert body["detail"]["balance_micros"] == 0
    assert body["detail"]["required_micros"] == 90000


def test_self_host_research_rate_limit_429(client, monkeypatch):
    import app.routes.self_host_research as sh_mod

    # Speed up rate-limit fill by shrinking the window and cap.
    monkeypatch.setattr(sh_mod, "_SELF_HOST_RATE_LIMIT_PER_MINUTE", 1)
    monkeypatch.setattr(sh_mod, "_SELF_HOST_WINDOW_SECONDS", 1)

    first = _call(client)  # first call OK
    assert first.status_code == 200
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
    assert sh_mod._recorded[0]["call_details"]["cost_dollars"] == 0.0
    assert sh_mod._recorded[0]["prompt_tokens"] == 0
    assert sh_mod._recorded[0]["completion_tokens"] == 0
    assert sh_mod._recorded[0]["total_tokens"] == 0
    assert "degraded" not in sh_mod._recorded[0]["call_details"]


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
    assert len(sh_mod._recorded) == 0


def test_self_host_research_insufficient_evidence_no_content_no_debit(client, monkeypatch):
    import app.routes.self_host_research as sh_mod
    from app.capabilities.chainlens.research.schemas import ResearchOutput

    async def _fake_executor(payload: Any, ctx: Any = None) -> Any:
        return ResearchOutput(
            status="insufficient_evidence",
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
            degradation_reason="insufficient_evidence",
        )

    monkeypatch.setattr(sh_mod, "build_research_executor", lambda: _fake_executor)

    response = _call(client)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "insufficient_evidence"
    assert len(sh_mod._debit_calls["debit"]) == 0
    assert len(sh_mod._recorded) == 0


def test_self_host_research_bearer_header_with_extra_space_200(client, monkeypatch):
    import app.routes.self_host_research as sh_mod

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

    response = client.post(
        "/v1/self-host/research",
        json={"query": "test"},
        headers={"Authorization": "Bearer  valid-self-host-key"},
    )
    assert response.status_code == 200


def test_self_host_research_correlation_id_passed_to_engine(client, monkeypatch):
    import app.routes.self_host_research as sh_mod
    from app.capabilities.chainlens.research.schemas import ResearchOutput, Source

    captured: dict[str, Any] = {}

    async def _fake_executor(payload: Any, ctx: Any = None) -> Any:
        captured["correlation_id"] = payload.correlation_id
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

    response = client.post(
        "/v1/self-host/research",
        json={"query": "test", "correlation_id": "test-corr-123"},
        headers={"Authorization": "Bearer valid-self-host-key"},
    )
    assert response.status_code == 200
    assert captured.get("correlation_id") == "test-corr-123"


def test_self_host_research_token_kind_after_self_host_401(client, monkeypatch):
    """A token kind lexicographically after 'self_host' must still be rejected."""
    import app.routes.self_host_research as sh_mod

    async def _resolve_pat(_session: Any, token: str) -> Any:
        return SimpleNamespace(
            id=3,
            token_kind="zzz",
            workspace_id=42,
            user=_FakeUser(),
            label="bad",
            token_prefix="nw_pat_t",
            expires_at=None,
            last_used_at=None,
        )

    monkeypatch.setattr(sh_mod, "resolve_pat", _resolve_pat)

    response = _call(client, token="any-key")
    assert response.status_code == 401
    assert "self-host" in response.text.lower()


async def test_resolve_workspace_id_filters_by_user(client):
    """_resolve_workspace_id queries workspaces by the user's id, not >."""
    import app.routes.self_host_research as sh_mod

    user = _FakeUser()
    pat = _FakePAT()
    pat.workspace_id = None
    captured: dict[str, Any] = {}

    class _StmtCapture:
        async def execute(self, stmt: Any) -> Any:
            captured["stmt"] = stmt
            return SimpleNamespace(scalar_one_or_none=lambda: 7)

    result = await sh_mod._resolve_workspace_id(_StmtCapture(), user, pat)
    assert result == 7
    compiled = str(captured["stmt"].compile())
    assert "user_id =" in compiled
    assert "LIMIT" in compiled


def test_self_host_research_billed_micros_boundaries(client):
    """_billed_micros treats None, negative and zero as free and floors positives."""
    import app.routes.self_host_research as sh_mod

    assert sh_mod._billed_micros(None) == 0
    assert sh_mod._billed_micros(-1) == 0
    assert sh_mod._billed_micros(0) == 0
    assert sh_mod._billed_micros(1) == 1
    assert sh_mod._billed_micros(48200) == 72300


def test_self_host_research_cost_defaults(monkeypatch):
    """Default cost multiplier and fallback micros are exercised when config omits them."""
    import app.routes.self_host_research as sh_mod

    class _EmptyConfig:
        pass

    monkeypatch.setattr(sh_mod, "config", _EmptyConfig())

    assert sh_mod._self_host_multiplier() == 1.5
    assert sh_mod._fallback_micros() == 60000


def test_self_host_research_rate_limit_constants(client):
    """Rate limit defaults are stable."""
    import app.routes.self_host_research as sh_mod

    assert sh_mod._SELF_HOST_RATE_LIMIT_PER_MINUTE == 120
    assert sh_mod._SELF_HOST_WINDOW_SECONDS == 60


def test_self_host_research_incr_memory_window(client, monkeypatch):
    """_incr_memory only keeps timestamps strictly inside the window."""
    from threading import Lock

    import app.routes.self_host_research as sh_mod

    monkeypatch.setattr(sh_mod, "_memory", sh_mod.defaultdict(list))
    monkeypatch.setattr(sh_mod, "_memory_lock", Lock())
    monkeypatch.setattr(sh_mod.time, "monotonic", lambda: 100.0)

    sh_mod._memory["key"] = [89.0, 90.0]
    count = sh_mod._incr_memory("key", 10)
    assert count == 1
    assert sh_mod._memory["key"] == [100.0]


def test_self_host_research_redis_client_uses_decode_responses(monkeypatch):
    """_redis_client creates the client with decode_responses=True."""
    import redis

    import app.routes.self_host_research as sh_mod

    called: list[dict[str, Any]] = []

    def _fake_from_url(_url: str, **kwargs: Any) -> Any:
        called.append(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(redis, "from_url", _fake_from_url)
    sh_mod._redis = None
    sh_mod._redis_client()
    assert called[0].get("decode_responses") is True


async def test_self_host_research_redis_expire_on_first_call(client, monkeypatch):
    """_incr sets Redis key expiry on the very first call only."""
    import app.routes.self_host_research as sh_mod

    expire_calls: list[tuple[str, int]] = []

    class _FakeRedis:
        def incr(self, _key: str) -> int:
            return 1

        def expire(self, key: str, seconds: int) -> None:
            expire_calls.append((key, seconds))

    monkeypatch.setattr(sh_mod, "_redis_client", lambda: _FakeRedis())
    sh_mod._redis = None

    count = await sh_mod._aincr("rate-limit-key", sh_mod._SELF_HOST_WINDOW_SECONDS)
    assert count == 1
    assert expire_calls == [("rate-limit-key", 60)]


async def test_charge_self_host_research_small_positive_cost_debits(client, fake_session):
    """A small positive cost with content triggers a real debit."""
    import app.routes.self_host_research as sh_mod
    from app.capabilities.chainlens.research.schemas import ResearchOutput, Source

    user = _FakeUser()
    user.credit_micros_balance = 10
    output = ResearchOutput(
        status="complete",
        answer="a",
        sources=[Source(title="s", url="https://example.com")],
        cost_micros=1,
        cost_dollars=0.000001,
        cost_basis="actual",
        resolved_mode="balanced",
        mode_requested="balanced",
        tokens_total=1,
        tokens_prompt=1,
        tokens_completion=0,
        duration_ms=1000,
        first_token_time_ms=100,
        degraded=False,
        degradation_reason=None,
    )

    billed = await sh_mod._charge_self_host_research(
        fake_session, user, 42, output, "run-1"
    )
    assert billed == 1
    assert sh_mod._debit_calls["debit"][-1]["cost_micros"] == 1


async def test_charge_self_host_research_no_content_positive_cost_debits(
    client, fake_session
):
    """A positive engine cost even without content should still be debited."""
    import app.routes.self_host_research as sh_mod
    from app.capabilities.chainlens.research.schemas import ResearchOutput

    user = _FakeUser()
    user.credit_micros_balance = 10
    output = ResearchOutput(
        status="insufficient_evidence",
        answer="",
        sources=[],
        cost_micros=1,
        cost_dollars=0.000001,
        cost_basis="actual",
        resolved_mode=None,
        mode_requested="balanced",
        tokens_total=None,
        tokens_prompt=None,
        tokens_completion=None,
        duration_ms=1000,
        first_token_time_ms=100,
        degraded=True,
        degradation_reason="insufficient_evidence",
    )

    billed = await sh_mod._charge_self_host_research(
        fake_session, user, 42, output, "run-1"
    )
    assert billed == 1
    assert sh_mod._debit_calls["debit"][-1]["cost_micros"] == 1


async def test_charge_self_host_research_zero_cost_returns_zero(client, fake_session):
    """A zero-cost complete call returns billed_micros 0 and records no debit."""
    import app.routes.self_host_research as sh_mod
    from app.capabilities.chainlens.research.schemas import ResearchOutput, Source

    user = _FakeUser()
    user.credit_micros_balance = 10
    output = ResearchOutput(
        status="complete",
        answer="answer",
        sources=[Source(title="s", url="https://example.com")],
        cost_micros=0,
        cost_dollars=0.0,
        cost_basis="actual",
        resolved_mode="balanced",
        mode_requested="balanced",
        tokens_total=1,
        tokens_prompt=1,
        tokens_completion=0,
        duration_ms=1000,
        first_token_time_ms=100,
        degraded=False,
        degradation_reason=None,
    )

    billed = await sh_mod._charge_self_host_research(
        fake_session, user, 42, output, "run-1"
    )
    assert billed == 0
    assert len(sh_mod._debit_calls["debit"]) == 0


def test_self_host_research_invalid_scheme_401(client, monkeypatch):
    """A non-Bearer Authorization scheme is rejected before the PAT lookup."""
    import app.routes.self_host_research as sh_mod

    async def _resolve_pat(_session: Any, _token: str) -> Any:
        return SimpleNamespace(
            id=1,
            token_kind="self_host",
            workspace_id=42,
            user=_FakeUser(),
            last_used_at=None,
        )

    monkeypatch.setattr(sh_mod, "resolve_pat", _resolve_pat)

    response = client.post(
        "/v1/self-host/research",
        json={"query": "test"},
        headers={"Authorization": "zzz valid-self-host-key"},
    )
    assert response.status_code == 401

    # A scheme lexicographically before "bearer" also has to be rejected.
    response = client.post(
        "/v1/self-host/research",
        json={"query": "test"},
        headers={"Authorization": "aaa valid-self-host-key"},
    )
    assert response.status_code == 401


def test_self_host_research_pat_without_user_401(client, monkeypatch):
    """A PAT that resolves without a user must still fail closed."""
    import app.routes.self_host_research as sh_mod

    async def _resolve_pat(_session: Any, _token: str) -> Any:
        return SimpleNamespace(
            id=1,
            token_kind="self_host",
            workspace_id=42,
            user=None,
            last_used_at=None,
        )

    monkeypatch.setattr(sh_mod, "resolve_pat", _resolve_pat)

    response = _call(client)
    assert response.status_code == 401


def test_self_host_research_degraded_with_content_records_flag(client, monkeypatch):
    """A degraded result with content still records the degraded flag."""
    import app.routes.self_host_research as sh_mod
    from app.capabilities.chainlens.research.schemas import ResearchOutput, Source

    async def _fake_executor(payload: Any, ctx: Any = None) -> Any:
        return ResearchOutput(
            status="partial",
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
            degradation_reason="insufficient_evidence",
        )

    monkeypatch.setattr(sh_mod, "build_research_executor", lambda: _fake_executor)

    response = _call(client)
    assert response.status_code == 200
    assert sh_mod._recorded[0]["call_details"]["degraded"] is True


def test_self_host_research_answer_only_missing_cost_uses_fallback(
    client, monkeypatch
):
    """An answer-only result with no engine cost still bills the fallback."""
    import app.routes.self_host_research as sh_mod
    from app.capabilities.chainlens.research.schemas import ResearchOutput

    async def _fake_executor(payload: Any, ctx: Any = None) -> Any:
        return ResearchOutput(
            status="insufficient_evidence",
            answer="answer",
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
            degradation_reason="insufficient_evidence",
        )

    monkeypatch.setattr(sh_mod, "build_research_executor", lambda: _fake_executor)

    response = _call(client)
    assert response.status_code == 200
    assert sh_mod._debit_calls["debit"][0]["cost_micros"] == 90000


def test_self_host_research_incr_memory_varied_timestamps(client, monkeypatch):
    """_incr_memory rejects timestamps via actual subtraction, not modulo/multiply."""
    from threading import Lock

    import app.routes.self_host_research as sh_mod

    monkeypatch.setattr(sh_mod, "_memory", sh_mod.defaultdict(list))
    monkeypatch.setattr(sh_mod, "_memory_lock", Lock())
    monkeypatch.setattr(sh_mod.time, "monotonic", lambda: 100.0)

    sh_mod._memory["key"] = [50.0, 89.0, 90.0, 0.05, 0.3]
    count = sh_mod._incr_memory("key", 10)
    assert count == 1
    assert sh_mod._memory["key"] == [100.0]


async def test_self_host_research_redis_expire_only_on_first_exact_count(
    client, monkeypatch
):
    """_incr only expires on the single Redis count equal to one."""
    import app.routes.self_host_research as sh_mod

    expire_calls: list[tuple[str, int]] = []
    counts = iter([0, 2, 1])

    class _FakeRedis:
        def incr(self, _key: str) -> int:
            return next(counts)

        def expire(self, key: str, seconds: int) -> None:
            expire_calls.append((key, seconds))

    monkeypatch.setattr(sh_mod, "_redis_client", lambda: _FakeRedis())
    sh_mod._redis = None

    assert await sh_mod._aincr("rate-limit-key", sh_mod._SELF_HOST_WINDOW_SECONDS) == 0
    assert await sh_mod._aincr("rate-limit-key", sh_mod._SELF_HOST_WINDOW_SECONDS) == 2
    assert await sh_mod._aincr("rate-limit-key", sh_mod._SELF_HOST_WINDOW_SECONDS) == 1
    assert expire_calls == [("rate-limit-key", 60)]


async def test_resolve_workspace_id_limits_to_one(client):
    """_resolve_workspace_id uses LIMIT 1."""
    import app.routes.self_host_research as sh_mod

    user = _FakeUser()
    pat = _FakePAT()
    pat.workspace_id = None
    captured: dict[str, Any] = {}

    class _StmtCapture:
        async def execute(self, stmt: Any) -> Any:
            captured["stmt"] = stmt
            return SimpleNamespace(scalar_one_or_none=lambda: 7)

    await sh_mod._resolve_workspace_id(_StmtCapture(), user, pat)
    compiled_params = captured["stmt"].compile(compile_kwargs={"literal_binds": True})
    compiled = str(compiled_params)
    assert "LIMIT 1" in compiled


def test_self_host_research_rate_limit_key_is_credential(client, monkeypatch):
    """Rate-limit counter uses the real credential, not the header separator."""
    import app.routes.self_host_research as sh_mod

    async def _resolve_any(_session: Any, _token: str) -> Any:
        return _FakePAT()

    monkeypatch.setattr(sh_mod, "resolve_pat", _resolve_any)
    monkeypatch.setattr(sh_mod, "_SELF_HOST_RATE_LIMIT_PER_MINUTE", 1)
    monkeypatch.setattr(sh_mod, "_SELF_HOST_WINDOW_SECONDS", 1)

    first_one = _call(client, token="token-one")
    first_two = _call(client, token="token-two")
    assert first_one.status_code == 200
    assert first_two.status_code == 200

    second_one = _call(client, token="token-one")
    assert second_one.status_code == 429


async def test_charge_self_host_research_zero_and_negative_cost_return_zero(
    client, fake_session
):
    """Zero or negative engine cost results return billed_micros 0."""
    import app.routes.self_host_research as sh_mod
    from app.capabilities.chainlens.research.schemas import ResearchOutput

    user = _FakeUser()
    user.credit_micros_balance = 10

    # No content + zero cost hits the early return.
    output_zero = ResearchOutput(
        status="insufficient_evidence",
        answer="",
        sources=[],
        cost_micros=0,
        cost_dollars=0.0,
        cost_basis=None,
        resolved_mode=None,
        mode_requested="balanced",
        tokens_total=None,
        tokens_prompt=None,
        tokens_completion=None,
        duration_ms=1000,
        first_token_time_ms=100,
        degraded=True,
        degradation_reason="insufficient_evidence",
    )
    billed = await sh_mod._charge_self_host_research(
        fake_session, user, 42, output_zero, "run-1"
    )
    assert billed == 0

    # Negative cost with content hits the second guard.
    output_neg = ResearchOutput(
        status="complete",
        answer="answer",
        sources=[],
        cost_micros=-1,
        cost_dollars=-0.000001,
        cost_basis="actual",
        resolved_mode="balanced",
        mode_requested="balanced",
        tokens_total=1,
        tokens_prompt=1,
        tokens_completion=0,
        duration_ms=1000,
        first_token_time_ms=100,
        degraded=False,
        degradation_reason=None,
    )
    billed = await sh_mod._charge_self_host_research(
        fake_session, user, 42, output_neg, "run-1"
    )
    assert billed == 0


async def test_charge_self_host_research_zero_cost_commits_session(client, fake_session):
    """A zero-cost audit row is committed even when no debit occurs."""
    import app.routes.self_host_research as sh_mod
    from app.capabilities.chainlens.research.schemas import ResearchOutput, Source

    user = _FakeUser()
    output = ResearchOutput(
        status="complete",
        answer="answer",
        sources=[Source(title="s", url="https://example.com")],
        cost_micros=0,
        cost_dollars=0.0,
        cost_basis="actual",
        resolved_mode="balanced",
        mode_requested="balanced",
        tokens_total=1,
        tokens_prompt=1,
        tokens_completion=0,
        duration_ms=1000,
        first_token_time_ms=100,
        degraded=False,
        degradation_reason=None,
    )

    billed = await sh_mod._charge_self_host_research(
        fake_session, user, 42, output, "run-1"
    )
    assert billed == 0
    assert fake_session.committed is True
    assert len(sh_mod._recorded) == 1


def test_self_host_research_no_workspace_403(client, monkeypatch, fake_session):
    """A self-host key with no workspace and no owner workspace is rejected."""
    import app.routes.self_host_research as sh_mod

    async def _resolve_pat(_session: Any, _token: str) -> Any:
        return SimpleNamespace(
            id=1,
            token_kind="self_host",
            workspace_id=None,
            user=_FakeUser(),
            last_used_at=None,
        )

    monkeypatch.setattr(sh_mod, "resolve_pat", _resolve_pat)
    fake_session.set_execute_result(None)

    response = _call(client)
    assert response.status_code == 403
    assert "no workspace" in response.text.lower()


def test_self_host_research_workspace_fallback_uses_owner_workspace(
    client, monkeypatch, fake_session
):
    """A PAT without workspace falls back to a workspace owned by the user."""
    import app.routes.self_host_research as sh_mod

    async def _resolve_pat(_session: Any, _token: str) -> Any:
        return SimpleNamespace(
            id=1,
            token_kind="self_host",
            workspace_id=None,
            user=_FakeUser(),
            last_used_at=None,
        )

    monkeypatch.setattr(sh_mod, "resolve_pat", _resolve_pat)
    fake_session.set_execute_result(99)

    response = _call(client)
    assert response.status_code == 200
    assert sh_mod._recorded[0]["workspace_id"] == 99


def test_self_host_research_post_call_insufficient_credits_402(client, monkeypatch):
    """An InsufficientCreditsError raised during post-call billing maps to 402."""
    import app.routes.self_host_research as sh_mod
    from app.services.wallet_credit import InsufficientCreditsError

    async def _apply_debit_raise(_session: Any, _user_id: Any, _cost_micros: int) -> int:
        raise InsufficientCreditsError(
            message="short",
            balance_micros=100,
            required_micros=72300,
        )

    monkeypatch.setattr(sh_mod, "apply_debit", _apply_debit_raise)

    response = _call(client)
    assert response.status_code == 402
    body = response.json()
    assert body["detail"]["error_code"] == "insufficient_credits"
    assert body["detail"]["balance_micros"] == 100
    assert body["detail"]["required_micros"] == 72300


def test_self_host_research_inactive_user_401(client, monkeypatch):
    """A PAT for an inactive user is rejected."""
    import app.routes.self_host_research as sh_mod

    user = _FakeUser()
    user.is_active = False

    async def _resolve_pat(_session: Any, _token: str) -> Any:
        return SimpleNamespace(
            id=1,
            token_kind="self_host",
            workspace_id=42,
            user=user,
            last_used_at=None,
        )

    monkeypatch.setattr(sh_mod, "resolve_pat", _resolve_pat)

    response = _call(client)
    assert response.status_code == 401
