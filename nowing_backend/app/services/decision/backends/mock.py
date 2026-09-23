"""Mock backend — deterministic answers for unit tests (``DECISION_BACKEND=mock``).

No network, no SDK. Answers are engineered to always pass strict
validation: the distribution sums to 1, the choice is the argmax, and
the score equals the probability-weighted level.
"""

from __future__ import annotations

import time
from typing import Any

from app.services.decision.errors import DecisionError
from app.services.decision.types import (
    Answer,
    BackendResult,
    ChoiceQuestion,
    NoulQuestion,
    Question,
    ScoreQuestion,
)

_TOP_PROBABILITY = 0.9


def _distribution(ids: list[str], top: str) -> dict[str, float]:
    """0.9 on ``top``, 0.1 spread evenly over the rest — always sums to 1."""
    if len(ids) == 1:
        return {top: 1.0}
    rest = 1.0 - _TOP_PROBABILITY
    share = rest / (len(ids) - 1)
    return {i: (_TOP_PROBABILITY if i == top else share) for i in ids}


class MockBackend:
    """Deterministic ``DecisionBackend`` — no external calls."""

    name = "mock"

    async def decide(
        self,
        state: dict[str, Any],
        questions: dict[str, Question],
        *,
        model: str | None = None,
        timeout: float | None = None,
    ) -> BackendResult:
        start = time.perf_counter()
        answers: dict[str, Answer] = {}
        for qid, question in questions.items():
            answers[qid] = self._answer(question)
        return BackendResult(
            answers=answers,
            model="mock",
            latency_ms=(time.perf_counter() - start) * 1000,
            input_tokens=None,
            output_tokens=None,
        )

    @staticmethod
    def _answer(question: Question) -> Answer:
        if isinstance(question, ChoiceQuestion):
            options = list(question.criteria.keys())
            if not options:
                raise DecisionError(
                    "MockBackend cannot answer a choice question with no criteria",
                    code="backend_error",
                )
            chosen = options[0]
            return Answer(
                kind="choice",
                value=chosen,
                confidence=_TOP_PROBABILITY,
                probabilities=_distribution(options, chosen),
            )
        if isinstance(question, ScoreQuestion):
            n_levels = len(question.criteria)
            if n_levels == 0:
                raise DecisionError(
                    "MockBackend cannot answer a score question with no criteria",
                    code="backend_error",
                )
            ids = [str(i) for i in range(n_levels)]
            top = ids[-1]  # deterministic: highest rubric level
            probs = _distribution(ids, top)
            # score = probability-weighted level so strict validation holds.
            score = sum(int(level) * p for level, p in probs.items())
            return Answer(
                kind="score",
                value=score,
                confidence=_TOP_PROBABILITY,
                probabilities=probs,
            )
        if isinstance(question, NoulQuestion):
            return Answer(
                kind="noul",
                value=_TOP_PROBABILITY,
                confidence=_TOP_PROBABILITY,
                probabilities=None,
            )
        raise DecisionError(
            f"MockBackend does not support question type {type(question).__name__!r}",
            code="backend_error",
        )
