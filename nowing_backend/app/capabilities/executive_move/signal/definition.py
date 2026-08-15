"""Register the ``executive_move.signal`` capability."""

from __future__ import annotations

from app.capabilities.core import Capability, register_capability
from app.lead_intelligence.signals.schemas import SignalInput, SignalOutput

from .executor import build_signal_executor

EXECUTIVE_MOVE_SIGNAL = Capability(
    name="executive_move.signal",
    description="Detect executive_move buying-intent signals for a company.",
    input_schema=SignalInput,
    output_schema=SignalOutput,
    executor=build_signal_executor("executive_move"),
    billing_unit=None,
    context_aware=True,
    docs_url="/docs/lead-intelligence/signals/executive_move",
    metadata={
        "emits_signals": True,
        "signal_types": ["executive_move"],
    },
)

register_capability(EXECUTIVE_MOVE_SIGNAL)
