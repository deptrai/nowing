"""D8 / Story 3.17 AC3: exactly one log + exactly one counter attempt per ordinary failure or truncation."""

from __future__ import annotations

import logging

import pytest

from app.observability import metrics as ot_metrics

pytestmark = pytest.mark.unit


class _FakeCounter:
    def __init__(self):
        self.calls: list[tuple[int, dict]] = []

    def add(self, value, attrs=None):
        self.calls.append((value, dict(attrs or {})))


@pytest.fixture
def fake_counter(monkeypatch: pytest.MonkeyPatch) -> _FakeCounter:
    counter = _FakeCounter()
    monkeypatch.setattr(ot_metrics, "_is_enabled", lambda: True)
    monkeypatch.setattr(ot_metrics, "_memory_injection_failures", lambda: counter)
    return counter


@pytest.fixture
def fake_truncated_counter(monkeypatch: pytest.MonkeyPatch) -> _FakeCounter:
    counter = _FakeCounter()
    monkeypatch.setattr(ot_metrics, "_is_enabled", lambda: True)
    monkeypatch.setattr(ot_metrics, "_memory_injection_truncated", lambda: counter)
    return counter


def test_record_memory_injection_failure_logs_and_counts_once(
    fake_counter: _FakeCounter, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="memory_injection.failure"):
        ot_metrics.record_memory_injection_failure(
            scope="user", stage="search", reason="query_error"
        )

    assert len(fake_counter.calls) == 1
    value, attrs = fake_counter.calls[0]
    assert value == 1
    assert attrs == {"scope": "user", "stage": "search", "reason": "query_error"}

    records = [r for r in caplog.records if r.name == "memory_injection.failure"]
    assert len(records) == 1
    assert records[0].message == "memory_injection.failure"
    assert records[0].scope == "user"
    assert records[0].stage == "search"
    assert records[0].reason == "query_error"


def test_record_memory_injection_truncated_logs_and_counts_once(
    fake_truncated_counter: _FakeCounter, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="memory_injection.truncated"):
        ot_metrics.record_memory_injection_truncated(scope="team")

    assert len(fake_truncated_counter.calls) == 1
    value, attrs = fake_truncated_counter.calls[0]
    assert value == 1
    assert attrs == {"scope": "team"}

    records = [r for r in caplog.records if r.name == "memory_injection.truncated"]
    assert len(records) == 1
    assert records[0].message == "memory_injection.truncated"
    assert records[0].scope == "team"


def test_record_memory_injection_failure_attrs_are_exactly_scope_stage_reason(
    fake_counter: _FakeCounter,
) -> None:
    ot_metrics.record_memory_injection_failure(
        scope="team", stage="render", reason="budget_violation"
    )

    _, attrs = fake_counter.calls[0]
    assert set(attrs) == {"scope", "stage", "reason"}


def test_record_memory_injection_failure_counts_even_if_logging_raises(
    fake_counter: _FakeCounter, monkeypatch: pytest.MonkeyPatch
) -> None:
    logger = logging.getLogger("memory_injection.failure")

    def _boom(*_args, **_kwargs):
        raise RuntimeError("logging backend exploded")

    monkeypatch.setattr(logger, "warning", _boom)

    ot_metrics.record_memory_injection_failure(
        scope="user", stage="embedding", reason="zero_norm"
    )

    assert len(fake_counter.calls) == 1


def test_record_memory_injection_failure_swallows_counter_backend_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _ExplodingCounter:
        def add(self, *_args, **_kwargs):
            raise RuntimeError("otel backend exploded")

    monkeypatch.setattr(ot_metrics, "_is_enabled", lambda: True)
    monkeypatch.setattr(
        ot_metrics, "_memory_injection_failures", lambda: _ExplodingCounter()
    )

    ot_metrics.record_memory_injection_failure(
        scope="team", stage="session", reason="enter_error"
    )


def test_record_memory_injection_failure_is_noop_when_otel_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counter = _FakeCounter()
    monkeypatch.setattr(ot_metrics, "_is_enabled", lambda: False)
    monkeypatch.setattr(ot_metrics, "_memory_injection_failures", lambda: counter)

    ot_metrics.record_memory_injection_failure(
        scope="user", stage="display_name", reason="lookup_error"
    )

    assert counter.calls == []


def test_record_memory_injection_truncated_is_noop_when_otel_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counter = _FakeCounter()
    monkeypatch.setattr(ot_metrics, "_is_enabled", lambda: False)
    monkeypatch.setattr(ot_metrics, "_memory_injection_truncated", lambda: counter)

    ot_metrics.record_memory_injection_truncated(scope="user")

    assert counter.calls == []
