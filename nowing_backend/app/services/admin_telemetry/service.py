from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import case, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    TokenUsage,
)

from ._helpers import _ALLOWED_PROVIDERS, _clamp_window
from .costs import CostTelemetryMixin
from .health import ProxyHealthMixin
from .margin import MarginTelemetryMixin
from .queues import QueueTelemetryMixin

logger = logging.getLogger(__name__)


class AdminTelemetryService(
    CostTelemetryMixin, MarginTelemetryMixin, ProxyHealthMixin, QueueTelemetryMixin
):
    """Aggregate telemetry for platform superadmins.

    Reuses SQL patterns from :class:`app.services.usage_service.UsageService`
    but removes the workspace scoping and adds admin-only dimensions.
    """

    def __init__(self, session: AsyncSession | None):
        self.session = session

    def _cutoff(self, window_hours: int) -> datetime:
        """Return the earliest inclusive timestamp for the window.

        Floored to the bucket boundary (hour or day) so time-series buckets
        start cleanly. This may slightly widen the window to the nearest whole
        bucket; callers display ``window_hours`` as requested.
        """
        window_hours = _clamp_window(window_hours)
        raw = datetime.now(UTC) - timedelta(hours=window_hours)
        if self._granularity(window_hours) == "hour":
            return raw.replace(minute=0, second=0, microsecond=0)
        return raw.replace(hour=0, minute=0, second=0, microsecond=0)

    def _granularity(self, window_hours: int) -> str:
        """Pick hour buckets for <= 48h, day buckets otherwise."""
        return "hour" if window_hours <= 48 else "day"

    def _token_filters(
        self, cutoff: datetime, workspace_id: int | None = None
    ) -> list[Any]:
        filters = [TokenUsage.created_at >= cutoff]
        if workspace_id is not None:
            filters.append(TokenUsage.workspace_id == workspace_id)
        return filters

    def _provider_expr(self) -> Any:
        """Resolve provider from model_breakdown JSONB, lower/trim, and bucket unsupported values to 'unknown'."""
        from_jsonb = func.trim(
            func.lower(
                func.coalesce(TokenUsage.model_breakdown["provider"].as_string(), "")
            )
        )
        from_details = func.trim(
            func.lower(
                func.coalesce(TokenUsage.call_details["provider"].as_string(), "")
            )
        )
        raw = func.coalesce(
            func.nullif(from_jsonb, ""),
            func.nullif(from_details, ""),
            "unknown",
        ).label("provider_raw")
        return case((raw.in_(list(_ALLOWED_PROVIDERS)), raw), else_="unknown").label(
            "provider"
        )

    def _model_expr(self) -> Any:
        """Resolve model key from model_breakdown JSONB."""
        return func.coalesce(
            func.nullif(func.trim(TokenUsage.model_breakdown["model"].as_string()), ""),
            func.coalesce(TokenUsage.call_details["model"].as_string(), ""),
            "unknown",
        ).label("model")

    def _prompt_tokens_expr(self) -> Any:
        return func.coalesce(func.sum(TokenUsage.prompt_tokens), 0).label(
            "input_tokens"
        )

    def _completion_tokens_expr(self) -> Any:
        return func.coalesce(func.sum(TokenUsage.completion_tokens), 0).label(
            "output_tokens"
        )
