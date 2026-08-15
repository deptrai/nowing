"""Capability registration for social.analyze_viral_outliers."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability
from app.capabilities.social.analyze_viral_outliers.executor import (
    build_analyze_outliers_executor,
)
from app.capabilities.social.analyze_viral_outliers.schemas import (
    SocialAnalyzeOutliersInput,
    SocialAnalyzeOutliersOutput,
)

SOCIAL_ANALYZE_VIRAL_OUTLIERS = Capability(
    name="social.analyze_viral_outliers",
    description="Analyze captured social feeds and identify outlier viral posts (>= 3x author baseline).",
    input_schema=SocialAnalyzeOutliersInput,
    output_schema=SocialAnalyzeOutliersOutput,
    executor=build_analyze_outliers_executor(),
    billing_unit=BillingUnit.SOCIAL_LEAD_ITEM,
    docs_url="/docs/capabilities/social/analyze_viral_outliers",
)

register_capability(SOCIAL_ANALYZE_VIRAL_OUTLIERS)
