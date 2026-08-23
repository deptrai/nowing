"""Tests for the canonical persisted ``[citation:<payload>]`` parser."""

from __future__ import annotations

import pytest

from app.agents.chat.multi_agent_chat.shared.citations.parser import (
    ChunkCitationMarker,
    RunCitationMarker,
    UrlCitationMarker,
    parse_citation_markers,
)

pytestmark = pytest.mark.unit


def test_parses_url_marker() -> None:
    markers = parse_citation_markers("See [citation:https://example.com/a]")
    assert len(markers) == 1
    assert isinstance(markers[0], UrlCitationMarker)
    assert markers[0].url == "https://example.com/a"


def test_parses_chunk_marker() -> None:
    markers = parse_citation_markers("Chunk [citation:42]")
    assert len(markers) == 1
    assert isinstance(markers[0], ChunkCitationMarker)
    assert markers[0].chunk_id == 42
    assert markers[0].is_docs_chunk is False


def test_parses_doc_chunk_marker() -> None:
    markers = parse_citation_markers("Doc [citation:doc-7]")
    assert len(markers) == 1
    assert isinstance(markers[0], ChunkCitationMarker)
    assert markers[0].chunk_id == 7
    assert markers[0].is_docs_chunk is True


def test_parses_multi_id_payload() -> None:
    markers = parse_citation_markers("[citation:1, doc-2, 3]")
    assert len(markers) == 3
    assert markers[0].chunk_id == 1  # type: ignore[union-attr]
    assert markers[1].chunk_id == 2  # type: ignore[union-attr]
    assert markers[2].chunk_id == 3  # type: ignore[union-attr]


def test_parses_run_marker() -> None:
    run_id = "run_550e8400-e29b-41d4-a716-446655440000"
    markers = parse_citation_markers(f"Run [citation:{run_id}]")
    assert len(markers) == 1
    assert isinstance(markers[0], RunCitationMarker)
    assert markers[0].run_id == run_id


def test_skips_negative_chunk_ids() -> None:
    markers = parse_citation_markers("[citation:-5]")
    assert markers == []


def test_skips_unparseable_payload() -> None:
    markers = parse_citation_markers("[citation:not-a-number]")
    assert markers == []


def test_skips_unterminated_marker() -> None:
    markers = parse_citation_markers("[citation:https://example.com")
    assert markers == []


def test_drops_urlcite_placeholder() -> None:
    markers = parse_citation_markers("[citation:urlcite3]")
    assert markers == []
