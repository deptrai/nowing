"""Chat mode registry for the new-chat orchestrator (AD-120).

Each mode is keyed by a ``platform_metadata`` flag. The registry supplies the
feature-gate attributes, the system-prompt nudge, and the tool allow-list. The
``stream_new_chat`` orchestrator resolves the active mode from the thread's
metadata and applies it without hard-coded mode branches.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ChatMode:
    """A chat mode such as web-builder, presentation-studio, or meeting-minutes."""

    mode_id: str
    flag_key: str
    label: str
    system_prompt: str | None = None
    enabled_tools: list[str] | None = None
    workspace_feature_field: str | None = None
    global_config_attr: str | None = None
    artifact_kinds: list[str] = field(default_factory=list)
    error_code: str = "CHAT_MODE_DISABLED"
    error_message: str = "This chat mode is not enabled on this workspace plan"


_WEB_BUILDER_SYSTEM_PROMPT = (
    "You are in Web Builder mode. The user wants to build a lightweight "
    "sales/marketing web app such as a landing page, pricing page, lead-capture "
    "form, waitlist, or report. Ask a concise clarifying question only if the "
    "request is unclear, then call build_web_app with the user's description to "
    "produce the Next.js app."
)

_PRESENTATION_STUDIO_SYSTEM_PROMPT = (
    "You are in Presentation Studio mode. The user wants to generate a slide deck. "
    "Ask a concise clarifying question only if the request is unclear, then call "
    "generate_presentation with the user's description, output "
    "format (pptx or marp), and language."
)

_MEETING_MINUTES_SYSTEM_PROMPT = (
    "You are in Meeting Minutes mode. The user wants a transcript with speaker "
    "diarization, action items, and a summary from a meeting recording. Ask the "
    "user for the audio URL or document ID if they have not provided one, then "
    "call generate_meeting_minutes with audio_url or document_id and an optional "
    "language."
)

CHAT_MODES: dict[str, ChatMode] = {
    "default": ChatMode(
        mode_id="default",
        flag_key="default_mode",
        label="Default",
    ),
    "web_builder": ChatMode(
        mode_id="web_builder",
        flag_key="web_builder_mode",
        label="Web Builder",
        system_prompt=_WEB_BUILDER_SYSTEM_PROMPT,
        enabled_tools=["build_web_app"],
        workspace_feature_field="web_builder_enabled",
        global_config_attr="WEB_BUILDER_ENABLED",
        artifact_kinds=["web_app"],
        error_code="WEB_BUILDER_NOT_ENABLED",
        error_message="Web Builder is not enabled on this workspace plan",
    ),
    "presentation_studio": ChatMode(
        mode_id="presentation_studio",
        flag_key="presentation_studio_mode",
        label="Presentation Studio",
        system_prompt=_PRESENTATION_STUDIO_SYSTEM_PROMPT,
        enabled_tools=["generate_presentation"],
        workspace_feature_field="presentation_studio_enabled",
        global_config_attr="PRESENTATION_STUDIO_ENABLED",
        artifact_kinds=["presentation"],
        error_code="PRESENTATION_STUDIO_NOT_ENABLED",
        error_message="Presentation Studio is not enabled on this workspace plan",
    ),
    "meeting_minutes": ChatMode(
        mode_id="meeting_minutes",
        flag_key="meeting_minutes_mode",
        label="Meeting Minutes",
        system_prompt=_MEETING_MINUTES_SYSTEM_PROMPT,
        global_config_attr="MEETING_MINUTES_ENABLED",
        artifact_kinds=["meeting_minutes"],
        error_code="MEETING_MINUTES_NOT_ENABLED",
        error_message="Meeting Minutes is not enabled on this workspace plan",
    ),
}


def resolve_chat_mode(platform_metadata: dict[str, Any] | None) -> ChatMode:
    """Return the first chat mode whose flag key is exactly ``True``.

    Only a boolean ``True`` enables a mode (AC-1a). If more than one flag is
    ``True`` the result is ambiguous, so we fall back to ``default``.
    """
    metadata = platform_metadata or {}
    active = [
        mode
        for mode in CHAT_MODES.values()
        if mode.mode_id != "default" and metadata.get(mode.flag_key) is True
    ]
    if len(active) > 1:
        return CHAT_MODES["default"]
    if active:
        return active[0]
    return CHAT_MODES["default"]


def is_chat_mode_enabled(
    mode: ChatMode,
    *,
    workspace: Any | None,
    app_config: Any,
) -> bool:
    """Check the global and per-workspace feature gates for a chat mode.

    Fail-closed: a missing required workspace flag or missing workspace disables
    the mode, unless the global gate is also missing (in which case the mode is
    considered ungated and allowed).
    """
    if mode.global_config_attr and not getattr(
        app_config, mode.global_config_attr, False
    ):
        return False

    if mode.workspace_feature_field:
        if workspace is None:
            return False
        if not getattr(workspace, mode.workspace_feature_field, False):
            return False

    return True


def get_chat_mode_system_prompt(
    mode: ChatMode, base_instructions: str | None = None
) -> str | None:
    """Return the mode system prompt, prepended to any existing instructions."""
    if not mode.system_prompt:
        return base_instructions
    if base_instructions:
        return f"{mode.system_prompt}\n\n{base_instructions}"
    return mode.system_prompt
