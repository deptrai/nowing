"""Template variable interpolation and condition evaluation for sequence steps."""

from __future__ import annotations

import re
from typing import Any


def interpolate_template_variables(
    template_str: str, variables: dict[str, Any], fallback_blank: bool = True
) -> str:
    """Replace template variables like {customer_name}, {company}, {property_title}.

    ``{{var}}`` double-brace tokens (Story 37.5 spec syntax) are normalized to
    the single-brace form before interpolation so both spellings work — scoped
    to real token patterns only, so literal ``{{``/``}}`` in copy (JSON
    snippets, escaped braces) is left untouched.
    """
    if not template_str:
        return ""

    normalized = re.sub(
        r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", r"{\1}", template_str
    )

    def _replace(match: re.Match) -> str:
        key = match.group(1).strip()
        val = variables.get(key)
        if val is not None:
            return str(val)
        return "" if fallback_blank else match.group(0)

    return re.sub(r"\{\s*([a-zA-Z0-9_]+)\s*\}", _replace, normalized)


def interpolate_template_data(
    data: Any, variables: dict[str, Any], fallback_blank: bool = True
) -> Any:
    """Recursively interpolate ``{var}`` tokens inside dicts/lists/strings.

    Non-string scalars pass through unchanged; non-dict containers are
    tolerated (ZNS ``template_data`` may arrive as a list or raw string).
    """
    if isinstance(data, str):
        return interpolate_template_variables(data, variables, fallback_blank)
    if isinstance(data, dict):
        return {
            k: interpolate_template_data(v, variables, fallback_blank)
            for k, v in data.items()
        }
    if isinstance(data, (list, tuple)):
        return [
            interpolate_template_data(v, variables, fallback_blank) for v in data
        ]
    return data


def evaluate_condition_step(
    condition_config: dict[str, Any], context: dict[str, Any]
) -> int | None:
    """Evaluate condition predicate (e.g. has_replied, opened) and return next step order or None."""
    predicate = condition_config.get("predicate", "has_replied")
    if_true_step = condition_config.get("if_true_step")
    if_false_step = condition_config.get("if_false_step")

    is_matched = bool(context.get(predicate, False))
    return if_true_step if is_matched else if_false_step
