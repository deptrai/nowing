"""Signal capability executor factory."""

from __future__ import annotations

from typing import Any

from app.lead_intelligence.signals.schemas import SignalInput
from app.lead_intelligence.signals.service import SIGNAL_TYPES, SignalDetectionService


def build_signal_executor(signal_type: str):
    """Return an executor for the given signal type."""
    if signal_type not in SIGNAL_TYPES:
        raise ValueError(f"unknown signal_type: {signal_type}")

    async def _execute(payload: SignalInput, ctx: Any) -> Any:
        service = SignalDetectionService()
        return await service.detect(
            ctx.session,
            ctx,
            payload,
            signal_type,
        )

    return _execute
