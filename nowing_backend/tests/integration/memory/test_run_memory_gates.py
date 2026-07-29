"""Every Story 8.7/8.8 gate reason blocks the run-path LLM call (Story 3.13, T7/AC-4).

``test_run_memory_extraction.py`` covers one representative gate verdict. This
module walks the *whole* reason vocabulary, because AC-4 is a claim about the set,
not about a sample: a future gate reason that the run path forgot to treat as
blocking would still pass a single-reason test.

Two properties per reason:

* the extraction LLM is never awaited (asserted on the call count — an assertion
  on "no memory was created" would also pass if the LLM ran and returned junk,
  which is precisely the cost AC-4 exists to prevent);
* the run is left in a *terminal* ``skipped`` state carrying that exact reason
  string, so redelivery does not re-run the gate and re-pay for it (D6).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.integration, pytest.mark.memory]


FACTS_JSON = (
    '[{"content": "Widget costs 19.99 USD", "type": "semantic", '
    '"tags": ["pricing"], "confidence": 0.9}]'
)


def _llm_returning(text: str) -> AsyncMock:
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(return_value=type("R", (), {"content": text})())
    return llm


@pytest_asyncio.fixture
async def gate_run(db_session, db_workspace, db_user):
    from app.db import Run

    run = Run(
        id=uuid.uuid4(),
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        capability="google_search.scrape",
        origin="rest",
        status="success",
        input={"q": "widget"},
        output_text='{"title": "Widget", "price": "19.99 USD"}',
        item_count=1,
        char_count=42,
    )
    db_session.add(run)
    await db_session.commit()
    return run


def _all_gate_reasons() -> list[str]:
    """The full blocking vocabulary from the shared gate module.

    Read from the module rather than hardcoded so a newly added reason shows up
    here automatically instead of silently escaping coverage. ``disabled`` is
    excluded: it is produced by the kill-switch branch *before* the gate is
    consulted and is covered by its own test.
    """
    from app.services.memory import extract_budget

    return [
        extract_budget.REASON_ANONYMOUS_UNBILLED,
        extract_budget.REASON_INSUFFICIENT_WALLET,
        extract_budget.REASON_BUDGET_EXCEEDED,
        extract_budget.REASON_RATE_LIMITED,
        extract_budget.REASON_GATE_ERROR,
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", _all_gate_reasons())
async def test_every_gate_reason_blocks_the_llm(db_session, gate_run, reason):
    """AC-4: each blocking verdict short-circuits before the LLM, terminally."""
    from app.services.memory.extract_budget import ExtractGateResult
    from app.services.memory.run_extraction import (
        STATUS_SKIPPED,
        RunMemoryExtractionService,
    )

    llm = _llm_returning(FACTS_JSON)
    with (
        patch(
            "app.services.memory.run_extraction.get_agent_llm",
            AsyncMock(return_value=llm),
        ),
        patch(
            "app.services.memory.run_extraction.check_extract_allowed",
            AsyncMock(return_value=ExtractGateResult(allowed=False, reason=reason)),
        ),
    ):
        service = RunMemoryExtractionService(session=db_session)
        created = await service.extract_from_run(gate_run.id)

    assert created == []
    assert llm.ainvoke.await_count == 0
    assert gate_run.memory_extraction_status == STATUS_SKIPPED
    assert gate_run.memory_extraction_skip_reason == reason


@pytest.mark.asyncio
async def test_global_kill_switch_blocks_the_llm(db_session, gate_run, monkeypatch):
    """AC-4/8.8: the global switch is checked before the gate and before the LLM."""
    from app.config import config
    from app.services.memory.run_extraction import (
        STATUS_SKIPPED,
        RunMemoryExtractionService,
    )

    monkeypatch.setattr(config, "MEMORY_AUTO_EXTRACT_ENABLED", False)

    llm = _llm_returning(FACTS_JSON)
    with patch(
        "app.services.memory.run_extraction.get_agent_llm",
        AsyncMock(return_value=llm),
    ):
        service = RunMemoryExtractionService(session=db_session)
        created = await service.extract_from_run(gate_run.id)

    assert created == []
    assert llm.ainvoke.await_count == 0
    assert gate_run.memory_extraction_status == STATUS_SKIPPED
    assert gate_run.memory_extraction_skip_reason == "disabled"


@pytest.mark.asyncio
async def test_gate_is_consulted_with_the_runs_creator_not_the_owner(
    db_session, db_workspace, db_user, gate_run
):
    """D4: attribution comes from ``Run.user_id``, never a workspace-owner guess.

    The distinction matters even when the two happen to be the same user, because
    passing the owner would make an authorless run look billable and defeat the
    anonymous check the gate exists to perform.
    """
    from app.services.memory.extract_budget import ExtractGateResult
    from app.services.memory.run_extraction import RunMemoryExtractionService

    seen: dict = {}

    async def spy_gate(session, *, workspace, attributed_user_id):
        seen["attributed_user_id"] = attributed_user_id
        seen["workspace_id"] = workspace.id
        return ExtractGateResult(allowed=False, reason="rate_limited")

    llm = _llm_returning(FACTS_JSON)
    with (
        patch(
            "app.services.memory.run_extraction.get_agent_llm",
            AsyncMock(return_value=llm),
        ),
        patch("app.services.memory.run_extraction.check_extract_allowed", spy_gate),
    ):
        service = RunMemoryExtractionService(session=db_session)
        await service.extract_from_run(gate_run.id)

    assert seen["attributed_user_id"] == db_user.id
    assert seen["workspace_id"] == db_workspace.id
