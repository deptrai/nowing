"""The single failure type tools raise to speak plainly to the model.

A failed tool call should tell the model what to do next, not leak a stack
trace. Anything the caller could act on — no workspace selected, an unknown id,
a rejected request — is raised as ``ToolError`` with a sentence safe to surface.
"""

from __future__ import annotations


class ToolError(Exception):
    """A user-actionable failure whose message is meant for the model to read."""


class ThreadBusyError(ToolError):
    """The chat thread is busy (``409 THREAD_BUSY`` / ``TURN_CANCELLING``).

    Carries the backend error code so the caller can decide whether a retry is
    sensible (``THREAD_BUSY``) or the turn is being cancelled (``TURN_CANCELLING``).
    """

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(f"{error_code}: {message}")
        self.error_code = error_code
