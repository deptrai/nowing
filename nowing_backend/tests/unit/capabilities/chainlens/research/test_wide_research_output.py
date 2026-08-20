"""Unit tests for chainlens.research output/output_schema support (Story 26.9a)."""

from __future__ import annotations

import json

import pytest

from app.capabilities.chainlens.research.executor import _SSEParser
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


def test_sse_parser_captures_structured_output_from_done() -> None:
    """AC-4: _SSEParser stores the `output` object from a `done` frame."""
    matrix = {
        "topics": ["langchain", "langgraph"],
        "sources": [{"title": "X", "url": "https://x.com"}],
        "matrix": [[True, False]],
    }
    parser = _SSEParser()
    parser.feed_line(f"data: {json.dumps({'type': 'done', 'output': matrix})}")
    output = parser.finalize()
    assert output.structured_output == matrix


def test_sse_parser_parses_output_json_string_from_done() -> None:
    """Edge case: ChainLens may emit `output` as a JSON string."""
    matrix = {
        "topics": ["a", "b"],
        "sources": [{"title": "S", "url": "https://s.com"}],
        "matrix": [[True, False]],
    }
    parser = _SSEParser()
    parser.feed_line(
        f"data: {json.dumps({'type': 'done', 'output': json.dumps(matrix)})}"
    )
    output = parser.finalize()
    assert output.structured_output == matrix


def test_sse_parser_captures_output_block() -> None:
    """Edge case: ChainLens may stream the table as a `block { type: 'output' }`."""
    matrix = {
        "topics": ["a"],
        "sources": [{"title": "S", "url": "https://s.com"}],
        "matrix": [[True]],
    }
    parser = _SSEParser()
    parser.feed_line(
        f"data: {json.dumps({'type': 'block', 'block': {'id': 'out-1', 'type': 'output', 'data': matrix}})}"
    )
    output = parser.finalize()
    assert output.structured_output == matrix


def test_billable_units_counts_structured_output() -> None:
    """A table-only result must still bill one unit."""
    output = ResearchOutput(
        answer="",
        sources=[],
        structured_output={"topics": ["a"], "sources": [], "matrix": []},
    )
    assert output.billable_units == 1
