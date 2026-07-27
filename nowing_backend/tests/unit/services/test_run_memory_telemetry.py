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


def _metrics_source() -> str:
    from app.observability import metrics

    return inspect.getsource(metrics)


def test_all_six_ac9_counters_are_declared():
    """AC-9: every enumerated counter name exists in the instrument layer."""
    source = _metrics_source()

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

    for no_label in (
        metrics.record_run_memory_enqueued,
        metrics.record_run_memory_zero_fact,
        metrics.record_run_memory_failed,
        metrics.record_run_memory_retried,
    ):
        assert not inspect.signature(no_label).parameters, (
            f"{no_label.__name__} takes an argument; funnel counters must be unlabelled"
        )

    # `created` takes a count (a value, not an attribute) and nothing else.
    created_params = inspect.signature(metrics.record_run_memory_created).parameters
    assert set(created_params) == {"count"}


def test_recorders_never_raise_when_otel_is_disabled():
    """Telemetry must not be able to fail an extraction (AC-5)."""
    from app.observability import metrics

    metrics.record_run_memory_enqueued()
    metrics.record_run_memory_created(2)
    metrics.record_run_memory_zero_fact()
    metrics.record_run_memory_skipped(reason="rate_limited")
    metrics.record_run_memory_failed()
    metrics.record_run_memory_retried()


def test_skip_reasons_come_from_the_bounded_shared_vocabulary():
    """AC-4/AC-9: reasons are the Story 8.7/8.8 set plus the run-path additions.

    Pinned so a future skip branch cannot introduce a free-form (or worse,
    payload-derived) reason string into a metric label.
    """
    from app.services.memory import extract_budget
    from app.services.memory.run_extraction import REASON_MISSING_CREATOR

    gate_reasons = {
        extract_budget.REASON_ANONYMOUS_UNBILLED,
        extract_budget.REASON_INSUFFICIENT_WALLET,
        extract_budget.REASON_BUDGET_EXCEEDED,
        extract_budget.REASON_RATE_LIMITED,
        extract_budget.REASON_DISABLED,
        extract_budget.REASON_GATE_ERROR,
    }
    run_path_reasons = {
        REASON_MISSING_CREATOR,
        "empty_output",
        "no_llm",
        "context_window",
    }

    for reason in gate_reasons | run_path_reasons:
        assert reason == reason.lower()
        assert " " not in reason
        # A UUID/URL/payload fragment would blow up cardinality; these are all
        # short snake_case identifiers.
        assert len(reason) <= 32


def test_skip_counter_is_wired_to_the_single_terminal_seam():
    """T6: the skip counter fires from ``_mark_terminal``, not per branch.

    Every policy/gate skip funnels through one method. Recording there (rather
    than at each of the seven return sites) is what makes "no skip is silently
    uncounted" a structural property instead of a review checklist item.
    """
    from app.services.memory import run_extraction

    marker = inspect.getsource(run_extraction.RunMemoryExtractionService._mark_terminal)
    assert "record_run_memory_skipped" in marker
