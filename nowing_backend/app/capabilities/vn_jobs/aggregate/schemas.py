"""``vn_jobs.aggregate`` I/O contracts (re-exported from the aggregator)."""

from __future__ import annotations

from app.services.jobs_aggregator.schemas import (
    VnJobAggregatedListing,
    VnJobAggregateInput,
    VnJobAggregateOutput,
)

__all__ = ["VnJobAggregateInput", "VnJobAggregateOutput", "VnJobAggregatedListing"]
