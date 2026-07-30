from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.capabilities.chainlens.research.schemas import (
    ResearchInput,
    ResearchOutput,
    Source,
)

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


# Red-phase scaffolds for 9.1a


def test_research_output_status_enum_includes_engine_unavailable():
    from typing import get_args

    allowed = get_args(ResearchOutput.model_fields["status"].annotation)
    assert "engine_unavailable" in allowed


def test_research_output_includes_degradation_fields():
    expected = {
        "degraded",
        "degradation_reason",
        "engine_reason",
        "source_type",
        "document_id",
        "chunk_id",
        "block_type",
    }
    assert expected.issubset(ResearchOutput.model_fields.keys())


def test_source_includes_kb_locator_fields():
    expected = {"document_id", "chunk_id", "source_type"}
    assert expected.issubset(Source.model_fields.keys())


def test_research_output_supports_engine_unavailable_status():
    output = ResearchOutput(status="engine_unavailable")
    assert output.status == "engine_unavailable"


def test_research_output_engine_unavailable_billable_units_is_zero():
    output = ResearchOutput(status="engine_unavailable")
    assert output.billable_units == 0


def test_research_output_partial_with_fallback_is_billable():
    output = ResearchOutput(
        status="partial",
        answer="partial answer",
        sources=[{"title": "KB", "url": "nowing://documents/1/chunks/2"}],
        degraded=True,
    )
    assert output.billable_units == 1
    assert output.degraded is True


def test_source_accepts_internal_kb_url():
    source = Source(
        title="KB Document",
        url="nowing://documents/7/chunks/12",
        document_id=7,
        chunk_id=12,
        source_type="kb",
    )
    assert source.url == "nowing://documents/7/chunks/12"
    assert source.document_id == 7
    assert source.chunk_id == 12
    assert source.source_type == "kb"
