"""Unit tests for RunEventWriter."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.run_event_writer import RunEventWriter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_writer(run_id=None, redis=None, session_factory=None):
    run_id = run_id or uuid4()
    if redis is None:
        redis = AsyncMock()
        redis.publish = AsyncMock()
    if session_factory is None:
        session_factory = _mock_session_factory()
    return RunEventWriter(run_id, redis, session_factory)


def _mock_session_factory(max_seq=-1):
    """Return a context-manager-compatible session factory."""
    session = AsyncMock()
    # Seed seq result: COALESCE(MAX(seq), -1) + 1
    scalar_result = MagicMock()
    scalar_result.scalar.return_value = max_seq + 1
    session.execute = AsyncMock(return_value=scalar_result)
    session.commit = AsyncMock()

    class _FakeCtx:
        async def __aenter__(self):
            return session
        async def __aexit__(self, *_):
            pass

    def factory():
        return _FakeCtx()

    factory._session = session  # expose for assertions
    return factory


# ---------------------------------------------------------------------------
# Tests: write() / enqueue
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_enqueues_event():
    writer = _make_writer()
    writer.write("orchestra-spawn", {"agentId": "a1"})
    assert len(writer._deque) == 1


@pytest.mark.asyncio
async def test_write_multiple_events():
    writer = _make_writer()
    for i in range(5):
        writer.write("orchestra-spawn", {"agentId": f"a{i}"})
    assert len(writer._deque) == 5


# ---------------------------------------------------------------------------
# Tests: _seed_next_seq
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_seed_next_seq_from_empty_table():
    writer = _make_writer(session_factory=_mock_session_factory(max_seq=-1))
    await writer._seed_next_seq()
    assert writer._next_seq == 0


@pytest.mark.asyncio
async def test_seed_next_seq_continues_sequence():
    writer = _make_writer(session_factory=_mock_session_factory(max_seq=41))
    await writer._seed_next_seq()
    assert writer._next_seq == 42


# ---------------------------------------------------------------------------
# Tests: _seed_seen_events (dedup on resume, C4)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_seed_seen_events_populates_dedup_sets():
    run_id = uuid4()
    session = AsyncMock()
    rows = [
        ("orchestra-spawn", {"agentId": "agent-1"}),
        ("data-orchestra-source-fetched", {"data": {"agentId": "agent-1", "domain": "crypto"}}),
        ("data-orchestra-model-attribution", {"data": {"agentId": "agent-1"}}),
    ]
    # selectresult → mock that iterates rows
    result_mock = MagicMock()
    result_mock.__iter__ = MagicMock(return_value=iter(rows))
    session.execute = AsyncMock(return_value=result_mock)

    class _FakeCtx:
        async def __aenter__(self):
            return session
        async def __aexit__(self, *_):
            pass

    writer = RunEventWriter(run_id, AsyncMock(), lambda: _FakeCtx())
    await writer._seed_seen_events()

    assert "agent-1" in writer._seen_spawn_agents
    assert "agent-1:crypto" in writer._seen_source_keys
    assert "agent-1" in writer._seen_attribution_agents


# ---------------------------------------------------------------------------
# Tests: _should_dedup (C4)
# ---------------------------------------------------------------------------

def test_should_dedup_orchestra_spawn_duplicate():
    writer = _make_writer()
    writer._seen_spawn_agents.add("agt-1")
    assert writer._should_dedup("orchestra-spawn", {"agentId": "agt-1"}) is True


def test_should_dedup_orchestra_spawn_new():
    writer = _make_writer()
    assert writer._should_dedup("orchestra-spawn", {"agentId": "agt-new"}) is False


def test_should_dedup_source_fetched_duplicate():
    writer = _make_writer()
    writer._seen_source_keys.add("agt-1:defi")
    assert writer._should_dedup(
        "data-orchestra-source-fetched",
        {"data": {"agentId": "agt-1", "domain": "defi"}},
    ) is True


def test_should_dedup_other_event_not_deduped():
    writer = _make_writer()
    assert writer._should_dedup("text-delta", {"text": "hi"}) is False


# ---------------------------------------------------------------------------
# Tests: _coalesce_or_drop (queue overflow)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_text_delta_coalescing_upstream():
    """T5: text-delta for same agentId is coalesced in _pending_delta before deque insertion."""
    run_id = uuid4()
    writer = RunEventWriter(run_id, AsyncMock(), _mock_session_factory())

    # Write 3 text-delta for same agent — only last should survive in _pending_delta
    writer.write("text-delta", {"agentId": "a1", "text": "chunk1"})
    writer.write("text-delta", {"agentId": "a1", "text": "chunk2"})
    writer.write("text-delta", {"agentId": "a1", "text": "chunk3"})

    # _pending_delta holds (event_type, payload) tuple for latest unconsumed text-delta per agentId
    assert "a1" in writer._pending_delta
    _evt_type, _payload = writer._pending_delta["a1"]
    assert _evt_type == "text-delta"
    assert _payload["text"] == "chunk3"


@pytest.mark.asyncio
async def test_synthesis_text_delta_no_coalescing():
    """T5-fix: main synthesis text-delta (no agentId) must go to deque to preserve all tokens.

    Root cause of text storage bug: synthesis deltas had agentId="" → coalesced in
    _pending_delta[""] → ~80% of tokens dropped in 25ms flush windows.
    Fix: no-agentId text-delta falls through to deque so all tokens are preserved
    and text-start precedes text-delta in FIFO order.
    """
    run_id = uuid4()
    writer = RunEventWriter(run_id, AsyncMock(), _mock_session_factory())

    # Write 3 synthesis text-delta (no agentId) — ALL must survive in deque
    writer.write("text-delta", {"type": "text-delta", "id": "text_abc", "delta": "<!-- crypto"})
    writer.write("text-delta", {"type": "text-delta", "id": "text_abc", "delta": "-report-v2"})
    writer.write("text-delta", {"type": "text-delta", "id": "text_abc", "delta": " -->\n"})

    # All 3 deltas must be in deque (no coalescing)
    assert len(writer._deque) == 3
    # _pending_delta should NOT have the "" key
    assert "" not in writer._pending_delta

    # Order preserved (FIFO)
    events = list(writer._deque)
    assert events[0][1]["delta"] == "<!-- crypto"
    assert events[1][1]["delta"] == "-report-v2"
    assert events[2][1]["delta"] == " -->\n"


# ---------------------------------------------------------------------------
# Tests: _flush_batch — C6: INSERT before PUBLISH
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_flush_batch_inserts_before_publish():
    """C6: DB commit must happen before Redis publish."""
    run_id = uuid4()
    call_order = []

    session = AsyncMock()
    scalar_mock = MagicMock()
    scalar_mock.scalar.return_value = 0
    session.execute = AsyncMock(return_value=scalar_mock)

    async def _commit():
        call_order.append("commit")
    session.commit = _commit

    class _FakeCtx:
        async def __aenter__(self):
            return session
        async def __aexit__(self, *_):
            pass

    redis = AsyncMock()
    async def _publish(channel, data):
        call_order.append("publish")
    redis.publish = _publish

    writer = RunEventWriter(run_id, redis, lambda: _FakeCtx())
    writer._next_seq = 0

    await writer._flush_batch([("text-delta", {"text": "hi"})])

    commit_idx = call_order.index("commit")
    publish_idx = call_order.index("publish")
    assert commit_idx < publish_idx, "commit must happen before publish (C6)"


# ---------------------------------------------------------------------------
# Tests: idempotent seq on flush failure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_flush_batch_restores_seq_on_error():
    """On DB error, _next_seq is restored so retry reuses same range."""
    run_id = uuid4()
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=RuntimeError("db down"))

    class _FakeCtx:
        async def __aenter__(self):
            return session
        async def __aexit__(self, *_):
            pass

    writer = RunEventWriter(run_id, AsyncMock(), lambda: _FakeCtx())
    writer._next_seq = 10

    await writer._flush_batch([("text-delta", {"text": "retry-me"})])

    assert writer._next_seq == 10, "_next_seq should revert to pre-batch value on error"


# ---------------------------------------------------------------------------
# Tests: dedup updates seen-sets during flush
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_flush_batch_updates_seen_sets():
    run_id = uuid4()
    session = AsyncMock()
    scalar_mock = MagicMock()
    scalar_mock.scalar.return_value = 0
    session.execute = AsyncMock(return_value=scalar_mock)
    session.commit = AsyncMock()

    class _FakeCtx:
        async def __aenter__(self):
            return session
        async def __aexit__(self, *_):
            pass

    writer = RunEventWriter(run_id, AsyncMock(), lambda: _FakeCtx())
    writer._next_seq = 0

    await writer._flush_batch([("orchestra-spawn", {"agentId": "agt-x"})])
    assert "agt-x" in writer._seen_spawn_agents


# ---------------------------------------------------------------------------
# Tests: stop() drains queue before signalling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stop_signals_event():
    """stop() sets the _stop event so run_flush_loop can exit."""
    writer = _make_writer()
    writer.write("orchestra-spawn", {"agentId": "a1"})
    assert len(writer._deque) == 1

    # Drain manually to simulate flush having consumed the event
    writer._deque.clear()
    await writer.stop()
    assert writer._stop.is_set()


# ---------------------------------------------------------------------------
# T16: Advisory lock re-seeding prevents seq collision when two writers race
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_advisory_lock_reseeds_seq_on_conflict():
    """T16: When DB reports a higher seq (another writer advanced it),
    _flush_batch reassigns seq offsets to avoid collisions.
    """
    run_id = uuid4()
    call_count = 0

    session = AsyncMock()

    def _make_result(scalar_val):
        r = MagicMock()
        r.scalar.return_value = scalar_val
        return r

    # First call: advisory lock (returns nothing useful)
    # Second call: COALESCE(MAX(seq),-1)+1 → returns 5 (another writer got to seq 4)
    # Subsequent calls: INSERT / UPDATE
    async def _execute(stmt, params=None):
        nonlocal call_count
        call_count += 1
        stmt_str = str(stmt) if not isinstance(stmt, str) else stmt
        if "COALESCE" in stmt_str or "coalesce" in stmt_str.lower():
            return _make_result(5)  # DB says next seq is 5
        return _make_result(0)

    session.execute = AsyncMock(side_effect=_execute)
    session.commit = AsyncMock()

    class _FakeCtx:
        async def __aenter__(self):
            return session
        async def __aexit__(self, *_):
            pass

    writer = RunEventWriter(run_id, AsyncMock(), lambda: _FakeCtx())
    # Writer thinks it owns seq 0, but DB has advanced to 5
    writer._next_seq = 0

    await writer._flush_batch([
        ("text-delta", {"text": "a"}),
        ("text-delta", {"text": "b"}),
    ])

    # After flush, _next_seq should be 7 (5 + 2 events)
    assert writer._next_seq == 7, (
        f"Expected _next_seq=7 after advisory lock reseed from seq=5, got {writer._next_seq}"
    )


@pytest.mark.asyncio
async def test_advisory_lock_no_conflict_uses_writer_seq():
    """T16: When DB seq matches writer seq, no offset is applied."""
    run_id = uuid4()

    session = AsyncMock()

    async def _execute(stmt, params=None):
        stmt_str = str(stmt) if not isinstance(stmt, str) else stmt
        if "COALESCE" in stmt_str or "coalesce" in stmt_str.lower():
            r = MagicMock()
            r.scalar.return_value = 3  # DB says next seq is 3, matches writer
            return r
        return MagicMock()

    session.execute = AsyncMock(side_effect=_execute)
    session.commit = AsyncMock()

    class _FakeCtx:
        async def __aenter__(self):
            return session
        async def __aexit__(self, *_):
            pass

    writer = RunEventWriter(run_id, AsyncMock(), lambda: _FakeCtx())
    writer._next_seq = 3  # writer already at seq 3 (consistent)

    await writer._flush_batch([("orchestra-spawn", {"agentId": "a1"})])

    # seq was 3 before, 1 event → next is 4
    assert writer._next_seq == 4
