"""Prometheus metrics for crypto orchestra parallelism monitoring."""

try:
    from prometheus_client import Histogram

    PARALLELISM_RATIO_HISTOGRAM = Histogram(
        "crypto_orchestra_parallelism_ratio",
        "Ratio of total elapsed time to max individual agent duration (ideal = 1.0)",
        buckets=[1.0, 1.1, 1.2, 1.3, 1.5, 2.0, 3.0, float("inf")],
    )

    FULL_SUITE_DURATION_HISTOGRAM = Histogram(
        "crypto_orchestra_full_suite_duration_seconds",
        "End-to-end duration of full-suite (4-agent) queries",
        labelnames=["agents_count"],
        buckets=[5, 10, 20, 30, 45, 60, 75, 90, 120, float("inf")],
    )

except (ImportError, ValueError):
    # prometheus_client not installed — provide no-op stubs so tests skip gracefully
    class _NoOpHistogram:
        def observe(self, *args, **kwargs) -> None:
            pass

        def labels(self, *args, **kwargs) -> "_NoOpHistogram":
            return self

    PARALLELISM_RATIO_HISTOGRAM = _NoOpHistogram()  # type: ignore[assignment]
    FULL_SUITE_DURATION_HISTOGRAM = _NoOpHistogram()  # type: ignore[assignment]
