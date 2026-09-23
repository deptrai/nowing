"""Tests for notification formatting and HTTP dispatch (M7, L19)."""

from __future__ import annotations

import pytest

from nowing_evals.core.notifications import (
    _artifact_url,
    _md_code,
    _slack_text,
    _telegram_text,
    notify_gate_failure,
    notify_slack,
    notify_telegram,
)


def test_artifact_url_normalizes_prefix_without_trailing_slash():
    assert (
        _artifact_url(
            "runs/2026-08-04T00-00-00Z/regression/run_artifact.json",
            prefix="https://ci.example.com/artifacts",
        )
        == "https://ci.example.com/artifacts/runs/2026-08-04T00-00-00Z/regression/run_artifact.json"
    )


def test_artifact_url_keeps_local_path_when_prefix_empty():
    assert _artifact_url("/tmp/run_artifact.json", prefix="") == "/tmp/run_artifact.json"


def test_md_code_replaces_backticks():
    assert _md_code("foo `bar` baz") == "`foo 'bar' baz`"


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
        prefix="https://ci.example.com/",
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
        prefix="",
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
        prefix="https://ci.example.com/",
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
        run_artifact_path="runs/2026-08-04T00-00-00Z/regression/run(1)_artifact.json",
        prefix="https://ci.example.com/",
    )
    assert "`chat_regression`" in text
    assert "`mode_*_p95[ms]`" in text
    # Parentheses in the URL are percent-encoded to avoid breaking Telegram
    # Markdown link syntax.
    assert "[View run artifact](https://ci.example.com/runs/2026-08-04T00-00-00Z/regression/run%281%29_artifact.json)" in text


@pytest.mark.asyncio
async def test_notify_slack_posts_json_and_returns_true(respx_mock):
    import httpx

    respx_mock.post("https://hooks.slack.com/services/T/B/x").mock(return_value=httpx.Response(200))
    ok = await notify_slack(
        slack_webhook_url="https://hooks.slack.com/services/T/B/x",
        suite="chat",
        benchmark="regression",
        run_timestamp="2026-08-04T00:00:00Z",
        failing_thresholds=["mode_speed_p95_e2e_ms"],
        run_artifact_path="runs/2026-08-04T00-00-00Z/regression/run_artifact.json",
    )
    assert ok is True
    assert respx_mock.calls
    request = respx_mock.calls[0].request
    assert request.headers["content-type"] == "application/json"
    body = request.read().decode()
    assert "mode_speed_p95_e2e_ms" in body


@pytest.mark.asyncio
async def test_notify_telegram_posts_json_and_returns_true(respx_mock):
    import httpx

    respx_mock.post("https://api.telegram.org/botTOKEN/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    ok = await notify_telegram(
        bot_token="TOKEN",
        chat_id="CHAT_ID",
        suite="chat",
        benchmark="regression",
        run_timestamp="2026-08-04T00:00:00Z",
        failing_thresholds=["mode_speed_p95_e2e_ms"],
        run_artifact_path="runs/2026-08-04T00-00-00Z/regression/run_artifact.json",
    )
    assert ok is True
    assert respx_mock.calls
    request = respx_mock.calls[0].request
    body = request.read().decode()
    assert "chat" in body
    assert "CHAT_ID" in body


@pytest.mark.asyncio
async def test_notify_gate_failure_sends_to_both_channels(respx_mock, monkeypatch):
    import httpx

    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T/B/x")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "CHAT_ID")

    respx_mock.post("https://hooks.slack.com/services/T/B/x").mock(return_value=httpx.Response(200))
    respx_mock.post("https://api.telegram.org/botTOKEN/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )

    ok = await notify_gate_failure(
        suite="chat",
        benchmark="regression",
        run_timestamp="2026-08-04T00:00:00Z",
        failing_thresholds=["mode_speed_p95_e2e_ms"],
        run_artifact_path="runs/2026-08-04T00-00-00Z/regression/run_artifact.json",
    )
    assert ok is True
    assert len(respx_mock.calls) == 2


@pytest.mark.asyncio
async def test_notify_gate_failure_uses_explicit_args(respx_mock):
    import httpx

    respx_mock.post("https://hooks.slack.com/services/T/B/x").mock(return_value=httpx.Response(200))

    ok = await notify_gate_failure(
        suite="chat",
        benchmark="regression",
        run_timestamp="2026-08-04T00:00:00Z",
        failing_thresholds=["mode_speed_p95_e2e_ms"],
        run_artifact_path="runs/2026-08-04T00-00-00Z/regression/run_artifact.json",
        slack_url="https://hooks.slack.com/services/T/B/x",
    )
    assert ok is True
    assert len(respx_mock.calls) == 1
