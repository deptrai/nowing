"""Unit tests for ToolResultEnvelope (Story 42.2)."""

from __future__ import annotations

import json

import pytest

from app.capabilities.core.tool_result import (
    RECOVERY_HINT_MAP,
    ToolResultEnvelope,
    _sanitize_hint,
    from_exception,
    from_medirus,
)
from app.exceptions import ExternalServiceError
from app.proprietary.platforms.medirus.mcp_client import MedirusMcpError


def test_hint_map_seeded_with_four_codes():
    """RECOVERY_HINT_MAP seeds exactly the 4 known Medirus error codes."""
    assert set(RECOVERY_HINT_MAP) == {
        "MEDIRUS_4001",
        "MEDIRUS_4010",
        "MEDIRUS_4030",
        "MEDIRUS_5000",
    }


def test_from_medirus_success():
    env = from_medirus(
        {"success": True, "data": [{"id": "1", "text": "hi"}], "meta": {}}
    )
    assert env.status == "success"
    assert env.items == [{"id": "1", "text": "hi"}]
    assert env.reason is None
    assert env.recovery_hint is None


def test_from_medirus_empty_result():
    env = from_medirus({"success": True, "data": []})
    assert env.status == "empty_result"
    assert env.items == []


def test_from_medirus_degraded():
    env = from_medirus(
        {
            "success": True,
            "data": [{"id": "1"}],
            "meta": {"degraded": True, "degradation_reason": "fb rate-limited"},
        }
    )
    assert env.status == "degraded"
    assert env.reason == "fb rate-limited"


def test_from_medirus_dry_run_preview():
    env = from_medirus(
        {"success": True, "data": [{"id": "1"}], "dry_run": True}
    )
    assert env.status == "preview"


def test_from_medirus_dry_run_via_arguments():
    env = from_medirus(
        {
            "success": True,
            "data": [],
            "arguments": {"dryRun": True},
        }
    )
    assert env.status == "preview"


def test_from_medirus_preview_fallback_items():
    env = from_medirus({"success": True, "data": [], "preview": [{"id": "p"}]})
    assert env.status == "success"
    assert env.items == [{"id": "p"}]


def test_from_medirus_idempotent_envelope_passthrough():
    env_in = ToolResultEnvelope(
        status="failed", reason="boom", recovery_hint="retry", items=[]
    )
    env = from_medirus(env_in.model_dump())
    assert env.status == "failed"
    assert env.reason == "boom"
    assert env.recovery_hint == "retry"


@pytest.mark.parametrize(
    "code,expected_fragments",
    [
        ("MEDIRUS_4001", ["cooldown", "retry"]),
        ("MEDIRUS_4010", ["c_user", "MEDIRUS_FACEBOOK_ACCOUNT_ID"]),
        ("MEDIRUS_4030", ["proxy"]),
        ("MEDIRUS_5000", ["medirus-mcp.log", "retry"]),
    ],
)
def test_from_medirus_failed_seeded_codes(code, expected_fragments):
    env = from_medirus(
        {"success": False, "error": {"message": "boom", "code": code}}
    )
    assert env.status == "failed"
    assert env.reason == "boom"
    assert env.recovery_hint is not None
    for fragment in expected_fragments:
        assert fragment in env.recovery_hint


def test_from_medirus_failed_unknown_code_generic_hint():
    env = from_medirus(
        {"success": False, "error": {"message": "x", "code": "MEDIRUS_9999"}}
    )
    assert env.status == "failed"
    assert env.recovery_hint == "generic: check logs, retry"


def test_from_medirus_failed_suggested_action_marked_untrusted():
    env = from_medirus(
        {
            "success": False,
            "error": {
                "message": "auth expired",
                "code": "MEDIRUS_4010",
                "suggestedAction": "refresh your cookie jar",
            },
        }
    )
    assert "untrusted suggestedAction" in env.recovery_hint
    assert "refresh your cookie jar" in env.recovery_hint


def test_from_exception_generic():
    env = from_exception(ValueError("boom"))
    assert env.status == "failed"
    assert env.reason == "boom"
    assert env.recovery_hint == "generic: check logs, retry"
    assert env.items == []


def test_from_exception_coded_with_suggested_action():
    exc = MedirusMcpError(
        "auth expired",
        code="MEDIRUS_4010",
        suggested_action="set c_user/xs",
    )
    env = from_exception(exc)
    assert env.status == "failed"
    assert env.reason == "auth expired"
    assert "c_user" in env.recovery_hint
    assert "untrusted suggestedAction: set c_user/xs" in env.recovery_hint


def test_from_exception_external_service_error():
    exc = ExternalServiceError("scraper down", code="MEDIRUS_4001")
    env = from_exception(exc)
    assert env.status == "failed"
    assert env.reason == "scraper down"
    assert "cooldown" in env.recovery_hint


def test_sanitize_hint_strips_newlines_and_caps_500():
    dirty = "line one\nline\ttwo\x00three " + "x" * 600
    cleaned = _sanitize_hint(dirty)
    assert "\n" not in cleaned
    assert "\t" not in cleaned
    assert "\x00" not in cleaned
    assert len(cleaned) <= 500


def test_envelope_model_dump_json_serializable():
    env = from_medirus(
        {"success": True, "data": [{"id": "1"}], "meta": {"cost_micros": 1}}
    )
    payload = json.loads(json.dumps(env.model_dump(), ensure_ascii=False))
    assert payload["status"] == "success"
    assert payload["items"] == [{"id": "1"}]
    assert set(payload) == {"status", "reason", "recovery_hint", "items"}


def test_sanitize_hint_dirty_suggested_action_from_medirus():
    """Dirty suggestedAction (600 chars + newline + nul) is capped and cleaned."""
    dirty = "do x\n" + "\x00" + "y" * 600
    env = from_medirus(
        {
            "success": False,
            "error": {
                "message": "auth expired",
                "code": "MEDIRUS_4010",
                "suggestedAction": dirty,
            },
        }
    )
    assert env.recovery_hint is not None
    assert len(env.recovery_hint) <= 500
    assert "\n" not in env.recovery_hint
    assert "\x00" not in env.recovery_hint


def test_sanitize_hint_dirty_suggested_action_from_exception():
    dirty = "do x\n" + "\x00" + "y" * 600
    exc = MedirusMcpError(
        "auth expired", code="MEDIRUS_4010", suggested_action=dirty
    )
    env = from_exception(exc)
    assert env.recovery_hint is not None
    assert len(env.recovery_hint) <= 500
    assert "\n" not in env.recovery_hint
    assert "\x00" not in env.recovery_hint


def test_dry_run_failure_still_failed_with_hint():
    """A dryRun call whose result is {success:false} surfaces the error."""
    env = from_medirus(
        {
            "success": False,
            "data": [],
            "dry_run": True,
            "error": {"message": "auth expired", "code": "MEDIRUS_4010"},
        }
    )
    assert env.status == "failed"
    assert env.reason == "auth expired"
    assert "c_user" in env.recovery_hint


def test_dry_run_success_still_preview():
    env = from_medirus(
        {"success": True, "data": [{"id": "1"}], "dry_run": True}
    )
    assert env.status == "preview"
    assert env.items == [{"id": "1"}]


def test_preview_bool_flag_does_not_leak_into_items():
    env = from_medirus({"success": True, "data": None, "preview": True})
    assert env.status == "preview"
    assert env.items == []


def test_xact_prefix_normalized_to_medirus():
    env = from_medirus(
        {"success": False, "error": {"message": "circuit open", "code": "XACT_4001"}}
    )
    assert env.status == "failed"
    assert "cooldown" in env.recovery_hint


def test_unhashable_code_does_not_raise():
    env = from_medirus(
        {"success": False, "error": {"message": "x", "code": ["bad"]}}
    )
    assert env.status == "failed"
    assert env.recovery_hint == "generic: check logs, retry"


def test_non_dict_meta_does_not_raise():
    env = from_medirus(
        {"success": True, "data": [{"id": "1"}], "meta": "weird"}
    )
    assert env.status == "success"


def test_malformed_passthrough_falls_back_to_normalize():
    """Malformed passthrough payload falls through to normal normalize (no raise)."""
    env = from_medirus({"status": "bogus", "items": "notalist"})
    assert env.status == "empty_result"


def test_suggested_action_camel_case_top_level():
    env = from_medirus(
        {
            "success": False,
            "error": {"message": "auth expired", "code": "MEDIRUS_4010"},
            "suggestedAction": "refresh cookie",
        }
    )
    assert "untrusted suggestedAction: refresh cookie" in env.recovery_hint
