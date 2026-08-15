"""``procurement.summarize`` capability package."""

from __future__ import annotations

from .definition import PROCUREMENT_SUMMARIZE
from .schemas import ProcurementSummarizeInput, ProcurementSummarizeOutput

__all__ = ["PROCUREMENT_SUMMARIZE", "ProcurementSummarizeInput", "ProcurementSummarizeOutput"]
