"""Retry taxonomy for the run extraction task (Story 3.13, T7 / AC-5).

AC-5 splits extraction failures in two, and the split has a cost consequence, so
it is asserted on behaviour rather than on a type list:

* **transient** (timeout, connection, rate-limit, 5xx) — re-raised so Celery's
  ``autoretry_for`` re-runs the task, and the durable claim is *released* so the
  retry is not locked out by the ``pending`` marker its own earlier attempt wrote;
* **terminal** (auth, config, validation) — re-raised too, but the run is marked
  ``failed`` rather than released, because a retry would fail identically and
  re-pay for the same call.

The last test is the one that matters for money: a transient error must never
leave ``memory_create`` usage behind, because ``autoretry_for`` would then charge
again on the next attempt.
"""

from __future__ import annotations

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


@pytest_asyncio.fixture
async def committed_run(async_engine):
    """A committed successful run on its own connection (see the task tests)."""
    from app.db import Memory, Run, TokenUsage, User, Workspace
    from app.routes.workspaces_routes import create_default_roles_and_membership

    user_id = uuid.uuid4()
    run_id = uuid.uuid4()

    async with AsyncSession(bind=async_engine, expire_on_commit=False) as session:
        session.add(
            User(
                id=user_id,
                email=f"taxonomy-{user_id}@nowing.net",
                hashed_password="hashed",
                is_active=True,
                is_superuser=False,
                is_verified=True,
            )
        )
        await session.flush()
        workspace = Workspace(name=f"Taxonomy {user_id}", user_id=user_id)
        session.add(workspace)
        await session.flush()
        await create_default_roles_and_membership(session, workspace.id, user_id)
        session.add(
            Run(
                id=run_id,
                workspace_id=workspace.id,
                user_id=user_id,
                capability="web.crawl",
                origin="rest",
                status="success",
                input={"url": "https://example.com/widget"},
                output_text='{"price": "19.99 USD"}',
                item_count=1,
                char_count=24,
            )
        )
        await session.commit()
        workspace_id = workspace.id

    yield run_id, workspace_id

    async with AsyncSession(bind=async_engine, expire_on_commit=False) as session:
        await session.execute(delete(Memory).where(Memory.workspace_id == workspace_id))
        await session.execute(
            delete(TokenUsage).where(TokenUsage.workspace_id == workspace_id)
        )
        await session.execute(delete(Run).where(Run.id == run_id))
        await session.commit()
        await session.execute(delete(Workspace).where(Workspace.id == workspace_id))
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()


async def _state(async_engine, run_id, workspace_id):
    from app.db import Memory, Run, TokenUsage

    async with AsyncSession(bind=async_engine, expire_on_commit=False) as session:
        row = (
            await session.execute(
                select(
                    Run.memory_extraction_status, Run.memory_extraction_skip_reason
                ).where(Run.id == run_id)
            )
        ).one()
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
    return row[0], row[1], memories, usage


def _llm_raising(exc: BaseException) -> AsyncMock:
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(side_effect=exc)
    return llm


def _transient_error() -> BaseException:
    """A member of the shared transient tuple, built without guessing a ctor.

    ``litellm``'s exception constructors have required keyword arguments that
    differ between versions (and the test suite substitutes fakes for some), so
    the first tuple member that can be instantiated bare is used. ``TimeoutError``
    is in the tuple and always constructible, so this cannot fail to find one.
    """
    from app.services.memory.pipeline import TRANSIENT_LLM_ERRORS

    for exc_type in TRANSIENT_LLM_ERRORS:
        try:
            return exc_type("transient boom")
        except Exception:
            continue
    raise AssertionError("no constructible transient error in the shared tuple")


@pytest.mark.asyncio
async def test_transient_error_releases_claim_and_charges_nothing(
    async_engine, committed_run
):
    """AC-5: a transient failure is retryable AND leaves no usage row behind."""
    from app.tasks.celery_tasks.run_memory_extraction_task import (
        _extract_memory_after_run,
    )

    run_id, workspace_id = committed_run
    transient_exc = _transient_error()
    llm = _llm_raising(transient_exc)

    with patch(
        "app.services.memory.run_extraction.get_agent_llm",
        AsyncMock(return_value=llm),
    ), pytest.raises(type(transient_exc)):
        await _extract_memory_after_run(run_id, retries_left=True)

    status, _, memories, usage = await _state(async_engine, run_id, workspace_id)
    # Released, not terminal: `autoretry_for` must be able to re-claim.
    assert status is None
    assert memories == 0
    # The charge guard: a committed usage row here would be re-paid on retry.
    assert usage == 0


@pytest.mark.asyncio
async def test_transient_error_with_budget_exhausted_marks_failed(
    async_engine, committed_run
):
    """AC-5: once the retry budget is gone the run is terminal, not stuck pending."""
    from app.tasks.celery_tasks.run_memory_extraction_task import (
        _extract_memory_after_run,
    )

    run_id, workspace_id = committed_run
    transient_exc = _transient_error()
    llm = _llm_raising(transient_exc)

    with patch(
        "app.services.memory.run_extraction.get_agent_llm",
        AsyncMock(return_value=llm),
    ), pytest.raises(type(transient_exc)):
        await _extract_memory_after_run(run_id, retries_left=False)

    status, _, memories, usage = await _state(async_engine, run_id, workspace_id)
    assert status == "failed"
    assert memories == 0
    assert usage == 0


@pytest.mark.asyncio
async def test_terminal_error_marks_failed_without_release(
    async_engine, committed_run
):
    """AC-5: an auth/config error is terminal on the first attempt.

    Releasing the claim here would invite a retry that re-pays for a call which
    cannot succeed, so ``failed`` is written even with retries remaining.
    """
    from app.tasks.celery_tasks.run_memory_extraction_task import (
        _extract_memory_after_run,
    )

    run_id, workspace_id = committed_run

    class _AuthBoomError(Exception):
        """Stands in for an auth/config failure: outside the transient tuple."""

    llm = _llm_raising(_AuthBoomError("bad api key"))

    with patch(
        "app.services.memory.run_extraction.get_agent_llm",
        AsyncMock(return_value=llm),
    ), pytest.raises(_AuthBoomError):
        await _extract_memory_after_run(run_id, retries_left=True)

    status, _, memories, usage = await _state(async_engine, run_id, workspace_id)
    assert status == "failed"
    assert memories == 0
    assert usage == 0


@pytest.mark.asyncio
async def test_persistence_failure_leaves_no_partial_batch(
    async_engine, committed_run
):
    """AC-5: an embedding/persistence error commits nothing at all.

    The task-level counterpart of the service test: here the rollback happens
    inside the Celery entry point, which also writes the ``failed`` marker, so
    this pins down that the marker's own commit cannot smuggle a staged fact
    through.
    """
    from app.services.memory.repository import MemoryRepository
    from app.tasks.celery_tasks.run_memory_extraction_task import (
        _extract_memory_after_run,
    )

    run_id, workspace_id = committed_run

    async def exploding_create(self, **kwargs):
        raise RuntimeError("embedding backend exploded")

    llm = AsyncMock()
    llm.ainvoke = AsyncMock(return_value=type("R", (), {"content": FACTS_JSON})())

    with (
        patch(
            "app.services.memory.run_extraction.get_agent_llm",
            AsyncMock(return_value=llm),
        ),
        patch.object(MemoryRepository, "create_memory", exploding_create),
        pytest.raises(RuntimeError),
    ):
        await _extract_memory_after_run(run_id, retries_left=True)

    status, _, memories, usage = await _state(async_engine, run_id, workspace_id)
    assert status == "failed"
    assert memories == 0
    assert usage == 0
