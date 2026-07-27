"""Run-path memory extraction service tests (Story 3.13, T2 / AC-1, AC-4, AC-5).

Red-phase for ``RunMemoryExtractionService``. These cover what genuinely differs
from the chat path:

* the LLM must not be called at all when the source is empty or a Story 8.7/8.8
  gate blocks (AC-4) — asserted on the call count, not just on the outcome;
* a run batch is all-or-nothing: a failure on the *second* fact must leave zero
  memories, zero ``memory_create`` usage, no terminal ``completed`` marker and no
  ``memory.changed`` event (AC-5);
* provenance is ``source_type=SCRAPER_RUN`` / ``source_id=NULL`` /
  ``source_run_id=Run.id`` (AC-1, D4);
* the free-form ``Run.thread_id`` is never copied into ``research_thread_id``.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import func, select

pytestmark = [pytest.mark.integration, pytest.mark.memory]


FACTS_JSON = (
    '[{"content": "Competitor X sells the widget at 19.99 USD", '
    '"type": "semantic", "tags": ["pricing"], "confidence": 0.9},'
    '{"content": "Competitor X ships from Berlin", '
    '"type": "semantic", "tags": ["logistics"], "confidence": 0.9}]'
)


def _llm_returning(text: str) -> AsyncMock:
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(return_value=type("R", (), {"content": text})())
    return llm


@pytest_asyncio.fixture
async def scraper_run(db_session, db_workspace, db_user):
    """A committed successful run with a durable-fact-bearing output."""
    from app.db import Run

    run = Run(
        id=uuid.uuid4(),
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        # Deliberately subagent-shaped: must never be copied into
        # research_thread_id (D4).
        thread_id="2099::task:call_x",
        capability="amazon.scrape",
        origin="rest",
        status="success",
        input={"url": "https://example.com/widget"},
        output_text='{"title": "Widget", "price": "19.99 USD", "ships_from": "Berlin"}',
        item_count=1,
        char_count=64,
    )
    db_session.add(run)
    # Committed (a SAVEPOINT release under the integration session fixture), so
    # the row survives the service's own rollback in the all-or-nothing test —
    # otherwise "the run vanished" would be indistinguishable from "the marker
    # was not written", and the AC-5 assertion would prove nothing.
    await db_session.commit()
    return run


async def _usage_count(db_session, workspace_id: int) -> int:
    from app.db import TokenUsage

    result = await db_session.execute(
        select(func.count(TokenUsage.id)).where(
            TokenUsage.workspace_id == workspace_id,
            TokenUsage.usage_type == "memory_create",
        )
    )
    return int(result.scalar_one())


async def _memory_count(db_session, run_id) -> int:
    from app.db import Memory

    result = await db_session.execute(
        select(func.count(Memory.id)).where(Memory.source_run_id == run_id)
    )
    return int(result.scalar_one())


@pytest.mark.asyncio
async def test_run_extraction_creates_memory_with_run_provenance(
    db_session, db_workspace, db_user, scraper_run
):
    """AC-1: facts land with SCRAPER_RUN provenance and the run's creator."""
    from app.db import Memory, MemorySourceType
    from app.services.memory.run_extraction import RunMemoryExtractionService

    llm = _llm_returning(FACTS_JSON)
    with patch(
        "app.services.memory.run_extraction.get_agent_llm",
        AsyncMock(return_value=llm),
    ):
        service = RunMemoryExtractionService(session=db_session)
        created = await service.extract_from_run(scraper_run.id)

    assert len(created) == 2
    result = await db_session.execute(
        select(Memory).where(Memory.source_run_id == scraper_run.id)
    )
    memories = result.scalars().all()
    assert len(memories) == 2
    for memory in memories:
        assert memory.source_type == MemorySourceType.SCRAPER_RUN
        assert memory.source_id is None
        assert memory.source_run_id == scraper_run.id
        assert memory.workspace_id == db_workspace.id
        assert memory.created_by_id == db_user.id
        # D4: the free-form subagent thread_id must not leak in.
        assert memory.research_thread_id is None


@pytest.mark.asyncio
async def test_run_extraction_records_memory_create_usage(
    db_session, db_workspace, scraper_run
):
    """AC-4/D3: run path keeps the ``memory_create`` accounting row."""
    from app.services.memory.run_extraction import RunMemoryExtractionService

    llm = _llm_returning(FACTS_JSON)
    with patch(
        "app.services.memory.run_extraction.get_agent_llm",
        AsyncMock(return_value=llm),
    ):
        service = RunMemoryExtractionService(session=db_session)
        await service.extract_from_run(scraper_run.id)

    assert await _usage_count(db_session, db_workspace.id) == 1


@pytest.mark.asyncio
async def test_run_extraction_skips_llm_for_empty_output(db_session, scraper_run):
    """AC-4/D5: whitespace-only output must not reach the LLM at all."""
    from app.services.memory.run_extraction import RunMemoryExtractionService

    scraper_run.output_text = "   \n  "
    await db_session.flush()

    llm = _llm_returning(FACTS_JSON)
    with patch(
        "app.services.memory.run_extraction.get_agent_llm",
        AsyncMock(return_value=llm),
    ):
        service = RunMemoryExtractionService(session=db_session)
        created = await service.extract_from_run(scraper_run.id)

    assert created == []
    assert llm.ainvoke.await_count == 0


@pytest.mark.asyncio
async def test_run_extraction_skips_llm_when_creator_missing(db_session, scraper_run):
    """AC-4/D4: no trustworthy creator -> terminal skip BEFORE the LLM."""
    from app.services.memory.run_extraction import RunMemoryExtractionService

    scraper_run.user_id = None
    await db_session.flush()

    llm = _llm_returning(FACTS_JSON)
    with patch(
        "app.services.memory.run_extraction.get_agent_llm",
        AsyncMock(return_value=llm),
    ):
        service = RunMemoryExtractionService(session=db_session)
        created = await service.extract_from_run(scraper_run.id)

    assert created == []
    assert llm.ainvoke.await_count == 0
    assert scraper_run.memory_extraction_skip_reason == "missing_creator"


@pytest.mark.asyncio
async def test_run_extraction_skips_llm_when_gate_blocks(db_session, scraper_run):
    """AC-4: a blocking gate verdict prevents the LLM call."""
    from app.services.memory.extract_budget import ExtractGateResult
    from app.services.memory.run_extraction import RunMemoryExtractionService

    llm = _llm_returning(FACTS_JSON)
    with (
        patch(
            "app.services.memory.run_extraction.get_agent_llm",
            AsyncMock(return_value=llm),
        ),
        patch(
            "app.services.memory.run_extraction.check_extract_allowed",
            AsyncMock(
                return_value=ExtractGateResult(allowed=False, reason="rate_limited")
            ),
        ),
    ):
        service = RunMemoryExtractionService(session=db_session)
        created = await service.extract_from_run(scraper_run.id)

    assert created == []
    assert llm.ainvoke.await_count == 0
    assert scraper_run.memory_extraction_skip_reason == "rate_limited"


@pytest.mark.asyncio
async def test_run_extraction_skips_llm_when_workspace_opted_out(
    db_session, db_workspace, scraper_run
):
    """AC-4/8.8: per-workspace opt-out short-circuits before the LLM."""
    from app.services.memory.run_extraction import RunMemoryExtractionService

    db_workspace.memory_auto_extract_enabled = False
    await db_session.flush()

    llm = _llm_returning(FACTS_JSON)
    with patch(
        "app.services.memory.run_extraction.get_agent_llm",
        AsyncMock(return_value=llm),
    ):
        service = RunMemoryExtractionService(session=db_session)
        created = await service.extract_from_run(scraper_run.id)

    assert created == []
    assert llm.ainvoke.await_count == 0
    assert scraper_run.memory_extraction_skip_reason == "disabled"


@pytest.mark.asyncio
async def test_run_extraction_invalid_json_creates_no_memory(
    db_session, db_workspace, scraper_run
):
    """A malformed LLM response is not a system failure: zero memory, no raise."""
    from app.services.memory.run_extraction import RunMemoryExtractionService

    llm = _llm_returning("this is not json at all")
    with patch(
        "app.services.memory.run_extraction.get_agent_llm",
        AsyncMock(return_value=llm),
    ):
        service = RunMemoryExtractionService(session=db_session)
        created = await service.extract_from_run(scraper_run.id)

    assert created == []
    assert await _memory_count(db_session, scraper_run.id) == 0


@pytest.mark.asyncio
async def test_run_extraction_respects_max_items(
    db_session, db_workspace, scraper_run, monkeypatch
):
    """The shared max-items cap applies to the run path too (D3)."""
    from app.config import config
    from app.services.memory.run_extraction import RunMemoryExtractionService

    monkeypatch.setattr(config, "MEMORY_AUTO_EXTRACT_MAX_ITEMS", 1)

    llm = _llm_returning(FACTS_JSON)
    with patch(
        "app.services.memory.run_extraction.get_agent_llm",
        AsyncMock(return_value=llm),
    ):
        service = RunMemoryExtractionService(session=db_session)
        created = await service.extract_from_run(scraper_run.id)

    assert len(created) == 1


@pytest.mark.asyncio
async def test_run_extraction_is_all_or_nothing_on_second_fact_failure(
    db_session, db_workspace, scraper_run
):
    """AC-5: a failure on fact #2 rolls the whole batch back.

    Unlike the chat path (which tolerates a per-fact failure and commits the
    rest), a run batch must leave nothing behind: no memory rows, no
    ``memory_create`` usage row, no terminal ``completed`` marker, no event.
    """
    from app.services.memory.repository import MemoryRepository
    from app.services.memory.run_extraction import RunMemoryExtractionService

    run_id = scraper_run.id
    workspace_id = db_workspace.id

    real_create = MemoryRepository.create_memory
    calls = {"n": 0}

    async def flaky_create(self, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("embedding backend exploded")
        return await real_create(self, **kwargs)

    published: list = []

    async def capture_publish(self, workspace_id, payload):
        published.append(payload)

    llm = _llm_returning(FACTS_JSON)
    with (
        patch(
            "app.services.memory.run_extraction.get_agent_llm",
            AsyncMock(return_value=llm),
        ),
        patch.object(MemoryRepository, "create_memory", flaky_create),
        patch.object(MemoryRepository, "_publish_memory_changed", capture_publish),
    ):
        service = RunMemoryExtractionService(session=db_session)
        with pytest.raises(RuntimeError):
            await service.extract_from_run(run_id)

    await db_session.rollback()

    assert await _memory_count(db_session, run_id) == 0
    assert await _usage_count(db_session, workspace_id) == 0
    assert published == []

    # The terminal marker must not have survived either: the fixture committed
    # the run, so the row is still here and its extraction state is directly
    # observable. A `completed` marker without the memories it accounts for is
    # exactly the partial state AC-5 forbids.
    from app.db import Run

    run = await db_session.get(Run, run_id)
    assert run is not None
    assert run.memory_extraction_status != "completed"
    assert run.memory_extraction_completed_at is None


@pytest.mark.asyncio
async def test_run_extraction_zero_facts_still_marks_completed(db_session, scraper_run):
    """AC-6/D6: a successful zero-fact extraction is terminal, not retryable."""
    from app.services.memory.run_extraction import RunMemoryExtractionService

    llm = _llm_returning("[]")
    with patch(
        "app.services.memory.run_extraction.get_agent_llm",
        AsyncMock(return_value=llm),
    ):
        service = RunMemoryExtractionService(session=db_session)
        created = await service.extract_from_run(scraper_run.id)

    assert created == []
    assert scraper_run.memory_extraction_status == "completed"
    assert scraper_run.memory_extraction_completed_at is not None


@pytest.mark.asyncio
async def test_run_extraction_skips_when_already_extracted(db_session, scraper_run):
    """AC-6: an existing memory for this run short-circuits before the LLM."""
    from app.services.memory.run_extraction import RunMemoryExtractionService

    llm = _llm_returning(FACTS_JSON)
    with patch(
        "app.services.memory.run_extraction.get_agent_llm",
        AsyncMock(return_value=llm),
    ):
        service = RunMemoryExtractionService(session=db_session)
        await service.extract_from_run(scraper_run.id)
        first_calls = llm.ainvoke.await_count
        created_again = await service.extract_from_run(scraper_run.id)

    assert first_calls == 1
    assert created_again == []
    assert llm.ainvoke.await_count == 1
    assert await _memory_count(db_session, scraper_run.id) == 2


@pytest.mark.asyncio
async def test_run_extraction_skips_non_success_run(db_session, scraper_run):
    """D1: a failed run never produces memory."""
    from app.services.memory.run_extraction import RunMemoryExtractionService

    scraper_run.status = "error"
    await db_session.flush()

    llm = _llm_returning(FACTS_JSON)
    with patch(
        "app.services.memory.run_extraction.get_agent_llm",
        AsyncMock(return_value=llm),
    ):
        service = RunMemoryExtractionService(session=db_session)
        created = await service.extract_from_run(scraper_run.id)

    assert created == []
    assert llm.ainvoke.await_count == 0
