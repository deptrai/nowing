"""Versioned, workspace-scoped memory-recall evaluation suite."""

from __future__ import annotations

from ....core import registry as _registry
from .runner import MemoryRecallBenchmark

_registry.register(MemoryRecallBenchmark())

__all__ = ["MemoryRecallBenchmark"]
