"""T14: Byte-equivalence regression tests for Vercel UI Stream wire format.

Verifies that _parse_vercel_envelope (stream_new_chat.py) correctly parses all
SSE event shapes, and that _rebuild_vercel_wire (new_chat_routes.py) reconstructs
the canonical wire format from stored JSONB payloads.

Golden rule: for any SSE chunk C that parses to payload P,
  _rebuild_vercel_wire(P["type"], P) must produce a wire-format string that
  round-trips through JSON.parse on the FE to the same structured data.
"""

import json
import pytest

from app.tasks.chat.stream_new_chat import _parse_vercel_envelope
from app.routes.new_chat_routes import _rebuild_vercel_wire


# ---------------------------------------------------------------------------
# _parse_vercel_envelope
# ---------------------------------------------------------------------------

class TestParseVercelEnvelope:

    def test_full_json_envelope_orchestra_spawn(self):
        chunk = 'data: {"type":"orchestra-spawn","data":{"agentId":"agt-1","agentName":"DeFi"}}\n\n'
        result = _parse_vercel_envelope(chunk)
        assert result == {
            "type": "orchestra-spawn",
            "data": {"agentId": "agt-1", "agentName": "DeFi"},
        }

    def test_full_json_envelope_text_type(self):
        chunk = 'data: {"type":"data-message-id","data":{"messageId":42}}\n\n'
        result = _parse_vercel_envelope(chunk)
        assert result is not None
        assert result["type"] == "data-message-id"
        assert result["data"]["messageId"] == 42

    def test_vercel_text_delta_numeric_prefix(self):
        """Vercel protocol: 0:"hello" is a text-delta."""
        chunk = 'data: 0:"hello world"\n\n'
        result = _parse_vercel_envelope(chunk)
        assert result is not None
        assert result["type"] == "text-delta"
        assert result["_vercel"] == '0:"hello world"'

    def test_vercel_text_delta_letter_prefix(self):
        """Vercel protocol: g:"text" is also valid text delta prefix."""
        chunk = 'data: g:"chunk"\n\n'
        result = _parse_vercel_envelope(chunk)
        assert result is not None
        assert result["type"] == "text-delta"
        assert result["_vercel"] == 'g:"chunk"'

    def test_done_sentinel_returns_none(self):
        assert _parse_vercel_envelope("data: [DONE]\n\n") is None

    def test_non_data_line_returns_none(self):
        assert _parse_vercel_envelope("event: message\n\n") is None
        assert _parse_vercel_envelope(": heartbeat\n\n") is None

    def test_empty_chunk_returns_none(self):
        assert _parse_vercel_envelope("") is None

    def test_malformed_json_returns_none(self):
        assert _parse_vercel_envelope("data: {broken json}\n\n") is None

    def test_strips_leading_whitespace_in_data(self):
        chunk = 'data:   {"type":"orchestra-update","data":{}}\n\n'
        result = _parse_vercel_envelope(chunk)
        assert result is not None
        assert result["type"] == "orchestra-update"


# ---------------------------------------------------------------------------
# _rebuild_vercel_wire
# ---------------------------------------------------------------------------

class TestRebuildVercelWire:

    def test_text_delta_vercel_key(self):
        """text-delta with _vercel key → bare data: <vercel_str>\\n\\n"""
        payload = {"type": "text-delta", "_vercel": '0:"hello"'}
        wire = _rebuild_vercel_wire("text-delta", payload)
        assert wire == 'data: 0:"hello"\n\n'

    def test_full_json_envelope(self):
        """Structured envelope → bare data:{json}\\n\\n"""
        payload = {"type": "orchestra-spawn", "data": {"agentId": "a1"}}
        wire = _rebuild_vercel_wire("orchestra-spawn", payload)
        assert wire.startswith("data: ")
        assert wire.endswith("\n\n")
        parsed = json.loads(wire[6:])
        assert parsed["type"] == "orchestra-spawn"
        assert parsed["data"]["agentId"] == "a1"

    def test_legacy_raw_passthrough(self):
        """Legacy _raw payloads (9-UX-1b era) are passed through verbatim."""
        raw = 'data: 0:"legacy chunk"\n\n'
        payload = {"_raw": raw}
        wire = _rebuild_vercel_wire("text-delta", payload)
        assert wire == raw

    def test_non_dict_payload_serialized_as_json(self):
        wire = _rebuild_vercel_wire("unknown", [1, 2, 3])
        assert wire == "data: [1, 2, 3]\n\n"

    def test_no_event_header_in_output(self):
        """Critical: Vercel UI Stream must NOT have event: header lines."""
        payload = {"type": "orchestra-done", "data": {"agentId": "a1"}}
        wire = _rebuild_vercel_wire("orchestra-done", payload)
        assert "event:" not in wire

    # ---------------------------------------------------------------------------
    # Round-trip: parse → rebuild produces equivalent wire output
    # ---------------------------------------------------------------------------

    @pytest.mark.parametrize("original_chunk", [
        'data: {"type":"orchestra-spawn","data":{"agentId":"agt-1","agentName":"News"}}\n\n',
        'data: {"type":"orchestra-update","data":{"agentId":"agt-1","step":"fetching"}}\n\n',
        'data: {"type":"orchestra-complete","data":{"sessionId":"run-abc","agentIds":["agt-1"]}}\n\n',
        'data: {"type":"data-orchestra-narration","data":{"text":"Analyzing TVL..."}}\n\n',
    ])
    def test_round_trip_json_events(self, original_chunk):
        """parse → rebuild → FE json.parse returns same structured data."""
        parsed = _parse_vercel_envelope(original_chunk)
        assert parsed is not None

        wire = _rebuild_vercel_wire(parsed["type"], parsed)
        assert wire.startswith("data: ")
        assert wire.endswith("\n\n")

        # Simulate FE: JSON.parse(wire[6:])
        reconstructed = json.loads(wire[6:])
        assert reconstructed["type"] == parsed["type"]
        if "data" in parsed:
            assert reconstructed.get("data") == parsed["data"]

    def test_round_trip_text_delta(self):
        """text-delta round-trip preserves exact vercel payload string."""
        chunk = 'data: 0:"hello"\n\n'
        parsed = _parse_vercel_envelope(chunk)
        assert parsed is not None
        wire = _rebuild_vercel_wire(parsed["type"], parsed)
        assert wire == chunk
