from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.capabilities.chainlens.research.schemas import ResearchInput, ResearchOutput

pytestmark = pytest.mark.unit


def test_research_input_estimated_units_is_one():
    payload = ResearchInput(query="test")
    assert payload.estimated_units == 1


def test_research_input_requires_query():
    with pytest.raises(ValidationError):
        ResearchInput()


def test_research_input_rejects_oversized_system_instructions():
    with pytest.raises(ValidationError):
        ResearchInput(query="test", system_instructions="x" * 2001)


def test_research_input_rejects_oversized_history():
    with pytest.raises(ValidationError):
        ResearchInput(query="test", history=[("human", "hi")] * 51)


def test_research_output_billable_units_zero_without_content():
    output = ResearchOutput(status="insufficient_evidence")
    assert output.billable_units == 0


def test_research_output_billable_units_one_with_answer():
    output = ResearchOutput(answer="answer")
    assert output.billable_units == 1


def test_research_output_billable_units_one_with_sources():
    output = ResearchOutput(sources=[{"title": "Source", "url": "https://example.com"}])
    assert output.billable_units == 1
