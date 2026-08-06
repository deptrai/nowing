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
