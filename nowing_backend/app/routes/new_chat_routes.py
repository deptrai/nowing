"""Compatibility barrel for new chat routes."""

from __future__ import annotations

from app.routes.new_chat import router
from app.routes.new_chat.chat import (
    load_llm_bundle,
    resolve_initial_auto_pin,
    stream_new_chat,
)
from app.routes.new_chat.messages import append_message
from app.routes.new_chat.shared import (
    _build_turn_status_payload,
    _compute_turn_cancelling_retry_delay,
    _find_pre_turn_checkpoint_id,
    _logger,
    _perf_log,
    _raise_if_thread_busy_for_start,
    _resolve_filesystem_selection,
    _revert_turns_for_regenerate,
    _set_retry_after_headers,
    _try_delete_sandbox,
    check_thread_access,
)
from app.routes.new_chat.threads import (
    create_thread,
    get_thread_full,
    list_threads,
    search_threads,
    update_thread,
    update_thread_visibility,
)
from app.utils.rbac import check_permission

__all__ = [
    "_build_turn_status_payload",
    "_compute_turn_cancelling_retry_delay",
    "_find_pre_turn_checkpoint_id",
    "_logger",
    "_perf_log",
    "_raise_if_thread_busy_for_start",
    "_resolve_filesystem_selection",
    "_revert_turns_for_regenerate",
    "_set_retry_after_headers",
    "_try_delete_sandbox",
    "append_message",
    "check_permission",
    "check_thread_access",
    "create_thread",
    "get_thread_full",
    "list_threads",
    "load_llm_bundle",
    "resolve_initial_auto_pin",
    "router",
    "search_threads",
    "stream_new_chat",
    "update_thread",
    "update_thread_visibility",
]
