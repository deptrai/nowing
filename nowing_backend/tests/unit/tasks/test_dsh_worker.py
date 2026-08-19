"""Unit tests for the DSH worker 60s hard timeout guards (Story 26.7 / AC-2)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.tasks import dsh_worker as dsh_module
from app.tasks.dsh_worker import DshWorker

pytestmark = pytest.mark.unit


class _HangingRedis:
    """Fake Redis whose stream calls sleep long enough to be treated as a hang."""

    def __init__(self, hang_seconds: float = 61.0) -> None:
        self.hang_seconds = hang_seconds

    async def xreadgroup(
        self,
        *,
        groupname: str,
        consumername: str,
        streams: dict[str, str],
        count: int,
        block: int,
    ) -> dict[str, Any]:
        await asyncio.sleep(self.hang_seconds)
        return {}

    async def xautoclaim(
        self,
        name: str,
        groupname: str,
        consumername: str,
        min_idle_time: int,
        start_id: str,
        count: int,
    ) -> tuple[str, list[tuple[str, dict[str, Any]]]]:
        await asyncio.sleep(self.hang_seconds)
        return (start_id, [])


class _RedisWithXAutoClaimShapes:
    """Fake Redis that returns XAUTOCLAIM responses in different shapes."""

    def __init__(self, response: list[Any]) -> None:
        self.response = response

    async def xautoclaim(
        self,
        name: str,
        groupname: str,
        consumername: str,
        min_idle_time: int,
        start_id: str,
        count: int,
    ) -> list[Any]:
        return self.response


@pytest.mark.asyncio
async def test_xreadgroup_61s_hang_is_terminated(monkeypatch):
    """A 61s XREADGROUP hang must be cancelled by the 60s wait_for guard."""
    monkeypatch.setattr(dsh_module, "_DSH_CALL_TIMEOUT_SECONDS", 0.1)
    monkeypatch.setattr(dsh_module.config, "DSH_CONSUMER_GROUP", "dsh_workers")
    monkeypatch.setattr(dsh_module.config, "DSH_STREAM_TASKS", "nowing:dsh:tasks")
    monkeypatch.setattr(dsh_module.config, "DSH_REDIS_BLOCK_MS", 5000)

    worker = DshWorker(redis_client=_HangingRedis())
    start = asyncio.get_event_loop().time()
    with pytest.raises(TimeoutError):
        await worker._read_new_messages(_HangingRedis())
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed < 2.0


@pytest.mark.asyncio
async def test_xautoclaim_61s_hang_is_terminated(monkeypatch):
    """A 61s XAUTOCLAIM hang must be cancelled by the 60s wait_for guard."""
    monkeypatch.setattr(dsh_module, "_DSH_CALL_TIMEOUT_SECONDS", 0.1)
    monkeypatch.setattr(dsh_module.config, "DSH_STREAM_TASKS", "nowing:dsh:tasks")
    monkeypatch.setattr(dsh_module.config, "DSH_CONSUMER_GROUP", "dsh_workers")
    monkeypatch.setattr(dsh_module.config, "DSH_XAUTOCLAIM_MIN_IDLE_MS", 60000)

    worker = DshWorker(redis_client=_HangingRedis())
    start = asyncio.get_event_loop().time()
    with pytest.raises(TimeoutError):
        await worker._autoclaim(_HangingRedis())
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed < 2.0


@pytest.mark.parametrize(
    "response",
    [
        ["0-0", [("msg-1", {"mission_id": "abc"})]],
        ["0-0", [("msg-1", {"mission_id": "abc"})], []],
    ],
    ids=["2-element", "3-element"],
)
@pytest.mark.asyncio
async def test_xautoclaim_handles_response_shapes(response, monkeypatch):
    """redis-py can return 2 or 3 elements from XAUTOCLAIM; both must parse."""
    monkeypatch.setattr(dsh_module.config, "DSH_STREAM_TASKS", "nowing:dsh:tasks")
    monkeypatch.setattr(dsh_module.config, "DSH_CONSUMER_GROUP", "dsh_workers")

    fake_redis = _RedisWithXAutoClaimShapes(response)
    worker = DshWorker(redis_client=fake_redis)
    claimed = await worker._autoclaim(fake_redis)
    assert len(claimed) == 1
    assert claimed[0][0] == "msg-1"
    assert claimed[0][1]["mission_id"] == "abc"
