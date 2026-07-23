"""Unit tests for unified memory service (Story 3.8)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.db import Memory

pytestmark = [pytest.mark.unit, pytest.mark.memory]


class _FakeResult:
    def __init__(self, value=None, rows=None):
        self._value = value
        self._rows = rows or []

    async def scalar_one_or_none(self):
        return self._value

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, scalar_value=None, rows=None):
        self.commit_calls = 0
        self.added: list = []
        self.scalar_value = scalar_value
        self.rows = rows or []

    def add(self, obj) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commit_calls += 1

    async def execute(self, *_args, **_kwargs):
        return _FakeResult(self.scalar_value, self.rows)

    async def refresh(self, obj, attribute_names=None):
        return obj


@pytest.mark.asyncio
async def test_repository_dedup_updates_existing_memory():
    """High-similarity memory triggers update instead of duplicate insert."""
    from app.services.memory.repository import MemoryRepository

    fake_session = _FakeSession(scalar_value=None)
    repo = MemoryRepository(session=fake_session)
    existing = MagicMock(spec=Memory)
    existing.id = 1

    with patch.object(
        repo,
        "_find_near_duplicate",
        side_effect=[None, existing],
    ):
        created = await repo.create_memory(
            workspace_id=1,
            content="Fact one",
            embedding=[0.1] * 384,
            type="semantic",
        )
        assert isinstance(created, Memory)

        updated = await repo.create_memory(
            workspace_id=1,
            content="Fact one",
            embedding=[0.1] * 384,
            type="semantic",
        )
        assert updated.id == 1
        assert fake_session.commit_calls == 2


@pytest.mark.asyncio
async def test_hybrid_search_ranking_prefers_keyword_and_semantic_overlap():
    """RRF combines vector and keyword ranks; closest match wins."""
    from app.services.memory.search import MemoryHybridSearch

    memory1 = SimpleNamespace(
        id=1,
        content="Competitor X pricing strategy 2026",
        type="semantic",
        tags=[],
        confidence=1.0,
        source_type="manual",
        source_id=None,
    )
    memory2 = SimpleNamespace(
        id=2,
        content="Market strategy overview",
        type="semantic",
        tags=[],
        confidence=1.0,
        source_type="manual",
        source_id=None,
    )

    fake_session = _FakeSession(rows=[(memory1, 0.9), (memory2, 0.7)])
    search = MemoryHybridSearch(session=fake_session)
    results = await search.search(
        workspace_id=1,
        query="pricing strategy",
        query_embedding=[0.1] * 384,
        top_k=2,
    )

    assert len(results) == 2
    assert results[0].content == "Competitor X pricing strategy 2026"
    assert results[1].content == "Market strategy overview"


def test_parser_extracts_facts_from_markdown():
    """Parser turns legacy markdown bullets into structured Memory facts."""
    from app.services.memory.parser import parse_memory_markdown_to_facts

    markdown = "## Facts\n- 2026-07-22: Fact one\n- 2026-07-23: Fact two\n"
    facts = parse_memory_markdown_to_facts(markdown)

    assert len(facts) == 2
    assert facts[0].content == "Fact one"
    assert facts[1].content == "Fact two"
    assert all(f.type == "semantic" for f in facts)


def test_renderer_outputs_markdown_from_memory_rows():
    """Renderer turns Memory rows into the legacy markdown shape."""
    from app.services.memory.renderer import render_memory_markdown

    class FakeMemory:
        id = 1
        content = "Fact one"
        created_at = "2026-07-22T00:00:00"
        type = "semantic"

    markdown = render_memory_markdown([FakeMemory()], scope="team")
    assert "## Facts" in markdown
    assert "Fact one" in markdown
    assert "2026-07-22" in markdown
