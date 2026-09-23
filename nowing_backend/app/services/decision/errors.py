"""Error taxonomy for the decision service.

Two failure classes, both meaning "caller falls back to existing
behavior" (advisory/additive, AD-J1):

- ``DecisionError`` — transport/backend/flag failures (5xx, 529,
  timeout, missing API key, disabled). Retrying later may succeed.
- ``InvalidDecisionAnswer`` — the backend answered but the answer is
  malformed or miscalibrated. Retrying the same request is unlikely to
  help; the answer must never reach an action.
"""

from __future__ import annotations

from app.exceptions import NowingError


class DecisionError(NowingError):
    """Backend/transport/flag failure — caller falls back."""

    def __init__(
        self,
        message: str = "A decision request failed.",
        *,
        code: str = "DECISION_ERROR",
        status_code: int = 502,
    ) -> None:
        super().__init__(message, code=code, status_code=status_code)


class InvalidDecisionAnswer(DecisionError):  # noqa: N818 — spec-mandated name
    """Malformed or miscalibrated answer — never becomes an action."""

    def __init__(
        self,
        message: str = "The decision backend returned an invalid answer.",
        *,
        code: str = "INVALID_DECISION_ANSWER",
    ) -> None:
        super().__init__(message, code=code, status_code=502)
