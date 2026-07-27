"""Save-time validation of a plan's ``params`` against each step's action model.

Story 3.14 (D9): before this module, ``AutomationService.create()``/``update()``
validated only trigger params — a plan step with an unknown action, an unknown
params key, a missing required field, or an out-of-range literal (e.g.
``continue_research`` ``top_k=6``) reached a run before any error surfaced.

A Jinja-templated value (``{{ ... }}``) can't be checked before the template
context exists at run time, so it's exempted per-field rather than failing the
whole step. When every field is static the full ``params_model`` validates at
once (covering cross-field validators); when some are templated, only the
non-templated fields validate — individually, via
``FieldInfo.rebuild_annotation()`` + ``TypeAdapter`` — so a static field next to
a templated sibling is still checked (e.g. a literal ``top_k=6`` fails even
though ``query`` is templated).
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.automations.actions import get_action
from app.automations.schemas.definition.plan_step import PlanStep

_JINJA_PATTERN = re.compile(r"{{.*}}", re.DOTALL)


class StepValidationError(ValueError):
    """A plan step's action or params failed save-time validation."""

    def __init__(self, step_id: str, message: str) -> None:
        super().__init__(f"step {step_id!r}: {message}")
        self.step_id = step_id


def validate_plan_steps(plan: list[PlanStep]) -> None:
    """Validate every step's params against its registered action.

    Raises :class:`StepValidationError` on the first failing step.
    """
    for step in plan:
        _validate_step(step)


def _validate_step(step: PlanStep) -> None:
    action = get_action(step.action)
    if action is None:
        raise StepValidationError(step.step_id, f"unknown action {step.action!r}")

    params = step.params or {}
    model_fields = action.params_model.model_fields

    for key in params:
        if key not in model_fields:
            raise StepValidationError(
                step.step_id,
                f"unknown params field {key!r} for action {step.action!r}",
            )

    templated_keys = {key for key, value in params.items() if _is_templated(value)}

    if not templated_keys:
        try:
            action.params_model.model_validate(params)
        except ValidationError as exc:
            raise StepValidationError(step.step_id, str(exc)) from exc
        return

    missing = sorted(
        name
        for name, field in model_fields.items()
        if field.is_required() and name not in params
    )
    if missing:
        raise StepValidationError(
            step.step_id, f"missing required field(s): {', '.join(missing)}"
        )

    for key, value in params.items():
        if key in templated_keys:
            continue
        adapter = TypeAdapter(model_fields[key].rebuild_annotation())
        try:
            adapter.validate_python(value)
        except ValidationError as exc:
            raise StepValidationError(step.step_id, f"{key}: {exc}") from exc


def _is_templated(value: Any) -> bool:
    return isinstance(value, str) and bool(_JINJA_PATTERN.search(value))
