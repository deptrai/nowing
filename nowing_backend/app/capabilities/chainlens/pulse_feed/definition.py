"""``chainlens.pulse_feed`` capability registration (Story 20.10)."""

from __future__ import annotations

from app.capabilities.chainlens.pulse_feed.executor import build_pulse_feed_executor
from app.capabilities.chainlens.pulse_feed.schemas import (
    PulseFeedInput,
    PulseFeedOutput,
)
from app.capabilities.core import BillingUnit, Capability, register_capability

CHAINLENS_PULSE_FEED = Capability(
    name="chainlens.pulse_feed",
    description=(
        "Curated market and competitor intelligence feed. "
        "Use when user asks 'what's new in tech/ai', 'latest competitor moves', "
        "or wants to browse proactive market signals rather than on-demand search."
    ),
    input_schema=PulseFeedInput,
    output_schema=PulseFeedOutput,
    executor=build_pulse_feed_executor(),
    billing_unit=BillingUnit.CHAINLENS_QUERY,
    docs_url="/docs/connectors/native/chainlens-pulse-feed",
    context_aware=True,
)

register_capability(CHAINLENS_PULSE_FEED)
