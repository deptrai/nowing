"""AI Lead Generation Enterprise Evaluation Suite (Story 21.15 / Story 28.5).

Registers the enterprise lead generation benchmark assessing multi-source
harvesting, intent routing, ICP compliance, and entity deduplication.
"""

from ...core.registry import register
from .metrics import (
    contact_accuracy,
    duplicate_rate,
    false_positive_rate,
    icp_match_rate,
    intent_signal_precision,
    precision_at_k,
    recall_at_source,
    time_to_first_lead,
)
from .runner import (
    LeadGenerationBenchmark,
    TestCase,
    evaluate_lead_generation_gate,
    load_lead_generation_gate,
)

register(LeadGenerationBenchmark())

__all__ = [
    "LeadGenerationBenchmark",
    "TestCase",
    "contact_accuracy",
    "duplicate_rate",
    "evaluate_lead_generation_gate",
    "false_positive_rate",
    "icp_match_rate",
    "intent_signal_precision",
    "load_lead_generation_gate",
    "precision_at_k",
    "recall_at_source",
    "time_to_first_lead",
]
