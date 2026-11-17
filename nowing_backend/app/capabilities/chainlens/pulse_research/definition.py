"""``chainlens.pulse_research`` capability registration (Story 20.11)."""

from __future__ import annotations

from app.capabilities.chainlens.pulse_research.executor import (
    build_pulse_research_executor,
)
from app.capabilities.chainlens.research.schemas import ResearchOutput
from app.capabilities.core import BillingUnit, Capability, register_capability

CHAINLENS_PULSE_RESEARCH = Capability(
    name="chainlens.pulse_research",
    description=(
        "Run a cited deep-research report on a curated Pulse feed angle. "
        "Use when the user picks a news angle from the Pulse feed and wants "
        "a full deep-research report in one click."
    ),
    input_schema=None,  # PulseResearchInput uses camelCase aliases; registered below
    output_schema=ResearchOutput,
    executor=build_pulse_research_executor(),
    billing_unit=BillingUnit.CHAINLENS_QUERY,
    docs_url="/docs/connectors/native/chainlens-pulse-research",
    context_aware=True,
)

register_capability(CHAINLENS_PULSE_RESEARCH)
