"""Request/response schemas for the automations HTTP layer."""

from __future__ import annotations

from .automation import (
    AutomationCreate,
    AutomationDetail,
    AutomationList,
    AutomationSummary,
    AutomationUpdate,
)
from .playbook import (
    PlaybookCreate,
    PlaybookDetail,
    PlaybookInstantiate,
    PlaybookList,
    PlaybookSummary,
    PlaybookUpdate,
    PlaybookValidateInputs,
    PlaybookValidationResult,
)
from .run import RunDetail, RunList, RunSummary
from .trigger import TriggerCreate, TriggerDetail, TriggerUpdate

__all__ = [
    "AutomationCreate",
    "AutomationDetail",
    "AutomationList",
    "AutomationSummary",
    "AutomationUpdate",
    "PlaybookCreate",
    "PlaybookDetail",
    "PlaybookInstantiate",
    "PlaybookList",
    "PlaybookSummary",
    "PlaybookUpdate",
    "PlaybookValidateInputs",
    "PlaybookValidationResult",
    "RunDetail",
    "RunList",
    "RunSummary",
    "TriggerCreate",
    "TriggerDetail",
    "TriggerUpdate",
]
