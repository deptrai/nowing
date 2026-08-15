"""Executor for B2B Decision Maker Capability (Story 21.9 / AD-LI-6)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from app.capabilities.b2b.schemas import (
    B2BDecisionMakerInput,
    B2BDecisionMakerOutput,
    ExecutiveDecisionMakerItem,
)
from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.proprietary.platforms.linkedin.executive_dorker import dork_executives
from app.proprietary.platforms.linkedin.schemas import ExecutiveProfile

logger = logging.getLogger(__name__)

DorkFn = Callable[..., Awaitable[list[ExecutiveProfile]]]


def build_decision_maker_executor(dork_fn: DorkFn | None = None) -> Executor:
    """Build capability executor function for B2B executive discovery."""

    async def execute(payload: B2BDecisionMakerInput) -> B2BDecisionMakerOutput:
        fn = dork_fn or dork_executives
        emit_progress(
            "starting",
            f"Searching decision makers for '{payload.company_name}'",
            total=payload.limit,
            unit="profile",
        )

        profiles = await fn(
            company_name=payload.company_name,
            roles=payload.roles,
            domain=payload.domain,
            limit=payload.limit,
        )

        items = [
            ExecutiveDecisionMakerItem(
                full_name=p.full_name,
                title=p.title,
                company_name=p.company_name,
                linkedin_url=p.linkedin_url,
                linkedin_slug=p.linkedin_slug,
                email_prediction=p.email_prediction or (p.inferred_emails[0] if p.inferred_emails else None),
                inferred_emails=p.inferred_emails,
                confidence_score=p.confidence_score,
                verified_mx=p.verified_mx,
            )
            for p in profiles
        ]

        emit_progress(
            "done",
            f"Discovered {len(items)} decision makers for '{payload.company_name}'",
            current=len(items),
            unit="profile",
        )

        return B2BDecisionMakerOutput(
            company_name=payload.company_name,
            domain=payload.domain,
            executives=items,
            total_found=len(items),
        )

    return execute
