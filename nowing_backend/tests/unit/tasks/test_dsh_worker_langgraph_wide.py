"""Red-phase tests for LangGraph executor wide-research dispatch (Story 26.9a)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from app.tasks.dsh_worker_langgraph import LangGraphMissionExecutor

pytestmark = pytest.mark.unit


class _FakeDshRestClient:
    """Minimal fake DshRestClient that records chainlens_research kwargs."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.mission: dict[str, Any] = {}

    def _record(self, name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.calls.append((name, args, kwargs))
        return self.mission

    async def get_mission(self, mission_id: Any) -> dict[str, Any]:
        return self._record("get_mission", mission_id)

    async def patch_checkpoint(
        self, mission_id: Any, update: dict[str, Any]
    ) -> dict[str, Any]:
        self.mission.update(update)
        self.mission["checkpoint"] = (
            update.get("checkpoint") or self.mission.get("checkpoint") or {}
        )
        return self.mission

    async def chainlens_research(
        self,
        workspace_id: int,
        query: str,
        output: str | None = None,
        output_schema: dict[str, Any] | None = None,
        mode: str = "balanced",
    ) -> dict[str, Any]:
        return self._record(
            "chainlens_research",
            workspace_id,
            query,
            output=output,
            output_schema=output_schema,
            mode=mode,
        )

    async def batch_ingest_leads(
        self, workspace_id: int, leads: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return {"ingested": len(leads), "lead_id_mapping": {}}

    async def notify_high_fit_lead(
        self, mission_id: Any, lead_id: Any, contact_id: Any = None
    ) -> dict[str, Any]:
        return self._record("notify_high_fit_lead", mission_id, lead_id, contact_id)

    async def aclose(self) -> None:
        pass


@pytest.fixture
def fake_client() -> _FakeDshRestClient:
    return _FakeDshRestClient()


@pytest.mark.skip("RED: wide-research dispatch not implemented (Story 26.9a)")
@pytest.mark.asyncio
async def test_crawl_node_dispatches_with_output_table_and_schema(
    fake_client: _FakeDshRestClient,
) -> None:
    """AC-2: When research_mode='wide', _crawl_node calls chainlens_research with output='table' + output_schema."""
    mission_id = uuid4()
    mission = {
        "id": mission_id,
        "workspace_id": 42,
        "mission_type": "deep_lead_research",
        "payload": {
            "query": "so sánh 20 framework AI Agent 2026",
            "extras": {"research_mode": "wide"},
        },
        "checkpoint": {"version": 1, "phase": "crawl", "subtasks": []},
    }

    executor = LangGraphMissionExecutor(fake_client)  # type: ignore[arg-type]
    await executor.run(mission)

    research_calls = [c for c in fake_client.calls if c[0] == "chainlens_research"]
    assert len(research_calls) == 1
    _, _, kwargs = research_calls[0]
    assert kwargs.get("output") == "table"
    assert kwargs.get("output_schema") is not None
    assert kwargs.get("mode") == "balanced"
