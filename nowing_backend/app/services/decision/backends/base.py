"""Backend protocol for the decision service (AD-J1/AD-J2)."""

from __future__ import annotations

from typing import Any, Protocol

from app.services.decision.types import BackendResult, Question


class DecisionBackend(Protocol):
    """Port: evaluate ``questions`` against ``state``, return raw answers.

    Backends return *unvalidated* answers — ``DecisionService`` runs
    strict structural validation before callers see them. Backend
    failures (transport, auth, timeout, missing config) must raise
    ``DecisionError``; they must never leak SDK-specific exceptions.
    """

    name: str

    async def decide(
        self,
        state: dict[str, Any],
        questions: dict[str, Question],
        *,
        model: str | None = None,
        timeout: float | None = None,
    ) -> BackendResult: ...
