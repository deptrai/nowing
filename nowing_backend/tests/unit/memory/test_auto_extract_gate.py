"""Red-phase unit scaffolds for the auto-extract cost-control gate (Story 8.7).

These describe the intended contract of the NEW gate module
``app.services.memory.extract_budget`` (``check_extract_allowed`` +
``ExtractGateResult``) that does NOT exist yet. Every test is marked
``@pytest.mark.skip`` so the suite collects cleanly (red phase). A developer
removes the skip on the task they are activating; the test then FAILS until the
gate is implemented — this is the intended TDD red phase.

Gate contract under test (AR-6 / RS-1):
    async def check_extract_allowed(
        session, *, workspace, attributed_user_id
    ) -> ExtractGateResult          # .allowed: bool, .reason: str | None

Ordered gates (first block wins), all evaluated BEFORE any LLM call:
    1. anonymous (no billable owner)     -> reason="anonymous_unbilled"
    2. wallet spendable < min reserve    -> reason="insufficient_wallet"
    3. period spend >= budget cap        -> reason="budget_exceeded"
    4. rate count >= rate max            -> reason="rate_limited"

The gate is expected to compose three seams the tests monkeypatch:
    extract_budget._wallet_spendable_micros(session, user_id) -> int
    extract_budget._period_spend_micros(session, workspace_id) -> int
    extract_budget._rate_count(workspace_id) -> int
"""

from __future__ import annotations

from uuid import UUID

import pytest

pytestmark = pytest.mark.unit

_OWNER = UUID("00000000-0000-0000-0000-0000000000cc")
_WORKSPACE_ID = 1


class _FakeWorkspace:
    """Minimal stand-in for ``app.db.Workspace`` (only billing fields matter)."""

    def __init__(self, workspace_id: int = _WORKSPACE_ID, owner_id: UUID | None = _OWNER):
        self.id = workspace_id
        self.user_id = owner_id
        self.memory_auto_extract_enabled = True


def _seam(monkeypatch, *, spendable: int, spent: int, rate: int) -> None:
    """Stub the three collaborator seams the gate composes."""
    import app.services.memory.extract_budget as gate

    async def _wallet(_session, _user_id):
        return spendable

    async def _period(_session, _workspace_id):
        return spent

    async def _rate(_workspace_id):
        return rate

    monkeypatch.setattr(gate, "_wallet_spendable_micros", _wallet, raising=False)
    monkeypatch.setattr(gate, "_period_spend_micros", _period, raising=False)
    monkeypatch.setattr(gate, "_rate_count", _rate, raising=False)


def _defaults(monkeypatch, **overrides: int) -> None:
    """Apply default-safe config (caps disabled), with per-test overrides."""
    from app.config import config

    values = {
        "MEMORY_AUTO_EXTRACT_MIN_RESERVE_MICROS": 100,
        "MEMORY_AUTO_EXTRACT_BUDGET_MICROS": 0,
        "MEMORY_AUTO_EXTRACT_RATE_MAX": 0,
        "MEMORY_AUTO_EXTRACT_RATE_WINDOW_SECONDS": 3600,
    }
    values.update(overrides)
    for key, val in values.items():
        monkeypatch.setattr(config, key, val, raising=False)


# ---------------------------------------------------------------------------
# AC1 — Wallet pre-check
# ---------------------------------------------------------------------------


async def test_gate_blocks_when_wallet_below_min_reserve(monkeypatch):
    """P0/AC1: spendable balance below the min reserve blocks extraction."""
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch, MEMORY_AUTO_EXTRACT_MIN_RESERVE_MICROS=100)
    _seam(monkeypatch, spendable=50, spent=0, rate=0)

    result = await check_extract_allowed(
        object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is False
    assert result.reason == "insufficient_wallet"


async def test_gate_allows_when_wallet_covers_min_reserve(monkeypatch):
    """P0/AC1: spendable balance at/above the min reserve allows extraction."""
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch, MEMORY_AUTO_EXTRACT_MIN_RESERVE_MICROS=100)
    _seam(monkeypatch, spendable=100, spent=0, rate=0)

    result = await check_extract_allowed(
        object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is True
    assert result.reason is None


# ---------------------------------------------------------------------------
# AC2 — Spend/budget cap per period
# ---------------------------------------------------------------------------


async def test_gate_blocks_when_period_spend_at_or_over_cap(monkeypatch):
    """P0/AC2: summed memory_create spend >= cap blocks extraction."""
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch, MEMORY_AUTO_EXTRACT_BUDGET_MICROS=10_000)
    _seam(monkeypatch, spendable=1_000_000, spent=10_000, rate=0)

    result = await check_extract_allowed(
        object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is False
    assert result.reason == "budget_exceeded"


async def test_gate_allows_when_period_spend_under_cap(monkeypatch):
    """P1/AC2: spend below the cap allows extraction."""
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch, MEMORY_AUTO_EXTRACT_BUDGET_MICROS=10_000)
    _seam(monkeypatch, spendable=1_000_000, spent=9_999, rate=0)

    result = await check_extract_allowed(
        object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is True


async def test_gate_budget_disabled_by_default_no_gating(monkeypatch):
    """P1/AC2+AC6: cap unset/0 (default) applies no budget gating."""
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch, MEMORY_AUTO_EXTRACT_BUDGET_MICROS=0)
    # Even a huge historical spend must not block when the cap is disabled.
    _seam(monkeypatch, spendable=1_000_000, spent=999_999_999, rate=0)

    result = await check_extract_allowed(
        object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is True


# ---------------------------------------------------------------------------
# AC3 — Time-based rate-limit
# ---------------------------------------------------------------------------


async def test_gate_blocks_when_rate_limit_reached(monkeypatch):
    """P1/AC3: window count >= rate max blocks extraction."""
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch, MEMORY_AUTO_EXTRACT_RATE_MAX=5)
    _seam(monkeypatch, spendable=1_000_000, spent=0, rate=5)

    result = await check_extract_allowed(
        object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is False
    assert result.reason == "rate_limited"


async def test_gate_allows_under_rate_limit(monkeypatch):
    """P1/AC3: window count below rate max allows extraction."""
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch, MEMORY_AUTO_EXTRACT_RATE_MAX=5)
    _seam(monkeypatch, spendable=1_000_000, spent=0, rate=4)

    result = await check_extract_allowed(
        object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is True


async def test_gate_rate_limit_disabled_by_default(monkeypatch):
    """P1/AC3+AC6: rate max unset/0 (default) applies no throttling."""
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch, MEMORY_AUTO_EXTRACT_RATE_MAX=0)
    _seam(monkeypatch, spendable=1_000_000, spent=0, rate=10_000)

    result = await check_extract_allowed(
        object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is True


# ---------------------------------------------------------------------------
# AC4 — Anonymous attribution
# ---------------------------------------------------------------------------


async def test_gate_blocks_anonymous_turn_unbilled(monkeypatch):
    """P0/AC4: no billable owner -> block with reason=anonymous_unbilled."""
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch)
    _seam(monkeypatch, spendable=0, spent=0, rate=0)
    anon_workspace = _FakeWorkspace(owner_id=None)

    result = await check_extract_allowed(
        object(), workspace=anon_workspace, attributed_user_id=None
    )

    assert result.allowed is False
    assert result.reason == "anonymous_unbilled"


# ---------------------------------------------------------------------------
# AC6 — Fail-safe & no-regression defaults
# ---------------------------------------------------------------------------


async def test_gate_allows_by_default_with_funded_wallet(monkeypatch):
    """P0/AC6: all caps at defaults + funded wallet behaves like baseline (allow)."""
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch)  # budget=0, rate=0, min_reserve=100
    _seam(monkeypatch, spendable=5_000_000, spent=0, rate=0)

    result = await check_extract_allowed(
        object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is True
    assert result.reason is None


async def test_gate_fails_closed_on_wallet_check_error(monkeypatch):
    """P1/AC6: an error inside the wallet seam blocks extraction, never raises."""
    import app.services.memory.extract_budget as gate
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch)

    async def _boom(_session, _user_id):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(gate, "_wallet_spendable_micros", _boom, raising=False)

    result = await check_extract_allowed(
        object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is False
    assert result.reason == "insufficient_wallet"


# ---------------------------------------------------------------------------
# AC8 — Observability: machine-parseable reasons
# ---------------------------------------------------------------------------


async def test_gate_reasons_are_stable_identifiers(monkeypatch):
    """P1/AC8: block reasons are drawn from the documented reason set."""
    from app.services.memory.extract_budget import check_extract_allowed

    allowed_reasons = {
        "anonymous_unbilled",
        "insufficient_wallet",
        "budget_exceeded",
        "rate_limited",
    }

    _defaults(monkeypatch, MEMORY_AUTO_EXTRACT_BUDGET_MICROS=1)
    _seam(monkeypatch, spendable=1_000_000, spent=1_000, rate=0)

    result = await check_extract_allowed(
        object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is False
    assert result.reason in allowed_reasons
