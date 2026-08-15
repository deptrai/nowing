"""Executor for social.generate_viral_drafts capability."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.capabilities.core.types import CapabilityContext
from app.capabilities.social.generate_viral_drafts.schemas import (
    SocialGenerateDraftsInput,
    SocialGenerateDraftsOutput,
)
from app.schemas.voice_profile import VoiceProfile
from app.services.social_copilot.draft_generator import ViralDraftGenerator


def build_generate_drafts_executor() -> Callable[
    [SocialGenerateDraftsInput, CapabilityContext], Any
]:
    async def execute(
        input_data: SocialGenerateDraftsInput,
        context: CapabilityContext,
    ) -> SocialGenerateDraftsOutput:
        generator = ViralDraftGenerator()
        voice = input_data.voice_profile or VoiceProfile(
            profile_name="Default Persona", tone="authoritative, pragmatic, direct"
        )
        drafts = await generator.generate_drafts(
            topic=input_data.topic,
            hook_taxonomy=input_data.hook_taxonomy,
            voice_profile=voice,
            target_platform=input_data.target_platform,
            n_variations=input_data.n_variations,
        )
        return SocialGenerateDraftsOutput(drafts=drafts, count=len(drafts))

    return execute
