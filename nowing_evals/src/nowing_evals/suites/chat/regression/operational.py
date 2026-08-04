"""Operational / stability metric extraction from chat SSE frames and call_details.

This is a read-only, best-effort parser. It walks the raw SSE events that
``NewChatClient`` already collects, plus the ``call_details`` payload from the
``data-token-usage`` frame, and emits counts for tool attempts, dropouts,
failure reasons, and fallback/degradation signals.

ponytail: the heuristics are intentionally shallow. The backend does not
normalize error codes in SSE payloads, so classification is keyword-driven.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _tool_output_is_error(output: Any) -> bool:
    """Return True if a tool-output-available payload indicates failure."""
    if output is None:
        return True
    if isinstance(output, dict):
        if output.get("status") == "error" or output.get("error"):
            return True
        result = output.get("result")
        return isinstance(result, str) and result.strip().lower().startswith("error:")
    return isinstance(output, str) and output.strip().lower().startswith("error:")


def _classify_error_text(text: str | None, code: str | None) -> str | None:
    """Map an error string or errorCode to a failure reason bucket."""
    blob = f"{code or ''} {text or ''}".lower()
    if not blob.strip():
        return None

    if "captcha" in blob:
        return "captcha"
    if any(
        term in blob for term in ("rate_limit", "rate-limit", "rate limited", "quota", "throttle")
    ):
        return "rate_limit"
    if any(term in blob for term in ("timeout", "timed out")):
        return "timeout"
    if any(term in blob for term in ("engine_unavailable", "engine unavailable")):
        return "engine_unavailable"
    if any(term in blob for term in ("5xx", "server error", "internal server error")):
        return "server_error"
    if any(term in blob for term in ("parse", "json decode", "invalid json", "unparseable")):
        return "parse_error"
    return "other"


def _count_keys(mapping: dict[str, Any], *keys: str) -> int:
    """Sum integer values under a set of keys, defaulting to 0."""
    return sum(int(mapping.get(k) or 0) for k in keys)


def _extract_call_details_metrics(call_details: Any) -> dict[str, Any]:
    """Extract lightweight metrics from a token-usage ``call_details`` payload."""
    calls: list[dict[str, Any]] = []
    if isinstance(call_details, dict):
        calls = call_details.get("calls") or []
    elif isinstance(call_details, list):
        calls = call_details

    total_model_calls = 0
    fallback_kb_hits = 0
    for call in calls:
        if not isinstance(call, dict):
            continue
        total_model_calls += 1
        # The backend sometimes records a fallback hit count for deep-research.
        fallback_kb_hits += _count_keys(
            call, "fallback_hit_count", "kb_fallback_hit_count", "fallback_hits"
        )

    return {
        "total_model_calls": total_model_calls,
        "fallback_kb_hits": fallback_kb_hits,
    }


def summarize_operational(
    raw_events: list[dict[str, Any]] | None,
    call_details: Any = None,
    text: str = "",
) -> dict[str, Any]:
    """Parse raw SSE events and call_details into an operational summary."""
    events = raw_events or []

    tool_attempts: dict[str, int] = {}
    tool_successes: dict[str, int] = {}
    tool_failures: dict[str, int] = {}
    tool_drops: dict[str, int] = {}

    # Track input/output by toolCallId to detect drops (input but no output).
    seen_tool_ids: set[str] = set()
    completed_tool_ids: set[str] = set()
    tool_name_by_id: dict[str, str] = {}

    error_frames: list[dict[str, str | None]] = []
    error_reason_counts: dict[str, int] = {}
    n_terminal_info = 0
    n_terminal_errors = 0
    degradation_reasons: dict[str, int] = {}
    engine_unavailable_count = 0

    def _record_error(text: str | None, code: str | None) -> None:
        nonlocal engine_unavailable_count
        reason = _classify_error_text(text, code)
        if reason:
            error_reason_counts[reason] = error_reason_counts.get(reason, 0) + 1
        error_frames.append({"text": text, "code": code})
        if reason == "engine_unavailable":
            engine_unavailable_count += 1

    for event in events:
        if not isinstance(event, dict):
            continue
        ev_type = event.get("type")
        if ev_type == "error":
            _record_error(event.get("errorText"), event.get("errorCode"))
            continue

        if ev_type in ("tool-input-start", "tool-input-available"):
            tool_name = event.get("toolName") or "unknown"
            tool_id = str(event.get("toolCallId") or "")
            tool_attempts[tool_name] = tool_attempts.get(tool_name, 0) + 1
            tool_name_by_id[tool_id] = tool_name
            seen_tool_ids.add(tool_id)
            continue

        if ev_type == "tool-output-available":
            tool_id = str(event.get("toolCallId") or "")
            tool_name = tool_name_by_id.get(tool_id)
            if not tool_name:
                # Fallback to a generic name if we never saw the input frame.
                tool_name = "unknown"
                tool_attempts[tool_name] = tool_attempts.get(tool_name, 0) + 1
            output = event.get("output")
            if _tool_output_is_error(output):
                tool_failures[tool_name] = tool_failures.get(tool_name, 0) + 1
                if isinstance(output, dict):
                    _record_error(output.get("error") or output.get("message"), None)
                    if output.get("degradation_reason"):
                        dr = output["degradation_reason"]
                        degradation_reasons[dr] = degradation_reasons.get(dr, 0) + 1
            else:
                tool_successes[tool_name] = tool_successes.get(tool_name, 0) + 1
            completed_tool_ids.add(tool_id)
            continue

        if ev_type == "data-terminal-info":
            data = event.get("data") or {}
            if isinstance(data, dict):
                n_terminal_info += 1
                if data.get("type") == "error":
                    n_terminal_errors += 1
                    _record_error(data.get("text"), None)
                if data.get("degradation_reason"):
                    dr = data["degradation_reason"]
                    degradation_reasons[dr] = degradation_reasons.get(dr, 0) + 1
            continue

        # Generic data frames may carry a degradation signal.
        data = event.get("data")
        if isinstance(data, dict) and data.get("degradation_reason"):
            dr = data["degradation_reason"]
            degradation_reasons[dr] = degradation_reasons.get(dr, 0) + 1

    # Dropout = started but never completed with an output.
    for tool_id in seen_tool_ids - completed_tool_ids:
        tool_name = tool_name_by_id.get(tool_id) or "unknown"
        tool_drops[tool_name] = tool_drops.get(tool_name, 0) + 1

    # Aggregate per-tool stats, ensuring every attempted tool appears.
    all_tools = set(tool_attempts) | set(tool_successes) | set(tool_failures) | set(tool_drops)
    tool_stats: dict[str, dict[str, int]] = {}
    for name in all_tools:
        attempts = tool_attempts.get(name, 0)
        successes = tool_successes.get(name, 0)
        failures = tool_failures.get(name, 0)
        drops = tool_drops.get(name, 0)
        tool_stats[name] = {
            "attempts": attempts,
            "successes": successes,
            "failures": failures,
            "drops": drops,
            "drop_rate": drops / attempts if attempts else 0.0,
            "success_rate": successes / attempts if attempts else 0.0,
        }

    total_attempts = sum(tool_attempts.values())
    total_successes = sum(tool_successes.values())
    total_failures = sum(tool_failures.values())
    total_drops = sum(tool_drops.values())

    scrape_attempts = tool_attempts.get("web_search", 0) + tool_attempts.get("web_scrape", 0)
    scrape_successes = tool_successes.get("web_search", 0) + tool_successes.get("web_scrape", 0)
    scrape_failures = tool_failures.get("web_search", 0) + tool_failures.get("web_scrape", 0)

    call_details_metrics = _extract_call_details_metrics(call_details)

    return {
        "scrape_attempts": scrape_attempts,
        "scrape_successes": scrape_successes,
        "scrape_failures": scrape_failures,
        "scrape_success_rate": (scrape_successes / scrape_attempts if scrape_attempts else None),
        "total_tool_attempts": total_attempts,
        "total_tool_successes": total_successes,
        "total_tool_failures": total_failures,
        "total_tool_drops": total_drops,
        "tool_drop_rate": (total_drops / total_attempts if total_attempts else 0.0),
        "tool_stats": tool_stats,
        "n_error_frames": len(error_frames),
        "error_reason_counts": error_reason_counts,
        "n_terminal_info": n_terminal_info,
        "n_terminal_errors": n_terminal_errors,
        "degradation_reasons": degradation_reasons,
        "engine_unavailable_count": engine_unavailable_count,
        **call_details_metrics,
    }
