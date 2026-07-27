"""Celery-task idempotency tests for run memory extraction (Story 3.13, T3).

The service-level guards are covered in ``test_run_memory_extraction.py``. What
this module pins down is the *claim* layer, which only exists because Celery
delivery is at-least-once (D6/AC-6):

* two workers racing on the same run resolve to exactly one LLM call — for a
  facts-producing run and for a zero-fact run;
* a transient failure releases the claim so ``autoretry_for`` can re-claim;
* an exhausted retry budget writes the terminal ``failed`` marker;
* a terminal run is never re-claimed.

The concurrency tests use two *separate* sessions on the session-scoped engine
rather than the savepoint-based ``db_session`` fixture: a CAS that two coroutines
must contend on is meaningless if both run inside one transaction.
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration, pytest.mark.memory]


FACTS_JSON = (
    '[{"content": "Widget costs 19.99 USD at competitor X", '
    '"type": "semantic", "tags": ["pricing"], "confidence": 0.9}]'
)


def _llm_returning(text: str) -> AsyncMock:
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(return_value=type("R", (), {"content": text})())
    return llm


@pytest_asyncio.fixture
async def committed_run(async_engine):
    """A truly committed successful run, plus its workspace/user.

    Committed for real (not inside a savepoint) so two independent sessions can
    contend for the CAS. Everything is torn down explicitly at the end.
    """
    from app.db import Memory, Run, TokenUsage, User, Workspace
    from app.routes.workspaces_routes import create_default_roles_and_membership

    user_id = uuid.uuid4()
    run_id = uuid.uuid4()

    async with AsyncSession(bind=async_engine, expire_on_commit=False) as session:
        user = User(
            id=user_id,
            email=f"race-{user_id}@nowing.net",
            hashed_password="hashed",
            is_active=True,
            is_superuser=False,
            is_verified=True,
        )
        session.add(user)
        await session.flush()

        workspace = Workspace(name=f"Race Space {user_id}", user_id=user_id)
        session.add(workspace)
        await session.flush()
        await create_default_roles_and_membership(session, workspace.id, user_id)

        run = Run(
            id=run_id,
            workspace_id=workspace.id,
            user_id=user_id,
            thread_id=None,
            capability="amazon.scrape",
            origin="rest",
            status="success",
            input={"url": "https://example.com/widget"},
            output_text='{"title": "Widget", "price": "19.99 USD"}',
            item_count=1,
            char_count=42,
        )
        session.add(run)
        await session.commit()
        workspace_id = workspace.id

    yield run_id, workspace_id, user_id

    async with AsyncSession(bind=async_engine, expire_on_commit=False) as session:
        await session.execute(delete(Memory).where(Memory.workspace_id == workspace_id))
        await session.execute(
            delete(TokenUsage).where(TokenUsage.workspace_id == workspace_id)
        )
        await session.execute(delete(Run).where(Run.id == run_id))
        await session.commit()
        # Workspace/user rows cascade from the workspace delete.
        await session.execute(delete(Workspace).where(Workspace.id == workspace_id))
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()


async def _counts(async_engine, run_id, workspace_id) -> tuple[int, int, str | None]:
    from app.db import Memory, Run, TokenUsage

    async with AsyncSession(bind=async_engine, expire_on_commit=False) as session:
        memories = int(
            (
                await session.execute(
                    select(func.count(Memory.id)).where(Memory.source_run_id == run_id)
                )
            ).scalar_one()
        )
        usage = int(
            (
                await session.execute(
                    select(func.count(TokenUsage.id)).where(
                        TokenUsage.workspace_id == workspace_id,
                        TokenUsage.usage_type == "memory_create",
                    )
                )
            ).scalar_one()
        )
        status = (
            await session.execute(
                select(Run.memory_extraction_status).where(Run.id == run_id)
            )
        ).scalar_one()
    return memories, usage, status


@pytest.mark.asyncio
async def test_two_concurrent_workers_make_exactly_one_llm_call(
    async_engine, committed_run
):
    """AC-6: a facts-producing run racing two workers yields ONE LLM call."""
    from app.tasks.celery_tasks.run_memory_extraction_task import (
        _extract_memory_after_run,
    )

    run_id, workspace_id, _ = committed_run
    llm = _llm_returning(FACTS_JSON)

    with patch(
        "app.services.memory.run_extraction.get_agent_llm",
        AsyncMock(return_value=llm),
    ):
        await asyncio.gather(
            _extract_memory_after_run(run_id),
            _extract_memory_after_run(run_id),
        )

    assert llm.ainvoke.await_count == 1
    memories, usage, status = await _counts(async_engine, run_id, workspace_id)
    assert memories == 1
    assert usage == 1
    assert status == "completed"


@pytest.mark.asyncio
async def test_two_concurrent_workers_zero_fact_run_calls_llm_once(
    async_engine, committed_run
):
    """AC-6: the zero-fact case is terminal too — no second LLM call."""
    from app.tasks.celery_tasks.run_memory_extraction_task import (
        _extract_memory_after_run,
    )

    run_id, workspace_id, _ = committed_run
    llm = _llm_returning("[]")

    with patch(
        "app.services.memory.run_extraction.get_agent_llm",
        AsyncMock(return_value=llm),
    ):
        await asyncio.gather(
            _extract_memory_after_run(run_id),
            _extract_memory_after_run(run_id),
        )

    assert llm.ainvoke.await_count == 1
    memories, _, status = await _counts(async_engine, run_id, workspace_id)
    assert memories == 0
    assert status == "completed"


@pytest.mark.asyncio
async def test_redelivery_after_completion_makes_no_llm_call(
    async_engine, committed_run
):
    """AC-6: a terminal run is never re-claimed on redelivery."""
    from app.tasks.celery_tasks.run_memory_extraction_task import (
        _extract_memory_after_run,
    )

    run_id, workspace_id, _ = committed_run
    llm = _llm_returning(FACTS_JSON)

    with patch(
        "app.services.memory.run_extraction.get_agent_llm",
        AsyncMock(return_value=llm),
    ):
        await _extract_memory_after_run(run_id)
        first = llm.ainvoke.await_count
        await _extract_memory_after_run(run_id)

    assert first == 1
    assert llm.ainvoke.await_count == 1
    memories, usage, _ = await _counts(async_engine, run_id, workspace_id)
    assert memories == 1
    assert usage == 1


@pytest.mark.asyncio
async def test_transient_failure_releases_claim_for_retry(async_engine, committed_run):
    """A transient error must not leave the run locked out of its own retry."""
    from app.tasks.celery_tasks.run_memory_extraction_task import (
        _extract_memory_after_run,
    )

    run_id, workspace_id, _ = committed_run

    llm = AsyncMock()
    llm.ainvoke = AsyncMock(side_effect=TimeoutError("upstream slow"))

    with (
        patch(
            "app.services.memory.run_extraction.get_agent_llm",
            AsyncMock(return_value=llm),
        ),
        pytest.raises(TimeoutError),
    ):
        await _extract_memory_after_run(run_id, retries_left=True)

    _, _, status = await _counts(async_engine, run_id, workspace_id)
    assert status is None, "claim must be released so autoretry can re-claim"

    # And the retry then succeeds and lands memory.
    good = _llm_returning(FACTS_JSON)
    with patch(
        "app.services.memory.run_extraction.get_agent_llm",
        AsyncMock(return_value=good),
    ):
        await _extract_memory_after_run(run_id)

    memories, usage, status = await _counts(async_engine, run_id, workspace_id)
    assert memories == 1
    assert usage == 1
    assert status == "completed"


@pytest.mark.asyncio
async def test_exhausted_retry_budget_marks_failed(async_engine, committed_run):
    """With no retries left, the transient failure becomes terminal ``failed``."""
    from app.tasks.celery_tasks.run_memory_extraction_task import (
        _extract_memory_after_run,
    )

    run_id, workspace_id, _ = committed_run

    llm = AsyncMock()
    llm.ainvoke = AsyncMock(side_effect=TimeoutError("upstream slow"))

    with (
        patch(
            "app.services.memory.run_extraction.get_agent_llm",
            AsyncMock(return_value=llm),
        ),
        pytest.raises(TimeoutError),
    ):
        await _extract_memory_after_run(run_id, retries_left=False)

    memories, usage, status = await _counts(async_engine, run_id, workspace_id)
    assert status == "failed"
    assert memories == 0
    assert usage == 0


@pytest.mark.asyncio
async def test_task_is_registered_with_celery():
    """T3: the task module must actually be included in the Celery app."""
    from app.celery_app import celery_app

    assert "extract_memory_after_run" in celery_app.tasks
