"""Unit tests for Unified Usage & Service Ledger Service (Story 21.7 / AC-6).

Validates aggregation of both TokenUsage (LLM) and BillingEvent (Business Events),
categorization into 5 service buckets, and unified transaction history.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest

from app.db import (
    User,
)
from app.schemas.usage import (
    ServiceCategory,
)
from app.services.usage_service import (
    UsageService,
    map_event_to_service_category,
)

pytestmark = pytest.mark.unit


def test_map_event_to_service_category() -> None:
    """Classifies various LLM usage types and BillingEvent types into 5 standard service buckets."""
    # AI Generation
    assert map_event_to_service_category("chat", None) == ServiceCategory.AI_GENERATION
    assert (
        map_event_to_service_category("indexing", None) == ServiceCategory.AI_GENERATION
    )
    assert (
        map_event_to_service_category("deep_research", None)
        == ServiceCategory.AI_GENERATION
    )

    # Web Search
    assert (
        map_event_to_service_category("web_crawl", None) == ServiceCategory.WEB_SEARCH
    )
    assert (
        map_event_to_service_category("exa_search", None) == ServiceCategory.WEB_SEARCH
    )
    assert (
        map_event_to_service_category("serp_query", None) == ServiceCategory.WEB_SEARCH
    )

    # Social Media
    assert (
        map_event_to_service_category("social_post_scrape", None)
        == ServiceCategory.SOCIAL_MEDIA
    )
    assert (
        map_event_to_service_category("xactions_ingest", None)
        == ServiceCategory.SOCIAL_MEDIA
    )
    assert (
        map_event_to_service_category(None, "signal_scan")
        == ServiceCategory.SOCIAL_MEDIA
    )

    # Phone Waterfall
    assert (
        map_event_to_service_category("phone_waterfall", None)
        == ServiceCategory.PHONE_WATERFALL
    )
    assert (
        map_event_to_service_category(None, "contact_enrichment")
        == ServiceCategory.PHONE_WATERFALL
    )

    # Outcome Meetings
    assert (
        map_event_to_service_category(None, "outcome_meeting_booked")
        == ServiceCategory.OUTCOME_MEETINGS
    )


class _FakeResult:
    def __init__(
        self,
        rows: list[Any] | None = None,
        mappings_data: list[dict[str, Any]] | None = None,
        scalar_val: Any = None,
    ) -> None:
        self._rows = rows or []
        self._mappings = mappings_data or []
        self._scalar = scalar_val

    def all(self) -> list[Any]:
        return self._rows

    def scalars(self) -> Any:
        class _ScalarMapper:
            def __init__(self, data: list[Any]) -> None:
                self._data = data

            def all(self) -> list[Any]:
                return self._data

            def first(self) -> Any:
                return self._data[0] if self._data else None

        return _ScalarMapper(self._rows)

    def mappings(self) -> Any:
        class _Mapper:
            def __init__(self, data: list[dict[str, Any]]) -> None:
                self._data = data

            def all(self) -> list[dict[str, Any]]:
                return self._data

        return _Mapper(self._mappings)

    def scalar_one(self) -> Any:
        return self._scalar


class _FakeSession:
    def __init__(
        self,
        token_rows: list[Any] | None = None,
        billing_rows: list[Any] | None = None,
    ) -> None:
        self.token_rows = token_rows or []
        self.billing_rows = billing_rows or []
        self._exec_count = 0

    async def execute(self, _stmt: Any, _params: Any = None) -> _FakeResult:
        if self._exec_count == 0:
            self._exec_count += 1
            return _FakeResult(rows=self.token_rows)
        return _FakeResult(rows=self.billing_rows)


class _Row:
    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.mark.asyncio
async def test_get_service_breakdown_aggregation() -> None:
    """Calculates cost and token aggregates grouped by 5 service categories."""
    user = User()
    user.id = uuid4()
    user.credit_micros_balance = 5_000_000

    token_rows = [
        _Row(usage_type="chat", total_tokens=120_000, cost_micros=0, event_count=45),
        _Row(
            usage_type="web_crawl",
            total_tokens=5_000,
            cost_micros=50_000,
            event_count=10,
        ),
    ]

    billing_rows = [
        _Row(event_type="signal_scan", cost_micros=200_000, event_count=25),
        _Row(event_type="contact_enrichment", cost_micros=600_000, event_count=10),
        _Row(event_type="outcome_meeting_booked", cost_micros=2_000_000, event_count=1),
    ]

    session = _FakeSession(token_rows=token_rows, billing_rows=billing_rows)
    service = UsageService(session, user)

    start_date = datetime.now(UTC) - timedelta(days=30)
    end_date = datetime.now(UTC)

    breakdown = await service.get_service_breakdown(
        workspace_id=1,
        start_date=start_date,
        end_date=end_date,
    )

    assert len(breakdown) == 5
    ai_gen = next(b for b in breakdown if b.category == ServiceCategory.AI_GENERATION)
    assert ai_gen.cost_micros == 0  # $0 chat turns
    assert ai_gen.total_tokens == 120_000

    meetings = next(
        b for b in breakdown if b.category == ServiceCategory.OUTCOME_MEETINGS
    )
    assert meetings.cost_micros == 2_000_000
    assert meetings.event_count == 1


@pytest.mark.asyncio
async def test_get_per_turn_usage_groups_by_turn() -> None:
    """Groups TokenUsage rows by message/thread/id and computes token categories."""
    user = User()
    user.id = uuid4()
    user.credit_micros_balance = 0

    now = datetime.now(UTC)
    token_rows = [
        _Row(
            id=1,
            message_id=100,
            thread_id=None,
            workspace_id=1,
            usage_type="chat",
            resolved_mode="balanced",
            model_breakdown=None,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_micros=1_000_000,
            created_at=now,
        ),
        _Row(
            id=2,
            message_id=None,
            thread_id=10,
            workspace_id=1,
            usage_type="memory_create",
            resolved_mode=None,
            model_breakdown=None,
            prompt_tokens=200,
            completion_tokens=100,
            total_tokens=300,
            cost_micros=500_000,
            created_at=now - timedelta(minutes=1),
        ),
        _Row(
            id=3,
            message_id=None,
            thread_id=None,
            workspace_id=1,
            usage_type="memory_embedding",
            resolved_mode=None,
            model_breakdown=None,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=75,
            cost_micros=0,
            created_at=now - timedelta(minutes=2),
        ),
    ]

    session = _FakeSession(token_rows=token_rows, billing_rows=[])
    service = UsageService(session, user)

    result = await service.get_per_turn_usage(
        workspace_id=1, start_date=now - timedelta(days=1), end_date=now
    )

    assert result.workspace_id == 1
    assert len(result.items) == 3

    chat = next(i for i in result.items if i.turn_key == "100")
    assert chat.turn_type == "message"
    assert chat.capability == "chat"
    assert chat.resolved_model == "balanced"
    assert chat.llm_tokens == 150
    assert chat.embedding_tokens == 0
    assert chat.cost_micros == 1_000_000

    memory = next(i for i in result.items if i.turn_key == "10")
    assert memory.turn_type == "thread"
    assert memory.capability == "memory_create"
    assert memory.llm_tokens == 300
    assert memory.cost_micros == 500_000

    embedding = next(i for i in result.items if i.turn_key == "3")
    assert embedding.turn_type == "event"
    assert embedding.capability == "memory_embedding"
    assert embedding.embedding_tokens == 75
    assert embedding.llm_tokens == 0
