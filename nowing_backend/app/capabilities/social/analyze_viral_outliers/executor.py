"""Executor for social.analyze_viral_outliers capability."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.capabilities.core.types import CapabilityContext
from app.capabilities.social.analyze_viral_outliers.schemas import (
    SocialAnalyzeOutliersInput,
    SocialAnalyzeOutliersOutput,
)
from app.db import async_session_maker
from app.services.social_copilot.outlier_detector import OutlierDetector


def build_analyze_outliers_executor() -> Callable[
    [SocialAnalyzeOutliersInput, CapabilityContext], Any
]:
    async def execute(
        input_data: SocialAnalyzeOutliersInput,
        context: CapabilityContext,
    ) -> SocialAnalyzeOutliersOutput:
        if not context.workspace_id:
            raise ValueError("Capability context missing workspace_id")

        async with async_session_maker() as session:
            detector = OutlierDetector(session=session)
            outliers = await detector.find_outliers(
                workspace_id=context.workspace_id,
                client_id=context.client_id or "default",
                target_keywords=input_data.keywords if input_data.keywords else None,
                min_multiplier=input_data.min_multiplier,
                min_engagement=input_data.min_engagement,
            )
            return SocialAnalyzeOutliersOutput(
                outliers=outliers, total_found=len(outliers)
            )

    return execute
