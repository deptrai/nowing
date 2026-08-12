"""Unit tests for ``MemoryHybridSearch`` result handling and bounds (Story 3.14).

These are pure unit tests: the SQL layer is mocked so the focus is on
validation, metadata parsing, scope, and ``top_k`` boundaries.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.services.memory.search import MemoryHybridSearch, _ranked_metadata_reason

pytestmark = [pytest.mark.unit, pytest.mark.memory]


class _FakeResult:
    def __init__(self, rows: list[tuple[object, object, object]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[object, object, object]]:
        return self._rows

    def scalars(self) -> _FakeResult:
        return self


class _FakeMemory:
    def __init__(self, *, embedding: list[float] | None, memory_id: int = 1) -> None:
        self.id = memory_id
        self.embedding = embedding
        self.created_at = "2026-07-26"
        self.type = "semantic"


def _make_session(rows: list[tuple[object, object, object]]) -> MagicMock:
    session = MagicMock()
    session.execute = AsyncMock(return_value=_FakeResult(rows))
    return session


def _make_search(
    rows: list[tuple[object, object, object]],
    *,
    dim: int = 3,
    monkeypatch: pytest.MonkeyPatch,
) -> MemoryHybridSearch:
    import app.services.memory.search as search_module

    monkeypatch.setattr(
        search_module.config, "embedding_model_instance", SimpleNamespace(dimension=dim)
    )
    session = _make_session(rows)
    return MemoryHybridSearch(session)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "top_k",
    [0, True, 6, -1, 5.0, "5"],
    ids=["zero", "bool-True", "above-five", "negative", "float", "string"],
)
async def test_search_rejects_out_of_bounds_top_k(
    top_k: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D9: internal search raises for 0, bool, 6+, or non-integer top_k."""
    search = _make_search([], monkeypatch=monkeypatch)
    with pytest.raises(ValueError, match="top_k must be a positive integer"):
        await search.search(
            workspace_id=1,
            query="test",
            query_embedding=[0.1, 0.2, 0.3],
            top_k=top_k,  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "workspace_id,user_id,research_thread_id",
    [
        (None, None, None),
        (1, uuid4(), None),
        (None, uuid4(), 7),
        (1, uuid4(), 7),
    ],
    ids=[
        "neither-scope",
        "both-workspace-and-user",
        "thread-without-workspace",
        "thread-with-both-scopes",
    ],
)
async def test_search_rejects_ambiguous_scope(
    workspace_id: int | None,
    user_id: object,
    research_thread_id: int | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A7/D5: ambiguous or missing scope with/without a thread is rejected."""
    search = _make_search([], monkeypatch=monkeypatch)
    with pytest.raises(ValueError):
        await search.search(
            workspace_id=workspace_id,
            user_id=user_id,
            query="test",
            query_embedding=[0.1, 0.2, 0.3],
            research_thread_id=research_thread_id,
            top_k=5,
        )


@pytest.mark.asyncio
async def test_search_skips_non_numeric_metadata_and_logs_reason(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A2: non-numeric score/similarity must be skipped with the non_numeric reason."""
    memory = _FakeMemory(embedding=[0.1, 0.2, 0.3])
    search = _make_search([(memory, "not-a-number", 0.9)], monkeypatch=monkeypatch)

    with caplog.at_level("WARNING", logger="app.services.memory.search"):
        hits = await search.search(
            workspace_id=1,
            query="test",
            query_embedding=[0.1, 0.2, 0.3],
            top_k=5,
        )

    assert hits == []
    assert "non_numeric" in caplog.text


@pytest.mark.asyncio
async def test_search_skips_missing_metadata_and_logs_reason(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A2: missing score/similarity must be skipped with the missing reason."""
    memory = _FakeMemory(embedding=[0.1, 0.2, 0.3])
    search = _make_search([(memory, 0.9, None)], monkeypatch=monkeypatch)

    with caplog.at_level("WARNING", logger="app.services.memory.search"):
        hits = await search.search(
            workspace_id=1,
            query="test",
            query_embedding=[0.1, 0.2, 0.3],
            top_k=5,
        )

    assert hits == []
    assert "missing" in caplog.text


@pytest.mark.asyncio
async def test_search_skips_non_finite_metadata_and_logs_reason(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A2: NaN/Inf score/similarity must be skipped with the non_finite reason."""
    memory = _FakeMemory(embedding=[0.1, 0.2, 0.3])
    search = _make_search([(memory, float("nan"), 0.9)], monkeypatch=monkeypatch)

    with caplog.at_level("WARNING", logger="app.services.memory.search"):
        hits = await search.search(
            workspace_id=1,
            query="test",
            query_embedding=[0.1, 0.2, 0.3],
            top_k=5,
        )

    assert hits == []
    assert "non_finite" in caplog.text


def test_ranked_metadata_reason() -> None:
    """``_ranked_metadata_reason`` returns the correct typed reason or None."""
    assert _ranked_metadata_reason(None, 0.9) == "missing"
    assert _ranked_metadata_reason(0.9, None) == "missing"
    assert _ranked_metadata_reason("abc", 0.9) == "non_numeric"
    assert _ranked_metadata_reason(0.9, "abc") == "non_numeric"
    assert _ranked_metadata_reason(float("nan"), 0.9) == "non_finite"
    assert _ranked_metadata_reason(float("inf"), 0.9) == "non_finite"
    assert _ranked_metadata_reason(0.5, 0.9) is None


def _compile_conditions(conditions: list[object]) -> str:
    """Render scope conditions to SQL for assertion without a real DB."""
    return str(
        select(1)
        .where(*conditions)
        .compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def test_scope_conditions_client_set() -> None:
    """AC-18.6: a scoped request hard-filters to the supplied client_id."""
    conditions = MemoryHybridSearch._scope_conditions(
        workspace_id=1,
        user_id=None,
        research_thread_id=None,
        client_id="bds",
    )
    sql = _compile_conditions(conditions)
    assert "memories.client_id = 'bds'" in sql
    assert "memories.client_id IS NULL" not in sql


def test_scope_conditions_client_unset() -> None:
    """AC-18.6: an unscoped request only sees client_id IS NULL rows."""
    conditions = MemoryHybridSearch._scope_conditions(
        workspace_id=1,
        user_id=None,
        research_thread_id=None,
        client_id=None,
    )
    sql = _compile_conditions(conditions)
    assert "memories.client_id IS NULL" in sql
    assert "memories.client_id = " not in sql


def test_scope_conditions_client_mismatched() -> None:
    """AC-18.6: a different client value still produces a strict literal filter."""
    conditions = MemoryHybridSearch._scope_conditions(
        workspace_id=1,
        user_id=None,
        research_thread_id=None,
        client_id="other",
    )
    sql = _compile_conditions(conditions)
    assert "memories.client_id = 'other'" in sql
    assert "memories.client_id = 'bds'" not in sql


@pytest.mark.asyncio
async def test_search_passes_client_id_to_tenant_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``search`` threads the supplied client_id through to GUCs and scope."""
    import app.services.memory.search as search_module

    monkeypatch.setattr(search_module, "set_request_tenant_context", AsyncMock())
    search = _make_search([], monkeypatch=monkeypatch)

    await search.search(
        workspace_id=1,
        query="test",
        query_embedding=[0.1, 0.2, 0.3],
        top_k=5,
        client_id="bds",
    )

    call_kwargs = search_module.set_request_tenant_context.call_args.kwargs
    assert call_kwargs["workspace_id"] == 1
    assert call_kwargs["client_id"] == "bds"


@pytest.mark.asyncio
async def test_search_normalizes_empty_client_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-18.8: an empty client_id string is treated as unscoped."""
    import app.services.memory.search as search_module

    monkeypatch.setattr(search_module, "set_request_tenant_context", AsyncMock())
    search = _make_search([], monkeypatch=monkeypatch)

    await search.search(
        workspace_id=1,
        query="test",
        query_embedding=[0.1, 0.2, 0.3],
        top_k=5,
        client_id="",
    )

    call_kwargs = search_module.set_request_tenant_context.call_args.kwargs
    assert call_kwargs["client_id"] is None
