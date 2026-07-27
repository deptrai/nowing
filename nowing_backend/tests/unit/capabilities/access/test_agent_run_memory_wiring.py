"""Agent-door wiring for run memory extraction (Story 3.13, T4 / AC-1, AC-5).

Two things the agent door owes this story, neither of which existed at baseline:

* it must pass the active chat principal into ``record_run(user_id=...)``, because
  an authorless run can only ever be skipped as ``missing_creator`` (D4);
* it must call the completion seam after — and only after — a *successful* record,
  and a failure inside the seam must not change what the tool returns (AC-5).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel, Field

from app.capabilities.core.types import BillingUnit, Capability

pytestmark = pytest.mark.asyncio


class _EchoInput(BaseModel):
    text: str = Field(description="The text to echo back.")


class _EchoOutput(BaseModel):
    echoed: str

    @property
    def billable_units(self) -> int:
        return 1


def _capability(*, name: str = "amazon.scrape") -> Capability:
    async def _executor(payload: _EchoInput) -> _EchoOutput:
        return _EchoOutput(echoed=payload.text)

    return Capability(
        name=name,
        description=f"{name} does a thing.",
        input_schema=_EchoInput,
        output_schema=_EchoOutput,
        executor=_executor,
        billing_unit=BillingUnit.WEB_CRAWL,
    )


class _FakeSessionCtx:
    async def __aenter__(self):
        return SimpleNamespace()

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def door(monkeypatch):
    """Agent door with billing, session and recorder stubbed out."""
    from app.capabilities.core.access import agent as mod

    monkeypatch.setattr(mod, "async_session_maker", lambda: _FakeSessionCtx())
    monkeypatch.setattr(mod, "charge_capability", AsyncMock(return_value=42))
    monkeypatch.setattr(mod, "gate_capability", AsyncMock())

    recorded: list[dict] = []
    enqueued: list[str | None] = []

    async def fake_record_run(session, **kwargs):
        recorded.append(kwargs)
        return "11111111-1111-1111-1111-111111111111"

    monkeypatch.setattr(mod, "record_run", fake_record_run)
    monkeypatch.setattr(
        mod,
        "enqueue_run_memory_extraction_after_commit",
        lambda run_id: enqueued.append(run_id),
    )
    return SimpleNamespace(
        module=mod, recorded=recorded, enqueued=enqueued, monkeypatch=monkeypatch
    )


def _tool(door, *, user_id=None):
    tools = door.module.build_capability_tools(
        workspace_id=7, capabilities=[_capability()], user_id=user_id
    )
    return next(t for t in tools if t.name == "amazon_scrape")


async def test_agent_run_carries_the_active_creator(door):
    """D4/T4: the chat principal reaches ``record_run(user_id=...)``."""
    import uuid

    user_id = uuid.uuid4()
    await _tool(door, user_id=user_id).coroutine(text="hello")

    assert len(door.recorded) == 1
    assert door.recorded[0]["user_id"] == user_id
    assert door.recorded[0]["status"] == "success"


async def test_agent_run_without_creator_still_records(door):
    """An authorless invocation is still recorded — extraction decides to skip."""
    await _tool(door, user_id=None).coroutine(text="hello")

    assert door.recorded[0]["user_id"] is None


async def test_successful_agent_run_hits_the_completion_seam(door):
    """AC-1: a successful agent run enqueues exactly one extraction."""
    await _tool(door, user_id=None).coroutine(text="hello")

    assert door.enqueued == ["11111111-1111-1111-1111-111111111111"]


async def test_failed_agent_run_does_not_enqueue(door):
    """D1: an executor failure records ``error`` and enqueues nothing."""

    async def boom(payload):
        raise RuntimeError("upstream is down")

    cap = _capability()
    cap = Capability(
        name=cap.name,
        description=cap.description,
        input_schema=cap.input_schema,
        output_schema=cap.output_schema,
        executor=boom,
        billing_unit=cap.billing_unit,
    )
    tools = door.module.build_capability_tools(workspace_id=7, capabilities=[cap])
    tool = next(t for t in tools if t.name == "amazon_scrape")

    with pytest.raises(RuntimeError):
        await tool.coroutine(text="hello")

    assert door.enqueued == []
    assert door.recorded[0]["status"] == "error"


async def test_unreachable_broker_does_not_break_the_tool_result(door):
    """AC-5: a dead broker must not change the capability response.

    Exercises the *real* seam (not a stub) with a ``.delay`` that raises, which is
    what a down broker looks like from here. The tool must still return its
    payload, because the scrape itself already succeeded and the run row is
    already durable.
    """
    from app.services.memory import run_enqueue

    door.monkeypatch.setattr(
        door.module,
        "enqueue_run_memory_extraction_after_commit",
        run_enqueue.enqueue_run_memory_extraction_after_commit,
    )

    def dead_broker(_run_id):
        raise RuntimeError("broker unreachable")

    door.monkeypatch.setattr(
        "app.tasks.celery_tasks.run_memory_extraction_task.extract_memory_after_run.delay",
        dead_broker,
    )

    result = await _tool(door).coroutine(text="hello")

    assert result["echoed"] == "hello"
    assert result["run_id"] == "run_11111111-1111-1111-1111-111111111111"
