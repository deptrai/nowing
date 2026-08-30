"""Template variable interpolation and condition evaluation for sequence steps."""

from __future__ import annotations

import re
from typing import Any


def interpolate_template_variables(
    template_str: str, variables: dict[str, Any], fallback_blank: bool = True
) -> str:
    """Replace template variables like {customer_name}, {company}, {property_title}."""
    if not template_str:
        return ""

    def _replace(match: re.Match) -> str:
        key = match.group(1).strip()
        val = variables.get(key)
        if val is not None:
            return str(val)
        return "" if fallback_blank else match.group(0)

    return re.sub(r"\{([a-zA-Z0-9_]+)\}", _replace, template_str)


def evaluate_condition_step(
    condition_config: dict[str, Any], context: dict[str, Any]
) -> int | None:
    """Evaluate condition predicate (e.g. has_replied, opened) and return next step order or None."""
    predicate = condition_config.get("predicate", "has_replied")
    if_true_step = condition_config.get("if_true_step")
    if_false_step = condition_config.get("if_false_step")

    is_matched = bool(context.get(predicate, False))
    return if_true_step if is_matched else if_false_step
