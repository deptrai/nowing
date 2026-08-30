"""Sequencer constants, error types, and analytics data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# Default allowed channels in MVP (Story 24.1 / AD-41)
ALLOWED_OUTBOUND_CHANNELS = ["email"]

# Opt-out trigger keywords
OPT_OUT_KEYWORDS = {
    "stop",
    "huy",
    "hủy",
    "ngung",
    "ngưng",
    "unsubscribe",
    "optout",
    "opt-out",
}


class DeferredChannelError(Exception):
    """Raised when an outreach channel is not supported in the MVP release (AD-41 / DEF-102)."""


@dataclass
class ChannelAnalytics:
    """Per-channel metrics for a sequence."""

    channel: str = "email"
    sent: int = 0
    delivered: int = 0
    opened: int = 0
    replied: int = 0
    bounced: int = 0
    failed: int = 0
    skipped: int = 0
    cost_micros: int = 0


@dataclass
class SequenceAnalytics:
    """Aggregated metrics for a sequence."""

    total_enrolled: int = 0
    active_scheduled: int = 0
    delivered_count: int = 0
    responded_count: int = 0
    unsubscribed_count: int = 0
    failed_count: int = 0
    total_cost_micros: int = 0
    channel_breakdown: list[ChannelAnalytics] = field(default_factory=list)
