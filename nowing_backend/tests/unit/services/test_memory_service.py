"""Unit tests for the first-class memory service bridge."""

from __future__ import annotations

import pytest

from app.services.memory import (
    MemoryScope,
    read_memory,
    reset_memory,
    save_memory,
)

pytestmark = pytest.mark.unit


class _FakeResult:
    def __init__(self, rows: list | None = None):
        self._rows = rows or []

    def scalars(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeMemory:
    def __init__(self, content: str, created_at: str, type: str = "semantic") -> None:
        self.id = 1
        self.content = content
        self.created_at = created_at
        self.type = type


class _FakeSession:
    def __init__(self, rows: list | None = None) -> None:
        self.commit_calls = 0
        self.rollback_calls = 0
        self.added: list = []
        self.rows = rows or []

    def add(self, obj) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commit_calls += 1

    async def rollback(self) -> None:
        self.rollback_calls += 1

    async def execute(self, *_args, **_kwargs):
        return _FakeResult(self.rows)

    async def delete(self, *_args, **_kwargs):
        pass


@pytest.mark.asyncio
async def test_read_memory_renders_from_memory_rows() -> None:
    session = _FakeSession(rows=[_FakeMemory("Fact one", "2026-07-22T00:00:00")])
    markdown = await read_memory(
        scope=MemoryScope.TEAM,
        target_id=1,
        session=session,
    )
    assert "## Facts" in markdown
    assert "Fact one" in markdown


@pytest.mark.asyncio
async def test_reset_memory_commits_delete() -> None:
    session = _FakeSession()
    result = await reset_memory(
        scope=MemoryScope.TEAM,
        target_id=1,
        session=session,
    )
    assert result.status == "saved"
    assert result.memory_md == ""
    assert session.commit_calls == 1


@pytest.mark.asyncio
async def test_save_memory_no_update_sentinel_is_no_op() -> None:
    session = _FakeSession()
    result = await save_memory(
        scope=MemoryScope.USER,
        target_id="00000000-0000-0000-0000-000000000000",
        content="NO_UPDATE",
        session=session,
    )
    assert result.status == "no_op"
    assert "No memory update requested" in result.message
    assert session.commit_calls == 0


@pytest.mark.asyncio
async def test_save_memory_rejects_no_heading() -> None:
    session = _FakeSession()
    result = await save_memory(
        scope=MemoryScope.USER,
        target_id="00000000-0000-0000-0000-000000000000",
        content="Just some reasoning text without a heading.",
        session=session,
    )
    assert result.status == "error"
    assert session.commit_calls == 0
