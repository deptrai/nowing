"""Built-in trigger types — each in its own subpackage, self-registering at import."""

from __future__ import annotations

from . import event, memory_change, schedule  # noqa: F401
