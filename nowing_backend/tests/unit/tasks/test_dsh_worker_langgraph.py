"""Unit tests for the LangGraph DSH mission executor (Story 26.8 spike)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from app.tasks.dsh_worker_langgraph import LangGraphMissionExecutor

pytestmark = pytest.mark.unit


class _FakeDshRestClient:
    """Minimal fake of DshRestClient for hermetic LangGraph executor tests."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.mission: dict[str, Any] = {}

    def _record(self, name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.calls.append((name, args, kwargs))
        return self.mission

    async def get_mission(self, mission_id: Any) -> dict[str, Any]:
        return self._record("get_mission", mission_id)

    async def patch_checkpoint(self, mission_id: Any, update: dict[str, Any]) -> dict[str, Any]:
        self.mission.update(update)
        self.mission["checkpoint"] = update.get("checkpoint") or self.mission.get("checkpoint") or {}
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
                },
                {
                    "url": "https://example.org/empty",
                    "domain": "example.org",
                },
            ],
        }

    async def batch_ingest_leads(
        self, workspace_id: int, leads: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return {
            "ingested": len(leads),
            "lead_id_mapping": {lead.get("value_hmac", "h1"): str(uuid4()) for lead in leads},
        }

    async def notify_high_fit_lead(
        self, mission_id: Any, lead_id: Any, contact_id: Any = None
    ) -> dict[str, Any]:
        return self._record("notify_high_fit_lead", mission_id, lead_id, contact_id)

    async def aclose(self) -> None:
        pass


@pytest.fixture
def fake_client() -> _FakeDshRestClient:
    return _FakeDshRestClient()


@pytest.mark.asyncio
async def test_langgraph_executor_runs_full_pipeline(fake_client: _FakeDshRestClient) -> None:
    mission_id = uuid4()
    mission = {
        "id": mission_id,
        "workspace_id": 42,
        "mission_type": "deep_lead_research",
        "payload": {"query": "Công ty AI tại TP HCM"},
        "checkpoint": {"version": 1, "phase": "crawl", "subtasks": []},
    }

    executor = LangGraphMissionExecutor(fake_client)  # type: ignore[arg-type]
    await executor.run(mission)

    checkpoint = fake_client.mission.get("checkpoint", {})
    assert fake_client.mission.get("status") == "success"
    assert fake_client.mission.get("phase") == "terminal"
    assert fake_client.mission.get("progress_percent") == 100

    subtasks = checkpoint.get("subtasks", [])
    assert {s["id"] for s in subtasks if s["status"] == "success"} == {
        "crawl",
        "reasoning",
        "extraction",
        "ingestion",
    }

    assert len(checkpoint.get("sources", [])) == 2
    # The example.com source has company + phone + email; the example.org source
    # has only a domain. The legacy executor keeps any lead with at least one
    # of phone/email/domain, so we expect two leads (one enriched, one domain-only).
    assert len(checkpoint.get("leads", [])) == 2
    assert checkpoint["leads"][0]["company_name"] == "Acme"


@pytest.mark.asyncio
async def test_langgraph_executor_resumes_from_existing_subtask(
    fake_client: _FakeDshRestClient,
) -> None:
    """If 'crawl' is already marked success, the graph should skip it."""
    mission_id = uuid4()
    mission = {
        "id": mission_id,
        "workspace_id": 42,
        "mission_type": "deep_lead_research",
        "payload": {"query": "AI companies"},
        "checkpoint": {
            "version": 1,
            "phase": "reasoning",
            "subtasks": [
                {
                    "id": "crawl",
                    "status": "success",
                    "run_id": "run-001",
                    "sources_count": 2,
                }
            ],
            "sources": [{"url": "https://resumed.example", "domain": "resumed.example", "company_name": "ResumedCo"}],
        },
    }

    executor = LangGraphMissionExecutor(fake_client)  # type: ignore[arg-type]
    await executor.run(mission)

    # chainlens_research should NOT have been called because crawl was already done.
    call_names = [c[0] for c in fake_client.calls]
    assert "chainlens_research" not in call_names

    checkpoint = fake_client.mission.get("checkpoint", {})
    assert fake_client.mission.get("status") == "success"
    assert checkpoint["leads"][0]["company_name"] == "ResumedCo"


@pytest.mark.asyncio
async def test_langgraph_executor_clears_current_subtask_id(fake_client: _FakeDshRestClient) -> None:
    """The terminal/success checkpoint must clear current_subtask_id."""
    mission_id = uuid4()
    mission = {
        "id": mission_id,
        "workspace_id": 42,
        "mission_type": "deep_lead_research",
        "payload": {"query": "AI companies"},
        "checkpoint": {"version": 1, "phase": "crawl", "subtasks": []},
    }

    executor = LangGraphMissionExecutor(fake_client)  # type: ignore[arg-type]
    await executor.run(mission)

    assert fake_client.mission.get("status") == "success"
    assert fake_client.mission.get("phase") == "terminal"
    assert fake_client.mission.get("current_subtask_id") is None
    assert fake_client.mission.get("progress_percent") == 100
    checkpoint = fake_client.mission.get("checkpoint", {})
    assert checkpoint.get("current_subtask_id") is None
    assert checkpoint.get("phase") == "terminal"
