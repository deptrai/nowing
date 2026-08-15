"""Capability registration for social.generate_viral_drafts."""

from __future__ import annotations

from app.capabilities.core import Capability, register_capability
from app.capabilities.social.generate_viral_drafts.executor import (
    build_generate_drafts_executor,
)
from app.capabilities.social.generate_viral_drafts.schemas import (
    SocialGenerateDraftsInput,
    SocialGenerateDraftsOutput,
)

SOCIAL_GENERATE_VIRAL_DRAFTS = Capability(
    name="social.generate_viral_drafts",
    description="Rewrite deconstructed viral post structures into voice-matched draft variations (Twitter, Facebook, LinkedIn).",
    input_schema=SocialGenerateDraftsInput,
    output_schema=SocialGenerateDraftsOutput,
    executor=build_generate_drafts_executor(),
    billing_unit=None,
    docs_url="/docs/capabilities/social/generate_viral_drafts",
)

register_capability(SOCIAL_GENERATE_VIRAL_DRAFTS)
