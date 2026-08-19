"""Unit tests for DshWorker executor wiring (Story 26.8 spike)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from app.config import config
from app.tasks.dsh_worker import DshWorker

pytestmark = pytest.mark.unit


class _FakeRedis:
    """Minimal Redis fake for DshWorker wiring tests."""

    def __init__(self) -> None:
        self.locks: dict[str, str] = {}

    async def set(self, key: str, value: str, *, nx: bool = False, ex: int | None = None) -> bool | None:
        if nx and key in self.locks:
            return None
        self.locks[key] = value
        return True

    async def get(self, key: str) -> str | None:
        return self.locks.get(key)

    async def eval(self, script: str, num_keys: int, key: str, value: str, ttl: int) -> int:
        # Lua script only extends if we own the lock.
        if self.locks.get(key) == value:
            self.locks[key] = value
            return 1
        return 0

    async def xack(self, *args: Any, **kwargs: Any) -> int:
        return 1

    async def aclose(self) -> None:
        pass


class _FakeDshRestClient:
    """Minimal fake of DshRestClient for wiring tests."""

    def __init__(
        self,
        mission: dict[str, Any] | None = None,
        enforce_version: bool = False,
    ) -> None:
        self.mission = mission or {}
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.enforce_version = enforce_version

    def _record(self, name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.calls.append((name, args, kwargs))
        return self.mission

    async def get_mission(self, mission_id: Any) -> dict[str, Any]:
        return self._record("get_mission", mission_id)

    async def patch_checkpoint(self, mission_id: Any, update: dict[str, Any]) -> dict[str, Any]:
        current_checkpoint = self.mission.get("checkpoint") or {}
        current_version = current_checkpoint.get("version") or 0
        checkpoint = update.get("checkpoint")
        if checkpoint is not None:
            new_version = checkpoint.get("version") or 0
            if self.enforce_version and new_version < current_version:
                raise RuntimeError(
                    f"Stale checkpoint version {new_version} < {current_version}"
                )
            checkpoint = dict(checkpoint)
            checkpoint["version"] = max(new_version, current_version) + 1
            update["checkpoint"] = checkpoint
        self.mission.update(update)
        if checkpoint is not None:
            self.mission["checkpoint"] = checkpoint
        return self._record("patch_checkpoint", mission_id, update) or self.mission

    async def chainlens_research(self, workspace_id: int, query: str) -> dict[str, Any]:
        return {
            "run_id": "run-001",
            "sources": [
                {
                    "url": "https://example.com/acme",
                    "domain": "example.com",
                    "company_name": "Acme",
                    "phone": "+84-123-456-789",
                    "email": "hello@acme.com",
                    "fit_score": 85.0,
                }
            ],
        }

    async def batch_ingest_leads(
        self, workspace_id: int, leads: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return {
            "ingested": len(leads),
            "lead_id_mapping": {"h1": str(uuid4())},
        }

    async def notify_high_fit_lead(
        self, mission_id: Any, lead_id: Any, contact_id: Any = None
    ) -> dict[str, Any]:
        return self._record("notify_high_fit_lead", mission_id, lead_id, contact_id)

    async def aclose(self) -> None:
        pass


@pytest.fixture
def mission() -> dict[str, Any]:
    mid = uuid4()
    return {
        "id": mid,
        "workspace_id": 42,
        "mission_type": "deep_lead_research",
        "payload": {"query": "AI companies"},
        "checkpoint": {"version": 1, "phase": "crawl", "subtasks": []},
    }


@pytest.mark.asyncio
async def test_worker_uses_langgraph_executor_when_flag_set(monkeypatch, mission: dict[str, Any]) -> None:
    """DshWorker must instantiate and run LangGraphMissionExecutor when configured."""
    monkeypatch.setattr(config, "DSH_EXECUTOR_ENGINE", "langgraph")

    fake_client = _FakeDshRestClient(mission)
    fake_redis = _FakeRedis()

    worker = DshWorker(redis_client=fake_redis, rest_client=fake_client)
    fields = {"mission_id": str(mission["id"])}

    should_ack = await worker._handle_message(fake_redis, "0-1", fields)

    assert should_ack is True
    assert fake_client.mission.get("status") == "success"
    assert fake_client.mission.get("phase") == "terminal"
    assert fake_client.mission.get("progress_percent") == 100

    call_names = [c[0] for c in fake_client.calls]
    assert "patch_checkpoint" in call_names
    assert "get_mission" in call_names


class _FailingExecutor:
    """Executor that patches a checkpoint and then raises (simulates a mid-graph crash)."""

    def __init__(self, rest_client: _FakeDshRestClient) -> None:
        self.rest_client = rest_client

    async def run(self, mission: dict[str, Any]) -> None:
        checkpoint = mission.get("checkpoint") or {}
        await self.rest_client.patch_checkpoint(
            mission["id"],
            {
                "status": "running",
                "phase": "ingestion",
                "progress_percent": 90,
                "current_subtask_id": "ingestion",
                "checkpoint": checkpoint,
            },
        )
        raise RuntimeError("Simulated executor failure")


@pytest.mark.asyncio
async def test_worker_refreshes_mission_before_retry(monkeypatch, mission: dict[str, Any]) -> None:
    """If the executor raised after bumping the checkpoint, the retry must use the fresh version."""
    monkeypatch.setattr(config, "DSH_EXECUTOR_ENGINE", "langgraph")

    fake_client = _FakeDshRestClient(mission, enforce_version=True)
    fake_redis = _FakeRedis()
    failing_executor = _FailingExecutor(fake_client)

    worker = DshWorker(
        redis_client=fake_redis,
        rest_client=fake_client,
        executor=failing_executor,
    )
    fields = {"mission_id": str(mission["id"])}

    should_ack = await worker._handle_message(fake_redis, "0-1", fields)

    assert should_ack is False
    assert fake_client.mission.get("status") == "pending"
    assert fake_client.mission.get("retry_count") == 1
    checkpoint = fake_client.mission.get("checkpoint") or {}
    assert checkpoint.get("version") > 1

    call_names = [c[0] for c in fake_client.calls]
    # The worker must re-fetch the mission after the exception before retrying,
    # otherwise the next patch would be stale.
    assert call_names.count("get_mission") >= 2


class _RecordingLegacyExecutor:
    """Records that the legacy executor was instantiated and called."""

    def __init__(self, rest_client: _FakeDshRestClient) -> None:
        self.rest_client = rest_client
        self.run_calls: list[dict[str, Any]] = []

    async def run(self, mission: dict[str, Any]) -> None:
        self.run_calls.append(mission)


@pytest.mark.asyncio
async def test_worker_uses_legacy_executor_when_flag_set(monkeypatch, mission: dict[str, Any]) -> None:
    """DshWorker must instantiate the legacy executor when DSH_EXECUTOR_ENGINE=legacy."""
    import app.tasks.dsh_worker as dsh_worker_module

    monkeypatch.setattr(config, "DSH_EXECUTOR_ENGINE", "legacy")

    legacy_runs: list[dict[str, Any]] = []

    def _make_legacy(rest_client: _FakeDshRestClient) -> _RecordingLegacyExecutor:
        executor = _RecordingLegacyExecutor(rest_client)
        legacy_runs.append(executor)
        return executor

    monkeypatch.setattr(dsh_worker_module, "DeepLeadResearchExecutor", _make_legacy)

    fake_client = _FakeDshRestClient(mission)
    fake_redis = _FakeRedis()

    worker = DshWorker(redis_client=fake_redis, rest_client=fake_client)
    fields = {"mission_id": str(mission["id"])}

    should_ack = await worker._handle_message(fake_redis, "0-1", fields)

    assert should_ack is True
    assert len(legacy_runs) == 1
    assert legacy_runs[0].run_calls[0]["id"] == mission["id"]
    assert fake_client.mission.get("status") == "success"
