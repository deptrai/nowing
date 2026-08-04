"""Unit tests for chat/regression operational parser."""

from __future__ import annotations

from nowing_evals.suites.chat.regression.operational import (
    _classify_error_text,
    _tool_output_is_error,
    summarize_operational,
)


def test_tool_output_is_error_detects_status_and_error() -> None:
    assert _tool_output_is_error(None) is True
    assert _tool_output_is_error({"status": "error"}) is True
    assert _tool_output_is_error({"error": "boom"}) is True
    assert _tool_output_is_error({"result": "Error: something"}) is True
    assert _tool_output_is_error({"result": "ok"}) is False
    assert _tool_output_is_error("error: bad") is True
    assert _tool_output_is_error("ok") is False


def test_classify_error_text_maps_reasons() -> None:
    assert _classify_error_text("Captcha required", None) == "captcha"
    assert _classify_error_text("Rate limited by provider", None) == "rate_limit"
    assert _classify_error_text("Request timed out", "TimeoutError") == "timeout"
    assert _classify_error_text("5xx from upstream", None) == "server_error"
    assert _classify_error_text("Parse error", None) == "parse_error"
    assert _classify_error_text("engine_unavailable", None) == "engine_unavailable"
    assert _classify_error_text("unknown thing", None) == "other"
    assert _classify_error_text(None, None) is None


def test_summarize_operational_counts_tool_attempts_and_drops() -> None:
    raw = [
        {"type": "tool-input-start", "toolCallId": "t1", "toolName": "web_search"},
        {"type": "tool-input-start", "toolCallId": "t2", "toolName": "web_search"},
        {
            "type": "tool-output-available",
            "toolCallId": "t1",
            "output": {"status": "completed", "count": 3},
        },
    ]
    out = summarize_operational(raw, text="text")
    assert out["total_tool_attempts"] == 2
    assert out["total_tool_successes"] == 1
    assert out["total_tool_drops"] == 1
    assert out["tool_stats"]["web_search"]["attempts"] == 2
    assert out["tool_stats"]["web_search"]["drops"] == 1
    assert out["scrape_attempts"] == 2
    assert out["scrape_successes"] == 1
    assert out["scrape_failures"] == 0


def test_summarize_operational_classifies_errors_and_failures() -> None:
    raw = [
        {"type": "error", "errorText": "Rate limited", "errorCode": "RATE_LIMIT"},
        {
            "type": "tool-output-available",
            "toolCallId": "t1",
            "toolName": "web_scrape",
            "output": {"status": "error", "error": "Captcha required"},
        },
        {"type": "tool-input-start", "toolCallId": "t1", "toolName": "web_scrape"},
    ]
    out = summarize_operational(raw, text="text")
    assert out["n_error_frames"] == 2
    assert out["error_reason_counts"]["rate_limit"] == 1
    assert out["error_reason_counts"]["captcha"] == 1
    assert out["total_tool_failures"] == 1
    assert out["total_tool_drops"] == 0


def test_summarize_operational_terminal_info_error() -> None:
    raw = [{"type": "data-terminal-info", "data": {"type": "error", "text": "timeout from engine"}}]
    out = summarize_operational(raw, text="text")
    assert out["n_terminal_info"] == 1
    assert out["n_terminal_errors"] == 1
    assert out["error_reason_counts"]["timeout"] == 1


def test_summarize_operational_extracts_call_details_fallback_hits() -> None:
    call_details = {
        "calls": [
            {"fallback_hit_count": 2},
            {"fallback_hits": 3},
        ]
    }
    out = summarize_operational([], call_details=call_details, text="text")
    assert out["total_model_calls"] == 2
    assert out["fallback_kb_hits"] == 5


def test_summarize_operational_empty() -> None:
    out = summarize_operational(None, text="text")
    assert out["total_tool_attempts"] == 0
    assert out["scrape_success_rate"] is None
