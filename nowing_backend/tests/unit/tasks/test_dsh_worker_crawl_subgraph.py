"""Red-phase unit tests for WideResearchCrawlSubgraph (Story 26.9a)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from app.tasks.dsh_worker import DshRestClient

pytestmark = pytest.mark.unit


@pytest.mark.skip("RED: app.tasks.dsh_worker_crawl_subgraph not implemented (Story 26.9a)")
@pytest.mark.asyncio
async def test_subgraph_builds_and_persists_matrix() -> None:
    """AC-1, AC-4, AC-5: WideResearchCrawlSubgraph builds a graph, runs it, and persists wide_research_matrix + cost."""
    from app.tasks.dsh_worker_crawl_subgraph import WideResearchCrawlSubgraph

    client = DshRestClient("http://localhost", "pat", "secret")  # type: ignore[arg-type]
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
    assert checkpoint["wide_research_matrix"] is not None
    assert checkpoint.get("cost_micros") is not None
    assert checkpoint.get("sources") is not None


@pytest.mark.skip("RED: WideResearchCrawlSubgraph degradation not implemented (Story 26.9a)")
@pytest.mark.asyncio
async def test_subgraph_marks_degraded_when_chainlens_unavailable() -> None:
    """AC-6: If ChainLens returns degraded, the subgraph must set checkpoint.degraded and continue."""
    from app.tasks.dsh_worker_crawl_subgraph import WideResearchCrawlSubgraph

    client = DshRestClient("http://localhost", "pat", "secret")  # type: ignore[arg-type]
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


@pytest.mark.skip("RED: WideResearchCrawlSubgraph resumption not implemented (Story 26.9a)")
@pytest.mark.asyncio
async def test_subgraph_skips_chainlens_when_matrix_already_in_checkpoint() -> None:
    """AC-7: If checkpoint already has wide_research_matrix, skip the ChainLens call and rehydrate."""
    from app.tasks.dsh_worker_crawl_subgraph import WideResearchCrawlSubgraph

    client = DshRestClient("http://localhost", "pat", "secret")  # type: ignore[arg-type]
    graph = WideResearchCrawlSubgraph.build(client)

    matrix = {
        "topics": ["A"],
        "sources": [{"title": "X", "url": "https://x.com"}],
        "matrix": [[True]],
    }
    state: dict[str, Any] = {
        "mission_id": str(uuid4()),
        "workspace_id": 42,
        "query": "so sánh 20 framework AI Agent 2026",
        "payload": {"query": "...", "extras": {"research_mode": "wide"}},
        "checkpoint": {
            "version": 1,
            "subtasks": [{"id": "crawl", "status": "success"}],
            "wide_research_matrix": matrix,
            "sources": matrix["sources"],
        },
    }
    final_state = await graph.ainvoke(state)
    assert final_state["checkpoint"]["wide_research_matrix"] == matrix
