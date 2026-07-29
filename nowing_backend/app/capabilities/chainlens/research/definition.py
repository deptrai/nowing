"""``chainlens.research`` capability registration."""

from __future__ import annotations

from app.capabilities.chainlens.research.executor import build_research_executor
from app.capabilities.chainlens.research.schemas import ResearchInput, ResearchOutput
from app.capabilities.core import BillingUnit, Capability, register_capability

CHAINLENS_RESEARCH = Capability(
    name="chainlens.research",
    description=(
        "Multi-source web research via ChainLens Research. Returns a synthesized "
        "answer with cited sources. Best for literature reviews, due diligence, "
        "and deep factual Q&A."
    ),
    input_schema=ResearchInput,
    output_schema=ResearchOutput,
    executor=build_research_executor(),
    billing_unit=BillingUnit.CHAINLENS_QUERY,
    docs_url="/docs/connectors/native/chainlens-research",
    context_aware=True,
)

register_capability(CHAINLENS_RESEARCH)
