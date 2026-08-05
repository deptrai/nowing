"""Regression checks for 4.8g/9.3 backend review findings (H8, M15, M16, B1-B8)."""

from __future__ import annotations

import json
import time

import pytest

from app.capabilities.chainlens.research.executor import (
    _parse_engine_ts,
    _parse_sse,
    _SSEParser,
    _to_int,
)
from app.capabilities.chainlens.research.schemas import ResearchInput

pytestmark = pytest.mark.unit


def _sse_line(payload: object) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def test_parse_engine_ts_accepts_epoch_ms():
    assert _parse_engine_ts(1000) == 1000
    assert _parse_engine_ts(1500.0) == 1500
    assert _parse_engine_ts("1970-01-01T00:00:01Z") == 1000


def test_parse_engine_ts_rejects_bool_and_non_finite():
    assert _parse_engine_ts(True) is None
    assert _parse_engine_ts(False) is None
    assert _parse_engine_ts(-1) is None
    assert _parse_engine_ts(float("nan")) is None
    assert _parse_engine_ts(float("inf")) is None


def test_to_int_rejects_bool_and_negative():
    assert _to_int(True) is None
    assert _to_int(False) is None
    assert _to_int(-1) is None
    assert _to_int(42) == 42
    assert _to_int("42") == 42
    assert _to_int(3.0) == 3


def test_extract_cost_rejects_infinity_and_nan():
    raw = _sse_line({"type": "usage", "costDollars": float("inf")})
    raw += _sse_line({"type": "usage", "costDollars": float("nan")})
    raw += _sse_line({"type": "done", "costDollars": 0.123})
    output = _parse_sse(raw)
    assert output.cost_micros == 123000


def test_extract_cost_preserves_zero_tokens_total():
    raw = _sse_line(
        {
            "type": "usage",
            "costDollars": 0.001,
            "tokens": {"total": 0},
            "totalTokens": 100,
        }
    )
    output = _parse_sse(raw)
    assert output.tokens_total == 0


def test_usage_event_is_terminal_without_done():
    raw = _sse_line({"type": "usage", "costDollars": 0.001})
    output = _parse_sse(raw)
    assert output.status == "engine_unavailable"
    assert output.cost_micros == 1000


def test_record_first_token_emits_once():
    from app.capabilities.core.progress import progress_scope

    raw = (
        _sse_line(
            {
                "type": "block",
                "block": {"id": "txt", "type": "text", "data": "First"},
            }
        )
        + _sse_line(
            {
                "type": "progress",
                "requestAcceptedAt": "1970-01-01T00:00:01Z",
                "firstFactualChunkAt": "1970-01-01T00:00:02.8Z",
            }
        )
        + _sse_line({"type": "done"})
    )

    with progress_scope() as reporter:
        parser = _SSEParser(start_time=time.perf_counter())
        for line in raw.splitlines():
            parser.feed_line(line)
        parser.finalize()

    first_token_events = [e for e in reporter.coarse if e["phase"] == "first_token"]
    assert len(first_token_events) == 1


async def test_research_input_tier_defaults_and_passed_to_chainlens(monkeypatch):
    from app.capabilities.chainlens.research import executor as executor_mod

    captured: dict = {}

    class _FakeResponse:
        status_code = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def aiter_lines(self):
            yield _sse_line({"type": "done"})

        async def aclose(self):
            pass

    class _FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        def stream(self, method, url, **kwargs):
            captured["json"] = kwargs.get("json")
            return _FakeResponse()

    fake_config = type(
        "config",
        (),
        {
            "CHAINLENS_API_KEY": "test-key",
            "CHAINLENS_API_URL": "https://chainlens.test",
            "CHAINLENS_REQUEST_TIMEOUT_SECONDS": 30,
        },
    )
    monkeypatch.setattr(executor_mod, "config", fake_config)
    monkeypatch.setattr(executor_mod.httpx, "AsyncClient", _FakeClient)

    payload = ResearchInput(query="test", tier="reason")
    await executor_mod._call_chainlens(payload)
    assert captured["json"]["tier"] == "reason"
    assert ResearchInput(query="test").tier == "research"


def test_research_input_mode_description_includes_auto():
    field = ResearchInput.model_fields["mode"]
    assert "auto" in (field.description or "")
