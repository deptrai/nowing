"""Unit tests for `_with_heartbeat` cancellation safety (Story 11.7 T2).

Round-2 review of Story 11.6 flagged that `task.cancel()` propagates
`CancelledError` into the inner generator at arbitrary `await` points,
risking partial DB session / LangGraph state corruption. T2 hardens the
cleanup with a two-phase drain (cancel + aclose) shielded against outer
cancellation.

These tests verify the `finally` block actually invokes the inner generator's
cleanup protocol (`GeneratorExit` via `aclose()`).
"""
from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import pytest

from app.tasks.chat.stream_new_chat import _with_heartbeat

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_inner_generator_finally_runs_on_consumer_disconnect():
    """When the consumer stops iterating mid-stream, the inner generator's
    `try/finally` MUST execute (not be skipped because of CancelledError
    landing at the wrong await)."""
    cleanup_marker = {"ran": False}

    async def inner_gen() -> AsyncGenerator[str, None]:
        try:
            yield "first\n\n"
            # Simulate inner work that the consumer never gets to.
            await asyncio.sleep(60)
            yield "never\n\n"  # pragma: no cover
        finally:
            cleanup_marker["ran"] = True

    wrapped = _with_heartbeat(inner_gen(), timeout=10.0)

    # Consume the first chunk, then close the wrapped generator (simulates
    # Starlette dropping the SSE consumer after the first event).
    received = await wrapped.__anext__()
    assert received == "first\n\n"

    await wrapped.aclose()
    # Give the cleanup time to run.
    await asyncio.sleep(0.05)

    assert cleanup_marker["ran"] is True, (
        "inner generator's finally block did not run — cleanup leaked"
    )


@pytest.mark.asyncio
async def test_inner_generator_finally_runs_on_outer_task_cancellation():
    """When the wrapper itself is cancelled (e.g. Starlette kills the
    StreamingResponse task), inner cleanup still runs via shielded aclose()."""
    cleanup_marker = {"ran": False}

    async def inner_gen() -> AsyncGenerator[str, None]:
        try:
            yield "data\n\n"
            await asyncio.sleep(60)  # waiting for next event
            yield "never\n\n"  # pragma: no cover
        finally:
            cleanup_marker["ran"] = True

    async def consumer():
        async for _ in _with_heartbeat(inner_gen(), timeout=5.0):
            # Hold here until cancelled by the test.
            await asyncio.sleep(60)

    task = asyncio.create_task(consumer())
    # Let the loop pick up the first yield.
    await asyncio.sleep(0.1)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Allow cleanup to flush.
    await asyncio.sleep(0.1)

    assert cleanup_marker["ran"] is True


@pytest.mark.asyncio
async def test_misbehaving_inner_generator_does_not_propagate_past_wrapper():
    """An inner generator that raises during its own cleanup must not bubble
    past `_with_heartbeat` and crash the SSE response."""

    async def inner_gen() -> AsyncGenerator[str, None]:
        try:
            yield "ok\n\n"
            await asyncio.sleep(60)
        finally:
            # Simulate cleanup raising (e.g. DB session close fails).
            raise RuntimeError("cleanup boom")

    wrapped = _with_heartbeat(inner_gen(), timeout=10.0)
    await wrapped.__anext__()

    # aclose() should not propagate the inner RuntimeError.
    await wrapped.aclose()


@pytest.mark.asyncio
async def test_heartbeat_yielded_when_inner_idle():
    """Smoke check: the heartbeat path still works after the cancellation
    refactor — wrapper yields a `: heartbeat\\n\\n` SSE comment when the
    inner generator is idle past `timeout`."""

    async def inner_gen() -> AsyncGenerator[str, None]:
        await asyncio.sleep(0.3)  # idle past timeout
        yield "real-event\n\n"

    chunks = []
    async for c in _with_heartbeat(inner_gen(), timeout=0.05):
        chunks.append(c)
        # Break as soon as we've seen at least one heartbeat AND the real event.
        has_heartbeat = any(x.startswith(":") and "heartbeat" in x for x in chunks)
        has_real = any(x == "real-event\n\n" for x in chunks)
        if has_heartbeat and has_real:
            break

    assert any(x.startswith(":") and "heartbeat" in x for x in chunks), (
        f"no heartbeat seen during idle period; chunks={chunks}"
    )
    assert chunks[-1] == "real-event\n\n", (
        f"expected last chunk to be real event; chunks={chunks}"
    )
