"""``vn_bds.aggregate`` I/O contracts (re-exported from the aggregator)."""

from __future__ import annotations

from app.services.bds_aggregator.schemas import (
    VnBdsAggregatedListing,
    VnBdsAggregateInput,
    VnBdsAggregateOutput,
)

__all__ = ["VnBdsAggregateInput", "VnBdsAggregateOutput", "VnBdsAggregatedListing"]
