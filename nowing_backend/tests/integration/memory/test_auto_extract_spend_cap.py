"""Integration tests for auto-extract cost controls (Story 8.7).

Exercises ``MemoryExtractionService.extract_from_turn`` (and the enqueue-side
short-circuit in ``finalize_assistant_message``) end-to-end against the memory
subsystem, asserting that the spend/budget cap, wallet pre-check, time
rate-limit, and anonymous-skip behaviours gate extraction BEFORE any LLM call.

Note the asymmetry the two call sites deliberately have: the authoritative
service-side gate evaluates all four checks, while the enqueue-side fast-path
evaluates only the workspace-scoped caps (budget, rate) and never fails closed.
It carries no principal, because the streaming caller is not guaranteed to be
the author of the turn's user message. So a wallet-based block is observable at
the service level only; enqueue-side tests use the budget cap instead.

**Hermeticity.** Two autouse fixtures make isolation structural rather than
per-test discipline: ``pinned_gate_config`` pins every setting an assertion
depends on, and ``no_real_redis`` installs an in-process Redis double so no test
-- present or future -- can open a socket to ``config.REDIS_APP_URL`` even when
it raises ``MEMORY_AUTO_EXTRACT_RATE_MAX`` above zero.

Reuses the shared memory fixtures (``db_session``, ``db_workspace``, ``db_user``)
from ``tests/integration/conftest.py`` and the local ``chat_turn`` /
``patched_embeddings`` helpers below. Does NOT modify any shared conftest.

**Test id / priority convention.** Every test docstring opens with
``{EPIC}.{STORY}-{LEVEL}-{SEQ} - P{n}/AC{n}:`` so `trace` can map ids to
acceptance criteria mechanically and `grep "P0/"` is exhaustive.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from tests.utils.fake_redis import install_fake_redis

pytestmark = [pytest.mark.integration, pytest.mark.memory]

# The confidence the fixture fact carries, and the threshold pinned below it.
# The *relationship* between these two is what makes every "extraction proceeds"
# assertion in this file work: `extraction.py` keeps only facts whose confidence
# is >= the threshold. The fact JSON is built from the constant, and the
# invariant is asserted at import, so the two cannot drift apart silently --
# raising the fact's confidence used to be able to empty the filter and turn
# four tests red with nothing pointing at the cause.
_FACT_CONFIDENCE = 0.95
_CONFIDENCE_THRESHOLD = 0.7

_HIGH_CONFIDENCE_FACT = (
    '[{"content":"Competitor X raised prices by 10% in Q2 2026.",'
    '"type":"semantic","tags":["competitor","pricing"],'
    f'"confidence":{_FACT_CONFIDENCE}}}]'
)

assert _CONFIDENCE_THRESHOLD < _FACT_CONFIDENCE, (
    "the fixture fact must clear the pinned confidence threshold, otherwise "
    "every 'extraction proceeds' assertion in this file fails for a reason "
    "unrelated to the cost-control gate under test"
)

_FUNDED_BALANCE_MICROS = 5_000_000
_MIN_RESERVE_MICROS = 100
_RATE_WINDOW_SECONDS = 3600

# The logger owning the enqueue-side try/except that _assert_no_swallowed_exception
# probes. Scoped by name so ambient ERROR output from SQLAlchemy/asyncpg or any
# other component cannot fail an assertion about THIS code path.
_FINALIZE_LOGGER = "app.tasks.chat.streaming.flows.shared.assistant_finalize"


# ---------------------------------------------------------------------------
# Autouse hermeticity fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def pinned_gate_config(monkeypatch):
    """Pin every setting these tests' assertions depend on.

    Without this the verdicts depend on the ambient ``.env``: a
    ``MEMORY_AUTO_EXTRACT_MIN_RESERVE_MICROS`` above the funded fixtures would
    turn the "proceeds" cases red, and -- less obviously -- a
    ``MEMORY_AUTO_EXTRACT_CONFIDENCE`` above the fixture fact's 0.95 would empty
    the qualifying-facts filter in ``extraction.py`` and silently break four
    "proceeds" assertions without touching a line of test code.
    """
    from app.config import config

    for key, value in (
        ("MEMORY_AUTO_EXTRACT_ENABLED", True),
        ("MEMORY_AUTO_EXTRACT_CONFIDENCE", _CONFIDENCE_THRESHOLD),
        ("MEMORY_AUTO_EXTRACT_MAX_ITEMS", 3),
        ("MEMORY_AUTO_EXTRACT_MIN_RESERVE_MICROS", _MIN_RESERVE_MICROS),
        ("MEMORY_AUTO_EXTRACT_BUDGET_MICROS", 0),
        ("MEMORY_AUTO_EXTRACT_BUDGET_WINDOW", "day"),
        ("MEMORY_AUTO_EXTRACT_RATE_MAX", 0),
        ("MEMORY_AUTO_EXTRACT_RATE_WINDOW_SECONDS", _RATE_WINDOW_SECONDS),
    ):
        monkeypatch.setattr(config, key, value)


@pytest.fixture(autouse=True)
def no_real_redis(monkeypatch):
    """Guarantee no test in this module can reach a real Redis.

    ``extract_budget`` caches a sync ``redis`` client in a module global and
    reads ``nowing:memory_extract_rate:<workspace_id>`` whenever
    ``MEMORY_AUTO_EXTRACT_RATE_MAX > 0``. A test that raises that setting
    without stubbing the seam would otherwise make its verdict a function of
    process-external state nobody seeds or cleans, cache a live client into the
    module for the rest of the session, and -- because redis-py is built with no
    ``socket_connect_timeout`` -- hang on a blackholed host instead of failing
    fast.

    Autouse rather than opt-in on purpose: this is the class of mistake that is
    easy to reintroduce and invisible when it passes (in CI, with no Redis
    service, the live read merely falls back and the test goes green for a
    reason nobody asserted).

    Yields the double so a test can seed ``.store`` or assert on ``.ttls``.
    """
    import app.services.memory.extract_budget as gate

    return install_fake_redis(monkeypatch, gate)


# ---------------------------------------------------------------------------
# Data fixtures and factories
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def chat_turn(db_session, db_workspace, db_user):
    """A user+assistant message pair sharing one ``turn_id`` (owner-authored)."""
    from app.db import NewChatMessage, NewChatMessageRole, NewChatThread

    thread = NewChatThread(
        title="Spend-Cap Test",
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
    )
    db_session.add(thread)
    await db_session.flush()

    turn_id = "chat:turn:8-7"
    user_message = NewChatMessage(
        thread_id=thread.id,
        role=NewChatMessageRole.USER,
        content=[{"type": "text", "text": "Competitor X raised prices by 10%."}],
        turn_id=turn_id,
        author_id=db_user.id,
    )
    assistant_message = NewChatMessage(
        thread_id=thread.id,
        role=NewChatMessageRole.ASSISTANT,
        content=[
            {"type": "text", "text": "Yes, competitor X raised prices 10% in Q2 2026."}
        ],
        turn_id=turn_id,
    )
    db_session.add(user_message)
    db_session.add(assistant_message)
    await db_session.flush()
    return thread, user_message, assistant_message


@pytest_asyncio.fixture
async def anon_chat_turn(db_session, db_workspace):
    """A turn whose user message has NO author (anonymous / no billable owner)."""
    from app.db import NewChatMessage, NewChatMessageRole, NewChatThread

    thread = NewChatThread(title="Anon Turn", workspace_id=db_workspace.id)
    db_session.add(thread)
    await db_session.flush()

    turn_id = "chat:turn:8-7-anon"
    user_message = NewChatMessage(
        thread_id=thread.id,
        role=NewChatMessageRole.USER,
        content=[{"type": "text", "text": "Remember I like dark mode."}],
        turn_id=turn_id,
        author_id=None,
    )
    assistant_message = NewChatMessage(
        thread_id=thread.id,
        role=NewChatMessageRole.ASSISTANT,
        content=[{"type": "text", "text": "Noted -- you prefer dark mode."}],
        turn_id=turn_id,
    )
    db_session.add(user_message)
    db_session.add(assistant_message)
    await db_session.flush()
    return thread, user_message, assistant_message


@pytest_asyncio.fixture
async def funded_wallet(db_session, db_user):
    """Owner wallet comfortably above the min reserve.

    Sets BOTH balance and reserved so "is zeroing `reserved` load-bearing?" has
    one answer in one place -- the previous per-test copies disagreed.
    """
    db_user.credit_micros_balance = _FUNDED_BALANCE_MICROS
    db_user.credit_micros_reserved = 0
    await db_session.flush()
    return db_user


@pytest_asyncio.fixture
async def empty_wallet(db_session, db_user):
    """Owner wallet with nothing spendable (below the min reserve)."""
    db_user.credit_micros_balance = 0
    db_user.credit_micros_reserved = 0
    await db_session.flush()
    return db_user


@pytest_asyncio.fixture
async def disabled_workspace(db_session, db_workspace):
    """Workspace with the per-workspace auto-extract flag turned off (AC-5)."""
    db_workspace.memory_auto_extract_enabled = False
    await db_session.flush()
    return db_workspace


@pytest_asyncio.fixture
async def seed_memory_spend(db_session, db_workspace, db_user):
    """Factory: record prior in-period ``memory_create`` spend for the workspace.

    Owns the zero-valued token columns so callers state only what matters --
    the cost -- instead of repeating an 11-line row construction.
    """

    async def _seed(cost_micros: int):
        from app.db import TokenUsage

        row = TokenUsage(
            usage_type="memory_create",
            workspace_id=db_workspace.id,
            user_id=db_user.id,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost_micros=cost_micros,
        )
        db_session.add(row)
        await db_session.flush()
        return row

    return _seed


@pytest.fixture
def record_extraction_spy(monkeypatch):
    """Replace ``extraction.record_extraction`` with a recorder.

    Returns the list of workspace ids it was called with, so a test can assert
    on *whether and how often* the rate counter was advanced without depending
    on the counter backend at all.
    """
    import app.services.memory.extraction as extraction_module

    recorded: list[int] = []

    async def _spy(workspace_id):
        recorded.append(workspace_id)

    monkeypatch.setattr(extraction_module, "record_extraction", _spy)
    return recorded


@pytest.fixture
def patched_embeddings(monkeypatch):
    """Deterministic embeddings so persistence works without a real model."""

    def _fake_embed_texts(texts):
        return [[0.1] * 384 for _ in texts]

    monkeypatch.setattr("app.services.memory.repository.embed_texts", _fake_embed_texts)
    return _fake_embed_texts


@pytest.fixture
def fake_llm(monkeypatch):
    """Patch ``get_agent_llm`` to return an AsyncMock; used to assert (non-)calls."""
    llm = AsyncMock()
    llm.ainvoke.return_value = type("FakeMsg", (), {"content": _HIGH_CONFIDENCE_FACT})()
    monkeypatch.setattr(
        "app.services.memory.extraction.get_agent_llm",
        AsyncMock(return_value=llm),
    )
    return llm


# ---------------------------------------------------------------------------
# Query and log helpers (pure extraction -- no assertions hidden in here)
# ---------------------------------------------------------------------------


async def _memory_create_usage_count(db_session, thread_id) -> int:
    from sqlalchemy import func, select

    from app.db import TokenUsage

    result = await db_session.execute(
        select(func.count())
        .select_from(TokenUsage)
        .where(
            TokenUsage.thread_id == thread_id,
            TokenUsage.usage_type == "memory_create",
        )
    )
    return int(result.scalar_one())


async def _memory_count_for_message(db_session, message_id) -> int:
    from sqlalchemy import func, select

    from app.db import Memory

    result = await db_session.execute(
        select(func.count()).select_from(Memory).where(Memory.source_id == message_id)
    )
    return int(result.scalar_one())


def _log_messages(caplog) -> list[str]:
    return [record.getMessage() for record in caplog.records]


def _skip_lines(caplog) -> list[str]:
    """Structured ``memory_extract_skip`` lines only (mirrors the unit file)."""
    return [m for m in _log_messages(caplog) if "memory_extract_skip" in m]


def _assert_no_swallowed_exception(caplog):
    """Assert the enqueue pre-check *decided* rather than crashed.

    The pre-check lives inside ``try/except Exception``, which logs at ERROR and
    then falls through. Since falling through means "enqueue anyway", a crash
    could not by itself produce a false "no task enqueued" — 8.7-INT-015 asserts
    exactly that. What this guard buys is diagnostic rather than corrective: a
    negative test that passes *while* the block is exploding is passing for the
    wrong reason, and the failure message names the offending log lines instead
    of leaving a bare ``assert_not_called`` to explain itself.

    Scoped to the ``assistant_finalize`` logger on purpose: filtering every
    logger would let an unrelated ERROR from SQLAlchemy, asyncpg or another
    component fail an assertion about this code path.
    """
    exploded = [
        r.getMessage()
        for r in caplog.records
        if r.levelno >= logging.ERROR and r.name == _FINALIZE_LOGGER
    ]
    assert not exploded, f"pre-check raised instead of deciding: {exploded}"


def _make_stream_result(assistant_message_id: int, turn_id: str):
    from app.tasks.chat.streaming.shared.stream_result import StreamResult

    return StreamResult(
        turn_id=turn_id,
        assistant_message_id=assistant_message_id,
        accumulated_text="ok",
    )


def _service(db_session, db_workspace, db_user=None):
    from app.services.memory.extraction import MemoryExtractionService

    return MemoryExtractionService(
        session=db_session,
        workspace_id=db_workspace.id,
        user_id=None if db_user is None else db_user.id,
    )


# ---------------------------------------------------------------------------
# AC1 - Wallet pre-check BEFORE the extraction LLM call
# ---------------------------------------------------------------------------


async def test_extract_skips_before_llm_when_wallet_insufficient(
    db_session,
    db_workspace,
    db_user,
    empty_wallet,
    chat_turn,
    patched_embeddings,
    fake_llm,
):
    """8.7-INT-001 - P0/AC1: balance 0 -> no LLM call, no memories, no usage row."""
    thread, _user, assistant = chat_turn
    memories = await _service(db_session, db_workspace, db_user).extract_from_turn(
        thread.id, assistant.turn_id, assistant.id
    )

    assert memories == []
    fake_llm.ainvoke.assert_not_awaited()
    assert await _memory_count_for_message(db_session, assistant.id) == 0
    assert await _memory_create_usage_count(db_session, thread.id) == 0


async def test_extract_proceeds_when_wallet_funded(
    db_session,
    db_workspace,
    db_user,
    funded_wallet,
    chat_turn,
    patched_embeddings,
    fake_llm,
):
    """8.7-INT-002 - P0/AC1: sufficient balance -> LLM called, fact persisted."""
    thread, _user, assistant = chat_turn
    memories = await _service(db_session, db_workspace, db_user).extract_from_turn(
        thread.id, assistant.turn_id, assistant.id
    )

    assert len(memories) == 1
    fake_llm.ainvoke.assert_awaited_once()
    assert await _memory_create_usage_count(db_session, thread.id) == 1


# ---------------------------------------------------------------------------
# AC2 - Per-workspace spend/budget cap over a rolling period
# ---------------------------------------------------------------------------


async def test_extract_skips_when_workspace_over_budget(
    db_session,
    db_workspace,
    db_user,
    funded_wallet,
    seed_memory_spend,
    chat_turn,
    patched_embeddings,
    fake_llm,
    monkeypatch,
):
    """8.7-INT-003 - P0/AC2: prior memory_create spend >= cap -> skip, no new spend."""
    from app.config import config

    monkeypatch.setattr(config, "MEMORY_AUTO_EXTRACT_BUDGET_MICROS", 10_000)
    await seed_memory_spend(10_000)

    thread, _user, assistant = chat_turn
    memories = await _service(db_session, db_workspace, db_user).extract_from_turn(
        thread.id, assistant.turn_id, assistant.id
    )

    assert memories == []
    fake_llm.ainvoke.assert_not_awaited()
    assert await _memory_count_for_message(db_session, assistant.id) == 0


async def test_extract_proceeds_when_under_an_enabled_budget(
    db_session,
    db_workspace,
    db_user,
    funded_wallet,
    seed_memory_spend,
    chat_turn,
    patched_embeddings,
    fake_llm,
    monkeypatch,
):
    """8.7-INT-004 - P1/AC2: an ENABLED cap with spend below it still lets through.

    Distinguishes "the cap is enforced" from "the cap blocks everything once
    enabled" -- without this, a cap that always blocked would look correct.
    """
    from app.config import config

    monkeypatch.setattr(config, "MEMORY_AUTO_EXTRACT_BUDGET_MICROS", 10_000)
    await seed_memory_spend(9_999)

    thread, _user, assistant = chat_turn
    memories = await _service(db_session, db_workspace, db_user).extract_from_turn(
        thread.id, assistant.turn_id, assistant.id
    )

    assert len(memories) == 1
    fake_llm.ainvoke.assert_awaited_once()


async def test_extract_unchanged_when_budget_default(
    db_session,
    db_workspace,
    db_user,
    funded_wallet,
    chat_turn,
    patched_embeddings,
    fake_llm,
):
    """8.7-INT-005 - P1/AC2+AC6: budget unset/0 (default) -> baseline behaviour."""
    thread, _user, assistant = chat_turn
    memories = await _service(db_session, db_workspace, db_user).extract_from_turn(
        thread.id, assistant.turn_id, assistant.id
    )

    assert len(memories) == 1
    fake_llm.ainvoke.assert_awaited_once()


# ---------------------------------------------------------------------------
# AC3 - Time-based rate-limit
# ---------------------------------------------------------------------------


async def test_extract_skips_when_rate_limited(
    db_session,
    db_workspace,
    db_user,
    funded_wallet,
    chat_turn,
    patched_embeddings,
    fake_llm,
    no_real_redis,
    monkeypatch,
):
    """8.7-INT-006 - P1/AC3: window count at the rate max -> skip.

    Seeds the count through the in-process Redis double rather than stubbing the
    seam, so the real ``_rate_count`` -> key-format -> ``GET`` path is exercised.
    """
    from app.config import config

    monkeypatch.setattr(config, "MEMORY_AUTO_EXTRACT_RATE_MAX", 3)
    no_real_redis.store[f"nowing:memory_extract_rate:{db_workspace.id}"] = 3

    thread, _user, assistant = chat_turn
    memories = await _service(db_session, db_workspace, db_user).extract_from_turn(
        thread.id, assistant.turn_id, assistant.id
    )

    assert memories == []
    fake_llm.ainvoke.assert_not_awaited()


async def test_rate_counter_not_incremented_when_the_llm_call_fails(
    db_session,
    db_workspace,
    db_user,
    funded_wallet,
    chat_turn,
    patched_embeddings,
    fake_llm,
    record_extraction_spy,
    monkeypatch,
):
    """8.7-INT-007 - P1/AC3: transient LLM failures must not burn rate-limit slots.

    ``extract_from_turn`` re-raises the transient errors listed in the Celery
    task's ``autoretry_for`` (max_retries=3), and a turn that produced no
    memories does not trip the idempotency guard on redelivery. Recording the
    extraction before the call would therefore let one logical turn consume up
    to four slots and silently throttle the workspace.
    """
    from app.config import config

    monkeypatch.setattr(config, "MEMORY_AUTO_EXTRACT_RATE_MAX", 5)
    fake_llm.ainvoke.side_effect = TimeoutError("provider timed out")

    thread, _user, assistant = chat_turn
    with pytest.raises(TimeoutError):
        await _service(db_session, db_workspace, db_user).extract_from_turn(
            thread.id, assistant.turn_id, assistant.id
        )

    assert record_extraction_spy == []


async def test_rate_counter_incremented_once_on_success(
    db_session,
    db_workspace,
    db_user,
    funded_wallet,
    chat_turn,
    patched_embeddings,
    fake_llm,
    record_extraction_spy,
    monkeypatch,
):
    """8.7-INT-008 - P1/AC3: a successful extraction records exactly one increment."""
    from app.config import config

    monkeypatch.setattr(config, "MEMORY_AUTO_EXTRACT_RATE_MAX", 5)

    thread, _user, assistant = chat_turn
    memories = await _service(db_session, db_workspace, db_user).extract_from_turn(
        thread.id, assistant.turn_id, assistant.id
    )

    assert len(memories) == 1
    assert record_extraction_spy == [db_workspace.id]


# ---------------------------------------------------------------------------
# AC4 - Anonymous-chat attribution edge (FR-17)
# ---------------------------------------------------------------------------


async def test_extract_skips_anonymous_turn(
    db_session, db_workspace, anon_chat_turn, patched_embeddings, fake_llm
):
    """8.7-INT-009 - P0/AC4: no billable owner on the turn -> skip, no LLM, no usage."""
    thread, _user, assistant = anon_chat_turn
    memories = await _service(db_session, db_workspace).extract_from_turn(
        thread.id, assistant.turn_id, assistant.id
    )

    assert memories == []
    fake_llm.ainvoke.assert_not_awaited()
    assert await _memory_create_usage_count(db_session, thread.id) == 0


# ---------------------------------------------------------------------------
# AC5 - Kill-switch / flags remain authoritative (regression, Dep 8.8)
# ---------------------------------------------------------------------------


async def test_global_kill_switch_off_skips_without_llm(
    db_session,
    db_workspace,
    db_user,
    funded_wallet,
    chat_turn,
    patched_embeddings,
    fake_llm,
    monkeypatch,
):
    """8.7-INT-010 - P0/AC5: MEMORY_AUTO_EXTRACT_ENABLED=False -> [] and no LLM call."""
    from app.config import config

    monkeypatch.setattr(config, "MEMORY_AUTO_EXTRACT_ENABLED", False)

    thread, _user, assistant = chat_turn
    memories = await _service(db_session, db_workspace, db_user).extract_from_turn(
        thread.id, assistant.turn_id, assistant.id
    )

    assert memories == []
    fake_llm.ainvoke.assert_not_awaited()


async def test_workspace_flag_off_skips_without_llm(
    db_session,
    db_workspace,
    db_user,
    funded_wallet,
    disabled_workspace,
    chat_turn,
    patched_embeddings,
    fake_llm,
):
    """8.7-INT-011 - P0/AC5: workspace.memory_auto_extract_enabled=False -> no LLM call."""
    thread, _user, assistant = chat_turn
    memories = await _service(db_session, db_workspace, db_user).extract_from_turn(
        thread.id, assistant.turn_id, assistant.id
    )

    assert memories == []
    fake_llm.ainvoke.assert_not_awaited()


# ---------------------------------------------------------------------------
# AC7 - Enqueue-side short-circuit (defense in depth)
# ---------------------------------------------------------------------------


@pytest.fixture
def _finalize_deps(monkeypatch, db_session):
    """Wire finalize_assistant_message's real DB lookups onto the test session.

    ``shielded_async_session`` normally opens a brand-new engine connection,
    which would not see the (uncommitted, savepoint-scoped) db_workspace /
    db_user rows this test seeds. Patching it to hand back the test's own
    ``db_session`` keeps the gate's queries inside the same transaction that
    gets rolled back at teardown, while still exercising the REAL
    ``finalize_assistant_message`` control flow (no mocking of the gate or
    the enqueue check itself). Patching the module attribute is sound because
    ``assistant_finalize`` imports both names lazily inside the function body,
    so the lookup resolves at call time.

    Also stubs ``finalize_assistant_turn`` (the DB write for the assistant
    message content, covered by its own tests elsewhere) so this test can
    call ``finalize_assistant_message`` without pre-creating a full
    streaming payload.
    """
    from contextlib import asynccontextmanager

    import app.db as db_module

    @asynccontextmanager
    async def _fake_shielded_session():
        yield db_session

    monkeypatch.setattr(db_module, "shielded_async_session", _fake_shielded_session)

    finalize_turn = AsyncMock()
    monkeypatch.setattr(
        "app.tasks.chat.persistence.finalize_assistant_turn", finalize_turn
    )
    return finalize_turn


@pytest.fixture
def celery_delay(monkeypatch):
    """Mock only the Celery boundary; the gate and the DB stay real.

    ``.delay(...)`` is a synchronous Celery call (never awaited by the
    production code), so a plain MagicMock -- not AsyncMock -- matches how it is
    actually invoked.
    """
    delay = MagicMock()
    monkeypatch.setattr(
        "app.tasks.celery_tasks.memory_extraction_task.extract_memory_after_chat_turn.delay",
        delay,
    )
    return delay


async def _run_finalize(db_workspace, db_user, chat_turn):
    from app.services.token_tracking_service import TurnTokenAccumulator
    from app.tasks.chat.streaming.flows.shared.assistant_finalize import (
        finalize_assistant_message,
    )

    thread, _user, assistant = chat_turn
    await finalize_assistant_message(
        stream_result=_make_stream_result(assistant.id, assistant.turn_id),
        chat_id=thread.id,
        workspace_id=db_workspace.id,
        user_id=str(db_user.id),
        accumulator=TurnTokenAccumulator(),
        log_prefix="test",
    )
    return assistant


async def test_finalize_skips_enqueue_when_gate_blocks(
    db_workspace,
    db_user,
    funded_wallet,
    seed_memory_spend,
    chat_turn,
    _finalize_deps,
    celery_delay,
    monkeypatch,
    caplog,
):
    """8.7-INT-012 - P1/AC7: an over-budget workspace -> no Celery task enqueued.

    Uses the budget cap rather than the wallet: the enqueue-side check is
    principal-free by design, so only the workspace-scoped caps can block here.
    """
    from app.config import config

    monkeypatch.setattr(config, "MEMORY_AUTO_EXTRACT_BUDGET_MICROS", 10_000)
    await seed_memory_spend(10_000)

    with caplog.at_level(logging.INFO):
        await _run_finalize(db_workspace, db_user, chat_turn)

    celery_delay.assert_not_called()
    _assert_no_swallowed_exception(caplog)
    lines = _skip_lines(caplog)
    assert len(lines) == 1, f"AC-8 requires a single structured line, got {lines}"
    assert "reason=budget_exceeded" in lines[0]
    assert "stage=enqueue" in lines[0]


async def test_finalize_enqueues_when_gate_allows(
    db_workspace, db_user, funded_wallet, chat_turn, _finalize_deps, celery_delay
):
    """8.7-INT-013 - P1/AC7: no caps -> the Celery task IS enqueued exactly once."""
    assistant = await _run_finalize(db_workspace, db_user, chat_turn)

    celery_delay.assert_called_once_with(assistant.id, client_id=None)


async def test_finalize_enqueues_when_owner_wallet_is_empty(
    db_workspace, db_user, empty_wallet, chat_turn, _finalize_deps, celery_delay
):
    """8.7-INT-014 - P1/AC7+D2: the enqueue-side check carries no principal.

    The streaming caller is not guaranteed to be the author of the turn's user
    message (``resume_chat`` authorizes at workspace level), so a wallet verdict
    here could drop a turn the authoritative gate would allow. The task must be
    enqueued and ``extract_from_turn`` left to decide -- verified separately by
    8.7-INT-001. Decision record D2 in the story documents why this deliberately
    departs from AC-7's literal "or wallet-insufficient" wording.
    """
    assistant = await _run_finalize(db_workspace, db_user, chat_turn)

    celery_delay.assert_called_once_with(assistant.id, client_id=None)


async def test_finalize_enqueues_when_the_precheck_itself_errors(
    db_workspace,
    db_user,
    funded_wallet,
    chat_turn,
    _finalize_deps,
    celery_delay,
    monkeypatch,
):
    """8.7-INT-015 - P1/AC7: a failing fast-path must not permanently drop the work.

    The fast-path is an optimisation; the authoritative gate is the one allowed
    to decide. Blocking on its own failure would mean the real gate never runs.
    """
    import app.services.memory.extract_budget as gate
    from app.config import config

    monkeypatch.setattr(config, "MEMORY_AUTO_EXTRACT_BUDGET_MICROS", 10_000)

    async def _boom(_session, _workspace_id):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(gate, "_period_spend_micros", _boom)

    assistant = await _run_finalize(db_workspace, db_user, chat_turn)

    celery_delay.assert_called_once_with(assistant.id, client_id=None)


async def test_finalize_skips_enqueue_when_disabled(
    db_workspace,
    db_user,
    funded_wallet,
    disabled_workspace,
    chat_turn,
    _finalize_deps,
    celery_delay,
    caplog,
):
    """8.7-INT-016 - P0/AC5+AC8: the kill-switch short-circuits, and says so structurally."""
    with caplog.at_level(logging.INFO):
        await _run_finalize(db_workspace, db_user, chat_turn)

    celery_delay.assert_not_called()
    _assert_no_swallowed_exception(caplog)
    lines = _skip_lines(caplog)
    assert len(lines) == 1
    assert "reason=disabled" in lines[0]
    assert f"workspace_id={db_workspace.id}" in lines[0]
    assert "stage=enqueue" in lines[0]


# ---------------------------------------------------------------------------
# AC8 - Observability of skips
# ---------------------------------------------------------------------------


async def test_skip_emits_structured_log_and_no_usage(
    db_session,
    db_workspace,
    db_user,
    empty_wallet,
    chat_turn,
    patched_embeddings,
    fake_llm,
    caplog,
):
    """8.7-INT-017 - P1/AC8: a wallet skip emits ONE line with reason + workspace_id."""
    thread, _user, assistant = chat_turn
    with caplog.at_level(logging.INFO):
        memories = await _service(db_session, db_workspace, db_user).extract_from_turn(
            thread.id, assistant.turn_id, assistant.id
        )

    assert memories == []

    lines = _skip_lines(caplog)
    assert len(lines) == 1, f"AC-8 requires a single structured line, got {lines}"
    assert "reason=insufficient_wallet" in lines[0]
    assert f"workspace_id={db_workspace.id}" in lines[0]
    assert "stage=service" in lines[0]
    assert await _memory_create_usage_count(db_session, thread.id) == 0


async def test_disabled_skip_emits_structured_log(
    db_session,
    db_workspace,
    db_user,
    funded_wallet,
    disabled_workspace,
    chat_turn,
    patched_embeddings,
    fake_llm,
    caplog,
):
    """8.7-INT-018 - P1/AC8: `disabled` is one of the five skip kinds AC-8 enumerates.

    It short-circuits before the gate runs, so the service itself has to emit the
    structured line -- a DEBUG message without a machine-parseable ``reason=`` is
    invisible to log consumers.
    """
    thread, _user, assistant = chat_turn
    with caplog.at_level(logging.INFO):
        memories = await _service(db_session, db_workspace, db_user).extract_from_turn(
            thread.id, assistant.turn_id, assistant.id
        )

    assert memories == []
    fake_llm.ainvoke.assert_not_awaited()

    lines = _skip_lines(caplog)
    assert len(lines) == 1
    assert "reason=disabled" in lines[0]
    assert f"workspace_id={db_workspace.id}" in lines[0]
