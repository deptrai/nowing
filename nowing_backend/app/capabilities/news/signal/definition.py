"""Register the ``news.signal`` capability."""

from __future__ import annotations

from app.capabilities.core import Capability, register_capability
from app.lead_intelligence.signals.schemas import SignalInput, SignalOutput

from .executor import build_signal_executor

NEWS_SIGNAL = Capability(
    name="news.signal",
    description="Detect news buying-intent signals for a company.",
    input_schema=SignalInput,
    output_schema=SignalOutput,
    executor=build_signal_executor("news"),
    billing_unit=None,
    context_aware=True,
    docs_url="/docs/lead-intelligence/signals/news",
    metadata={
        "emits_signals": True,
        "signal_types": ["news"],
    },
)

register_capability(NEWS_SIGNAL)
