"""Redaction self-checks."""

from app.services.okf import redact_secrets


def test_redacts_sensitive_dict_keys() -> None:
    payload = {
        "api_key": "super-secret",
        "token": "nw_pat_abc123",
        "client_secret": "xyz",
        "authorization": "Bearer token",
        "safe_field": "keep me",
    }
    redacted = redact_secrets(payload)
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["token"] == "[REDACTED]"
    assert redacted["client_secret"] == "[REDACTED]"
    assert redacted["authorization"] == "[REDACTED]"
    assert redacted["safe_field"] == "keep me"


def test_redacts_token_patterns_in_strings() -> None:
    assert redact_secrets("sk-abc123xyz") == "[REDACTED]"
    assert redact_secrets("pat_abc123") == "[REDACTED]"
    assert redact_secrets("nw_pat_abc123") == "[REDACTED]"
    assert redact_secrets("Bearer eyJtoken") == "[REDACTED]"


def test_redacts_long_hex_secrets() -> None:
    assert redact_secrets("deadbeef0123456789ab") == "[REDACTED]"
    assert redact_secrets("short") == "short"


def test_redacts_nested_structures() -> None:
    payload = {
        "level1": {
            "password": "hunter2",
            "list": ["sk-abc", {"private_key": "-----BEGIN RSA-----"}],
        }
    }
    redacted = redact_secrets(payload)
    assert redacted["level1"]["password"] == "[REDACTED]"
    assert redacted["level1"]["list"][0] == "[REDACTED]"
    assert redacted["level1"]["list"][1]["private_key"] == "[REDACTED]"


def test_does_not_mutate_original() -> None:
    payload = {"api_key": "secret"}
    redacted = redact_secrets(payload)
    assert payload["api_key"] == "secret"
    assert redacted["api_key"] == "[REDACTED]"
