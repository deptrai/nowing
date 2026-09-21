"""Question registry — named, versioned question sets (AD-J5).

Question text lives here, never inline at call sites, so instructions
stay consistent and version bumps are auditable (model/question-set
changes require re-running the eval gate).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.services.decision.types import Question


@dataclass(frozen=True)
class QuestionSet:
    """A named, versioned bundle of questions for one decision task.

    ``required_state_keys`` lists the state keys a caller must supply for
    the set's questions to be answerable — pass it to
    ``DecisionService.decide(..., required_state_keys=...)`` so a missing
    key fails fast (``invalid_request``) before any paid backend call.
    """

    name: str
    version: str
    questions: dict[str, Question]
    required_state_keys: tuple[str, ...] = ()


class QuestionRegistry:
    """Lookup of question sets by name."""

    def __init__(self) -> None:
        self._sets: dict[str, QuestionSet] = {}

    def register(
        self,
        name: str,
        questions: dict[str, Question],
        *,
        version: str = "1.0.0",
        required_state_keys: Iterable[str] = (),
    ) -> None:
        if name in self._sets:
            raise ValueError(f"Question set {name!r} is already registered")
        self._sets[name] = QuestionSet(
            name=name,
            version=version,
            questions=questions,
            required_state_keys=tuple(required_state_keys),
        )

    def get(self, name: str) -> dict[str, Question]:
        """Return a copy of the questions dict for ``name`` — pass
        straight to ``DecisionService.decide(state, questions=...)``.

        A shallow copy keeps a caller that mutates the dict from
        corrupting the registry singleton; the ``Question`` values are
        frozen dataclasses, so no deeper copy is needed.
        """
        return dict(self.get_set(name).questions)

    def get_set(self, name: str) -> QuestionSet:
        """Return the full ``QuestionSet`` (questions + version)."""
        try:
            return self._sets[name]
        except KeyError:
            raise KeyError(
                f"Unknown question set {name!r}. Available: {sorted(self._sets)}"
            ) from None

    def version(self, name: str) -> str:
        return self.get_set(name).version

    def names(self) -> list[str]:
        return sorted(self._sets)


__all__ = ["QuestionRegistry", "QuestionSet"]
