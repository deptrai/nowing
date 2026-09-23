"""Backward-compatible shim for the refactored sequencer package.

This module re-exports the public API previously defined in the monolithic
``app.services.sequencer_service`` module so that existing imports continue to
work. New code should import directly from ``app.services.sequencer``.
"""

from __future__ import annotations

from app.lead_intelligence.dnc.service import DncComplianceService
from app.redis_client import get_redis_client
from app.services.sequencer import (
    ALLOWED_OUTBOUND_CHANNELS,
    NEUTRAL_RESOLUTION,
    OPT_OUT_KEYWORDS,
    VN_TZ,
    ChannelAnalytics,
    DeferredChannelError,
    HonorificQualityGate,
    HonorificResolution,
    SequenceAnalytics,
    SequencerService,
    VietnamHonorificResolver,
    calculate_step_eta,
    evaluate_condition_step,
    interpolate_template_data,
    interpolate_template_variables,
    is_dispatch_curfew,
)

__all__ = [
    "ALLOWED_OUTBOUND_CHANNELS",
    "NEUTRAL_RESOLUTION",
    "OPT_OUT_KEYWORDS",
    "VN_TZ",
    "ChannelAnalytics",
    "DeferredChannelError",
    "DncComplianceService",
    "HonorificQualityGate",
    "HonorificResolution",
    "SequenceAnalytics",
    "SequencerService",
    "VietnamHonorificResolver",
    "calculate_step_eta",
    "evaluate_condition_step",
    "get_redis_client",
    "interpolate_template_data",
    "interpolate_template_variables",
    "is_dispatch_curfew",
]
