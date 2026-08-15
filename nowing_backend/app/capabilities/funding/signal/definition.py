"""Register the ``funding.signal`` capability."""

from __future__ import annotations

from app.capabilities.core import Capability, register_capability
from app.lead_intelligence.signals.schemas import SignalInput, SignalOutput

from .executor import build_signal_executor

FUNDING_SIGNAL = Capability(
    name="funding.signal",
    description="Detect funding buying-intent signals for a company.",
    input_schema=SignalInput,
    output_schema=SignalOutput,
    executor=build_signal_executor("funding"),
    billing_unit=None,
    context_aware=True,
    docs_url="/docs/lead-intelligence/signals/funding",
    metadata={
        "emits_signals": True,
        "signal_types": ["funding"],
    },
)

register_capability(FUNDING_SIGNAL)
