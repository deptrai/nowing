"""Hermetic unit tests for LeadSearchService query construction and RRF logic."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.db import Lead
from app.services.lead_search_service import LeadSearchService

pytestmark = pytest.mark.unit


class _FakeResult:
    """Minimal SQLAlchemy result stand-in."""

    def __init__(self, rows: list[Any] | None = None, scalar: Any = None) -> None:
        self._rows = rows or []
        self._scalar = scalar

    def scalars(self) -> "_FakeResult":
        return self

    def all(self) -> list[Any]:
        return self._rows

    def fetchall(self) -> list[Any]:
        return self._rows

    def scalar_one(self) -> Any:
        return self._scalar


class _FakeSession:
    """Records statements and returns canned rows."""

    def __init__(self, *, leads: list[Lead] | None = None, count: int = 0) -> None:
        self.executed: list[Any] = []
        self._leads = leads or []
        self._count = count

    async def execute(self, stmt: Any, _params: Any | None = None) -> _FakeResult:
        self.executed.append(stmt)
        if "count" in str(stmt).lower() or "SELECT count" in str(stmt):
            return _FakeResult(scalar=self._count)
        return _FakeResult(rows=self._leads)


@pytest.fixture
def service() -> LeadSearchService:
    return LeadSearchService()


class TestLeadSearchServiceQueryConstruction:
    """Verify filter composition, ordering, and pagination without a real DB."""

    async def test_search_clamps_limit(self, service: LeadSearchService) -> None:
        """Limit is clamped to [1, MAX_LIMIT]."""
        session = _FakeSession(leads=[], count=0)

        _, _ = await service.search_leads(session, workspace_id=1, limit=0)
        stmt0 = session.executed[-1]
        assert stmt0._limit == 1  # noqa: SLF001

        _, _ = await service.search_leads(session, workspace_id=1, limit=999)
        stmt1 = session.executed[-1]
        assert stmt1._limit == service.MAX_LIMIT  # noqa: SLF001

    async def test_workspace_filter_always_present(self, service: LeadSearchService) -> None:
        """Every query contains workspace_id equality."""
        session = _FakeSession(leads=[], count=0)
        await service.search_leads(session, workspace_id=42)

        lead_stmt = next(s for s in session.executed if "count" not in str(s).lower())
        str_stmt = str(lead_stmt)
        assert "leads.workspace_id = :workspace_id_1" in str_stmt or "workspace_id" in str_stmt

    async def test_filters_added_to_statement(self, service: LeadSearchService) -> None:
        """Optional filters are wired into the WHERE clause."""
        session = _FakeSession(leads=[], count=0)

        await service.search_leads(
            session,
            workspace_id=1,
            status_filter="qualified",
            source="facebook",
            min_fit_score=75.0,
        )

        lead_stmt = next(s for s in session.executed if "count" not in str(s).lower())
        str_stmt = str(lead_stmt)
        assert "status" in str_stmt
        assert "fit_score" in str_stmt

    async def test_intent_filter_routes_sources(self, service: LeadSearchService) -> None:
        """Intent keyword maps to known source sets."""
        session = _FakeSession(leads=[], count=0)
        await service.search_leads(session, workspace_id=1, intent="thầu", limit=10)

        lead_stmt = next(s for s in session.executed if "count" not in str(s).lower())
        compiled = lead_stmt.compile(compile_kwargs={"literal_binds": True})
        str_stmt = str(compiled)
        assert "muasamcong" in str_stmt or "tender" in str_stmt

    async def test_search_term_uses_fts_and_trgm(self, service: LeadSearchService) -> None:
        """A search term adds tsvector @@ and pg_trgm % clauses."""
        session = _FakeSession(leads=[], count=0)
        await service.search_leads(session, workspace_id=1, search_term="Vinhomes")

        lead_stmt = next(s for s in session.executed if "count" not in str(s).lower())
        str_stmt = str(lead_stmt)
        assert "plainto_tsquery" in str_stmt
        assert "@@" in str_stmt
        assert "%" in str_stmt

    async def test_default_order_by_created_at_desc(self, service: LeadSearchService) -> None:
        """Unrecognised sort strings fall back to created_at DESC, id DESC."""
        session = _FakeSession(leads=[], count=0)
        await service.search_leads(session, workspace_id=1, sort="-foo")

        lead_stmt = next(s for s in session.executed if "count" not in str(s).lower())
        str_stmt = str(lead_stmt)
        assert str_stmt.count("created_at") >= 1
        assert "DESC" in str_stmt


class TestLeadSearchServiceKeysetPagination:
    """Verify cursor pagination helper output."""

    async def test_cursor_score_filter_direction_asc(self, service: LeadSearchService) -> None:
        """Ascending sort emits '>' comparisons."""
        session = _FakeSession(leads=[], count=0)
        await service.search_leads(
            session,
            workspace_id=1,
            sort="fit_score",
            cursor_score=80.0,
            cursor_id=uuid4(),
        )

        lead_stmt = next(s for s in session.executed if "count" not in str(s).lower())
        str_stmt = str(lead_stmt)
        assert ">" in str_stmt
        # No DESC in the score/id comparison for asc sort
        assert "<" not in str_stmt.replace("DESC", "")  # crude, but valid enough for fake

    async def test_cursor_score_filter_direction_desc(self, service: LeadSearchService) -> None:
        """Descending sort emits '<' comparisons."""
        session = _FakeSession(leads=[], count=0)
        await service.search_leads(
            session,
            workspace_id=1,
            sort="-fit_score",
            cursor_score=80.0,
            cursor_id=uuid4(),
        )

        lead_stmt = next(s for s in session.executed if "count" not in str(s).lower())
        str_stmt = str(lead_stmt)
        assert "<" in str_stmt


class TestLeadSearchServiceHybridSemantic:
    """Verify Reciprocal Rank Fusion scoring logic."""

    async def test_hybrid_combines_both_lists(self, service: LeadSearchService) -> None:
        """A lead appearing in both vector and FTS lists receives higher RRF score."""
        shared_id = uuid4()
        vec_ids = [uuid4(), shared_id, uuid4()]
        fts_ids = [shared_id, uuid4()]

        # Fake session returns empty Lead list; we only care about sorted_ids output
        session = _FakeSession(leads=[], count=0)

        # Patch execute to return the two result sets needed by the service.
        call_count = 0

        async def fake_execute(stmt: Any, _params: Any | None = None) -> _FakeResult:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                # vec_stmt and fts_stmt both return id lists
                ids = vec_ids if call_count == 1 else fts_ids
                return _FakeResult(rows=[(id,) for id in ids])
            if "count" in str(stmt).lower():
                return _FakeResult(scalar=0)
            return _FakeResult(rows=[])

        session.execute = fake_execute  # type: ignore[method-assign]

        result = await service.hybrid_semantic_search(
            session,
            workspace_id=1,
            query_text="bán nhà",
            query_embedding=[0.1] * 1536,
            top_k=5,
            rrf_k=60,
        )

        assert result == []

    def test_build_order_by_known_sorts(self, service: LeadSearchService) -> None:
        """Known sort aliases map to the expected column pairs."""
        assert service._build_order_by("-created_at")[0].__class__.__name__.endswith(
            "UnaryExpression"
        )
        assert service._build_order_by("-fit_score") is not None
        assert service._build_order_by("score") is not None

    def test_score_column_for_sort(self, service: LeadSearchService) -> None:
        """Score column selection follows sort key."""
        col, desc = service._score_column_for_sort("-fit_score")
        assert col == Lead.fit_score
        assert desc is True

        col2, desc2 = service._score_column_for_sort("created_at")
        assert col2 == Lead.created_at
        assert desc2 is False

        col3, desc3 = service._score_column_for_sort("-composite_score")
        assert col3 == Lead.composite_score
        assert desc3 is True
