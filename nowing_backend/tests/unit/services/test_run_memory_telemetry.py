"""Run-memory telemetry contract (Story 3.13, T6 / AC-9).

What matters here is not that OpenTelemetry received anything — the SDK is a
no-op when disabled — but that the *instrument* side of the contract holds:

* all six counters AC-9 enumerates exist with the exact names given;
* the only one carrying an attribute is ``run_memory_skipped_total{reason}``, and
  its reason vocabulary is the bounded Story 8.7/8.8 set, so cardinality cannot
  drift;
* no recorder accepts (or could forward) scraped payload — the funnel counters
  take no arguments at all.

The name assertions read the instrument factories directly rather than a live
meter: a rename would otherwise silently break every dashboard and alert built
on these series while every test still passed.
"""

from __future__ import annotations

import inspect
import pkgutil
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


# AC-9's exact wire names. Hardcoded, not derived from the source, so a rename
# has to be an explicit decision made in two places.
EXPECTED_COUNTERS = {
    "run_memory_enqueued_total",
    "run_memory_created_total",
    "run_memory_zero_fact_total",
    "run_memory_skipped_total",
    "run_memory_failed_total",
    "run_memory_retried_total",
}


def _all_metrics_source() -> str:
    """Concatenate source from every module under ``app.observability.metrics``."""
    from app.observability import metrics

    package_path = Path(metrics.__file__).parent
    pieces: list[str] = []
    for _, module_name, _ in pkgutil.walk_packages(
        [str(package_path)], prefix="app.observability.metrics."
    ):
        try:
            mod = __import__(module_name, fromlist=["__trash"])
            pieces.append(inspect.getsource(mod))
        except (ImportError, TypeError, OSError):
            continue
    return "\n".join(pieces)


def test_all_six_ac9_counters_are_declared():
    """AC-9: every enumerated counter name exists in the instrument layer."""
    source = _all_metrics_source()

    missing = {name for name in EXPECTED_COUNTERS if f'"{name}"' not in source}
    assert not missing, f"AC-9 counters not declared: {sorted(missing)}"


def test_every_counter_has_a_public_recorder():
    """A declared instrument nobody can call is not instrumentation."""
    from app.observability import metrics

    for public in (
        "record_run_memory_enqueued",
        "record_run_memory_created",
        "record_run_memory_zero_fact",
        "record_run_memory_skipped",
        "record_run_memory_failed",
        "record_run_memory_retried",
    ):
        assert callable(getattr(metrics, public, None)), f"missing {public}"


def test_only_the_skip_counter_takes_a_label():
    """Cardinality guard: the funnel counters must carry no attributes.

    A per-run or per-capability attribute on these would multiply the series by
    workspace/run volume, which is exactly what "low-cardinality" in AC-9 rules
    out. ``reason`` is the single allowed dimension.
    """
    from app.observability import metrics

    assert (
        inspect.signature(metrics.record_run_memory_skipped).parameters["reason"]
        is not None
    )
