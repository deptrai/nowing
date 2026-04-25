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
    writer.write("text-delta", {"agentId": "a1", "text": "hello"})
    assert writer._queue.qsize() == 1


@pytest.mark.asyncio
async def test_write_multiple_events():
    writer = _make_writer()
    for i in range(5):
        writer.write("text-delta", {"agentId": "a1", "text": f"chunk-{i}"})
    assert writer._queue.qsize() == 5


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
async def test_coalesce_text_delta_on_overflow():
    """When queue is full, newer text-delta for same agent replaces older one."""
    run_id = uuid4()
    # Create writer with tiny queue
    writer = RunEventWriter(run_id, AsyncMock(), _mock_session_factory())
    writer._queue = asyncio.Queue(maxsize=2)

    writer._queue.put_nowait(("text-delta", {"agentId": "a1", "text": "chunk1"}))
    writer._queue.put_nowait(("text-delta", {"agentId": "a2", "text": "other"}))

    # Queue full — coalesce should replace a1's entry
    writer._coalesce_or_drop("text-delta", {"agentId": "a1", "text": "chunk2"})

    # a1 entry should have been replaced
    items = []
    while not writer._queue.empty():
        items.append(writer._queue.get_nowait())

    a1_items = [i for i in items if i[1].get("agentId") == "a1"]
    assert len(a1_items) == 1
    assert a1_items[0][1]["text"] == "chunk2"


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
async def test_stop_waits_for_queue_drain():
    writer = _make_writer()
    writer.write("text-delta", {"text": "pending"})
    assert not writer._queue.empty()

    # Drain manually to simulate flush
    writer._queue.get_nowait()
    await writer.stop()
    assert writer._stop.is_set()
