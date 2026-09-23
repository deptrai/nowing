"""Strict structural validation for typed answers (AD-J1).

Every ``Answer`` must pass :func:`validate_answer` before it enters a
``DecisionResult``. Pattern ported from jev-ultrafast ``validate_choice()``
(reference only — not vendored):

- Choice: chosen id ∈ offered ids; probability keys exactly match ids;
  values finite ∈ [0,1]; distribution sums to 1 ± 0.02; chosen = argmax.
- Score: probability keys exactly match level ids ``"0".."n-1"``; values
  finite ∈ [0,1]; sum ≈ 1 ± 0.02; score finite ∈ [0, n-1]; and the score
  must equal the probability-weighted mean of the levels — the Score
  analogue of "chosen = argmax" (the SDK defines ``score`` as the
  expected value of the level distribution, so argmax alone is
  insufficient: a bimodal {0: .5, 2: .5} yields a legitimate score of
  1.0 whose argmax is not ``round(score)``).
- Noul: finite float ∈ [0,1].

Any failure raises ``InvalidDecisionAnswer`` — the answer is dropped,
never returned to the caller, and never becomes an action.
"""

from __future__ import annotations

import math

from app.services.decision.errors import InvalidDecisionAnswer
from app.services.decision.types import (
    Answer,
    ChoiceQuestion,
    NoulQuestion,
    Question,
    ScoreQuestion,
)

# Probability distributions from the backend are allowed ±2% drift from 1.0
# (model rounding), and a score may drift ±0.05 levels from the exact
# probability-weighted mean.
_SUM_TOLERANCE = 0.02
_SCORE_TOLERANCE = 0.05


def validate_answer(answer: Answer, question: Question) -> Answer:
    """Validate ``answer`` against ``question``. Returns it unchanged.

    Raises:
        InvalidDecisionAnswer: on any structural or calibration violation.
    """
    if isinstance(question, ChoiceQuestion):
        if answer.kind != "choice":
            raise InvalidDecisionAnswer(
                f"answer kind {answer.kind!r} does not match choice question"
            )
        return _validate_choice(answer, question)
    if isinstance(question, ScoreQuestion):
        if answer.kind != "score":
            raise InvalidDecisionAnswer(
                f"answer kind {answer.kind!r} does not match score question"
            )
        return _validate_score(answer, question)
    if isinstance(question, NoulQuestion):
        if answer.kind != "noul":
            raise InvalidDecisionAnswer(
                f"answer kind {answer.kind!r} does not match noul question"
            )
        return _validate_noul(answer)
    raise InvalidDecisionAnswer(f"unknown question type {type(question).__name__!r}")


def _validate_probabilities(
    probs: dict[str, float] | None, offered_ids: set[str], kind: str
) -> dict[str, float]:
    if probs is None or not isinstance(probs, dict):
        raise InvalidDecisionAnswer(f"{kind} answer has no probabilities")
    if set(probs.keys()) != offered_ids:
        raise InvalidDecisionAnswer(
            f"{kind} probability keys {sorted(probs)} do not match "
            f"offered ids {sorted(offered_ids)}"
        )
    for key, p in probs.items():
        if (
            not isinstance(p, (int, float))
            or isinstance(p, bool)
            or not math.isfinite(p)
            or not 0 <= p <= 1
        ):
            raise InvalidDecisionAnswer(
                f"{kind} probability for {key!r} is not a finite value in [0,1]: {p!r}"
            )
    total = sum(probs.values())
    if abs(total - 1.0) > _SUM_TOLERANCE:
        raise InvalidDecisionAnswer(
            f"{kind} probabilities sum to {total:.4f}, expected 1±{_SUM_TOLERANCE}"
        )
    return probs


def _validate_choice(answer: Answer, question: ChoiceQuestion) -> Answer:
    offered = set(question.criteria.keys())
    if not isinstance(answer.value, str) or answer.value not in offered:
        raise InvalidDecisionAnswer(
            f"choice {answer.value!r} not in offered ids {sorted(offered)}"
        )
    probs = _validate_probabilities(answer.probabilities, offered, "choice")
    # "chosen = argmax": the reported choice must attain the max
    # probability (ties and float near-ties are fine as long as the
    # choice is among them).
    if probs[answer.value] < max(probs.values()) - 1e-9:
        raise InvalidDecisionAnswer(
            f"choice {answer.value!r} is not the argmax of the probability "
            f"distribution ({probs[answer.value]:.4f} < {max(probs.values()):.4f})"
        )
    _validate_confidence(answer.confidence, "choice")
    return answer


def _validate_score(answer: Answer, question: ScoreQuestion) -> Answer:
    n_levels = len(question.criteria)
    if n_levels == 0:
        raise InvalidDecisionAnswer("score question has no rubric levels")
    offered = {str(i) for i in range(n_levels)}
    probs = _validate_probabilities(answer.probabilities, offered, "score")
    if (
        not isinstance(answer.value, (int, float))
        or isinstance(answer.value, bool)
        or not math.isfinite(float(answer.value))
        or not 0 <= float(answer.value) <= n_levels - 1
    ):
        raise InvalidDecisionAnswer(
            f"score {answer.value!r} is not a finite value in [0,{n_levels - 1}]"
        )
    expected = sum(int(level) * p for level, p in probs.items())
    if abs(float(answer.value) - expected) > _SCORE_TOLERANCE:
        raise InvalidDecisionAnswer(
            f"score {float(answer.value):.4f} does not match the "
            f"probability-weighted level {expected:.4f}"
        )
    _validate_confidence(answer.confidence, "score")
    return answer


def _validate_noul(answer: Answer) -> Answer:
    if (
        not isinstance(answer.value, (int, float))
        or isinstance(answer.value, bool)
        or not math.isfinite(float(answer.value))
        or not 0 <= float(answer.value) <= 1
    ):
        raise InvalidDecisionAnswer(
            f"noul {answer.value!r} is not a finite value in [0,1]"
        )
    _validate_confidence(answer.confidence, "noul")
    return answer


def _validate_confidence(confidence: float, kind: str) -> None:
    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not math.isfinite(float(confidence))
        or not 0 <= float(confidence) <= 1
    ):
        raise InvalidDecisionAnswer(
            f"{kind} confidence {confidence!r} is not a finite value in [0,1]"
        )
