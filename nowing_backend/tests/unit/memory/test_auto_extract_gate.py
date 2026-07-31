"""Unit tests for the auto-extract cost-control gate (Story 8.7).

Covers ``app.services.memory.extract_budget`` in isolation: the ordered gate
ladder, the workspace-scoped enqueue-side variant, error containment, and the
Redis-backed rate counter (including its in-memory fallback).

Gate contract under test (AR-6 / RS-1):
    async def check_extract_allowed(
        session, *, workspace, attributed_user_id
    ) -> ExtractGateResult          # .allowed: bool, .reason: str | None

Ordered gates (first block wins), all evaluated BEFORE any LLM call:
    1. anonymous (no billable owner)     -> reason="anonymous_unbilled"
    2. wallet spendable < min reserve    -> reason="insufficient_wallet"
    3. period spend >= budget cap        -> reason="budget_exceeded"
    4. rate count >= rate max            -> reason="rate_limited"

Note on gate 2: the wallet check is an *eligibility* gate, not a spend meter --
extraction never debits the wallet (AD-8 excludes memory from the debit
surface). See the module docstring of ``extract_budget`` for the full framing.

The ladder composes three seams these tests monkeypatch:
    extract_budget._wallet_spendable_micros(session, user_id) -> int
    extract_budget._period_spend_micros(session, workspace_id) -> int
    extract_budget._rate_count(workspace_id) -> int

``check_workspace_gates(session, *, workspace)`` is the principal-free
enqueue-side variant: budget + rate only, and it never fails closed.

**Test id / priority convention.** Every test docstring opens with
``{EPIC}.{STORY}-{LEVEL}-{SEQ} - P{n}/AC{n}:`` so `trace` can map ids to
acceptance criteria mechanically and `grep "P0/"` is exhaustive rather than
approximate. Seam-level tests that back an AC indirectly still carry the AC
they serve.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

import pytest

from tests.utils.fake_redis import install_fake_redis

pytestmark = pytest.mark.unit

_OWNER = UUID("00000000-0000-0000-0000-0000000000cc")
_WORKSPACE_ID = 1

# Threshold the gate compares the wallet against, and a balance comfortably
# above it. Named because "is this number meant to clear the floor, or to BE the
# floor?" is otherwise a trip to `_defaults` on every read -- and because the
# same intent was previously expressed as both 1_000_000 and 5_000_000.
_MIN_RESERVE_MICROS = 100
_FUNDED_SPENDABLE_MICROS = 1_000_000
_RATE_WINDOW_SECONDS = 3600


class _FakeWorkspace:
    """Minimal stand-in for ``app.db.Workspace`` (only ``.id`` is read)."""

    def __init__(
        self, workspace_id: int = _WORKSPACE_ID, owner_id: UUID | None = _OWNER
    ):
        self.id = workspace_id
        self.user_id = owner_id
        self.memory_auto_extract_enabled = True


class _BrokenWorkspace:
    """Stands in for a detached/expired ORM instance: reading ``.id`` raises."""

    @property
    def id(self):
        raise RuntimeError("instance is detached from its session")


def _seam(monkeypatch, *, spendable: int, spent: int, rate: int) -> None:
    """Stub the three collaborator seams the gate composes."""
    import app.services.memory.extract_budget as gate

    async def _wallet(_session, _user_id):
        return spendable

    async def _period(_session, _workspace_id):
        return spent

    async def _rate(_workspace_id):
        return rate

    monkeypatch.setattr(gate, "_wallet_spendable_micros", _wallet)
    monkeypatch.setattr(gate, "_period_spend_micros", _period)
    monkeypatch.setattr(gate, "_rate_count", _rate)


def _defaults(monkeypatch, **overrides: object) -> None:
    """Apply default-safe config (caps disabled), with per-test overrides.

    Pinned explicitly so these tests never depend on the ambient ``.env``.
    """
    from app.config import config

    values: dict[str, object] = {
        "MEMORY_AUTO_EXTRACT_MIN_RESERVE_MICROS": _MIN_RESERVE_MICROS,
        "MEMORY_AUTO_EXTRACT_BUDGET_MICROS": 0,
        "MEMORY_AUTO_EXTRACT_BUDGET_WINDOW": "day",
        "MEMORY_AUTO_EXTRACT_RATE_MAX": 0,
        "MEMORY_AUTO_EXTRACT_RATE_WINDOW_SECONDS": _RATE_WINDOW_SECONDS,
    }
    values.update(overrides)
    for key, val in values.items():
        monkeypatch.setattr(config, key, val)


@pytest.fixture(autouse=True)
def no_real_redis(monkeypatch):
    """Guarantee no test in this module can reach a real Redis.

    Autouse, and deliberately not merely available on request. This file is
    marked ``pytest.mark.unit`` — "pure logic tests, no DB or external services"
    — so a socket opened from here is a contract violation, not just a slow
    test. ``extract_budget`` caches a sync ``redis`` client in a module global
    and reads it whenever ``MEMORY_AUTO_EXTRACT_RATE_MAX > 0``, so a future test
    that raises that setting without stubbing the ``_rate_count`` seam would
    otherwise open ``config.REDIS_APP_URL`` and make its verdict a function of
    process-external state. That exact mistake already happened once in the
    sibling integration module; a per-test convention did not prevent it, so it
    is enforced structurally in both files now.

    Tests that need to control the counter can request this fixture by name and
    seed ``.store``, or call :func:`_failing_redis` for the fallback paths.
    """
    import app.services.memory.extract_budget as gate

    return install_fake_redis(monkeypatch, gate)


def _failing_redis(monkeypatch):
    """Re-install the double in failing mode to exercise the fallback paths."""
    import app.services.memory.extract_budget as gate

    return install_fake_redis(monkeypatch, gate, fail=True)


def _skip_lines(caplog) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if "memory_extract_skip" in record.getMessage()
    ]


# ---------------------------------------------------------------------------
# AC1 - Wallet pre-check
# ---------------------------------------------------------------------------


async def test_gate_blocks_when_wallet_below_min_reserve(monkeypatch):
    """8.7-UNIT-001 - P0/AC1: spendable below the min reserve blocks extraction."""
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch)
    _seam(monkeypatch, spendable=_MIN_RESERVE_MICROS - 50, spent=0, rate=0)

    result = await check_extract_allowed(
        object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is False
    assert result.reason == "insufficient_wallet"


async def test_gate_allows_when_wallet_covers_min_reserve(monkeypatch):
    """8.7-UNIT-002 - P0/AC1: spendable AT the min reserve allows (>= boundary)."""
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch)
    _seam(monkeypatch, spendable=_MIN_RESERVE_MICROS, spent=0, rate=0)

    result = await check_extract_allowed(
        object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is True
    assert result.reason is None


async def test_wallet_seam_clamps_negative_spendable(monkeypatch):
    """8.7-UNIT-003 - P2/AC1: a negative canonical balance is clamped to 0.

    ``wallet_credit.spendable_micros`` can return a negative difference; callers
    must only ever compare non-negative amounts.
    """
    import app.services.memory.extract_budget as gate
    from app.services import wallet_credit

    calls: list[object] = []

    async def _canonical(_session, user_id):
        calls.append(user_id)
        return -500

    monkeypatch.setattr(wallet_credit, "spendable_micros", _canonical)

    assert await gate._wallet_spendable_micros(object(), _OWNER) == 0
    assert calls == [_OWNER], "the gate must delegate, not re-implement the read"


async def test_wallet_seam_treats_missing_user_as_nothing_spendable(monkeypatch):
    """8.7-UNIT-004 - P2/AC1: a user_id that no longer resolves fails closed at 0.

    The canonical reader raises ``ValueError``; the gate must translate that to
    "nothing spendable" and reserve its wallet-*error* path for real query
    failures.
    """
    import app.services.memory.extract_budget as gate
    from app.services import wallet_credit

    async def _missing(_session, _user_id):
        raise ValueError("User with ID ... not found")

    monkeypatch.setattr(wallet_credit, "spendable_micros", _missing)

    assert await gate._wallet_spendable_micros(object(), _OWNER) == 0


# ---------------------------------------------------------------------------
# AC2 - Spend/budget cap per period
# ---------------------------------------------------------------------------


async def test_gate_blocks_when_period_spend_at_or_over_cap(monkeypatch):
    """8.7-UNIT-005 - P0/AC2: summed memory_create spend >= cap blocks."""
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch, MEMORY_AUTO_EXTRACT_BUDGET_MICROS=10_000)
    _seam(monkeypatch, spendable=_FUNDED_SPENDABLE_MICROS, spent=10_000, rate=0)

    result = await check_extract_allowed(
        object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is False
    assert result.reason == "budget_exceeded"


async def test_gate_allows_when_period_spend_under_cap(monkeypatch):
    """8.7-UNIT-006 - P1/AC2: spend one micro below the cap allows."""
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch, MEMORY_AUTO_EXTRACT_BUDGET_MICROS=10_000)
    _seam(monkeypatch, spendable=_FUNDED_SPENDABLE_MICROS, spent=9_999, rate=0)

    result = await check_extract_allowed(
        object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is True


async def test_gate_budget_disabled_by_default_no_gating(monkeypatch):
    """8.7-UNIT-007 - P1/AC2+AC6: cap unset/0 (default) applies no gating."""
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch, MEMORY_AUTO_EXTRACT_BUDGET_MICROS=0)
    # Even a huge historical spend must not block when the cap is disabled.
    _seam(monkeypatch, spendable=_FUNDED_SPENDABLE_MICROS, spent=999_999_999, rate=0)

    result = await check_extract_allowed(
        object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is True


@pytest.mark.parametrize(
    ("window", "expected_days"),
    [
        ("day", 1),
        ("week", 7),
        ("month", 30),
        # Config validation normalises unknown values, but the consumer must
        # not crash (or silently pick a longer window) if one ever reaches it.
        ("fortnight", 1),
    ],
)
async def test_period_window_start_maps_the_window_setting(
    monkeypatch, window, expected_days
):
    """8.7-UNIT-008 - P2/AC2: the rolling lookback honours day/week/month.

    Rolling, not calendar -- a burst right after midnight must not slip through
    (Dev Notes R4). ``month`` is a flat 30 days.
    """
    from app.services.memory.extract_budget import _period_window_start

    now = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)
    _defaults(monkeypatch, MEMORY_AUTO_EXTRACT_BUDGET_WINDOW=window)

    assert (now - _period_window_start(now)).days == expected_days


# ---------------------------------------------------------------------------
# AC3 - Time-based rate-limit
# ---------------------------------------------------------------------------


async def test_gate_blocks_when_rate_limit_reached(monkeypatch):
    """8.7-UNIT-009 - P1/AC3: window count AT the rate max blocks (>= boundary)."""
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch, MEMORY_AUTO_EXTRACT_RATE_MAX=5)
    _seam(monkeypatch, spendable=_FUNDED_SPENDABLE_MICROS, spent=0, rate=5)

    result = await check_extract_allowed(
        object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is False
    assert result.reason == "rate_limited"


async def test_gate_allows_under_rate_limit(monkeypatch):
    """8.7-UNIT-010 - P1/AC3: window count one below the rate max allows."""
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch, MEMORY_AUTO_EXTRACT_RATE_MAX=5)
    _seam(monkeypatch, spendable=_FUNDED_SPENDABLE_MICROS, spent=0, rate=4)

    result = await check_extract_allowed(
        object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is True


async def test_gate_rate_limit_disabled_by_default(monkeypatch):
    """8.7-UNIT-011 - P1/AC3+AC6: rate max unset/0 (default) applies no throttling."""
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch, MEMORY_AUTO_EXTRACT_RATE_MAX=0)
    _seam(monkeypatch, spendable=_FUNDED_SPENDABLE_MICROS, spent=0, rate=10_000)

    result = await check_extract_allowed(
        object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is True


async def test_rate_count_reads_the_documented_redis_key(monkeypatch, no_real_redis):
    """8.7-UNIT-012 - P2/AC3: the counter is read from the documented key.

    Pins ``nowing:memory_extract_rate:<workspace_id>`` so an operator can
    inspect or clear it, and so a rename cannot pass silently.
    """
    from app.services.memory.extract_budget import _rate_count

    _defaults(monkeypatch, MEMORY_AUTO_EXTRACT_RATE_MAX=5)
    client = no_real_redis
    client.store["nowing:memory_extract_rate:7"] = 4

    assert await _rate_count(7) == 4
    assert await _rate_count(8) == 0, "the counter must be per-workspace"


async def test_record_extraction_increments_and_refreshes_ttl(
    monkeypatch, no_real_redis
):
    """8.7-UNIT-013 - P1/AC3: each recorded extraction increments and re-sets the TTL.

    The TTL is refreshed on *every* increment, not only the first: an EXPIRE
    lost after a successful INCR would otherwise leave a key with no TTL that
    never decays, throttling the workspace permanently.

    Two increments in one test on purpose: "the TTL is set on the second call
    too" is the whole contract, so the sequence cannot be split without losing
    what is being asserted.
    """
    from app.services.memory.extract_budget import record_extraction

    window = 120
    _defaults(
        monkeypatch,
        MEMORY_AUTO_EXTRACT_RATE_MAX=5,
        MEMORY_AUTO_EXTRACT_RATE_WINDOW_SECONDS=window,
    )
    client = no_real_redis
    key = "nowing:memory_extract_rate:7"

    await record_extraction(7)
    assert client.store[key] == 1
    assert client.ttls[key] == window

    client.ttls.clear()
    await record_extraction(7)
    assert client.store[key] == 2
    assert client.ttls[key] == window, "TTL must be refreshed on every increment"


async def test_record_extraction_is_noop_when_rate_limit_disabled(monkeypatch):
    """8.7-UNIT-014 - P1/AC6: with the rate limit off, the path touches NEITHER backend.

    Installs a FAILING Redis double on purpose: a guard that only checks
    ``RATE_MAX <= 0`` on the fast path but still calls through on a boundary
    error (e.g. a mutated ``< 0``) would hit this client, get caught, and fall
    through to the in-memory fallback -- silently mutating ``_memory_hits``
    while the Redis-side assertion below stays green. Asserting ``_rate_count``
    afterwards closes that gap: it reads whichever backend the guard actually
    reached.
    """
    from app.services.memory.extract_budget import _rate_count, record_extraction

    _defaults(monkeypatch, MEMORY_AUTO_EXTRACT_RATE_MAX=0)
    client = _failing_redis(monkeypatch)  # any command would raise

    await record_extraction(7)

    assert client.store == {}
    assert client.ttls == {}
    assert await _rate_count(7) == 0, (
        "no backend -- Redis or in-memory fallback -- may be touched while the "
        "rate limit is disabled"
    )


async def test_rate_counter_falls_back_to_in_memory_when_redis_is_down(monkeypatch):
    """8.7-UNIT-015 - P1/AC3+AC6: unreachable Redis degrades to a per-worker window.

    Mirrors ``app.capabilities.core.access.rate_limit``: the rate-limit is an
    abuse guard, so it must neither block legitimate extraction nor silently
    stop counting.

    Drives read -> incr -> incr -> read in one test on purpose: the contract is
    that the fallback *accumulates across calls*, which a split into
    single-action tests could not express.
    """
    from app.services.memory.extract_budget import _rate_count, record_extraction

    _defaults(
        monkeypatch,
        MEMORY_AUTO_EXTRACT_RATE_MAX=5,
        MEMORY_AUTO_EXTRACT_RATE_WINDOW_SECONDS=120,
    )
    _failing_redis(monkeypatch)

    assert await _rate_count(7) == 0
    await record_extraction(7)
    await record_extraction(7)
    assert await _rate_count(7) == 2
    assert await _rate_count(8) == 0, "the fallback must stay per-workspace"


# ---------------------------------------------------------------------------
# AC4 - Anonymous attribution
# ---------------------------------------------------------------------------


async def test_gate_blocks_anonymous_turn_unbilled(monkeypatch):
    """8.7-UNIT-016 - P0/AC4: no billable owner -> reason=anonymous_unbilled.

    Also pins gate ORDER: spendable is 0, which would block on the wallet too,
    so only an anonymous check that runs FIRST yields this reason.
    """
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
# AC6 - Fail-safe & no-regression defaults
# ---------------------------------------------------------------------------


async def test_gate_allows_by_default_with_funded_wallet(monkeypatch):
    """8.7-UNIT-017 - P0/AC6: all caps at defaults + funded wallet behaves as baseline."""
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch)  # budget=0, rate=0, min_reserve=100
    _seam(monkeypatch, spendable=_FUNDED_SPENDABLE_MICROS, spent=0, rate=0)

    result = await check_extract_allowed(
        object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is True
    assert result.reason is None


async def test_gate_fails_closed_on_wallet_check_error(monkeypatch):
    """8.7-UNIT-018 - P1/AC6: an error in the wallet seam blocks, never raises."""
    import app.services.memory.extract_budget as gate
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch)

    async def _boom(_session, _user_id):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(gate, "_wallet_spendable_micros", _boom)

    result = await check_extract_allowed(
        object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is False
    assert result.reason == "insufficient_wallet"


async def test_gate_fails_closed_on_budget_check_error(monkeypatch):
    """8.7-UNIT-019 - P1/AC6: an error in the budget seam blocks extraction."""
    import app.services.memory.extract_budget as gate
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch, MEMORY_AUTO_EXTRACT_BUDGET_MICROS=10_000)
    _seam(monkeypatch, spendable=_FUNDED_SPENDABLE_MICROS, spent=0, rate=0)

    async def _boom(_session, _workspace_id):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(gate, "_period_spend_micros", _boom)

    result = await check_extract_allowed(
        object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is False
    assert result.reason == "budget_exceeded"


@pytest.mark.parametrize(
    ("config_key", "seam_name", "sentinel_reason"),
    [
        ("MEMORY_AUTO_EXTRACT_BUDGET_MICROS", "_period_spend_micros", "budget"),
        ("MEMORY_AUTO_EXTRACT_RATE_MAX", "_rate_count", "rate"),
    ],
)
async def test_gate_treats_a_negative_cap_as_disabled(
    monkeypatch, config_key, seam_name, sentinel_reason
):
    """8.7-UNIT-030 - P1/AC6: a negative budget/rate config is disabled, not "always over".

    Mutation-gate survivor (`<= 0` mutated to `== 0`): for any NON-negative
    value the two are equivalent, so only a negative config value can
    distinguish them. With `== 0`, a negative cap would skip the disabled
    short-circuit and fall through to the comparison seam -- for budget that
    means comparing spend against a negative ceiling, which `spent >= cap` (spent
    is never negative) satisfies unconditionally, silently blocking every
    extraction. Asserted here by making the seam raise if it is ever called: a
    negative cap must short-circuit exactly like zero does.
    """
    import app.services.memory.extract_budget as gate
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch, **{config_key: -1})
    _seam(monkeypatch, spendable=_FUNDED_SPENDABLE_MICROS, spent=0, rate=0)

    async def _boom(*_args, **_kwargs):
        raise AssertionError(f"{seam_name} must not be consulted when {config_key} < 0")

    monkeypatch.setattr(gate, seam_name, _boom)

    result = await check_extract_allowed(
        object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is True, sentinel_reason


async def test_gate_enabled_rate_max_of_one_blocks_at_the_threshold(monkeypatch):
    """8.7-UNIT-031 - P1/AC3: rate_max=1 is a real, enabled limit -- not disabled.

    Mutation-gate survivor (`<= 0` mutated to `<= 1`): the mutant treats
    ``rate_max=1`` as disabled and skips the comparison entirely, so extraction
    would proceed no matter how high ``rate`` is. The boundary immediately
    above the disabled sentinel is exactly where that divergence is observable.
    """
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch, MEMORY_AUTO_EXTRACT_RATE_MAX=1)
    _seam(monkeypatch, spendable=_FUNDED_SPENDABLE_MICROS, spent=0, rate=1)

    result = await check_extract_allowed(
        object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is False
    assert result.reason == "rate_limited"


async def test_gate_blocks_when_rate_strictly_exceeds_max(monkeypatch):
    """8.7-UNIT-032 - P1/AC3: rate ABOVE the max blocks, not just rate AT the max.

    Mutation-gate survivors (`rate >= rate_max` mutated to `rate == rate_max` and
    to `rate is rate_max`): the existing at-the-boundary test (rate == rate_max)
    cannot distinguish `>=` from `==` or `is`, since all three agree there. Only
    a rate strictly past the max does.
    """
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch, MEMORY_AUTO_EXTRACT_RATE_MAX=5)
    _seam(monkeypatch, spendable=_FUNDED_SPENDABLE_MICROS, spent=0, rate=6)

    result = await check_extract_allowed(
        object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is False
    assert result.reason == "rate_limited"


async def test_gate_fails_closed_on_rate_check_error(monkeypatch):
    """8.7-UNIT-033 - P1/AC6: an error in the rate seam blocks, mirroring the budget case.

    Mutation-gate survivors in ``_check_rate``'s except branch (`if fail_closed`
    inverted to `if not fail_closed`; `allowed=False` flipped to `allowed=True`;
    `except Exception` narrowed to a type nothing raises) all require a test
    where ``_rate_count`` actually raises through the fail-closed
    (``check_extract_allowed``) path -- ``test_gate_fails_closed_on_budget_check_error``
    covers the analogous budget branch but the rate branch had no equivalent.
    Also kills the ``fail_closed=True`` -> ``False`` argument mutation at the
    ``check_extract_allowed`` call site: with that mutant, ``_check_rate``'s
    except returns ``None`` instead of a blocking verdict, and
    ``check_extract_allowed`` would fall through to ``allowed=True`` instead of
    stopping here.
    """
    import app.services.memory.extract_budget as gate
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch, MEMORY_AUTO_EXTRACT_RATE_MAX=5)
    _seam(monkeypatch, spendable=_FUNDED_SPENDABLE_MICROS, spent=0, rate=0)

    async def _boom(_workspace_id):
        raise RuntimeError("redis unavailable")

    monkeypatch.setattr(gate, "_rate_count", _boom)

    result = await check_extract_allowed(
        object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is False
    assert result.reason == "rate_limited"


async def test_gate_contains_an_error_raised_by_check_budget_itself(monkeypatch):
    """8.7-UNIT-034 - P2/AC6: the outer defense-in-depth catch-all actually catches.

    Mutation-gate survivors in ``check_extract_allowed``'s final ``except
    Exception`` (narrowed to a type nothing raises; ``allowed=False`` flipped to
    ``allowed=True``): every existing error test raises from a *seam* one level
    down, which is caught by ``_check_budget``/``_check_rate``'s own try/except
    before it ever reaches this outer layer. To exercise the outer layer itself,
    the whole helper function must raise -- simulating a bug in ``_check_budget``
    that its own error handling didn't anticipate.
    """
    import app.services.memory.extract_budget as gate
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch)
    _seam(monkeypatch, spendable=_FUNDED_SPENDABLE_MICROS, spent=0, rate=0)

    async def _boom(*_args, **_kwargs):
        raise RuntimeError("unexpected bug inside _check_budget")

    monkeypatch.setattr(gate, "_check_budget", _boom)

    result = await check_extract_allowed(
        object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is False
    assert result.reason == "gate_error"


async def test_budget_seam_not_consulted_when_cap_disabled(monkeypatch):
    """8.7-UNIT-020 - P1/AC6: with the cap off, a broken budget seam is never called.

    Guards the short-circuit: at defaults the gate must not pay for -- or be
    endangered by -- the aggregate query at all.
    """
    import app.services.memory.extract_budget as gate
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch, MEMORY_AUTO_EXTRACT_BUDGET_MICROS=0)
    _seam(monkeypatch, spendable=_FUNDED_SPENDABLE_MICROS, spent=0, rate=0)

    async def _boom(_session, _workspace_id):
        raise AssertionError("budget seam must not be consulted when the cap is 0")

    monkeypatch.setattr(gate, "_period_spend_micros", _boom)

    result = await check_extract_allowed(
        object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is True


async def test_gate_contains_an_unreadable_workspace(monkeypatch):
    """8.7-UNIT-021 - P1/AC6: a detached ORM instance fails closed instead of raising.

    Story 3.13 will call this gate from a second (scraper-run) path, so an
    expired/detached ``Workspace`` must resolve to a verdict, not an exception
    escaping into the caller.
    """
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch)
    _seam(monkeypatch, spendable=_FUNDED_SPENDABLE_MICROS, spent=0, rate=0)

    result = await check_extract_allowed(
        object(), workspace=_BrokenWorkspace(), attributed_user_id=_OWNER
    )

    assert result.allowed is False
    assert result.reason == "gate_error"


# ---------------------------------------------------------------------------
# AC7 - Enqueue-side variant: workspace-scoped caps only, never fails closed
# ---------------------------------------------------------------------------


async def test_workspace_gates_ignore_wallet_and_anonymous(monkeypatch):
    """8.7-UNIT-022 - P1/AC7: the enqueue-side check evaluates no principal.

    The enqueue site only knows the streaming caller, who is not guaranteed to
    be the author of the turn's user message, so a wallet/anonymous verdict
    there could drop a turn the authoritative gate would allow. It must also not
    add a ``User`` lookup to the shielded teardown path.
    """
    import app.services.memory.extract_budget as gate
    from app.services.memory.extract_budget import check_workspace_gates

    _defaults(monkeypatch)
    _seam(monkeypatch, spendable=0, spent=0, rate=0)

    wallet_calls: list[object] = []

    async def _spy(_session, user_id):
        wallet_calls.append(user_id)
        return 0

    monkeypatch.setattr(gate, "_wallet_spendable_micros", _spy)

    result = await check_workspace_gates(object(), workspace=_FakeWorkspace())

    assert result.allowed is True
    assert wallet_calls == [], "the enqueue-side gate must not read the wallet"


async def test_workspace_gates_block_on_budget(monkeypatch):
    """8.7-UNIT-023 - P1/AC7: the fast-path still honours the budget cap."""
    from app.services.memory.extract_budget import check_workspace_gates

    _defaults(monkeypatch, MEMORY_AUTO_EXTRACT_BUDGET_MICROS=10_000)
    _seam(monkeypatch, spendable=0, spent=10_000, rate=0)

    result = await check_workspace_gates(object(), workspace=_FakeWorkspace())

    assert result.allowed is False
    assert result.reason == "budget_exceeded"


async def test_workspace_gates_block_on_rate(monkeypatch):
    """8.7-UNIT-024 - P1/AC7: the fast-path still honours the rate limit."""
    from app.services.memory.extract_budget import check_workspace_gates

    _defaults(monkeypatch, MEMORY_AUTO_EXTRACT_RATE_MAX=3)
    _seam(monkeypatch, spendable=0, spent=0, rate=3)

    result = await check_workspace_gates(object(), workspace=_FakeWorkspace())

    assert result.allowed is False
    assert result.reason == "rate_limited"


async def test_workspace_gates_never_fail_closed(monkeypatch):
    """8.7-UNIT-025 - P1/AC7: uncertainty at the fast-path resolves to "enqueue anyway".

    Blocking here would drop the turn before the authoritative gate ever runs,
    inverting the documented defense-in-depth split.
    """
    import app.services.memory.extract_budget as gate
    from app.services.memory.extract_budget import check_workspace_gates

    _defaults(monkeypatch, MEMORY_AUTO_EXTRACT_BUDGET_MICROS=10_000)
    _seam(monkeypatch, spendable=_FUNDED_SPENDABLE_MICROS, spent=0, rate=0)

    async def _boom(_session, _workspace_id):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(gate, "_period_spend_micros", _boom)

    result = await check_workspace_gates(object(), workspace=_FakeWorkspace())

    assert result.allowed is True
    assert result.reason is None


async def test_workspace_gates_contain_an_unreadable_workspace(monkeypatch):
    """8.7-UNIT-026 - P2/AC7: even an unexpected error falls through to "enqueue anyway"."""
    from app.services.memory.extract_budget import check_workspace_gates

    _defaults(monkeypatch, MEMORY_AUTO_EXTRACT_BUDGET_MICROS=10_000)
    _seam(monkeypatch, spendable=_FUNDED_SPENDABLE_MICROS, spent=0, rate=0)

    result = await check_workspace_gates(object(), workspace=_BrokenWorkspace())

    assert result.allowed is True


# ---------------------------------------------------------------------------
# AC8 - Observability: machine-parseable reasons
# ---------------------------------------------------------------------------


async def test_gate_reason_vocabulary_is_stable():
    """8.7-UNIT-027 - P1/AC8: the exported reason vocabulary is fixed.

    Five of these are the skip kinds AC-8 enumerates (wallet / budget / rate /
    anon / disabled). ``disabled`` lives here even though the two call sites
    emit it -- the flag check runs before the gate -- so log consumers key off
    one vocabulary. ``gate_error`` is a sixth identifier that AC-8 does not
    list: it is not a skip *decision* but the AUTHORITATIVE gate's own
    containment verdict under AC-6 (a seam raising, or a detached
    ``Workspace``), exported for the same reason -- so a consumer can
    distinguish "policy blocked this" from "the gate could not decide". It is
    service-side only: ``check_workspace_gates`` never returns it, because the
    enqueue-side fast-path resolves every error to ``allowed=True`` (asserted by
    8.7-UNIT-025 and 8.7-UNIT-026).
    """
    from app.services.memory import extract_budget as gate

    assert gate.REASON_ANONYMOUS_UNBILLED == "anonymous_unbilled"
    assert gate.REASON_INSUFFICIENT_WALLET == "insufficient_wallet"
    assert gate.REASON_BUDGET_EXCEEDED == "budget_exceeded"
    assert gate.REASON_RATE_LIMITED == "rate_limited"
    assert gate.REASON_DISABLED == "disabled"
    assert gate.REASON_GATE_ERROR == "gate_error"


async def test_gate_reasons_are_stable_identifiers(monkeypatch, caplog):
    """8.7-UNIT-028 - P1/AC8: a block resolves to THE specific reason and logs it once.

    Asserting membership in the reason set would pass on any of the four, so a
    gate-ordering or wrong-reason regression would stay green. This setup -- a
    funded wallet, spend over a cap of 1, no rate limit -- has exactly one
    correct answer.
    """
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch, MEMORY_AUTO_EXTRACT_BUDGET_MICROS=1)
    _seam(monkeypatch, spendable=_FUNDED_SPENDABLE_MICROS, spent=1_000, rate=0)

    with caplog.at_level(logging.INFO):
        result = await check_extract_allowed(
            object(), workspace=_FakeWorkspace(), attributed_user_id=_OWNER
        )

    assert result.allowed is False
    assert result.reason == "budget_exceeded"

    lines = _skip_lines(caplog)
    assert len(lines) == 1, f"AC-8 requires a single structured line, got {lines}"
    assert "reason=budget_exceeded" in lines[0]
    assert f"workspace_id={_WORKSPACE_ID}" in lines[0]
    assert "spent=1000" in lines[0]
    assert "cap=1" in lines[0]


@pytest.mark.parametrize(
    ("overrides", "seams", "attributed_user_id", "expected"),
    [
        ({}, {"spendable": 0, "spent": 0, "rate": 0}, None, "anonymous_unbilled"),
        ({}, {"spendable": 0, "spent": 0, "rate": 0}, _OWNER, "insufficient_wallet"),
        (
            {"MEMORY_AUTO_EXTRACT_BUDGET_MICROS": 10},
            {"spendable": _FUNDED_SPENDABLE_MICROS, "spent": 10, "rate": 0},
            _OWNER,
            "budget_exceeded",
        ),
        (
            {"MEMORY_AUTO_EXTRACT_RATE_MAX": 2},
            {"spendable": _FUNDED_SPENDABLE_MICROS, "spent": 0, "rate": 2},
            _OWNER,
            "rate_limited",
        ),
    ],
)
async def test_every_block_logs_reason_and_workspace_id(
    monkeypatch, caplog, overrides, seams, attributed_user_id, expected
):
    """8.7-UNIT-029 - P1/AC8: every gate block emits one line with reason + workspace_id."""
    from app.services.memory.extract_budget import check_extract_allowed

    _defaults(monkeypatch, **overrides)
    _seam(monkeypatch, **seams)

    with caplog.at_level(logging.INFO):
        result = await check_extract_allowed(
            object(),
            workspace=_FakeWorkspace(),
            attributed_user_id=attributed_user_id,
        )

    assert result.reason == expected
    lines = _skip_lines(caplog)
    assert len(lines) == 1
    assert f"reason={expected}" in lines[0]
    assert f"workspace_id={_WORKSPACE_ID}" in lines[0]
    assert "stage=service" in lines[0]
