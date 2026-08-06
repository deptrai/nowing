"""Services for the automations HTTP layer (one service per resource)."""

from __future__ import annotations

from .automation import AutomationService, get_automation_service
from .model_policy import (
    AutomationModelPolicyError,
    assert_automation_models_billable,
    assert_models_billable,
    get_automation_model_eligibility,
    get_model_eligibility,
)
from .playbook_service import PlaybookService, get_playbook_service
from .run import RunService, get_run_service
from .trigger import TriggerService, get_trigger_service

__all__ = [
    "AutomationModelPolicyError",
    "AutomationService",
    "PlaybookService",
    "RunService",
    "TriggerService",
    "assert_automation_models_billable",
    "assert_models_billable",
    "get_automation_model_eligibility",
    "get_automation_service",
    "get_model_eligibility",
    "get_playbook_service",
    "get_run_service",
    "get_trigger_service",
]
