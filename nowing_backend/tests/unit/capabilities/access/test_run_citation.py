"""Tests for the run citation attachment helper."""

from __future__ import annotations

import pytest

from app.agents.chat.multi_agent_chat.shared.citations import (
    CitationRegistry,
    CitationSourceType,
)
from app.capabilities.core.access.run_citation import attach_run_citation

pytestmark = pytest.mark.unit


def test_attaches_run_and_returns_label_with_ordinal() -> None:
    registry = CitationRegistry()
    n, label = attach_run_citation(
        registry,
        run_external_id="run_550e8400-e29b-41d4-a716-446655440000",
        capability="web.scrape",
    )

    assert n == 1
    assert "[1]" in label
    assert "Cite this scraper run" in label
    entry = registry.resolve(1)
    assert entry is not None
    assert entry.source_type == CitationSourceType.RUN
    assert entry.locator == {"run_id": "run_550e8400-e29b-41d4-a716-446655440000"}
    assert entry.display == {"capability": "web.scrape"}


def test_same_run_dedups_to_one_label() -> None:
    registry = CitationRegistry()
    n1, _ = attach_run_citation(
        registry,
        run_external_id="run_550e8400-e29b-41d4-a716-446655440000",
        capability="web.scrape",
    )
    n2, _ = attach_run_citation(
        registry,
        run_external_id="run_550e8400-e29b-41d4-a716-446655440000",
        capability="web.scrape",
    )

    assert n1 == n2 == 1
    assert len(registry.by_n) == 1


def test_merge_preserves_run_citations_from_both_branches() -> None:
    # Two subagent branches each register a different RUN citation; merge
    # must keep both with stable ordinals and no loss.
    branch_a = CitationRegistry()
    attach_run_citation(
        branch_a,
        run_external_id="run_aaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        capability="web.scrape",
    )

    branch_b = CitationRegistry()
    attach_run_citation(
        branch_b,
        run_external_id="run_bbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        capability="amazon.scrape",
    )

    merged = branch_a.merge(branch_b)

    assert len(merged.by_n) == 2
    # branch_a's run keeps [1]; branch_b's run gets [2] (no collision).
    entry_a = merged.resolve(1)
    entry_b = merged.resolve(2)
    assert entry_a is not None and entry_a.source_type == CitationSourceType.RUN
    assert entry_b is not None and entry_b.source_type == CitationSourceType.RUN
    assert entry_a.locator["run_id"] == "run_aaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert entry_b.locator["run_id"] == "run_bbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def test_merge_dedups_same_run_across_branches() -> None:
    # The same run registered in both branches should merge to a single entry.
    run_id = "run_550e8400-e29b-41d4-a716-446655440000"
    branch_a = CitationRegistry()
    attach_run_citation(branch_a, run_external_id=run_id, capability="web.scrape")

    branch_b = CitationRegistry()
    attach_run_citation(branch_b, run_external_id=run_id, capability="web.scrape")

    merged = branch_a.merge(branch_b)

    assert len(merged.by_n) == 1
    assert merged.resolve(1).locator["run_id"] == run_id
