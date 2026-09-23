"""Local folder indexer constants and types."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

HeartbeatCallbackType = Callable[[int], Awaitable[None]]

DEFAULT_EXCLUDE_PATTERNS = [
    ".git",
    "node_modules",
    "__pycache__",
    ".DS_Store",
    ".obsidian",
    ".trash",
]

BATCH_CONCURRENCY = 5
UPLOAD_BATCH_CONCURRENCY = 5
