"""Registration of the ``b2b.decision_makers`` capability (Story 21.9 / AD-LI-6)."""

from __future__ import annotations

from app.capabilities.b2b.executor import build_decision_maker_executor
from app.capabilities.b2b.schemas import (
    B2BDecisionMakerInput,
    B2BDecisionMakerOutput,
)
from app.capabilities.core import Capability, register_capability

B2B_FIND_DECISION_MAKERS = Capability(
    name="b2b.decision_makers",
    description="Discover C-Level executives, Founders, and HR decision-makers for B2B outreach.",
    input_schema=B2BDecisionMakerInput,
    output_schema=B2BDecisionMakerOutput,
    executor=build_decision_maker_executor(),
    billing_unit=None,
    docs_url="/docs/lead-intelligence/decision-makers",
)

register_capability(B2B_FIND_DECISION_MAKERS)
