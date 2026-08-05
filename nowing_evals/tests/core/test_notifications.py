"""Tests for notification formatting (M7, L19)."""

from __future__ import annotations

from nowing_evals.core.notifications import _slack_text, _telegram_text


def test_slack_text_uses_clickable_link_with_prefix(monkeypatch):
    monkeypatch.setenv(
        "NOWING_EVALS_ARTIFACT_URL_PREFIX",
        "https://ci.example.com/",
    )
    text = _slack_text(
        suite="chat",
        benchmark="regression",
        run_timestamp="2026-08-04T00:00:00Z",
        failing_thresholds=["mode_speed_p95_e2e_ms"],
        run_artifact_path="runs/2026-08-04T00-00-00Z/regression/run_artifact.json",
        extra={"environment": "production", "build_id": "abc[123]"},
    )
    assert (
        "<https://ci.example.com/runs/2026-08-04T00-00-00Z/regression/run_artifact.json|View run artifact>"
        in text
    )
    assert "`mode_speed_p95_e2e_ms`" in text
    assert "`production`" in text
    assert "`abc[123]`" in text


def test_slack_text_falls_back_to_plain_path_without_prefix(monkeypatch):
    monkeypatch.delenv("NOWING_EVALS_ARTIFACT_URL_PREFIX", raising=False)
    text = _slack_text(
        suite="chat",
        benchmark="regression",
        run_timestamp="2026-08-04T00:00:00Z",
        failing_thresholds=["mode_speed_p95_e2e_ms"],
        run_artifact_path="runs/2026-08-04T00-00-00Z/regression/run_artifact.json",
    )
    assert "View run artifact" not in text
    assert "runs/2026-08-04T00-00-00Z/regression/run_artifact.json" in text


def test_telegram_text_wraps_thresholds_in_code_spans():
    text = _telegram_text(
        suite="chat",
        benchmark="regression",
        run_timestamp="2026-08-04T00:00:00Z",
        failing_thresholds=[
            "mode_speed_p95_e2e_ms",
            "scrape_failure_rate[web_search]",
        ],
        run_artifact_path="runs/2026-08-04T00-00-00Z/regression/run_artifact.json",
        extra={"environment": "production"},
    )
    assert "`mode_speed_p95_e2e_ms`" in text
    assert "`scrape_failure_rate[web_search]`" in text
    assert "`production`" in text


def test_telegram_text_does_not_crash_on_metacharacters(monkeypatch):
    monkeypatch.setenv(
        "NOWING_EVALS_ARTIFACT_URL_PREFIX",
        "https://ci.example.com/",
    )
    text = _telegram_text(
        suite="chat_regression",
        benchmark="regression",
        run_timestamp="2026-08-04T00:00:00Z",
        failing_thresholds=["mode_*_p95[ms]"],
        run_artifact_path="runs/2026-08-04T00-00-00Z/regression/run_artifact.json",
    )
    assert "`chat_regression`" in text
    assert "`mode_*_p95[ms]`" in text
