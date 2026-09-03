"""Base classes and types for Third-Party Health Probes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

HealthStatus = Literal["healthy", "degraded", "unavailable", "disabled", "not_configured"]


@dataclass
class HealthResult:
    """Standard probe result representing the health of a single service."""

    service_id: str
    service_name: str
    category: str
    display_group: str
    status: HealthStatus
    latency_ms: int | None = None
    last_error: str | None = None
    suggested_action: str | None = None
    error_rate_15m: float = 0.0
    success_rate_15m: float = 100.0
    metadata: dict[str, Any] = field(default_factory=dict)
    probed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for caching and serialization."""
        return {
            "service_id": self.service_id,
            "service_name": self.service_name,
            "category": self.category,
            "display_group": self.display_group,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "last_error": self.last_error,
            "suggested_action": self.suggested_action,
            "error_rate_15m": self.error_rate_15m,
            "success_rate_15m": self.success_rate_15m,
            "metadata": self.metadata,
            "probed_at": self.probed_at.isoformat(),
        }


class HealthProbe(ABC):
    """Abstract base class for all pluggable health probes."""

    @property
    @abstractmethod
    def service_id(self) -> str:
        """Unique identifier of the probed service (e.g., 'azure/gpt-5.1', 'batdongsan')."""
        ...

    @property
    @abstractmethod
    def service_name(self) -> str:
        """Human-readable name of the service."""
        ...

    @property
    @abstractmethod
    def category(self) -> str:
        """Category: infra, model, scraper, connector, proxy, research, messaging, payment, storage."""
        ...

    @property
    def display_group(self) -> str:
        """Logical UI group within the category."""
        return "General"

    @property
    def interval_seconds(self) -> int:
        """Default probe interval in seconds."""
        return 300

    @abstractmethod
    async def probe(self) -> HealthResult:
        """Execute non-destructive health probe and return standardized result."""
        ...
