"""Memory-recall benchmark (Story 3.9, AC-1).

Auto-discovery imports this package and the ``register`` call at the bottom puts
``memory/recall`` into the registry, which is what makes it show up in
``suites list`` / ``benchmarks list`` and runnable via ``run memory recall``.

``MemoriesClient`` is re-exported here on purpose: the runner resolves it via
this module's namespace so a test can swap the client without a live server.
"""

from __future__ import annotations

from ....core.clients import MemoriesClient
from ....core.registry import register
from .runner import MemoryRecallBenchmark

__all__ = ["MemoriesClient", "MemoryRecallBenchmark"]

register(MemoryRecallBenchmark())
