"""ToolResultEnvelope — single result contract at the Medirus→agent boundary (Story 42.2).

Every tool result crossing the tool→agent seam is one schema:
``{status, reason, recovery_hint, items}`` where ``status`` ∈
``success | empty_result | failed | degraded | preview``.

Lives in core (no LangChain import) so both the chat gateway and the
capability proxy executor can use it.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

HINT_MAX_CHARS = 500

# Seed hints for the Medirus error codes observed in production (spec A2).
# Each entry composes a recovery_hint from its non-null fields; unknown codes
# fall back to the generic hint.
RECOVERY_HINT_MAP: dict[str, dict[str, Any]] = {
    "MEDIRUS_4001": {
        "retest_command": "wait for circuit cooldown (~60s), then retry the same call",
    },
    "MEDIRUS_4010": {
        "credential_needed": "Facebook authCookie (c_user/xs)",
        "config_file": "Medirus/.env",
        "retest_command": (
            "re-run with dryRun=true using MEDIRUS_FACEBOOK_ACCOUNT_ID"
        ),
    },
    "MEDIRUS_4030": {
        "credential_needed": "residential proxy",
        "config_file": "Medirus/.env PROXY_*",
    },
    "MEDIRUS_5000": {
        "config_file": "medirus-mcp.log",
        "retest_command": "retry",
    },
}

GENERIC_HINT = "generic: check logs, retry"


class ToolResultEnvelope(BaseModel):
    """Normative result contract (AD-3) for every Medirus tool result."""

    model_config = ConfigDict(extra="ignore")

    status: Literal["success", "empty_result", "failed", "degraded", "preview"]
    reason: str | None = None
    recovery_hint: str | None = None
    items: list[Any] = []


def _sanitize_hint(hint: str) -> str:
    """Strip control chars/newlines, collapse whitespace, cap at 500 chars."""
    cleaned = "".join(
        " " if (ord(ch) < 32 or ord(ch) == 127) else ch for ch in hint
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:HINT_MAX_CHARS]


def _hint_for_code(
    code: Any, suggested_action: Any = None
) -> str:
    """Compose a recovery hint for a Medirus error code.

    Seeded codes get their hint-map entry; unknown codes get the generic
    hint. Legacy ``XACT_`` prefixes are normalized to ``MEDIRUS_`` before
    lookup (precedent: medirus_proxy error mapping). ``suggestedAction``
    forwarded from Medirus is always marked untrusted in the hint text.
    """
    normalized: str | None = None
    if isinstance(code, str) and code:
        normalized = code
        if normalized.startswith("XACT_"):
            normalized = "MEDIRUS_" + normalized[len("XACT_") :]
    entry = RECOVERY_HINT_MAP.get(normalized) if normalized else None
    if entry and "recovery_hint" in entry:
        hint = entry["recovery_hint"]
    elif entry:
        parts = []
        if entry.get("credential_needed"):
            parts.append(f"credential: {entry['credential_needed']}")
        if entry.get("config_file"):
            parts.append(f"config: {entry['config_file']}")
        if entry.get("retest_command"):
            parts.append(f"retest: {entry['retest_command']}")
        hint = "; ".join(parts) if parts else GENERIC_HINT
    else:
        hint = GENERIC_HINT

    if suggested_action:
        hint = f"{hint} (untrusted suggestedAction: {suggested_action})"
    return _sanitize_hint(hint)


def _error_text(error: Any) -> str | None:
    """Extract a human-readable reason from result.error (str or dict)."""
    if isinstance(error, dict):
        return error.get("message") or error.get("error")
    return error


def _error_code(result: dict[str, Any]) -> str | None:
    error = result.get("error")
    code = result.get("code")
    if not code and isinstance(error, dict):
        code = error.get("code")
    return code


def _error_suggested_action(result: dict[str, Any]) -> str | None:
    error = result.get("error")
    action = (
        result.get("suggested_action")
        or result.get("suggestedAction")
        or (error.get("suggestedAction") if isinstance(error, dict) else None)
    )
    return action


def from_medirus(
    result: dict[str, Any], tool_name: str | None = None
) -> ToolResultEnvelope:
    """Normalize a Medirus result dict into a ToolResultEnvelope.

    Idempotent: an input that already carries ``status`` + ``items`` keys is
    passed through as an envelope so gateway/executor chains stay safe.
    Never raises: malformed inputs fall back to a failed envelope.
    """
    if "status" in result and "items" in result:
        try:
            return ToolResultEnvelope.model_validate(result)
        except (ValidationError, ValueError):
            pass  # malformed passthrough — fall through to normal normalize

    data = result.get("data")
    preview = result.get("preview")

    meta = result.get("meta")
    if not isinstance(meta, dict):
        meta = {}
    arguments = result.get("arguments")
    if not isinstance(arguments, dict):
        arguments = {}

    dry_run = (
        bool(result.get("dry_run"))
        or bool(arguments.get("dryRun"))
        or (isinstance(preview, bool) and preview)
    )

    # Failure takes precedence over the dryRun preview flag: a dryRun call
    # that still failed must surface the error + recovery hint, not a preview.
    if result.get("success") is False:
        items = _coerce_items(data, preview)
        reason = (
            _error_text(result.get("error"))
            or result.get("message")
            or "Execution failed"
        )
        return ToolResultEnvelope(
            status="failed",
            reason=str(reason),
            recovery_hint=_hint_for_code(
                _error_code(result), _error_suggested_action(result)
            ),
            items=items,
        )

    items = _coerce_items(data, preview)

    if dry_run:
        return ToolResultEnvelope(status="preview", items=items)

    if meta.get("degraded"):
        degradation_reason = meta.get("degradation_reason")
        return ToolResultEnvelope(
            status="degraded",
            reason=str(degradation_reason) if degradation_reason is not None else None,
            items=items,
        )

    if not items:
        return ToolResultEnvelope(status="empty_result", items=[])

    return ToolResultEnvelope(status="success", items=items)


def _coerce_items(data: Any, preview: Any) -> list[Any]:
    """Pick item payload from ``data``/``preview``, excluding bool preview flags.

    An empty ``data`` list falls through to ``preview`` (Medirus may truncate
    data to [] and carry the preview slice separately).
    """
    if isinstance(data, list) and data:
        items: Any = data
    elif data and not isinstance(data, bool):
        items = [data]
    elif preview is not None and not isinstance(preview, bool):
        items = preview if isinstance(preview, list) else [preview]
    else:
        items = []
    return items


def from_exception(exc: Exception) -> ToolResultEnvelope:
    """Map an exception raised at the Medirus boundary into a failed envelope.

    Coded exceptions (MedirusMcpError, ExternalServiceError) get their hint
    from RECOVERY_HINT_MAP; anything else gets the generic hint.
    """
    code = getattr(exc, "code", None)
    if code:
        hint = _hint_for_code(code, getattr(exc, "suggested_action", None))
    else:
        hint = GENERIC_HINT
    reason = str(getattr(exc, "message", None) or exc)
    return ToolResultEnvelope(
        status="failed", reason=reason, recovery_hint=hint, items=[]
    )


__all__ = [
    "GENERIC_HINT",
    "RECOVERY_HINT_MAP",
    "ToolResultEnvelope",
    "from_exception",
    "from_medirus",
]