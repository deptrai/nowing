"""Tests for the web citation registration helper."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.agents.chat.multi_agent_chat.shared.citations import (
    CitationRegistry,
    CitationSourceType,
)
from app.capabilities.core.access.web_citation import register_web_citations

pytestmark = pytest.mark.unit


@dataclass
class _FakeSource:
    url: str
    title: str | None = None


def test_registers_each_url_as_web_result() -> None:
    registry = CitationRegistry()
    sources = [
        _FakeSource(url="https://example.com/a", title="Page A"),
        _FakeSource(url="https://example.com/b", title="Page B"),
        _FakeSource(url="https://example.com/c", title=None),
    ]

    ordinals = register_web_citations(registry, sources)

    assert ordinals == [1, 2, 3]
    for n, src in zip(ordinals, sources, strict=True):
        entry = registry.resolve(n)
        assert entry is not None
        assert entry.source_type == CitationSourceType.WEB_RESULT
        assert entry.locator == {"url": src.url}
    # Title stored in display when present, empty dict when not.
    assert registry.resolve(1).display == {"title": "Page A"}
    assert registry.resolve(3).display == {}


def test_duplicate_url_keeps_same_ordinal() -> None:
    registry = CitationRegistry()
    sources = [
        _FakeSource(url="https://example.com/a", title="First"),
        _FakeSource(url="https://example.com/a", title="Second"),
    ]

    ordinals = register_web_citations(registry, sources)

    assert ordinals == [1, 1]
    assert len(registry.by_n) == 1


def test_empty_url_skipped() -> None:
    registry = CitationRegistry()
    sources = [
        _FakeSource(url="", title="Empty"),
        _FakeSource(url="https://example.com/a", title="Good"),
        _FakeSource(url="  ", title="Whitespace"),
    ]

    ordinals = register_web_citations(registry, sources)

    assert ordinals == [1]
    assert len(registry.by_n) == 1


def test_empty_sources_returns_empty_list() -> None:
    registry = CitationRegistry()
    assert register_web_citations(registry, []) == []
    assert len(registry.by_n) == 0


def test_web_result_and_run_coexist() -> None:
    """RUN and WEB_RESULT citations should coexist without collision."""
    from app.capabilities.core.access.run_citation import attach_run_citation

    registry = CitationRegistry()
    n_run, _ = attach_run_citation(
        registry,
        run_external_id="run_550e8400-e29b-41d4-a716-446655440000",
        capability="chainlens.research",
    )
    n_web = register_web_citations(
        registry,
        [_FakeSource(url="https://example.com/source", title="Evidence")],
    )

    assert n_run == 1
    assert n_web == [2]
    assert registry.resolve(1).source_type == CitationSourceType.RUN
    assert registry.resolve(2).source_type == CitationSourceType.WEB_RESULT


def test_frontend_payload_returns_url() -> None:
    """The marker resolver should return the URL for WEB_RESULT entries."""
    from app.agents.chat.multi_agent_chat.shared.citations.markers import (
        to_frontend_payload,
    )

    registry = CitationRegistry()
    register_web_citations(
        registry,
        [_FakeSource(url="https://example.com/page", title="Page")],
    )

    entry = registry.resolve(1)
    payload = to_frontend_payload(entry)
    assert payload == "https://example.com/page"


def test_merge_preserves_web_results_from_both_branches() -> None:
    """Two branches each register different WEB_RESULT citations; merge keeps both."""
    branch_a = CitationRegistry()
    register_web_citations(
        branch_a,
        [_FakeSource(url="https://example.com/a", title="Page A")],
    )

    branch_b = CitationRegistry()
    register_web_citations(
        branch_b,
        [_FakeSource(url="https://example.com/b", title="Page B")],
    )

    merged = branch_a.merge(branch_b)

    assert len(merged.by_n) == 2
    entry_a = merged.resolve(1)
    entry_b = merged.resolve(2)
    assert entry_a is not None and entry_a.source_type == CitationSourceType.WEB_RESULT
    assert entry_b is not None and entry_b.source_type == CitationSourceType.WEB_RESULT
    assert entry_a.locator["url"] == "https://example.com/a"
    assert entry_b.locator["url"] == "https://example.com/b"
    assert entry_a.display["title"] == "Page A"


def test_merge_dedups_same_url_across_branches() -> None:
    """The same URL registered in both branches should merge to a single entry."""
    url = "https://example.com/shared"
    branch_a = CitationRegistry()
    register_web_citations(
        branch_a, [_FakeSource(url=url, title="First")]
    )

    branch_b = CitationRegistry()
    register_web_citations(
        branch_b, [_FakeSource(url=url, title="Second")]
    )

    merged = branch_a.merge(branch_b)

    assert len(merged.by_n) == 1
    entry = merged.resolve(1)
    assert entry is not None
    assert entry.source_type == CitationSourceType.WEB_RESULT
    assert entry.locator["url"] == url
