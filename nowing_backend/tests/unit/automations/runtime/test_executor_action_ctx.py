"""Lock that the executor propagates the captured model snapshot into the
``ActionContext``, so runs resolve their own model (insulated from chat /
workspace changes) and not the live workspace.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.automations.runtime.executor import _build_action_ctx
from app.automations.schemas.definition.envelope import (
    AutomationDefinition,
    AutomationModels,
)
from app.automations.schemas.definition.plan_step import PlanStep

pytestmark = pytest.mark.unit


def _run() -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        automation=SimpleNamespace(workspace_id=42, created_by_user_id="u-1"),
    )


def _definition(**kwargs) -> AutomationDefinition:
    return AutomationDefinition(
        name="A",
        plan=[PlanStep(step_id="s1", action="agent_task")],
        **kwargs,
    )


def test_build_action_ctx_propagates_captured_models() -> None:
    """``definition.models`` flows onto the ActionContext model fields."""
    models = AutomationModels(
        chat_model_id=-1,
        image_gen_model_id=5,
        vision_model_id=-1,
    )
    ctx = _build_action_ctx(
        cast(AsyncSession, None),
        _run(),
        PlanStep(step_id="s1", action="agent_task"),
        _definition(models=models),
    )

    assert ctx.workspace_id == 42
    assert ctx.chat_model_id == -1
    assert ctx.image_gen_model_id == 5
    assert ctx.vision_model_id == -1


def test_build_action_ctx_none_models_leaves_fields_none() -> None:
    """No captured snapshot → model fields are None (defensive fallback path)."""
    ctx = _build_action_ctx(
        cast(AsyncSession, None),
        _run(),
        PlanStep(step_id="s1", action="agent_task"),
        _definition(models=None),
    )

    assert ctx.chat_model_id is None
    assert ctx.image_gen_model_id is None
    assert ctx.vision_model_id is None


def test_build_action_ctx_propagates_schema_version() -> None:
    """Story 3.14 (D9): the run's definition ``schema_version`` threads onto the
    ``ActionContext``, so an action can branch on which contract produced it."""
    ctx = _build_action_ctx(
        cast(AsyncSession, None),
        _run(),
        PlanStep(step_id="s1", action="agent_task"),
        _definition(schema_version="1.0"),
    )

    assert ctx.schema_version == "1.0"
