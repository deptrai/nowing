"""Workspace limits service package (split from workspace_limits.py)."""

from __future__ import annotations

from .service import ResolvedWorkspaceLimits, WorkspaceLimitService

workspace_limit_service = WorkspaceLimitService()

# Re-export WorkspaceCreditService and errors for unified limits & credit access (Story 24.3)
from app.services.workspace_credit_service import (  # noqa: E402
    CreditDeductionResult,
    InsufficientCreditsError,
    MemberSpendStatus,
    SpendCapExceededError,
    WorkspaceCreditService,
    workspace_credit_service,
)

__all__ = [
    "CreditDeductionResult",
    "InsufficientCreditsError",
    "MemberSpendStatus",
    "ResolvedWorkspaceLimits",
    "SpendCapExceededError",
    "WorkspaceCreditService",
    "WorkspaceLimitService",
    "workspace_credit_service",
    "workspace_limit_service",
]
