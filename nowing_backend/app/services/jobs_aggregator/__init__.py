"""Vietnam job market aggregator (Epic 12)."""

from __future__ import annotations

from .orchestrator import aggregate_jobs
from .schemas import (
    VnJobAggregatedListing,
    VnJobAggregateInput,
    VnJobAggregateOutput,
)

__all__ = [
    "VnJobAggregateInput",
    "VnJobAggregateOutput",
    "VnJobAggregatedListing",
    "aggregate_jobs",
]
