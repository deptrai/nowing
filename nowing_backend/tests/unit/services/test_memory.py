"""Unit tests for unified memory service (Story 3.8)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.db import Memory

pytestmark = [pytest.mark.unit, pytest.mark.memory]


class _FakeResult:
    def __init__(self, value=None, rows=None):
        self._value = value
        self._rows = rows or []

    def scalar_one_or_none(self):
        return self._value

    def scalar_one(self):
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

    def expire(self, obj, attribute_names=None):
        pass


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


def test_hybrid_search_scope_requires_exactly_one_of_workspace_or_user():
    """D5: missing scope raises before any SQL is built — no broad OR."""
    from app.services.memory.search import MemoryHybridSearch

    with pytest.raises(ValueError):
        MemoryHybridSearch._scope_conditions(
            workspace_id=None, user_id=None, research_thread_id=None
        )


def test_hybrid_search_scope_rejects_both_workspace_and_user():
    """D5: ambiguous scope (both set) raises before any SQL is built."""
    from uuid import uuid4

    from app.services.memory.search import MemoryHybridSearch

    with pytest.raises(ValueError):
        MemoryHybridSearch._scope_conditions(
            workspace_id=1, user_id=uuid4(), research_thread_id=None
        )


def test_hybrid_search_thread_scope_requires_workspace():
    """D5: research_thread_id is workspace-only; personal + thread raises."""
    from uuid import uuid4

    from app.services.memory.search import MemoryHybridSearch

    with pytest.raises(ValueError):
        MemoryHybridSearch._scope_conditions(
            workspace_id=None, user_id=uuid4(), research_thread_id=7
        )


def test_hybrid_search_valid_scopes_do_not_raise():
    """A single non-None scope (workspace OR user) is accepted."""
    from uuid import uuid4

    from app.services.memory.search import MemoryHybridSearch

    MemoryHybridSearch._scope_conditions(
        workspace_id=1, user_id=None, research_thread_id=None
    )
    MemoryHybridSearch._scope_conditions(
        workspace_id=None, user_id=uuid4(), research_thread_id=None
    )
    MemoryHybridSearch._scope_conditions(
        workspace_id=1, user_id=None, research_thread_id=7
    )


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
