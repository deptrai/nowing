"""Register the ``tech_stack.signal`` capability."""

from __future__ import annotations

from app.capabilities.core import Capability, register_capability
from app.lead_intelligence.signals.schemas import SignalInput, SignalOutput

from .executor import build_signal_executor

TECH_STACK_SIGNAL = Capability(
    name="tech_stack.signal",
    description="Detect tech_stack buying-intent signals for a company.",
    input_schema=SignalInput,
    output_schema=SignalOutput,
    executor=build_signal_executor("tech_stack"),
    billing_unit=None,
    context_aware=True,
    docs_url="/docs/lead-intelligence/signals/tech_stack",
    metadata={
        "emits_signals": True,
        "signal_types": ["tech_stack"],
    },
)

register_capability(TECH_STACK_SIGNAL)
