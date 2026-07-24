"""``continue_research`` action: resume a saved research thread (recall + citations)."""

from __future__ import annotations

from .factory import build_handler
from .params import ContinueResearchActionParams

__all__ = ["ContinueResearchActionParams", "build_handler"]

# Side-effect: register on the actions store.
from . import definition  # noqa: F401
