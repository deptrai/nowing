"""Contract tests for story 9.2 — deep-research cost metering."""

from __future__ import annotations

import json

import pytest

from app.capabilities.chainlens.research.executor import _parse_sse
from app.capabilities.chainlens.research.schemas import ResearchOutput

pytestmark = [pytest.mark.unit, pytest.mark.contract]


def _sse_line(payload: object) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def test_parse_sse_usage_event_sets_cost_micros_and_basis():
    raw = _sse_line(
        {
            "type": "usage",
            "costDollars": 0.0123,
            "tokens": {"total": 1280},
        }
    )
    raw += _sse_line({"type": "done"})

    output = _parse_sse(raw)

    assert output.cost_micros == 12300
    assert output.cost_basis == "actual"
    assert output.tokens_total == 1280


def test_parse_sse_done_payload_sets_cost_micros():
    raw = _sse_line(
        {
            "type": "done",
            "chatId": "chat-123",
            "costDollars": 0.0105,
            "resolvedMode": "balanced",
            "estimated": True,
        }
    )

    output = _parse_sse(raw)

    assert output.cost_micros == 10500
    assert output.cost_basis == "estimated"
    assert output.resolved_mode == "balanced"


def test_parse_sse_done_usage_sets_cost_micros():
    """ChainLens 42-1 contract: costDollars lives inside done.usage."""
    raw = _sse_line(
        {
            "type": "done",
            "chatId": "chat-123",
            "resolvedMode": "balanced",
            "requestedMode": "auto",
            "usage": {
                "promptTokens": 4273,
                "completionTokens": 3677,
                "totalTokens": 7950,
                "model": "gemini-3.6-flash",
                "costDollars": 0.0105,
            },
        }
    )

    output = _parse_sse(raw)

    assert output.cost_micros == 10500
    assert output.cost_basis == "actual"
    assert output.resolved_mode == "balanced"
    assert output.tokens_total == 7950


def test_parse_sse_usage_after_done_is_parsed_defensively():
    raw = _sse_line({"type": "done"})
    raw += _sse_line(
        {
            "type": "usage",
            "costDollars": 0.0164,
            "resolvedMode": "deep",
        }
    )

    output = _parse_sse(raw)

    assert output.cost_micros == 16400
    assert output.resolved_mode == "deep"


def test_parse_sse_malformed_cost_dollars_uses_fallback():
    raw = _sse_line({"type": "usage", "costDollars": "free"})
    raw += _sse_line({"type": "done"})

    output = _parse_sse(raw)

    # Malformed cost should not crash; parser should leave cost_micros None.
    assert output.cost_micros is None


def test_parse_sse_negative_cost_dollars_is_ignored():
    raw = _sse_line({"type": "usage", "costDollars": -0.001})
    raw += _sse_line({"type": "done"})

    output = _parse_sse(raw)

    assert output.cost_micros is None


def test_parse_sse_one_micro_rounding():
    raw = _sse_line({"type": "usage", "costDollars": 0.000001})

    output = _parse_sse(raw)

    assert output.cost_micros == 1


def test_parse_sse_zero_cost_is_zero():
    raw = _sse_line({"type": "usage", "costDollars": 0.0})

    output = _parse_sse(raw)

    assert output.cost_micros == 0
    assert output.cost_basis == "actual"


def test_parse_sse_missing_tokens_total_is_none():
    raw = _sse_line({"type": "usage", "costDollars": 0.0123})

    output = _parse_sse(raw)

    assert output.cost_micros == 12300
    assert output.tokens_total is None


def test_parse_sse_missing_resolved_mode_uses_none():
    raw = _sse_line({"type": "usage", "costDollars": 0.0123, "estimated": False})

    output = _parse_sse(raw)

    assert output.cost_micros == 12300
    assert output.resolved_mode is None
    assert output.cost_basis == "actual"


def test_parse_sse_preserves_existing_output_fields():
    raw = _sse_line(
        {"type": "block", "block": {"id": "txt", "type": "text", "data": "Answer"}}
    )
    raw += _sse_line(
        {
            "type": "done",
            "costDollars": 0.0123,
            "chatId": "chat-123",
            "webUrl": "https://example.com",
        }
    )

    output = _parse_sse(raw)

    assert output.answer == "Answer"
    assert output.chat_id == "chat-123"
    assert output.web_url == "https://example.com"
    assert output.cost_micros == 12300


def test_parse_sse_rounds_half_up():
    raw = _sse_line({"type": "usage", "costDollars": 0.9999995})

    output = _parse_sse(raw)

    assert output.cost_micros == 1_000_000


def test_research_output_supports_cost_fields():
    output = ResearchOutput(
        answer="Answer",
        cost_micros=12300,
        cost_basis="actual",
        resolved_mode="quality",
        tokens_total=1280,
    )

    assert output.cost_micros == 12300
    assert output.cost_basis == "actual"
    assert output.resolved_mode == "quality"
    assert output.tokens_total == 1280


def test_parse_sse_terminal_done_overwrites_usage_cost():
    """A terminal ``done`` frame with costDollars overwrites an earlier ``usage`` cost."""
    raw = _sse_line({"type": "usage", "costDollars": 0.0123, "resolvedMode": "deep"})
    raw += _sse_line({"type": "done", "costDollars": 0.9999, "resolvedMode": "quality"})

    output = _parse_sse(raw)

    assert output.cost_micros == 999900
    assert output.resolved_mode == "quality"


def test_parse_sse_resolved_mode_from_resolved_mode_key():
    """resolved_mode uses resolved_mode when present."""
    raw = _sse_line(
        {"type": "usage", "costDollars": 0.0123, "resolved_mode": "balanced"}
    )

    output = _parse_sse(raw)

    assert output.resolved_mode == "balanced"


def test_parse_sse_nan_cost_dollars_is_ignored():
    raw = _sse_line({"type": "usage", "costDollars": float("nan")})
    raw += _sse_line({"type": "done"})

    output = _parse_sse(raw)

    assert output.cost_micros is None


def _load_fixture(name: str) -> object:
    path = f"tests/unit/capabilities/chainlens/research/fixtures/{name}"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize(
    "fixture_name",
    [
        "sse-done-estimated-2026-08-05.json",
        "sse-done-actual-2026-08-05.json",
    ],
)
def test_parse_sse_from_chainlens_golden_fixture(fixture_name):
    """ChainLens golden fixtures define the canonical done frame contract."""
    fixture = _load_fixture(fixture_name)
    raw = _sse_line(fixture["frame"])

    output = _parse_sse(raw)
    expected = fixture["expectedNowingParserOutput"]

    assert output.cost_dollars == expected["costDollars"]
    assert output.cost_micros == expected["costMicros"]
    assert output.cost_basis == expected["costBasis"]
    assert output.resolved_mode == expected["resolvedMode"]
    assert output.tokens_prompt == expected["promptTokens"]
    assert output.tokens_completion == expected["completionTokens"]
    assert output.tokens_total == expected["totalTokens"]
    assert output.model == expected["model"]
