"""Entity resolution — two-stage dedup helpers on top of DecisionService."""

from app.services.entity_resolution.service import (
    MAX_CANDIDATES_PER_ANCHOR,
    MAX_CONSECUTIVE_ERRORS,
    MAX_DECISION_CALLS_PER_RUN,
    EntityMatchResult,
    EntityVerdict,
    RefineStats,
    confirm_entity_match,
    refine_entity_groups,
    score_entity_pair,
)

__all__ = [
    "MAX_CANDIDATES_PER_ANCHOR",
    "MAX_CONSECUTIVE_ERRORS",
    "MAX_DECISION_CALLS_PER_RUN",
    "EntityMatchResult",
    "EntityVerdict",
    "RefineStats",
    "confirm_entity_match",
    "refine_entity_groups",
    "score_entity_pair",
]
