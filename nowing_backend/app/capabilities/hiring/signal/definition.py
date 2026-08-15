"""Register the ``hiring.signal`` capability."""

from __future__ import annotations

from app.capabilities.core import Capability, register_capability
from app.lead_intelligence.signals.schemas import SignalInput, SignalOutput

from .executor import build_signal_executor

HIRING_SIGNAL = Capability(
    name="hiring.signal",
    description="Detect hiring buying-intent signals for a company.",
    input_schema=SignalInput,
    output_schema=SignalOutput,
    executor=build_signal_executor("hiring"),
    billing_unit=None,
    context_aware=True,
    docs_url="/docs/lead-intelligence/signals/hiring",
    metadata={
        "emits_signals": True,
        "signal_types": ["hiring"],
    },
)

register_capability(HIRING_SIGNAL)
