"""``write_back_linear`` action: create or update a Linear issue."""

from __future__ import annotations

from .factory import build_handler
from .params import LinearActionParams

__all__ = ["LinearActionParams", "build_handler"]

# Side-effect: register on the actions store.
from . import definition  # noqa: F401
