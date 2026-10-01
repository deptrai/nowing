"""Unit tests for native wide_research matrix upgrade (Story 26.9c)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.tasks.dsh_worker_crawl_subgraph import (
    WideResearchCrawlSubgraph,
    _coerce_num_entities,
)

pytestmark = pytest.mark.unit


def _make_state(num_entities: int | None = 25) -> dict:
    payload = {"extras": {"mode": "balanced"}}
    if num_entities is not None:
        payload["extras"]["numEntities"] = num_entities
    return {
        "workspace_id": 15,
        "query": "Compare top AI search engines",
        "payload": payload,
        "checkpoint": {},
        "subtasks": [],
    }


def _make_subgraph():
    subgraph = WideResearchCrawlSubgraph.__new__(WideResearchCrawlSubgraph)
    subgraph._rest_client = MagicMock()
    subgraph._rest_client.chainlens_research = AsyncMock(
        return_value={
            "answer": "matrix",
            "structured_output": {
                "topics": ["AI Search"],
                "sources": [{"name": "Perplexity", "url": "https://pplx.ai"}],
                "matrix": [[True]],
            },
            "sources": [{"name": "Perplexity", "url": "https://pplx.ai"}],
            "cost_micros": 50_000,
            "status": "complete",
        }
    )
    return subgraph


class TestNativeWideResearchOutput:
    async def test_crawl_uses_wide_research_output(self):
        """Crawl subgraph must request output='wide_research' (Story 26.9c)."""
        subgraph = _make_subgraph()
        state = _make_state(num_entities=25)

        result = await subgraph.ainvoke(state)

        call_kwargs = subgraph._rest_client.chainlens_research.call_args.kwargs
        assert call_kwargs["output"] == "wide_research"
        assert call_kwargs["num_entities"] == 25
        assert result["phase"] == "reasoning"

    async def test_num_entities_clamped_to_50(self):
        assert _coerce_num_entities(100) == 50
        assert _coerce_num_entities(25) == 25
        assert _coerce_num_entities(None) is None
        assert _coerce_num_entities(0) is None
        assert _coerce_num_entities("abc") is None

    async def test_research_input_accepts_wide_research_output(self):
        from app.capabilities.chainlens.research.schemas import ResearchInput

        inp = ResearchInput(
            query="test",
            output="wide_research",
            num_entities=25,
            workspace_id=15,
        )
        assert inp.output == "wide_research"
        assert inp.num_entities == 25

    async def test_num_entities_validation_bounds(self):
        from pydantic import ValidationError

        from app.capabilities.chainlens.research.schemas import ResearchInput

        # 51 exceeds the 50 cap
        with pytest.raises(ValidationError):
            ResearchInput(query="x", output="wide_research", num_entities=51)

    async def test_resume_skips_chainlens_call(self):
        """AC-7: checkpoint with valid matrix skips re-invoking ChainLens."""
        subgraph = WideResearchCrawlSubgraph(rest_client=MagicMock())
        subgraph._rest_client.chainlens_research = AsyncMock()

        state = {
            "workspace_id": 15,
            "query": "compare",
            "payload": {"extras": {}},
            "checkpoint": {
                "wide_research_matrix": {
                    "topics": ["t1"],
                    "sources": [{"name": "s1", "url": "https://s1"}],
                    "matrix": [[True]],
                },
                "subtasks": [{"id": "crawl", "status": "success"}],
            },
            "subtasks": [{"id": "crawl", "status": "success"}],
        }

        result = await subgraph.ainvoke(state)

        subgraph._rest_client.chainlens_research.assert_not_called()
        assert result["phase"] == "reasoning"


