"""Backend-agnostic types for the decision service (AD-J1).

Questions and answers are defined here — not in ``typesafe_sdk`` — so
callers and the question registry stay vendor-neutral. ``backends/jev.py``
maps these onto the SDK's ``Choice``/``Score``/``Noul`` models; the mock
backend answers them directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass(frozen=True)
class Question:
    """Base typed-decision question. ``instructions`` is English (AD-J8)."""

    instructions: str
    kind: ClassVar[str] = "question"


@dataclass(frozen=True)
class ChoiceQuestion(Question):
    """Pick exactly one of ``criteria`` keys; values are descriptions."""

    kind: ClassVar[str] = "choice"
    criteria: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ScoreQuestion(Question):
    """Score on an ordinal rubric; ``criteria[i]`` describes level ``i``."""

    kind: ClassVar[str] = "score"
    criteria: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class NoulQuestion(Question):
    """Yes/no probability (0-1). ``criteria`` optionally names true/false."""

    kind: ClassVar[str] = "noul"
    criteria: dict[str, Any] | None = None


@dataclass(frozen=True)
class Answer:
    """Normalized typed answer (pre-validation shape, AD-J1).

    - ``kind``: ``"choice"`` | ``"score"`` | ``"noul"``
    - ``value``: choice id (str) for choice, float score/noul otherwise
    - ``confidence``: 0-1. For ``noul`` the noul value itself doubles as
      confidence so ``ConfidenceGate`` can treat every kind uniformly.
    - ``probabilities``: full distribution keyed by *string* ids
      (score level indices are normalized to ``"0"``, ``"1"``, ...).
      ``None`` for noul.
    """

    kind: str
    value: str | float
    confidence: float
    probabilities: dict[str, float] | None = None


@dataclass(frozen=True)
class BackendResult:
    """What a backend returns to ``DecisionService`` before validation."""

    answers: dict[str, Answer]
    model: str
    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True)
class DecisionResult:
    """Validated result handed to callers (AD-J1 interface)."""

    answers: dict[str, Answer]
    model: str
    backend: str
    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None
