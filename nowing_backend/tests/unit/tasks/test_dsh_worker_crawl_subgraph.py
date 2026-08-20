"""Unit tests for WideResearchCrawlSubgraph (Story 26.9a)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from app.tasks.dsh_worker_crawl_subgraph import WideResearchCrawlSubgraph

pytestmark = pytest.mark.unit


class _FakeDshRestClient:
    """Fake DshRestClient for hermetic wide-research subgraph tests."""

    def __init__(self, response: dict[str, Any] | None = None, exc: Exception | None = None) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.response = response or {}
        self.exc = exc

    async def chainlens_research(
        self,
        workspace_id: int,
        query: str,
        output: str | None = None,
        output_schema: dict[str, Any] | None = None,
        mode: str = "balanced",
    ) -> dict[str, Any]:
        self.calls.append(("chainlens_research", (workspace_id, query), {
            "output": output,
            "output_schema": output_schema,
            "mode": mode,
        }))
        if self.exc is not None:
            raise self.exc
        return self.response


@pytest.fixture
def sample_matrix() -> dict[str, Any]:
    return {
        "topics": ["langchain", "langgraph"],
        "sources": [{"title": "X", "url": "https://x.com", "source_type": "web"}],
        "matrix": [[True, False]],
    }


@pytest.mark.asyncio
async def test_subgraph_builds_and_persists_matrix(sample_matrix: dict[str, Any]) -> None:
    """AC-1, AC-4, AC-5: WideResearchCrawlSubgraph builds, runs, and persists wide_research_matrix + cost."""
    client = _FakeDshRestClient(
        response={
            "status": "complete",
            "structured_output": sample_matrix,
            "sources": sample_matrix["sources"],
            "cost_micros": 12345,
        }
    )
    graph = WideResearchCrawlSubgraph.build(client)
    assert graph is not None

    state: dict[str, Any] = {
        "mission_id": str(uuid4()),
        "workspace_id": 42,
        "query": "so sánh 20 framework AI Agent 2026",
        "payload": {
            "query": "so sánh 20 framework AI Agent 2026",
            "extras": {"research_mode": "wide"},
        },
        "checkpoint": {"version": 1, "subtasks": []},
    }
    final_state = await graph.ainvoke(state)
    checkpoint = final_state["checkpoint"]
    assert checkpoint["wide_research_matrix"] == sample_matrix
    assert checkpoint.get("cost_micros") == 12345
    assert checkpoint.get("sources") == sample_matrix["sources"]
    assert final_state["phase"] == "reasoning"

    # AC-2: verify the call payload
    assert len(client.calls) == 1
    _, _, kwargs = client.calls[0]
    assert kwargs["output"] == "table"
    assert kwargs["output_schema"] is not None
    assert kwargs["mode"] == "balanced"


@pytest.mark.asyncio
async def test_subgraph_marks_degraded_when_chainlens_unavailable() -> None:
    """AC-6: If ChainLens fails, the subgraph must set checkpoint.degraded and continue."""
    client = _FakeDshRestClient(exc=RuntimeError("upstream refused"))
    graph = WideResearchCrawlSubgraph.build(client)

    state: dict[str, Any] = {
        "mission_id": str(uuid4()),
        "workspace_id": 42,
        "query": "unreachable query",
        "payload": {"query": "unreachable query", "extras": {"research_mode": "wide"}},
        "checkpoint": {"version": 1, "subtasks": []},
    }
    final_state = await graph.ainvoke(state)
    checkpoint = final_state["checkpoint"]
    assert checkpoint.get("degraded") is True
    assert final_state["phase"] == "reasoning"


@pytest.mark.asyncio
async def test_subgraph_marks_degraded_for_partial_status() -> None:
    """AC-6: If ChainLens returns a non-complete status, the subgraph must mark degraded."""
    client = _FakeDshRestClient(
        response={
            "status": "partial",
            "degradation_reason": "insufficient_evidence",
            "sources": [],
            "cost_micros": 0,
        }
    )
    graph = WideResearchCrawlSubgraph.build(client)

    state: dict[str, Any] = {
        "mission_id": str(uuid4()),
        "workspace_id": 42,
        "query": "partial query",
        "payload": {"query": "partial query", "extras": {"research_mode": "wide"}},
        "checkpoint": {"version": 1, "subtasks": []},
    }
    final_state = await graph.ainvoke(state)
    checkpoint = final_state["checkpoint"]
    assert checkpoint.get("degraded") is True
    assert final_state["phase"] == "reasoning"


@pytest.mark.asyncio
async def test_subgraph_skips_chainlens_when_matrix_already_in_checkpoint(
    sample_matrix: dict[str, Any],
) -> None:
    """AC-7: If checkpoint already has wide_research_matrix, skip the ChainLens call and rehydrate."""
    client = _FakeDshRestClient(response={})  # would fail if called
    graph = WideResearchCrawlSubgraph.build(client)

    state: dict[str, Any] = {
        "mission_id": str(uuid4()),
        "workspace_id": 42,
        "query": "so sánh 20 framework AI Agent 2026",
        "payload": {"query": "...", "extras": {"research_mode": "wide"}},
        "checkpoint": {
            "version": 1,
            "subtasks": [{"id": "crawl", "status": "success"}],
            "wide_research_matrix": sample_matrix,
            "sources": sample_matrix["sources"],
        },
    }
    final_state = await graph.ainvoke(state)
    assert final_state["checkpoint"]["wide_research_matrix"] == sample_matrix
    assert not client.calls
