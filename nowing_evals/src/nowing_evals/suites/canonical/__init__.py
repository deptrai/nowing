"""Canonical dedup benchmark suite."""

from __future__ import annotations

from nowing_evals.core import registry as _registry

from .dedup import CanonicalDedupBenchmark

_registry.register(CanonicalDedupBenchmark())

__all__ = ["CanonicalDedupBenchmark"]
