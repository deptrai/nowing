"""Typed-decision layer (Epic 39).

``DecisionService`` is the single port for Choice/Score/Noul decisions
(AD-J1). Callers never import ``typesafe_sdk`` — only
``backends/jev.py`` may. Backend selection is config-driven (AD-J2) and
every call is flag-gated, strictly validated, and logged to
``TokenUsage`` (AD-J7).
"""

from app.services.decision.backends.base import DecisionBackend
from app.services.decision.errors import DecisionError, InvalidDecisionAnswer
from app.services.decision.gate import ConfidenceGate
from app.services.decision.questions import (
    QuestionRegistry,
    QuestionSet,
    get_question_registry,
)
from app.services.decision.service import DecisionService, get_decision_service
from app.services.decision.types import (
    Answer,
    BackendResult,
    ChoiceQuestion,
    DecisionResult,
    NoulQuestion,
    Question,
    ScoreQuestion,
)
from app.services.decision.validation import validate_answer

__all__ = [
    "Answer",
    "BackendResult",
    "ChoiceQuestion",
    "ConfidenceGate",
    "DecisionBackend",
    "DecisionError",
    "DecisionResult",
    "DecisionService",
    "InvalidDecisionAnswer",
    "NoulQuestion",
    "Question",
    "QuestionRegistry",
    "QuestionSet",
    "ScoreQuestion",
    "get_decision_service",
    "get_question_registry",
    "validate_answer",
]
