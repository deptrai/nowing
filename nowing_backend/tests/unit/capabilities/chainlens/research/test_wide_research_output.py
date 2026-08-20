"""Red-phase unit tests for chainlens.research output/output_schema support (Story 26.9a)."""

from __future__ import annotations

import pytest

from app.capabilities.chainlens.research.schemas import ResearchInput, ResearchOutput

pytestmark = pytest.mark.unit


def test_research_input_accepts_output_table_and_output_schema() -> None:
    """AC-3: ResearchInput must accept output='table' and an output_schema."""
    schema = {
        "type": "object",
        "properties": {
            "topics": {"type": "array", "items": {"type": "string"}},
            "sources": {"type": "array"},
            "matrix": {"type": "array"},
        },
    }
    payload = ResearchInput(
        query="so sánh 20 framework AI Agent 2026",
        output="table",
        output_schema=schema,
    )
    assert payload.output == "table"
    assert payload.output_schema == schema


def test_research_output_has_structured_output() -> None:
    """AC-4: ResearchOutput must carry parsed structured output from the ChainLens done frame."""
    matrix = {
        "topics": ["langchain", "langgraph"],
        "sources": [{"title": "X", "url": "https://x.com"}],
        "matrix": [[True, False]],
    }
    output = ResearchOutput(
        answer="",
        sources=[{"title": "X", "url": "https://x.com"}],
        structured_output=matrix,
    )
    assert output.structured_output == matrix
