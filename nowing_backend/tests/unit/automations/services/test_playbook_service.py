"""Unit tests for ``PlaybookService`` helpers."""

from __future__ import annotations

import pytest

from app.automations.schemas.definition import AutomationDefinition, Inputs
from app.automations.schemas.definition.execution import Execution
from app.automations.schemas.definition.plan_step import PlanStep
from app.automations.services.playbook_service import (
    _extract_inputs_schema,
    _extract_tool_scope,
    _validate_definition_plan,
    _validate_json_schema,
)


def test_extract_inputs_schema_returns_schema():
    definition = AutomationDefinition(
        name="t",
        plan=[PlanStep(step_id="s", action="agent_task")],
        inputs=Inputs(schema={"type": "object", "properties": {"q": {"type": "string"}}}),
    )
    assert _extract_inputs_schema(definition) == {
        "type": "object",
        "properties": {"q": {"type": "string"}},
    }


def test_extract_inputs_schema_defaults_to_empty_dict():
    definition = AutomationDefinition(
        name="t", plan=[PlanStep(step_id="s", action="agent_task")]
    )
    assert _extract_inputs_schema(definition) == {}


def test_extract_tool_scope_collects_plan_and_on_failure_actions():
    definition = AutomationDefinition(
        name="t",
        plan=[
            PlanStep(step_id="a", action="agent_task"),
            PlanStep(step_id="b", action="agent_task"),
            PlanStep(step_id="c", action="continue_research"),
        ],
        execution=Execution(
            on_failure=[PlanStep(step_id="f", action="write_back_slack")]
        ),
    )
    assert _extract_tool_scope(definition) == [
        "agent_task",
        "continue_research",
        "write_back_slack",
    ]


def test_validate_json_schema_rejects_malformed_schema():
    with pytest.raises(Exception):  # noqa: B017
        _validate_json_schema({"type": "not-a-real-type"})


def test_validate_json_schema_accepts_valid_schema():
    _validate_json_schema(
        {"type": "object", "properties": {"q": {"type": "string"}}}
    )  # should not raise


def test_validate_definition_plan_rejects_unknown_action():
    definition = AutomationDefinition(
        name="t",
        plan=[PlanStep(step_id="s1", action="not_a_real_action")],
    )
    with pytest.raises(Exception):  # noqa: B017
        _validate_definition_plan(definition)
