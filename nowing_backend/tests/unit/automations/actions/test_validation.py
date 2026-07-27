"""``validate_plan_steps`` registry save-time validator (Story 3.14, D9 point 4).

Uses the real, self-registered ``continue_research`` action
(``research_thread_id: int`` required, ``top_k: int = 5``, ``ge=1``, ``le=5``)
as the fixture action — no fake registry entries needed.
"""

from __future__ import annotations

import pytest

from app.automations.actions.builtin import (
    continue_research,  # noqa: F401  (self-registers)
)
from app.automations.actions.validation import StepValidationError, validate_plan_steps
from app.automations.schemas.definition.plan_step import PlanStep

pytestmark = pytest.mark.unit


def _step(step_id: str = "s1", action: str = "continue_research", **params) -> PlanStep:
    return PlanStep(step_id=step_id, action=action, params=params)


def test_unknown_action_raises() -> None:
    step = _step(action="does_not_exist", research_thread_id=1)

    with pytest.raises(StepValidationError, match="unknown action"):
        validate_plan_steps([step])


def test_unknown_params_field_raises() -> None:
    step = _step(research_thread_id=1, typo=True)

    with pytest.raises(StepValidationError, match="unknown params field"):
        validate_plan_steps([step])


def test_all_static_valid_passes() -> None:
    step = _step(research_thread_id=1, top_k=3)

    validate_plan_steps([step])  # no raise


def test_all_static_out_of_range_raises() -> None:
    step = _step(research_thread_id=1, top_k=6)

    with pytest.raises(StepValidationError):
        validate_plan_steps([step])


def test_all_static_missing_required_field_raises() -> None:
    step = _step(top_k=3)

    with pytest.raises(StepValidationError):
        validate_plan_steps([step])


def test_templated_field_is_deferred() -> None:
    """A templated ``research_thread_id`` can't be checked until run time."""
    step = _step(research_thread_id="{{ thread_id }}", top_k=5)

    validate_plan_steps([step])  # no raise: static top_k=5 is valid, template deferred


def test_templated_field_with_invalid_static_sibling_raises() -> None:
    """The templated field is deferred, but a static ``top_k=6`` sibling still fails."""
    step = _step(research_thread_id="{{ thread_id }}", top_k=6)

    with pytest.raises(StepValidationError, match="top_k"):
        validate_plan_steps([step])


def test_templated_field_missing_required_raises() -> None:
    """Templating one field doesn't excuse an entirely-omitted required field."""
    step = _step(top_k="{{ tk }}")

    with pytest.raises(StepValidationError, match="missing required field"):
        validate_plan_steps([step])


def test_first_failing_step_raises() -> None:
    good = _step(step_id="s1", research_thread_id=1, top_k=5)
    bad = _step(step_id="s2", research_thread_id=1, top_k=6)

    with pytest.raises(StepValidationError) as exc:
        validate_plan_steps([good, bad])

    assert exc.value.step_id == "s2"
