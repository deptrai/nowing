"""Capability registration for social.learn_voice."""

from __future__ import annotations

from app.capabilities.core import Capability, register_capability
from app.capabilities.social.learn_voice.executor import build_learn_voice_executor
from app.capabilities.social.learn_voice.schemas import (
    SocialLearnVoiceInput,
    SocialLearnVoiceOutput,
)

SOCIAL_LEARN_VOICE = Capability(
    name="social.learn_voice",
    description="Analyze user writing samples (>= 100 words) and extract structured voice profile.",
    input_schema=SocialLearnVoiceInput,
    output_schema=SocialLearnVoiceOutput,
    executor=build_learn_voice_executor(),
    billing_unit=None,
    docs_url="/docs/capabilities/social/learn_voice",
)

register_capability(SOCIAL_LEARN_VOICE)
