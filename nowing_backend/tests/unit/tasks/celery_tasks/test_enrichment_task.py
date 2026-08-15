"""Unit tests for the enrichment celery task (Story 21.3, Task 10)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.unit


class _FakeAsyncContextManager:
    def __init__(self, session: AsyncMock) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncMock:
        return self._session

    async def __aexit__(self, *_args) -> None:
        pass


class _FakeSessionMaker:
    def __init__(self, session: AsyncMock) -> None:
        self._session = session

    def __call__(self) -> _FakeAsyncContextManager:
        return _FakeAsyncContextManager(self._session)


def test_enrich_lead_task_runs_waterfall(monkeypatch) -> None:
    """The task loads a session and runs the provider waterfall."""
    from app.tasks.celery_tasks.enrichment_tasks import enrich_lead_task

    session = AsyncMock()
    monkeypatch.setattr(
        "app.tasks.celery_tasks.get_celery_session_maker",
        lambda: _FakeSessionMaker(session),
    )

    service = AsyncMock()
    service._run_waterfall = AsyncMock()
    monkeypatch.setattr(
        "app.tasks.celery_tasks.enrichment_tasks.EnrichmentService",
        lambda: service,
    )

    enrich_lead_task("req-123", 1, None)

    service._run_waterfall.assert_awaited_once_with(session, "req-123")


def test_enrich_lead_task_no_autoretry() -> None:
    """The task must not auto-retry (re-running duplicates contacts/billing)."""
    from app.tasks.celery_tasks.enrichment_tasks import enrich_lead_task

    task = enrich_lead_task._get_current_object()
    retry_options = {
        key
        for key in task.__dict__
        if "retry" in key or "autoretry" in key or key == "max_retries"
    }
    assert retry_options == set()
    assert task.name == "enrich_lead_task"


def test_enrich_lead_task_marks_request_failed_on_error(monkeypatch) -> None:
    """An unhandled waterfall error marks the request failed."""
    from app.tasks.celery_tasks.enrichment_tasks import enrich_lead_task

    session = AsyncMock()
    monkeypatch.setattr(
        "app.tasks.celery_tasks.get_celery_session_maker",
        lambda: _FakeSessionMaker(session),
    )

    service = AsyncMock()
    service._run_waterfall = AsyncMock(side_effect=RuntimeError("boom"))
    service._mark_failed = AsyncMock()
    monkeypatch.setattr(
        "app.tasks.celery_tasks.enrichment_tasks.EnrichmentService",
        lambda: service,
    )

    enrich_lead_task("req-123", 1, None)

    service._run_waterfall.assert_awaited_once_with(session, "req-123")
    service._mark_failed.assert_awaited_once_with(session, "req-123", 1, None)