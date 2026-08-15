"""Executor for social.learn_voice capability."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.capabilities.core.types import CapabilityContext
from app.capabilities.social.learn_voice.schemas import (
    SocialLearnVoiceInput,
    SocialLearnVoiceOutput,
)
from app.services.social_copilot.voice_learner import VoiceProfileLearner


def build_learn_voice_executor() -> Callable[
    [SocialLearnVoiceInput, CapabilityContext], Any
]:
    async def execute(
        input_data: SocialLearnVoiceInput,
        context: CapabilityContext,
    ) -> SocialLearnVoiceOutput:
        learner = VoiceProfileLearner()
        profile = await learner.extract_voice_profile(
            sample_text=input_data.sample_text,
            profile_name=input_data.profile_name,
            platform=input_data.platform,
        )
        return SocialLearnVoiceOutput(
            profile=profile, message="Voice profile extracted successfully"
        )

    return execute
