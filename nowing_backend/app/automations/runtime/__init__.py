"""Automation run executor: plan walker, step dispatch, retries, persistence."""

from __future__ import annotations

from .executor import execute_run
from .origin import (
    automation_run_origin,
    current_automation_run_id,
    get_current_automation_run_id,
)

__all__ = [
    "automation_run_origin",
    "current_automation_run_id",
    "execute_run",
    "get_current_automation_run_id",
]
