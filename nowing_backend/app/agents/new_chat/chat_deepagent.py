"""
Nowing deep agent implementation.

This module provides the factory function for creating Nowing deep agents
with configurable tools via the tools registry and configurable prompts
via NewLLMConfig.

We use ``create_agent`` (from langchain) rather than ``create_deep_agent``
(from deepagents) so that the middleware stack is fully under our control.
This lets us swap in ``NowingFilesystemMiddleware`` — a customisable
subclass of the default ``FilesystemMiddleware`` — while preserving every
other behaviour that ``create_deep_agent`` provides (todo-list, subagents,
summarisation, prompt-caching, etc.).
"""

import asyncio
import contextvars
import json
import logging
import os
import threading
import time
from collections import deque
from collections.abc import Sequence
from typing import Any

from deepagents import SubAgent, SubAgentMiddleware, __version__ as deepagents_version
from deepagents.backends import StateBackend
from deepagents.graph import BASE_AGENT_PROMPT
from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from deepagents.middleware.subagents import GENERAL_PURPOSE_SUBAGENT
from deepagents.middleware.summarization import create_summarization_middleware
from langchain.agents import create_agent
from langchain.agents.middleware import TodoListMiddleware
from langchain.agents.middleware.types import AgentMiddleware
from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.types import Checkpointer
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.context import NowingContextSchema
from app.agents.new_chat.llm_config import AgentConfig
from app.agents.new_chat.middleware import (
    DedupHITLToolCallsMiddleware,
    KnowledgeBaseSearchMiddleware,
    MemoryInjectionMiddleware,
    NowingFilesystemMiddleware,
)
from app.agents.new_chat.system_prompt import (
    build_configurable_system_prompt,
    build_nowing_system_prompt,
)
from app.observability.metrics import (
    AGENT_ERRORS_COUNTER,
    FULL_SUITE_DURATION_HISTOGRAM,
    GRACEFUL_DEGRADATION_COUNTER,
)
from app.agents.new_chat.subagents.crypto.defillama_spec import (
    DEFILLAMA_ALLOWED_TOOLS,
    DEFILLAMA_ANALYST_DESCRIPTION,
    DEFILLAMA_ANALYST_NAME,
    DEFILLAMA_ANALYST_PROMPT,
)
from app.agents.new_chat.subagents.crypto.news_spec import (
    NEWS_ALLOWED_TOOLS,
    NEWS_ANALYST_DESCRIPTION,
    NEWS_ANALYST_NAME,
    NEWS_ANALYST_PROMPT,
)
from app.agents.new_chat.subagents.crypto.sentiment_spec import (
    SENTIMENT_ALLOWED_TOOLS,
    SENTIMENT_ANALYST_DESCRIPTION,
    SENTIMENT_ANALYST_NAME,
    SENTIMENT_ANALYST_PROMPT,
)
from app.agents.new_chat.subagents.crypto.smart_contract_spec import (
    SMART_CONTRACT_ALLOWED_TOOLS,
    SMART_CONTRACT_ANALYST_DESCRIPTION,
    SMART_CONTRACT_ANALYST_NAME,
    SMART_CONTRACT_ANALYST_PROMPT,
)
from app.agents.new_chat.subagents.crypto.tokenomics_spec import (
    TOKENOMICS_ALLOWED_TOOLS,
    TOKENOMICS_ANALYST_DESCRIPTION,
    TOKENOMICS_ANALYST_NAME,
    TOKENOMICS_ANALYST_PROMPT,
)
from app.agents.new_chat.subagents.crypto.yield_optimizer_spec import (
    YIELD_OPTIMIZER_ALLOWED_TOOLS,
    YIELD_OPTIMIZER_DESCRIPTION,
    YIELD_OPTIMIZER_NAME,
    YIELD_OPTIMIZER_PROMPT,
)
from app.agents.new_chat.subagents.crypto.smart_money_spec import (
    SMART_MONEY_ALLOWED_TOOLS,
    SMART_MONEY_ANALYST_DESCRIPTION,
    SMART_MONEY_ANALYST_NAME,
    SMART_MONEY_ANALYST_PROMPT,
)
from app.agents.new_chat.subagents.crypto.whale_tracker_spec import (
    WHALE_TRACKER_ALLOWED_TOOLS,
    WHALE_TRACKER_DESCRIPTION,
    WHALE_TRACKER_NAME,
    WHALE_TRACKER_PROMPT,
)
from app.agents.new_chat.middleware.crypto_data_cache import CryptoDataCacheMiddleware
from app.agents.new_chat.tools.registry import build_tools_async
from app.db import ChatVisibility
from app.services.connector_service import ConnectorService
from app.utils.perf import get_perf_logger

_perf_log = get_perf_logger()

# =============================================================================
# Connector Type Mapping
# =============================================================================

# Maps SearchSourceConnectorType enum values to the searchable document/connector types
# used by pre-search middleware and web_search.
# Live search connectors (TAVILY_API, LINKUP_API, BAIDU_SEARCH_API) are routed to
# the web_search tool; all others are considered local/indexed data.
_CONNECTOR_TYPE_TO_SEARCHABLE: dict[str, str] = {
    # Live search connectors (handled by web_search tool)
    "TAVILY_API": "TAVILY_API",
    "LINKUP_API": "LINKUP_API",
    "BAIDU_SEARCH_API": "BAIDU_SEARCH_API",
    # Local/indexed connectors (handled by KB pre-search middleware)
    "SLACK_CONNECTOR": "SLACK_CONNECTOR",
    "TEAMS_CONNECTOR": "TEAMS_CONNECTOR",
    "NOTION_CONNECTOR": "NOTION_CONNECTOR",
    "GITHUB_CONNECTOR": "GITHUB_CONNECTOR",
    "LINEAR_CONNECTOR": "LINEAR_CONNECTOR",
    "DISCORD_CONNECTOR": "DISCORD_CONNECTOR",
    "JIRA_CONNECTOR": "JIRA_CONNECTOR",
    "CONFLUENCE_CONNECTOR": "CONFLUENCE_CONNECTOR",
    "CLICKUP_CONNECTOR": "CLICKUP_CONNECTOR",
    "GOOGLE_CALENDAR_CONNECTOR": "GOOGLE_CALENDAR_CONNECTOR",
    "GOOGLE_GMAIL_CONNECTOR": "GOOGLE_GMAIL_CONNECTOR",
    "GOOGLE_DRIVE_CONNECTOR": "GOOGLE_DRIVE_FILE",  # Connector type differs from document type
    "AIRTABLE_CONNECTOR": "AIRTABLE_CONNECTOR",
    "LUMA_CONNECTOR": "LUMA_CONNECTOR",
    "ELASTICSEARCH_CONNECTOR": "ELASTICSEARCH_CONNECTOR",
    "WEBCRAWLER_CONNECTOR": "CRAWLED_URL",  # Maps to document type
    "BOOKSTACK_CONNECTOR": "BOOKSTACK_CONNECTOR",
    "CIRCLEBACK_CONNECTOR": "CIRCLEBACK",  # Connector type differs from document type
    "OBSIDIAN_CONNECTOR": "OBSIDIAN_CONNECTOR",
    "DROPBOX_CONNECTOR": "DROPBOX_FILE",  # Connector type differs from document type
    "ONEDRIVE_CONNECTOR": "ONEDRIVE_FILE",  # Connector type differs from document type
    # Composio connectors (unified to native document types).
    # Reverse of NATIVE_TO_LEGACY_DOCTYPE in app.db.
    "COMPOSIO_GOOGLE_DRIVE_CONNECTOR": "GOOGLE_DRIVE_FILE",
    "COMPOSIO_GMAIL_CONNECTOR": "GOOGLE_GMAIL_CONNECTOR",
    "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR": "GOOGLE_CALENDAR_CONNECTOR",
    # Cryptocurrency data
    "DEXSCREENER_CONNECTOR": "DEXSCREENER_CONNECTOR",
}

# Document types that don't come from SearchSourceConnector but should always be searchable
_ALWAYS_AVAILABLE_DOC_TYPES: list[str] = [
    "EXTENSION",  # Browser extension data
    "FILE",  # Uploaded files
    "NOTE",  # User notes
    "YOUTUBE_VIDEO",  # YouTube videos
]


def _map_connectors_to_searchable_types(
    connector_types: list[Any],
) -> list[str]:
    """
    Map SearchSourceConnectorType enums to searchable document/connector types.

    This function:
    1. Converts connector type enums to their searchable counterparts
    2. Includes always-available document types (EXTENSION, FILE, NOTE, YOUTUBE_VIDEO)
    3. Deduplicates while preserving order

    Args:
        connector_types: List of SearchSourceConnectorType enum values

    Returns:
        List of searchable connector/document type strings
    """
    result_set: set[str] = set()
    result_list: list[str] = []

    # Add always-available document types first
    for doc_type in _ALWAYS_AVAILABLE_DOC_TYPES:
        if doc_type not in result_set:
            result_set.add(doc_type)
            result_list.append(doc_type)

    # Map each connector type to its searchable equivalent
    for ct in connector_types:
        # Handle both enum and string types
        ct_str = ct.value if hasattr(ct, "value") else str(ct)
        searchable = _CONNECTOR_TYPE_TO_SEARCHABLE.get(ct_str)
        if searchable and searchable not in result_set:
            result_set.add(searchable)
            result_list.append(searchable)

    return result_list


# =============================================================================
# Parallelism Telemetry Middleware
# =============================================================================

_agent_log = logging.getLogger("app.agents")

# ContextVar to pass model-call start time from abefore_model to aafter_model.
# Each async task/step gets its own copy, so concurrent agent calls don't interfere.
# Default is None (sentinel) so callers can detect "never set" and avoid inflated elapsed.
_prl_step_start: contextvars.ContextVar[float | None] = contextvars.ContextVar(
    "_prl_step_start", default=None
)


class _RateLimitState:
    """Thread-safe tracker for recent LLM 429 rate-limit events.

    Escalation levels (feeds ParallelSpawnDirectiveMiddleware spawn strategy):
      0 = clean             → Tier 1 (parallel 6-at-once)
      1 = under pressure    → Tier 2 (natural sequential, 1 per LangGraph turn)
      2 = sustained pressure → Tier 3 (paced sequential with forced asyncio.sleep
                               between agent emissions + protected synthesis retry)
    """

    def __init__(
        self, cooldown_seconds: float = 60.0, escalation_threshold: int = 3
    ) -> None:
        self._last_ts: float = 0.0
        self._cooldown = cooldown_seconds
        self._lock = threading.Lock()
        self._consecutive_events: int = 0
        self._escalation_threshold = escalation_threshold

    def mark_rate_limited(self) -> None:
        with self._lock:
            now = time.time()
            if (now - self._last_ts) < self._cooldown:
                self._consecutive_events += 1
            else:
                self._consecutive_events = 1
            self._last_ts = now

    def refresh_pressure(self) -> None:
        """Push cooldown timer forward without incrementing the 429 counter.

        Used during Tier 3 paced runs so the multi-minute sequential spawn
        doesn't let the cooldown expire mid-run — which would revert the
        next turn to Tier 1 parallel spawn and re-trigger the cascade.
        """
        with self._lock:
            if self._consecutive_events > 0:
                self._last_ts = time.time()

    def is_under_pressure(self) -> bool:
        with self._lock:
            if (time.time() - self._last_ts) >= self._cooldown:
                self._consecutive_events = 0
                return False
            return self._consecutive_events >= 1

    def escalation_level(self) -> int:
        """0 = clean, 1 = natural sequential, 2 = paced sequential."""
        with self._lock:
            if (time.time() - self._last_ts) >= self._cooldown:
                self._consecutive_events = 0
                return 0
            if self._consecutive_events >= self._escalation_threshold:
                return 2
            return 1 if self._consecutive_events >= 1 else 0

    @property
    def cooldown_seconds(self) -> float:
        return self._cooldown


_rate_limit_state = _RateLimitState(
    cooldown_seconds=float(os.getenv("CRYPTO_ORCHESTRA_RATE_LIMIT_COOLDOWN", "60")),
    escalation_threshold=int(os.getenv("CRYPTO_ORCHESTRA_ESCALATION_THRESHOLD", "3")),
)

_PACED_DELAY_SECONDS = float(os.getenv("CRYPTO_ORCHESTRA_PACED_DELAY_SECONDS", "7"))


def _already_spawned_agents(messages: list[Any]) -> set[str]:
    """Scan message history for prior `task(subagent_type=...)` tool calls.

    Used to resume a comprehensive-query orchestration after sequential
    degradation, so we don't re-spawn agents that already ran.
    """
    spawned: set[str] = set()
    for msg in messages:
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls is None and isinstance(msg, dict):
            tool_calls = msg.get("tool_calls")
        if not tool_calls:
            continue
        for tc in tool_calls:
            if isinstance(tc, dict):
                tc_name = tc.get("name")
                tc_args = tc.get("args") or {}
            else:
                tc_name = getattr(tc, "name", None)
                tc_args = getattr(tc, "args", {}) or {}
            if tc_name != "task":
                continue
            subtype = tc_args.get("subagent_type") if isinstance(tc_args, dict) else None
            if subtype:
                spawned.add(subtype)
    return spawned


_PROVIDER_RPM_LIMIT = int(os.getenv("PROVIDER_RPM_LIMIT", "0"))  # 0 = disabled
_PROVIDER_RATE_WINDOW_SECONDS = float(os.getenv("PROVIDER_RATE_WINDOW_SECONDS", "60"))
_PROVIDER_RATE_MAX_WAIT_SECONDS = float(os.getenv("PROVIDER_RATE_MAX_WAIT_SECONDS", "90"))

# ── Provider failover (Story 9-UX-4 / Option C) ──────────────────────────────
# When primary provider returns 429, immediately retry with failover provider.
# PROVIDER_FAILOVER_API_BASE / PROVIDER_FAILOVER_API_KEY: credentials for the
# backup provider (e.g. v98store). Leave blank to disable failover.
# PROVIDER_FAILOVER_MODEL: override model string for failover (empty = same as primary).
# PROVIDER_FAILOVER_COOLDOWN: seconds before trying primary again after a failover (default 120).
_FAILOVER_API_BASE: str = os.getenv("PROVIDER_FAILOVER_API_BASE", "").strip()
_FAILOVER_API_KEY: str = os.getenv("PROVIDER_FAILOVER_API_KEY", "").strip()
_FAILOVER_MODEL: str = os.getenv("PROVIDER_FAILOVER_MODEL", "").strip()
_FAILOVER_COOLDOWN: float = float(os.getenv("PROVIDER_FAILOVER_COOLDOWN", "120"))

# Cache: primary model string → failover ChatLiteLLM instance (built lazily)
_failover_llm_cache: dict[str, Any] = {}
# Per-model: timestamp until which we prefer the failover over the primary
_failover_active_until: dict[str, float] = {}


class _GlobalRateBucket:
    """Module-level minimum-interval pacer shared across ALL agent instances.

    Instantiated once, referenced by every ProviderRateLimitMiddleware + the
    monkey-patched ChatLiteLLM entrypoints so sub-agents, KB planner, and main
    orchestrator ALL share a single serialization queue.

    Design note (2026-04-25): previously used count-per-window token bucket
    which allowed bursts (8 calls in <10ms could all pass when slots were
    empty). Provider saw burst → 429 cascade. Now uses **strict minimum
    inter-call interval** = `window_seconds / max_rpm`. At 10 RPM →
    6s between any two provider calls. At 1 RPM → 60s. Bursts mathematically
    impossible.

    Serialization is enforced by `asyncio.Lock` held across both the spacing
    wait AND the timestamp update, so parallel callers queue behind each
    other rather than racing past the check.
    """

    def __init__(self, max_rpm: int, window_seconds: float, max_wait_seconds: float) -> None:
        self.max_rpm = max_rpm
        self.window = window_seconds
        self.max_wait = max_wait_seconds
        self.min_interval = (window_seconds / max_rpm) if max_rpm > 0 else 0.0
        self._last_call_ts: float = 0.0
        self._lock: asyncio.Lock | None = None

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def acquire(self) -> None:
        if self.max_rpm <= 0:
            return
        async with self._get_lock():
            now = time.time()
            if self._last_call_ts > 0:
                elapsed = now - self._last_call_ts
                if elapsed < self.min_interval:
                    wait_for = min(self.min_interval - elapsed, self.max_wait)
                    _agent_log.info(
                        "provider_rate_gate: spacing %.1fs before next call "
                        "(min_interval=%.1fs, elapsed=%.1fs)",
                        wait_for, self.min_interval, elapsed,
                    )
                    # AC4/AC13: emit rate-gate-wait event when wait ≥ 3s so FE
                    # can show educational "Pacing calls..." banner to user.
                    # V2-P9: classify reason by wait duration so the FE can
                    # render different copy for the three escalation tiers
                    # (matches AC1 union: 'min_interval' | 'paced' | 'retry').
                    if wait_for >= 3.0:
                        if wait_for >= 30.0:
                            _reason = "retry"  # very long waits indicate provider duress
                        elif wait_for >= 10.0:
                            _reason = "paced"  # sustained pacing during heavy load
                        else:
                            _reason = "min_interval"  # nominal RPM-limit pacing
                        _emit_rate_gate_event(wait_for, reason=_reason)
                    await asyncio.sleep(wait_for)
            # Record AFTER the sleep so the next caller sees the actual
            # dispatch moment, not the arrival moment.
            self._last_call_ts = time.time()


_global_rate_bucket = _GlobalRateBucket(
    max_rpm=_PROVIDER_RPM_LIMIT,
    window_seconds=_PROVIDER_RATE_WINDOW_SECONDS,
    max_wait_seconds=_PROVIDER_RATE_MAX_WAIT_SECONDS,
)


def _install_global_chat_litellm_rate_gate() -> None:
    """Monkey-patch ChatLiteLLM's async entrypoints so EVERY LLM call (agent
    middleware chain, KB planner, sub-agents, ad-hoc `llm.ainvoke`) passes
    through `_global_rate_bucket.acquire()` before hitting the provider.

    When PROVIDER_FAILOVER_API_BASE + PROVIDER_FAILOVER_API_KEY are configured,
    a 429 on the primary triggers an immediate retry on the failover provider
    (same model, different api_base/api_key) instead of backing off and waiting.
    The primary is parked for PROVIDER_FAILOVER_COOLDOWN seconds before being
    tried again.

    Idempotent — guards against double-wrapping on module reload.
    No-op when PROVIDER_RPM_LIMIT == 0 (bucket.acquire returns immediately).
    """
    if getattr(_install_global_chat_litellm_rate_gate, "_installed", False):
        return
    try:
        from langchain_litellm import ChatLiteLLM as _CLL
    except ImportError:
        return

    _orig_agenerate = _CLL._agenerate
    _orig_astream = _CLL._astream

    async def _gated_agenerate(self: Any, *args: Any, **kwargs: Any) -> Any:
        await _global_rate_bucket.acquire()
        primary_model: str = getattr(self, "model", "") or ""

        # If primary is in failover cooldown, go directly to failover
        if _is_failover_active(primary_model):
            failover = _get_or_build_failover(self)
            if failover is not None:
                return await _orig_agenerate(failover, *args, **kwargs)

        try:
            return await _orig_agenerate(self, *args, **kwargs)
        except Exception as exc:
            if not _is_rate_limit_exc(exc):
                raise
            failover = _get_or_build_failover(self)
            if failover is None:
                raise
            _agent_log.warning(
                "provider_failover: primary %s hit 429, switching to failover %s",
                primary_model, _FAILOVER_API_BASE,
            )
            _rate_limit_state.mark_rate_limited()
            _mark_failover_active(primary_model)
            _emit_failover_event(primary_model, _FAILOVER_API_BASE)
            return await _orig_agenerate(failover, *args, **kwargs)

    async def _gated_astream(self: Any, *args: Any, **kwargs: Any) -> Any:
        await _global_rate_bucket.acquire()
        primary_model: str = getattr(self, "model", "") or ""

        # If primary is in failover cooldown, go directly to failover
        if _is_failover_active(primary_model):
            failover = _get_or_build_failover(self)
            if failover is not None:
                async for chunk in _orig_astream(failover, *args, **kwargs):
                    yield chunk
                return

        chunks_yielded = 0
        try:
            async for chunk in _orig_astream(self, *args, **kwargs):
                chunks_yielded += 1
                yield chunk
        except Exception as exc:
            # Only failover if 429 fires before any tokens — mid-stream 429 cannot
            # be recovered cleanly (partial output already yielded).
            if chunks_yielded > 0 or not _is_rate_limit_exc(exc):
                raise
            failover = _get_or_build_failover(self)
            if failover is None:
                raise
            _agent_log.warning(
                "provider_failover: primary %s hit 429 (stream), switching to failover %s",
                primary_model, _FAILOVER_API_BASE,
            )
            _rate_limit_state.mark_rate_limited()
            _mark_failover_active(primary_model)
            _emit_failover_event(primary_model, _FAILOVER_API_BASE)
            async for chunk in _orig_astream(failover, *args, **kwargs):
                yield chunk

    _CLL._agenerate = _gated_agenerate  # type: ignore[method-assign]
    _CLL._astream = _gated_astream  # type: ignore[method-assign]
    _install_global_chat_litellm_rate_gate._installed = True  # type: ignore[attr-defined]
    if _PROVIDER_RPM_LIMIT > 0:
        _agent_log.info(
            "provider_rate_gate: installed ChatLiteLLM gate (%d RPM / %.0fs window "
            "→ min_interval=%.1fs between calls)",
            _PROVIDER_RPM_LIMIT, _PROVIDER_RATE_WINDOW_SECONDS,
            _global_rate_bucket.min_interval,
        )
    if _FAILOVER_API_BASE and _FAILOVER_API_KEY:
        _agent_log.info(
            "provider_failover: configured — failover_base=%s failover_model=%s cooldown=%.0fs",
            _FAILOVER_API_BASE, _FAILOVER_MODEL or "(same as primary)", _FAILOVER_COOLDOWN,
        )


def _disable_litellm_internal_retry_when_gated() -> None:
    """When the global rate gate is active, disable LiteLLM's internal 429 retry.

    Rationale: LiteLLM's default retry (3×, exponential backoff) amplifies 1
    logical call → up to 3 physical calls. That would let us exceed the
    `PROVIDER_RPM_LIMIT` budget by 3× and still hit provider 429. Our gate
    already paces requests intelligently; LiteLLM retry is redundant AND
    counter-productive when the gate is configured. No-op if gate disabled.
    """
    if _PROVIDER_RPM_LIMIT <= 0:
        return
    try:
        import litellm
        litellm.num_retries = 0
        _agent_log.info(
            "provider_rate_gate: disabled litellm.num_retries (gate handles pacing)"
        )
    except ImportError:
        pass


_install_global_chat_litellm_rate_gate()
_disable_litellm_internal_retry_when_gated()

# ContextVar for rate-gate SSE emission (AC13).
# Set by stream_new_chat.py before agent.astream_events() so the rate bucket
# (which lives in a sibling async context outside the LangChain runnable tree)
# can emit orchestra-rate-gate-wait events directly into the SSE stream.
# Type: callable taking (event_type: str, data: dict) -> None.
# Fallback: dispatch_custom_event when var is None (e.g. during tests).
_StreamWriter = "typing.Callable[[str, dict[str, Any]], None]"
_stream_writer_var: contextvars.ContextVar[Any | None] = contextvars.ContextVar(
    "_stream_writer_var", default=None
)

# T13: cancel signal propagated from run_manager into deep retry loops.
# Set by _execute() before calling stream_new_chat_detached so that
# _cancellable_sleep can interrupt long backoff waits on user cancel.
_stream_cancel_event_var: contextvars.ContextVar[asyncio.Event | None] = contextvars.ContextVar(
    "_stream_cancel_event_var", default=None
)


async def _cancellable_sleep(delay: float) -> None:
    """asyncio.sleep that wakes early and raises CancelledError when run is cancelled."""
    cancel_event = _stream_cancel_event_var.get()
    if cancel_event is None:
        await asyncio.sleep(delay)
        return
    try:
        await asyncio.wait_for(cancel_event.wait(), timeout=delay)
        raise asyncio.CancelledError("run cancelled by user")
    except asyncio.TimeoutError:
        pass


def _is_rate_limit_exc(exc: BaseException) -> bool:
    """Return True if *exc* is a 429 / RateLimitError from any LiteLLM provider."""
    try:
        from litellm.exceptions import RateLimitError as _LiteLLMRateLimit
        if isinstance(exc, _LiteLLMRateLimit):
            return True
    except ImportError:
        pass
    err = str(exc).lower()
    return "rate limit" in err or "ratelimiterror" in err or "429" in err


def _get_or_build_failover(primary: Any) -> Any | None:
    """Return a ChatLiteLLM failover instance for *primary*, building it lazily.

    Uses the same model string as the primary unless PROVIDER_FAILOVER_MODEL is set.
    Returns None when failover is not configured (env vars blank).
    """
    if not (_FAILOVER_API_BASE and _FAILOVER_API_KEY):
        return None
    primary_model: str = getattr(primary, "model", "") or ""
    failover_model = _FAILOVER_MODEL or primary_model
    cache_key = failover_model
    if cache_key not in _failover_llm_cache:
        try:
            from langchain_litellm import ChatLiteLLM as _CLL
            _failover_llm_cache[cache_key] = _CLL(
                model=failover_model,
                api_key=_FAILOVER_API_KEY,
                api_base=_FAILOVER_API_BASE,
                streaming=True,
            )
            _agent_log.info(
                "provider_failover: built failover LLM model=%s api_base=%s",
                failover_model, _FAILOVER_API_BASE,
            )
        except Exception as exc:
            _agent_log.warning("provider_failover: failed to build failover LLM: %s", exc)
            return None
    return _failover_llm_cache.get(cache_key)


def _mark_failover_active(model: str) -> None:
    """Record that failover is active for *model* — primary stays parked for cooldown."""
    _failover_active_until[model] = time.time() + _FAILOVER_COOLDOWN


def _is_failover_active(model: str) -> bool:
    """True if we should prefer failover over primary (still in cooldown window)."""
    until = _failover_active_until.get(model, 0.0)
    return time.time() < until


def _emit_failover_event(primary_model: str, failover_base: str) -> None:
    """Emit data-orchestra-provider-failover SSE event so FE can show a banner."""
    payload = {"reason": "rate_limit", "primaryModel": primary_model, "failoverBase": failover_base}
    writer = _stream_writer_var.get()
    if writer is not None:
        try:
            writer("data-orchestra-provider-failover", payload)
            return
        except Exception:
            pass
    try:
        from langchain_core.callbacks import dispatch_custom_event
        dispatch_custom_event("orchestra_provider_failover", payload)
    except (RuntimeError, LookupError):
        pass


def _emit_rate_gate_event(wait_seconds: float, reason: str = "min_interval") -> None:
    """Emit orchestra-rate-gate-wait event via ContextVar writer if set, else dispatch_custom_event.

    AC13 path: ContextVar set by stream_new_chat.py covers cases where the rate
    bucket is invoked outside any LangChain runnable context (Celery, direct
    sub-agent calls, monkey-patched LiteLLM gates). Falls back to
    `dispatch_custom_event` for tests and code paths that haven't set the writer.
    """
    payload = {"waitSeconds": round(wait_seconds, 1), "reason": reason}
    writer = _stream_writer_var.get()
    if writer is not None:
        try:
            writer("orchestra-rate-gate-wait", payload)
            return
        except Exception:
            pass
    try:
        from langchain_core.callbacks import dispatch_custom_event
        dispatch_custom_event("orchestra_rate_gate_wait", payload)
    except (RuntimeError, LookupError):
        # No active runnable context — silently drop (educational banner is best-effort).
        pass


def _extract_result_text(result: Any) -> str:
    """Extract text content from a LangGraph sub-agent result object.

    Handles three shapes:
    1. ``Command(update={"messages": [...]})`` — what deepagents' atask returns.
    2. Plain object with ``.messages`` attribute.
    3. dict with ``content`` key, or object with ``.content``.

    Defensive against future shape drift: only iterates list/tuple ``messages``,
    only joins explicit text blocks, swallows nothing — caller wraps in try/except.
    """
    if result is None:
        return ""
    # Shape 1: Command(update={"messages": [...]}) from deepagents.atask
    update = getattr(result, "update", None)
    if isinstance(update, dict):
        messages = update.get("messages")
        if isinstance(messages, (list, tuple)) and messages:
            text = _extract_text_from_messages(messages)
            if text:
                return text
    # Shape 2: object with .messages attribute (LangGraph response, etc.)
    messages = getattr(result, "messages", None)
    if isinstance(messages, (list, tuple)) and messages:
        text = _extract_text_from_messages(messages)
        if text:
            return text
    # Shape 3: ToolMessage / dict fallback
    if isinstance(result, dict):
        return str(result.get("content", ""))
    content = getattr(result, "content", None)
    if content:
        return str(content)
    return ""


def _extract_text_from_messages(messages: Any) -> str:
    """Walk messages from end → start, returning first non-empty text content.

    Only joins explicit text blocks for list-of-blocks content; skips tool_use,
    thinking, image, and any non-text blocks to avoid stringifying garbage.
    Handles dict-style blocks (`{"type": "text", "text": "..."}`) and
    object-style blocks (BaseModel-derived with `.type` and `.text` attrs).
    """
    for msg in reversed(messages):
        content = getattr(msg, "content", None)
        if not content:
            continue
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(block.get("text", ""))
                else:
                    # Object-style block (e.g. langchain content-block models):
                    # only accept when it has type="text" and a string .text.
                    btype = getattr(block, "type", None)
                    btext = getattr(block, "text", None)
                    if btype == "text" and isinstance(btext, str):
                        parts.append(btext)
            joined = "".join(parts).strip()
            if joined:
                return joined
    return ""


def _emit_orchestra_event(event_type: str, payload: dict[str, Any], custom_event_name: str | None = None) -> None:
    """Emit any orchestra-* event via ContextVar writer or dispatch_custom_event fallback.

    Used by SourceAttributionMiddleware for narration / source / fact / model events.
    """
    writer = _stream_writer_var.get()
    if writer is not None:
        try:
            writer(event_type, payload)
            return
        except Exception as exc:
            # Diagnostic visibility (v2-D2 patch P_DIAG): log writer failures so
            # we don't end up with silently broken UX. Continue to fallback.
            _agent_log.debug("orchestra writer failed for %s: %s", event_type, exc)
    try:
        from langchain_core.callbacks import dispatch_custom_event
        dispatch_custom_event(custom_event_name or event_type.replace("-", "_"), payload)
    except (RuntimeError, LookupError):
        pass

# Map tool name → (source_domain, favicon_url) for source attribution events
# (canonical source: narration_templates.py)
from app.agents.new_chat.subagents.crypto.narration_templates import (
    PRE_CALL as _TOOL_PRE_NARRATION,
    TOOL_SOURCE_MAP as _TOOL_SOURCE_MAP,
    TOOL_TONE as _TOOL_TONE,
    extract_facts as _extract_facts,
    post_call_narration as _post_call_narration,
)


def _extract_model_metadata(request: Any) -> tuple[str, str, str | None]:
    """Best-effort extraction of (model, provider, tier) from a model_call request.

    Returns ("", "", None) when the model object is not introspectable. Used by
    SourceAttributionMiddleware to emit AC9 model_attribution events.
    """
    model: Any = None
    for attr in ("model", "llm", "_model", "_llm"):
        candidate = getattr(request, attr, None)
        if candidate is not None:
            model = candidate
            break

    if model is None:
        return ("", "", None)

    # V2-P11: unwrap LangChain RunnableBinding / RunnableSequence wrappers
    # (`.bind(stop=...)`, `.with_structured_output(...)` etc.) which expose
    # the underlying model via `.bound` rather than `model_name`.
    for _ in range(3):  # cap recursion in case of pathological wrap chain
        if hasattr(model, "model_name") or hasattr(model, "model"):
            break
        bound = getattr(model, "bound", None)
        if bound is None:
            break
        model = bound

    model_name = (
        getattr(model, "model_name", None)
        or getattr(model, "model", None)
        or getattr(model, "name", None)
        or ""
    )
    if isinstance(model_name, str):
        # Strip litellm prefix routing (e.g. "openai/gpt-4o" → "gpt-4o").
        model_name = model_name.split("/", 1)[-1] if "/" in model_name else model_name

    provider = getattr(model, "provider", None) or getattr(model, "_llm_type", None) or ""
    if isinstance(provider, str) and provider.lower().startswith("chat-"):
        provider = provider[5:]
    if not provider and hasattr(model, "openai_api_base"):
        base = getattr(model, "openai_api_base", "") or ""
        if "trollllm" in base.lower():
            provider = "trollllm"
        elif "openai" in base.lower():
            provider = "openai"

    tier = getattr(model, "tier", None) or None
    return (str(model_name or ""), str(provider or ""), tier if isinstance(tier, str) else None)


class SourceAttributionMiddleware(AgentMiddleware):
    """Emits SSE events for narration (pre-call) and source attribution (post-call).

    AGENT IDENTITY CONTRACT (P8):
        Every event payload uses ``self._agent_name`` for both ``agentId`` and
        ``agentName`` fields. The FE orchestra-atom keys agents by ``agentId``,
        so the contract is: whatever string is passed to ``__init__(agent_name=...)``
        MUST equal the ``agentId`` used by the eventual ``orchestra-spawn`` emitter
        (currently TODO — pre-existing gap, not in 9-UX-1 scope).

        Today the constants ``DEFILLAMA_ANALYST_NAME``, ``TOKENOMICS_ANALYST_NAME``,
        etc. (see ``subagents/crypto/*/__init__.py``) are passed BOTH to
        ``_build_gp_middleware(agent_name=...)`` AND to the deepagents sub-agent
        spec's ``"name"`` field. When the orchestra-spawn pipeline is wired up
        (Story 9-FE-1 follow-up), it must use these same constants as ``agentId``.

    Registered in BOTH main deepagent_middleware AND _build_gp_middleware() per AC3.
    Uses dispatch_custom_event (LangChain) so events propagate through astream_events.
    Agent name is injected at construction so stream handler can attribute per-agent.
    """

    def __init__(self, agent_name: str = "orchestrator") -> None:
        self._agent_name = agent_name
        # Emit model_attribution exactly once per agent lifecycle
        self._model_attribution_emitted: bool = False

    async def awrap_model_call(self, request: Any, handler: Any) -> Any:
        # AC9: emit one orchestra-model-attribution event the first time this
        # agent's model is invoked, so the FE can render a "🤖 Sonnet · trollllm"
        # badge next to the agent's lane.
        if not self._model_attribution_emitted:
            self._model_attribution_emitted = True
            model_name, provider, tier = _extract_model_metadata(request)
            if model_name:
                payload: dict[str, Any] = {
                    "agentId": self._agent_name,
                    "agentName": self._agent_name,
                    "model": model_name,
                    "provider": provider or "unknown",
                }
                if tier:
                    payload["tier"] = tier
                _emit_orchestra_event(
                    "orchestra-model-attribution",
                    payload,
                    custom_event_name="orchestra_model_attribution",
                )

        # AC10: per-LLM-call telemetry tick — emitted AFTER successful handler
        # so retries (ModelRetryMiddleware re-entering this hook) don't over-count.
        # If handler raises, no tick emitted; resilience layer above retries.
        _result = await handler(request)
        _emit_orchestra_event(
            "orchestra-llm-call",
            {"agentId": self._agent_name, "agentName": self._agent_name},
            custom_event_name="orchestra_llm_call",
        )
        return _result

    async def awrap_tool_call(self, request: Any, handler: Any) -> Any:
        tool_name: str = getattr(request, "name", "") or ""

        # AC2: mandatory pre-call narration BEFORE handler(request) executes
        pre_text = _TOOL_PRE_NARRATION.get(tool_name)
        if pre_text:
            tone = _TOOL_TONE.get(tool_name, "fetching")
            _emit_orchestra_event(
                "orchestra-narration",
                {
                    "agentId": self._agent_name,
                    "agentName": self._agent_name,
                    "text": pre_text,
                    "tone": tone,
                },
                custom_event_name="orchestra_narration",
            )

        try:
            result = await handler(request)
        except Exception:
            # AC2 symmetric narration on tool failure — let the user know the
            # call failed instead of leaving them with the dangling pre-narration.
            _emit_orchestra_event(
                "orchestra-narration",
                {
                    "agentId": self._agent_name,
                    "agentName": self._agent_name,
                    "text": f"Tool {tool_name} thất bại — đang chuyển sang fallback...",
                    "tone": "analyzing",
                },
                custom_event_name="orchestra_narration",
            )
            raise

        # P19: skip source attribution when the tool returned an error payload.
        if isinstance(result, dict) and (result.get("error") or result.get("_error")):
            return result

        # AC3: post-call source attribution
        source_entry = _TOOL_SOURCE_MAP.get(tool_name)
        domain: str | None = None
        favicon: str = ""
        url: str = ""
        if source_entry:
            domain, favicon, url = source_entry
        elif isinstance(result, dict):
            domain = result.get("source_domain")
            if domain:
                favicon = f"https://icons.duckduckgo.com/ip3/{domain}.ico"
                url = f"https://{domain}/"

        if domain:
            _emit_orchestra_event(
                "orchestra-source-fetched",
                {
                    "agentId": self._agent_name,
                    "agentName": self._agent_name,
                    "source": {
                        "domain": domain,
                        "favicon": favicon,
                        "url": url,
                        "dataType": tool_name,
                    },
                },
                custom_event_name="orchestra_source_fetched",
            )

        # AC2 second-half: post-call narration summarising findings.
        # V2-P8: post-call tone defaults to "synthesizing" only for tools whose
        # purpose IS synthesis (chainlens_deep_research, etc.). For other tools
        # post-call narration reports findings → "analyzing" matches the
        # spec's intent better than blanket "synthesizing".
        post_text = _post_call_narration(tool_name, result)
        if post_text:
            pre_tone = _TOOL_TONE.get(tool_name, "fetching")
            post_tone = "synthesizing" if pre_tone == "synthesizing" else "analyzing"
            _emit_orchestra_event(
                "orchestra-narration",
                {
                    "agentId": self._agent_name,
                    "agentName": self._agent_name,
                    "text": post_text,
                    "tone": post_tone,
                },
                custom_event_name="orchestra_narration",
            )

        # AC4: emit one orchestra-fact-captured event per extracted numeric fact.
        for fact in _extract_facts(tool_name, result):
            payload: dict[str, Any] = {
                "agentId": self._agent_name,
                "agentName": self._agent_name,
                "factSummary": fact["factSummary"],
            }
            if "value" in fact:
                payload["value"] = fact["value"]
            if "unit" in fact:
                payload["unit"] = fact["unit"]
            _emit_orchestra_event(
                "orchestra-fact-captured",
                payload,
                custom_event_name="orchestra_fact_captured",
            )

        # Story 10.1.1: emit smart-money-flow event for FE visualization.
        # Only emit when payload has the visualization shape — error dicts
        # ({"error": ...}) must NOT be forwarded as flow data.
        if (
            tool_name == "get_smart_money_flow"
            and isinstance(result, dict)
            and "nodes" in result
            and "links" in result
        ):
            _emit_orchestra_event(
                "smart-money-flow",
                {
                    "agentId": self._agent_name,
                    "nodes": result.get("nodes", []),
                    "links": result.get("links", []),
                    "net_flow_amount": result.get("net_flow_amount", 0.0),
                    "currency": result.get("currency", "USD"),
                    "source_domain": result.get("source_domain"),
                    "cohort_summary": result.get("cohort_summary"),
                },
                custom_event_name="smart_money_flow",
            )

        return result


class ProviderRateLimitMiddleware(AgentMiddleware):
    """Global token-bucket rate limiter for LLM calls.

    Enforces ≤ PROVIDER_RPM_LIMIT calls per rolling PROVIDER_RATE_WINDOW_SECONDS
    across EVERY LLM invocation in the agent stack (main orchestrator, sub-agents,
    KB planner, synthesis). When the bucket is full, `awrap_model_call` sleeps
    until the oldest slot ages out — guaranteeing we never trigger provider 429.

    Every instance (main + sub-agent) shares the module-level `_global_rate_bucket`
    singleton so sub-agents spawned via SubAgentMiddleware can't bypass the cap.

    Zero-cost when `PROVIDER_RPM_LIMIT == 0` (disabled).
    """

    async def awrap_model_call(self, request: Any, handler: Any) -> Any:
        await _global_rate_bucket.acquire()
        return await handler(request)


_SUBAGENT_RETRY_MAX_WALL_SECONDS = float(
    os.getenv("SUBAGENT_RETRY_MAX_WALL_SECONDS", "900")  # 15 minutes absolute cap
)
_SUBAGENT_RETRY_BASE_BACKOFF = float(
    os.getenv("SUBAGENT_RETRY_BASE_BACKOFF", "5")
)
_SUBAGENT_RETRY_MAX_BACKOFF = float(
    os.getenv("SUBAGENT_RETRY_MAX_BACKOFF", "120")
)
_SUBAGENT_RETRY_MAX_ATTEMPTS = int(
    os.getenv("SUBAGENT_RETRY_MAX_ATTEMPTS", "5")
)


class SubAgentResilienceMiddleware(AgentMiddleware):
    """Intercept `task()` tool calls to retry on rate-limit with attempt cap.

    When a sub-agent raises `RateLimitError`, deepagents' `atask()` propagates
    it raw which would kill the LangGraph stream. This middleware retries the
    sub-agent with exponential backoff up to `SUBAGENT_RETRY_MAX_ATTEMPTS`
    (default 5). After exhaustion, a graceful ToolMessage error is returned so
    the coordinator can still synthesize with remaining agents.

    Retry schedule (configurable via env):
      - Base: 5s, doubling each attempt → 5, 10, 20, 40, 80 (then graceful error)
      - Per-attempt sleep capped at `SUBAGENT_RETRY_MAX_BACKOFF` (default 120s)
      - Attempt cap: `SUBAGENT_RETRY_MAX_ATTEMPTS` (default 5; total sleep ~155s)

    Non-rate-limit exceptions bubble up immediately (no retry — likely real bugs).
    Combined with the min-interval `_GlobalRateBucket` gate, rate-limit errors
    should be extremely rare — this middleware is a safety net for edge cases
    (clock skew, provider drift, shared-key contention from other processes).
    """

    async def awrap_tool_call(self, request: Any, handler: Any) -> Any:
        from langchain_core.messages import ToolMessage
        from langgraph.types import Command
        from litellm.exceptions import RateLimitError as _LiteLLMRateLimit

        tool_call = request.tool_call if hasattr(request, "tool_call") else {}
        tool_name = (
            tool_call.get("name") if isinstance(tool_call, dict)
            else getattr(tool_call, "name", None)
        )
        if tool_name != "task":
            return await handler(request)

        args = (
            tool_call.get("args") if isinstance(tool_call, dict)
            else getattr(tool_call, "args", {})
        ) or {}
        subagent_type = args.get("subagent_type", "unknown")
        tool_call_id = (
            tool_call.get("id") if isinstance(tool_call, dict)
            else getattr(tool_call, "id", None)
        )

        # V2-D1: emit orchestra-spawn so the FE creates an agent slot before
        # any narration/source/fact event for this sub-agent arrives.
        # agentId == subagent_type matches the SourceAttributionMiddleware
        # `agent_name` constant convention (P8 contract).
        _emit_orchestra_event(
            "orchestra-spawn",
            {
                "agentId": subagent_type,
                "agentName": subagent_type,
                "agentType": subagent_type,
            },
            custom_event_name="orchestra_spawn",
        )

        started_at = time.time()
        attempt = 0
        last_exc: Exception | None = None

        while True:
            try:
                _result = await handler(request)
                # Emit agent result text BEFORE orchestra-done so the FE applies
                # it while the session is still active (avoids race where
                # orchestra-complete arrives before data-agent-result and the
                # event is silently buffered).
                try:
                    _result_text = _extract_result_text(_result)
                except Exception:
                    _agent_log.exception(
                        "agent_result_extract_failed: %s", subagent_type
                    )
                    _result_text = ""
                _result_length = len(_result_text)
                _truncated = _result_length > 3000
                # Note: pass event_type="agent-result" (NOT "data-agent-result") because
                # _orchestra_writer routes non-bare-type events through format_data,
                # which automatically prepends "data-" to produce the wire type
                # "data-agent-result". Passing "data-agent-result" here would emit
                # "data-data-agent-result" which the FE would silently drop.
                _emit_orchestra_event(
                    "agent-result",
                    {
                        "agentId": subagent_type,
                        "resultText": _result_text[:3000] if _truncated else _result_text,
                        "resultLength": _result_length,
                        "truncated": _truncated,
                    },
                    custom_event_name="data_agent_result",
                )
                # Emit orchestra-done on the first successful attempt — even retries
                # converge to a single "done" event per task() invocation.
                _emit_orchestra_event(
                    "orchestra-done",
                    {"agentId": subagent_type, "citationIds": []},
                    custom_event_name="orchestra_done",
                )
                return _result
            except Exception as exc:
                err = str(exc).lower()
                is_rl = (
                    isinstance(exc, _LiteLLMRateLimit)
                    or "rate limit" in err
                    or "ratelimiterror" in err
                    or "429" in err
                )
                if not is_rl:
                    raise
                last_exc = exc
                attempt += 1
                elapsed = time.time() - started_at

                # Attempt cap — return graceful error after max retries so the
                # coordinator can still synthesize with the remaining agents.
                if attempt > _SUBAGENT_RETRY_MAX_ATTEMPTS:
                    # Validate tool_call envelope BEFORE emitting any "graceful"
                    # signals. If tool_call_id is missing, the only correct action
                    # is to re-raise — emitting orchestra-fail + incrementing the
                    # graceful-degradation counter would be misleading because the
                    # actual outcome is a hard crash, not graceful degradation.
                    if not tool_call_id:
                        raise
                    reason = f"rate limit retries exhausted ({attempt} attempts, {elapsed:.0f}s)"
                    _agent_log.warning(
                        "subagent_max_attempts: %s exhausted %d attempts (%.0fs), "
                        "returning graceful error for coordinator",
                        subagent_type, attempt, elapsed,
                    )
                    # Emit orchestra-fail (not orchestra-done) — graceful degradation
                    # is a real failure so the FE outcome detection (success/partial/failed)
                    # reflects reality and the agent lane shows a fail badge, not a check.
                    _emit_orchestra_event(
                        "orchestra-fail",
                        {
                            "agentId": subagent_type,
                            "errorCode": "rate_limit_exhausted",
                            "errorMessage": reason,
                        },
                        custom_event_name="orchestra_fail",
                    )
                    try:
                        GRACEFUL_DEGRADATION_COUNTER.labels(outcome="subagent_exhausted").inc()
                    except Exception:
                        pass
                    graceful_msg = (
                        f"⚠️ {subagent_type} không thể hoàn thành: {reason}.\n"
                        f"Dữ liệu từ agent này không có trong báo cáo này — "
                        f"coordinator sẽ bổ sung từ kiến thức chung."
                    )
                    # Also expose the graceful error text to the FE Result tab so the
                    # user can see WHY the agent failed (not just the fail badge).
                    _emit_orchestra_event(
                        "agent-result",
                        {
                            "agentId": subagent_type,
                            "resultText": graceful_msg,
                            "resultLength": len(graceful_msg),
                            "truncated": False,
                        },
                        custom_event_name="data_agent_result",
                    )
                    # Return the same shape as deepagents' atask() — Command(update=...)
                    # — so LangGraph merges the ToolMessage into graph state and the
                    # coordinator's next LLM call sees the graceful error text.
                    return Command(
                        update={
                            "messages": [
                                ToolMessage(
                                    content=graceful_msg,
                                    tool_call_id=tool_call_id,
                                    name=subagent_type,
                                )
                            ]
                        }
                    )

                delay = min(
                    _SUBAGENT_RETRY_BASE_BACKOFF * (2 ** (attempt - 1)),
                    _SUBAGENT_RETRY_MAX_BACKOFF,
                )
                _agent_log.warning(
                    "subagent_retry: %s attempt %d/%d (elapsed %.0fs) hit rate_limit, "
                    "sleeping %.0fs",
                    subagent_type, attempt, _SUBAGENT_RETRY_MAX_ATTEMPTS, elapsed, delay,
                )
                try:
                    GRACEFUL_DEGRADATION_COUNTER.labels(outcome="subagent_retry").inc()
                except Exception:
                    pass
                _rate_limit_state.mark_rate_limited()
                await _cancellable_sleep(delay)


class ParallelSpawnDirectiveMiddleware(AgentMiddleware):
    """Injects a parallel-spawn mandate into both system message and last human message.

    Placed immediately after SubAgentMiddleware. Modifies both:
    1. System message — persistent instruction
    2. Last HumanMessage — inline mandate for comprehensive-analysis queries
    """

    # Feature flag: CRYPTO_ORCHESTRA_ENABLE_WHALE_TRACKER=true adds the 7th sub-agent
    # (Story 9-UX-4 AC5). Evaluated once at class definition time (module load).
    _WHALE_TRACKER_ENABLED: bool = (
        os.getenv("CRYPTO_ORCHESTRA_ENABLE_WHALE_TRACKER", "false").strip().lower()
        in ("1", "true", "yes")
    )

    _AGENT_COUNT: int = 7 if _WHALE_TRACKER_ENABLED else 6

    _DIRECTIVE: str = (
        "## Task Tool: Mandatory Parallel Execution\n\n"
        f"IMMEDIATELY call task() for ALL {7 if _WHALE_TRACKER_ENABLED else 6} sub-agents in a SINGLE response — do NOT write any text first:\n"
        "1. defillama_analyst — on-chain TVL / DeFi metrics\n"
        "2. sentiment_analyst — market sentiment and fear/greed data\n"
        "3. news_analyst — latest news and market developments\n"
        "4. smart_contract_analyst — contract security analysis\n"
        "5. tokenomics_analyst — token supply, vesting, distribution, inflation/deflation\n"
        "6. yield_optimizer — DeFi yield recommendations by risk tier with security gate"
        + (
            "\n7. whale_tracker — smart-money wallet flows and whale accumulation signals"
            if _WHALE_TRACKER_ENABLED
            else ""
        )
        + "\n\nCRITICAL RULES:\n"
        "- Your ENTIRE response MUST consist of tool calls only — zero text before the first tool call.\n"
        f"- ALL {7 if _WHALE_TRACKER_ENABLED else 6} task() calls MUST appear in the SAME response to enable parallel execution.\n"
        "- Do NOT describe your plan. Do NOT acknowledge the request. Call task() immediately."
    )

    _INLINE_MANDATE: str = (
        "\n\n[SYSTEM OVERRIDE — PARALLEL EXECUTION REQUIRED]\n"
        f"You MUST respond with EXACTLY {7 if _WHALE_TRACKER_ENABLED else 6} simultaneous task() tool calls and NOTHING ELSE:\n"
        "  task(subagent_type='defillama_analyst', description='...')\n"
        "  task(subagent_type='sentiment_analyst', description='...')\n"
        "  task(subagent_type='news_analyst', description='...')\n"
        "  task(subagent_type='smart_contract_analyst', description='...')\n"
        "  task(subagent_type='tokenomics_analyst', description='...')\n"
        "  task(subagent_type='yield_optimizer', description='...')"
        + (
            "\n  task(subagent_type='whale_tracker', description='...')"
            if _WHALE_TRACKER_ENABLED
            else ""
        )
        + f"\nALL {7 if _WHALE_TRACKER_ENABLED else 6} calls in ONE response. Zero text. Zero preamble. Start with the first task() call NOW."
    )

    _KEYWORDS = (
        "phân tích toàn diện", "full analysis", "comprehensive", "đánh giá toàn diện",
        "investment analysis", "phân tích tổng thể", "full crypto analysis", "full review",
        "đánh giá chi tiết", "đánh giá investment", "phân tích chi tiết", "đánh giá đầy đủ",
        "investment-grade analysis", "comprehensive review",
    )

    # Priority-ordered list (name, description-template) for synthetic bypass.
    # Under rate-limit pressure, agents are spawned one-at-a-time in this order.
    # Easy-Wins Tier (tokenomics + defillama + yield) first — deterministic APIs,
    # less likely to hit external provider limits; Chainlens-heavy agents last.
    # whale_tracker appended last (Nansen-heavy) when feature flag is on (AC5).
    _COMPREHENSIVE_AGENTS: list[tuple[str, str]] = [
        ("tokenomics_analyst",
         "Analyze token supply, vesting, distribution, and inflation mechanics for: {q}"),
        ("defillama_analyst",
         "Analyze on-chain TVL and DeFi metrics for: {q}"),
        ("yield_optimizer",
         "Find best yield opportunities with risk tiers for: {q}"),
        ("smart_contract_analyst",
         "Analyze smart contract security for: {q}"),
        ("news_analyst",
         "Find latest news and market developments for: {q}"),
        ("sentiment_analyst",
         "Analyze market sentiment and fear/greed data for: {q}"),
        *( [("whale_tracker",
              "Identify top-10 holders, smart money flows, accumulation vs distribution signals for: {q}")]
           if _WHALE_TRACKER_ENABLED else [] ),
    ]

    async def awrap_model_call(self, request: Any, handler: Any) -> Any:
        import uuid
        from langchain_core.messages import AIMessage, HumanMessage

        try:
            from langchain.agents.middleware.types import ModelResponse
        except ImportError:
            _agent_log.warning(
                "ParallelSpawnDirectiveMiddleware: langchain.agents.middleware.types.ModelResponse "
                "not found — comprehensive queries will fall back to LLM-delegated spawning "
                "instead of guaranteed parallel bypass. AC1/AC2 may be unreliable."
            )
            ModelResponse = None

        # Detect comprehensive query in the last HumanMessage
        messages = list(request.messages)
        query_content = ""
        is_comprehensive = False
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            if not isinstance(msg, HumanMessage):
                continue
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            if any(kw in content.lower() for kw in self._KEYWORDS):
                is_comprehensive = True
                query_content = content
                break

        if is_comprehensive and ModelResponse is not None:
            # Synthetic bypass: build task() calls WITHOUT invoking the LLM.
            # Normal path: emit ALL remaining agents in one turn → LangGraph spawns them in
            # parallel (AC1/AC2 from Phase 1 Quality Gate).
            # Under rate-limit pressure: emit ONLY the next single agent → LangGraph loops
            # back into this middleware after it completes, we re-scan history, and emit the
            # next one. Natural sequential pacing without asyncio.gather.
            short_q = query_content[:300]
            already_spawned = _already_spawned_agents(messages)
            pending = [
                (name, desc) for name, desc in self._COMPREHENSIVE_AGENTS
                if name not in already_spawned
            ]

            # Tier 3 Option C: under sustained pressure, cap the analysis to
            # the top-2 deterministic-API agents (tokenomics + defillama).
            # Guarantees a useful partial answer in ~30-45s instead of failing
            # on the full 6-agent orchestra under strict RPM providers.
            if pending and not already_spawned and _rate_limit_state.escalation_level() >= 2:
                _agent_log.warning(
                    "rate_limit_reduced_scope (Tier 3): capping analysis to %d/%d "
                    "agents (%s) to guarantee completion under rate-limit pressure",
                    2, len(self._COMPREHENSIVE_AGENTS),
                    [p[0] for p in pending[:2]],
                )
                try:
                    GRACEFUL_DEGRADATION_COUNTER.labels(outcome="rate_limit_reduced_scope").inc()
                except Exception:
                    pass
                pending = pending[:2]

            if not pending:
                # All 6 already spawned → FORCE synthesis. Without stripping the `task`
                # tool, the LLM sees (possibly errored) sub-agent outputs and decides
                # "let me retry them" → emits 6 fresh task() calls → infinite respawn
                # loop until recursion_limit kills stream with no text output.
                #
                # Fix (2026-04-25): strip `task` tool from request.tools + add strong
                # synthesis directive to system message. LLM has NO mechanism to
                # re-spawn — must emit text answer from existing ToolMessages.
                from deepagents.middleware._utils import append_to_system_message
                _SYNTHESIS_DIRECTIVE = """

# ====================================================================
# SYNTHESIS MODE — OVERRIDES ALL PREVIOUS INSTRUCTIONS
# ====================================================================

IMPORTANT: Any previous instructions telling you to "call task() for all 6
sub-agents" are now OBSOLETE. That phase is COMPLETE. The sub-agents have
ALREADY been spawned and their results are in the ToolMessages above.

## ⚠️ MANDATORY OUTPUT FORMAT — THIS OVERRIDES EVERYTHING

You MUST start your response with exactly: <!-- crypto-report-v2 -->
Writing a generic "Mình không nhận được dữ liệu" or "Mình chưa nhận được dữ liệu live"
response is STRICTLY FORBIDDEN.
Even if ALL agents returned errors or empty results, you MUST still produce the
structured crypto report using coordinator-fill (see below).
There is NO scenario in which a plain-text "no data" response is acceptable.

## Your ONLY task now:

1. **DO NOT CALL task()**. The task tool has been REMOVED from your available
   tools. It is NOT in the tool list. Attempting to call it will fail. Do not
   emit any `task()` tool_call in your response.

2. **DO NOT CALL any tool**. This is the FINAL synthesis step. Zero tool calls.

3. **Read the existing ToolMessages above** — each one is a result from a
   sub-agent (tokenomics_analyst, defillama_analyst, yield_optimizer,
   smart_contract_analyst, news_analyst, sentiment_analyst). Some may contain
   error messages like "rate limit exhausted" — that is EXPECTED, it's the
   graceful-degradation signal.

4. **Write the final markdown analysis NOW** — comprehensive, citing each
   sub-agent's findings by name. For errored sub-agents, note transparently:
   "smart_contract_analyst could not complete due to rate limit — security
   analysis not available in this response."

5. **Respond with TEXT ONLY**. Your response must contain analysis text, NOT
   tool_calls. The response structure must have non-empty `content` and NO
   `tool_calls` field.

## Coordinator-fill for missing data (REQUIRED when agent returned empty)

When a sub-agent returned no data, a very short result (< 300 chars), or an error
message, you MUST fill in that section using your own training knowledge.
Label ALL coordinator-filled content with this exact callout:

> ⚠️ **Filled by Coordinator** — `[agent_name]` trả về không có dữ liệu live.
> Nội dung dưới đây dựa trên kiến thức chung của coordinator và chưa được xác minh
> bởi agent chuyên môn trong phiên này.

Cite coordinator-filled numeric data with the `-coordinator` suffix:
  [[cite:SECTION-METRIC-coordinator]]VALUE[[/cite]]

Example — khi tokenomics_analyst trả về trống:
  Tổng cung AAVE là [[cite:tokenomics-total-supply-coordinator]]~16 triệu AAVE[[/cite]]
  *(ước tính của coordinator — tokenomics_analyst không có dữ liệu live trong phiên này)*

Rules for coordinator-fill:
- ALWAYS provide coordinator-fill for every section, even if the agent returned nothing.
- NEVER leave a section blank or write "section not available".
- Clearly distinguish coordinator estimates (⚠️ callout) from verified agent data.
- For uncertain data, use ranges: "khoảng X–Y" with coordinator citation.
- Coordinator-fill is BETTER than no data — always choose to fill over refusing.

## Citation syntax (REQUIRED for every numeric data point)

Wrap EVERY specific number or statistic with a citation tag:
  [[cite:SECTION-METRIC-SOURCE]]VALUE[[/cite]]

Examples:
  - Price: [[cite:price-current-coingecko]]$2.34[[/cite]]
  - TVL: [[cite:tvl-total-defillama]]$1.2B[[/cite]]
  - APY: [[cite:yield-eth-aave]]4.5%[[/cite]]
  - Supply: [[cite:tokenomics-circulating-coingecko]]500M UNI[[/cite]]

ID format: {section}-{metric}-{provider} (all lowercase, hyphens only).
Providers: coingecko, defillama, goplus, certik, nansen, dune, tokeninsight, etherscan, dexscreener.
Do NOT cite text/qualitative findings, only numeric data.

## Cross-source conflict detection (REQUIRED when sources diverge — AC7, Story 9-UX-4)

When 2 or more sources report the SAME metric and their values differ by MORE than 10% (absolute delta), you MUST emit a conflict citation:

  [[cite:SECTION-METRIC-conflict-PROVIDER1-PROVIDER2]]VALUE1 vs VALUE2[[/cite]]

Examples:
  - GoPlus score 20/100 vs CertiK score 45/100 (delta = 25 > 10):
    [[cite:security-score-conflict-goplus-certik]]20/100 vs 45/100[[/cite]]
    → note: "Security scores diverge significantly — independently verify using both links."
  - Two TVL sources: DeFiLlama $1.2B vs Nansen on-chain $0.9B (delta = 25%):
    [[cite:tvl-total-conflict-defillama-nansen]]$1.2B vs $0.9B[[/cite]]

Rules:
- Only flag conflicts for NUMERIC metrics (not text/qualitative).
- Always explain WHY scores might differ (methodology differences, data lag, etc.).
- Do NOT flag conflicts when delta ≤ 10% — minor rounding differences are expected.
- If one source returned an error, note the gap but do NOT emit a conflict citation.

## Embedded chart syntax (OPTIONAL, only when data is available)

After a section that has time-series or distribution data, you MAY embed a chart:

```chart:CHART_ID
type: line|bar|pie|area|candle
title: Human readable title
xKey: date
yKey: value
yLabel: TVL (USD)
source: defillama
data: [{"date":"2024-01","value":1200000000},{"date":"2024-02","value":1350000000}]
```

Chart ID format: {type}-{token}-{metric} (e.g. tvl-uni-total, price-uni-7d).
Only embed a chart when you have at least 5 data points from the sub-agent results.
Do NOT fabricate data — only use numbers reported by sub-agents.

## ⚠️ FINAL CHECK before writing your response

Scan your draft. If you see ANY of these patterns, DELETE them and replace with
coordinator-filled crypto report content:
- "Mình không nhận được dữ liệu"
- "Mình chưa nhận được"
- "Không có đủ dữ liệu để"
- "Unable to provide"
- "data not available"
- Any response that does NOT start with `<!-- crypto-report-v2 -->`

The user already knows some data may be missing — they want the best analysis
possible, not a refusal. Show them what you know.

## Crypto report header

Start your response with EXACTLY this sentinel on its own line:
<!-- crypto-report-v2 -->

Then immediately begin the heading:
# Phân tích toàn diện [TOKEN NAME]

No other preamble.

## Follow-up questions (REQUIRED at end)

After your complete analysis, append EXACTLY this line as the VERY LAST line of your response:
<!--follow-ups:["<question 1>?","<question 2>?","<question 3>?","<question 4>?","<question 5>?","<question 6>?"]-->

Replace the placeholders with 4-6 context-aware follow-up questions in the same language as the report.
Questions should be specific to the token analyzed (include the token symbol/name).
Examples: "Tại sao TVL của [TOKEN] giảm trong Q4 2024?", "[TOKEN] vs [COMPETITOR]: ai có tokenomics tốt hơn?", "Fee switch proposal của [TOKEN] có khả thi không?"
Output the entire JSON array on ONE line. Do NOT add any text after this comment."""

                # NOTE: do NOT append self._DIRECTIVE here — it says "call 6 task()"
                # which CONTRADICTS the synthesis directive and causes the LLM to
                # hallucinate task() tool_calls even after we stripped the task tool.
                # Only the synthesis directive should be appended in this mode.
                new_sys = append_to_system_message(
                    request.system_message,
                    _SYNTHESIS_DIRECTIVE,
                )
                # Strip `task` tool so the LLM cannot emit task() — synthesis mode.
                def _tool_name(t: Any) -> str | None:
                    if isinstance(t, dict):
                        return t.get("name")
                    return getattr(t, "name", None)
                tools_without_task = [
                    t for t in request.tools if _tool_name(t) != "task"
                ]
                if len(tools_without_task) < len(request.tools):
                    _agent_log.info(
                        "synthesis_mode: stripped task tool (tools %d→%d), forcing final text",
                        len(request.tools), len(tools_without_task),
                    )
                synth_request = request.override(
                    system_message=new_sys,
                    messages=messages,
                    tools=tools_without_task,
                    tool_choice="none",  # Providers that respect this will skip any tool_call
                )

                # Synthesis retry: unbounded exponential backoff until success or
                # wall-clock cap. Same philosophy as SubAgentResilienceMiddleware.
                from litellm.exceptions import RateLimitError as _LiteLLMRateLimit
                synth_started = time.time()
                synth_attempt = 0
                while True:
                    try:
                        return await handler(synth_request)
                    except Exception as exc:
                        err = str(exc).lower()
                        is_rl = (
                            isinstance(exc, _LiteLLMRateLimit)
                            or "rate limit" in err
                            or "429" in err
                        )
                        if not is_rl:
                            raise
                        synth_attempt += 1
                        elapsed = time.time() - synth_started
                        # No wall-clock cap — synthesis MUST eventually complete.
                        # Provider 429 is transient; retry indefinitely with exponential
                        # backoff capped at MAX_BACKOFF. Operator sees progress every 10 attempts.
                        delay = min(
                            _SUBAGENT_RETRY_BASE_BACKOFF * (2 ** (synth_attempt - 1)),
                            _SUBAGENT_RETRY_MAX_BACKOFF,
                        )
                        if synth_attempt % 10 == 0:
                            _agent_log.warning(
                                "synthesis_persistent_retry: attempt %d / %.0fs elapsed",
                                synth_attempt, elapsed,
                            )
                        else:
                            _agent_log.warning(
                                "synthesis_retry: attempt %d (elapsed %.0fs) hit 429, "
                                "sleeping %.0fs",
                                synth_attempt, elapsed, delay,
                            )
                        _rate_limit_state.mark_rate_limited()
                        await _cancellable_sleep(delay)

            escalation = _rate_limit_state.escalation_level()
            under_pressure = escalation >= 1
            batch = pending[:1] if under_pressure else pending

            # Fix 3c — respawn-loop detection. If we're about to emit the exact same
            # agent-batch signature as the previous synthetic bypass, that means the
            # main agent has somehow looped back without progress (pending recomputation
            # missed an agent, or deepagents surfaced a stale state). Force synthesis
            # path to break the cycle.
            current_sig = tuple(sorted(name for name, _ in batch))
            prev_sig = getattr(self, "_last_batch_sig", None)
            self._last_batch_sig = current_sig  # type: ignore[attr-defined]
            if prev_sig == current_sig and len(already_spawned) >= 1:
                _agent_log.warning(
                    "respawn_loop_detected: batch=%s (already_spawned=%s) — forcing "
                    "synthesis path to break cycle",
                    current_sig, sorted(already_spawned),
                )
                try:
                    GRACEFUL_DEGRADATION_COUNTER.labels(outcome="respawn_loop_break").inc()
                except Exception:
                    pass
                # Jump to synthesis path by clearing the pending signature state so
                # subsequent turns don't re-trigger this branch.
                self._last_batch_sig = None  # type: ignore[attr-defined]
                # Use Fix 3a synthesis path directly (tool stripped + directive).
                from deepagents.middleware._utils import append_to_system_message
                _LOOP_BREAK_DIRECTIVE = """

## SYNTHESIS MODE (respawn loop detected) — CRITICAL

You appear to be repeating the same sub-agent spawn. That is not useful — the
previous spawn's results are already in the ToolMessage history above. Stop.
DO NOT call task() or any tool. Write the final markdown analysis NOW using
the existing ToolMessages. If some sub-agents errored, acknowledge and
synthesize with what's available."""
                # Same rule as Fix 3a: skip _DIRECTIVE to avoid contradictory
                # "call 6 task()" instruction bleeding into synthesis mode.
                new_sys = append_to_system_message(
                    request.system_message,
                    _LOOP_BREAK_DIRECTIVE,
                )
                def _tool_name_lb(t: Any) -> str | None:
                    return t.get("name") if isinstance(t, dict) else getattr(t, "name", None)
                tools_no_task = [t for t in request.tools if _tool_name_lb(t) != "task"]
                return await handler(request.override(
                    system_message=new_sys,
                    messages=messages,
                    tools=tools_no_task,
                    tool_choice="none",
                ))

            if escalation >= 2:
                # Tier 3: forced pacing — wait for rate-limit window to recover before
                # emitting the next agent. Guarantees completion at the cost of latency.
                _agent_log.warning(
                    "rate_limit_paced (Tier 3): sleeping %.1fs before spawning %s "
                    "(%d/%d remaining)",
                    _PACED_DELAY_SECONDS, batch[0][0], len(pending),
                    len(self._COMPREHENSIVE_AGENTS),
                )
                try:
                    GRACEFUL_DEGRADATION_COUNTER.labels(outcome="rate_limit_paced").inc()
                except Exception:
                    pass
                await _cancellable_sleep(_PACED_DELAY_SECONDS)
                # Keep pressure state hot: without this, cooldown (60s) would expire
                # mid-paced-run and the next turn would revert to Tier 1 parallel spawn,
                # re-triggering the rate-limit cascade we just degraded from.
                _rate_limit_state.refresh_pressure()
            elif under_pressure:
                _agent_log.warning(
                    "rate_limit_degraded (Tier 2): spawning sequentially "
                    "(next=%s, %d/%d remaining)",
                    batch[0][0], len(pending), len(self._COMPREHENSIVE_AGENTS),
                )
                try:
                    GRACEFUL_DEGRADATION_COUNTER.labels(outcome="rate_limit_degraded").inc()
                except Exception:  # metric registry may reject unknown label values
                    pass

            synthetic_ai = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "task",
                        "args": {
                            "subagent_type": name,
                            "description": desc.format(q=short_q),
                        },
                        "id": uuid.uuid4().hex[:8],
                        "type": "tool_call",
                    }
                    for name, desc in batch
                ],
            )
            return ModelResponse(result=[synthetic_ai])

        # Non-comprehensive query: pass through unchanged so the LLM follows
        # the DECISION RULE in system_prompt.py (call direct tool, no sub-agents).
        # Keep retry-on-429 wrapper because provider 429 is transient and we MUST
        # eventually complete the response. Exponential backoff capped at MAX_BACKOFF.
        main_attempt = 0
        main_started = time.time()
        while True:
            try:
                return await handler(request)
            except Exception as exc:
                err_str = str(exc).lower()
                is_rate_limit = (
                    "rate limit" in err_str
                    or "ratelimiterror" in err_str
                    or "429" in err_str
                )
                if not is_rate_limit:
                    raise
                _rate_limit_state.mark_rate_limited()
                main_attempt += 1
                main_elapsed = time.time() - main_started
                main_delay = min(
                    _SUBAGENT_RETRY_BASE_BACKOFF * (2 ** (main_attempt - 1)),
                    _SUBAGENT_RETRY_MAX_BACKOFF,
                )
                if main_attempt % 10 == 0:
                    _agent_log.warning(
                        "main_orchestrator_persistent_retry: attempt %d / %.0fs elapsed",
                        main_attempt, main_elapsed,
                    )
                else:
                    _agent_log.warning(
                        "main_orchestrator_retry: attempt %d (elapsed %.0fs) hit 429, "
                        "sleeping %.0fs",
                        main_attempt, main_elapsed, main_delay,
                    )
                try:
                    GRACEFUL_DEGRADATION_COUNTER.labels(outcome="main_retry").inc()
                except Exception:
                    pass
                await _cancellable_sleep(main_delay)
                # Loop and retry — never return placeholder, never give up.

    def wrap_model_call(self, request: Any, handler: Any) -> Any:
        return handler(request)


class ParallelismTelemetryMiddleware(AgentMiddleware):
    """Detects sequential task() spawns and logs a warning.

    When the LLM issues task() calls across multiple LangGraph steps instead of
    batching them in a single step (anti-pattern), this middleware logs a warning
    so operators can investigate prompt or model issues.

    Supports two usage patterns:
    - AgentMiddleware hooks: abefore_model / aafter_model (used in production graph)
    - Callable middleware:   await mw(state, config, next_fn)  (used in tests)
    """

    # Bounded dedupe of tool_call_ids already counted. Prevents double-counting when
    # the middleware fires across multiple model steps re-scanning accumulated state.
    _MAX_COUNTED_TOOL_CALLS = 10000

    def __init__(self) -> None:
        super().__init__()
        self._counted_tool_call_ids: set[str] = set()

    async def __call__(self, state: Any, config: Any, next_middleware: Any) -> Any:
        """Callable middleware interface for testing and pipeline composition.

        Calls next_middleware, then inspects the result state for task() tool calls.
        """
        _prl_step_start.set(time.perf_counter())
        result_state = await next_middleware(state, config)
        _start = _prl_step_start.get()
        _elapsed = time.perf_counter() - _start if _start is not None else 0.0
        self._check_spawn_pattern(result_state, _elapsed)
        self._track_degradation(result_state)
        return result_state

    async def abefore_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        _prl_step_start.set(time.perf_counter())
        return None

    async def aafter_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        _start = _prl_step_start.get()
        _elapsed = time.perf_counter() - _start if _start is not None else 0.0
        self._check_spawn_pattern(state, _elapsed)
        self._track_degradation(state)
        return None

    def _check_spawn_pattern(self, state: Any, elapsed: float) -> None:
        """Inspect state messages for task() tool_calls and log accordingly."""
        if isinstance(state, dict):
            messages = state.get("messages") or []
        else:
            messages = getattr(state, "messages", None) or []

        task_calls = []
        for msg in reversed(messages):
            if isinstance(msg, dict):
                role = msg.get("type") or msg.get("role") or ""
            else:
                role = getattr(msg, "type", None) or getattr(msg, "role", None) or ""
            if role not in ("ai", "assistant"):
                continue
            if isinstance(msg, dict):
                tool_calls = msg.get("tool_calls") or []
            else:
                tool_calls = getattr(msg, "tool_calls", None) or []
            for tc in tool_calls:
                if isinstance(tc, dict):
                    name = tc.get("name")
                else:
                    name = getattr(tc, "name", None)
                if name == "task":
                    task_calls.append(tc)
            if task_calls:
                break

        agent_count = len(task_calls)
        if agent_count >= 4:
            _agent_log.info(
                "parallel_spawn: %d agents dispatched in single step, elapsed=%.3fs",
                agent_count,
                elapsed,
            )
            FULL_SUITE_DURATION_HISTOGRAM.labels(agents_count="4+").observe(elapsed)
        elif agent_count >= 2:
            _agent_log.info(
                "parallel_spawn: %d agents dispatched in single step, elapsed=%.3fs",
                agent_count,
                elapsed,
            )
            FULL_SUITE_DURATION_HISTOGRAM.labels(agents_count="2-3").observe(elapsed)
        elif agent_count == 1:
            # Single task() per step is the sequential anti-pattern — find query snippet
            _query_snippet = ""
            for _m in reversed(messages):
                if isinstance(_m, dict):
                    _role = _m.get("type") or _m.get("role") or ""
                else:
                    _role = getattr(_m, "type", None) or getattr(_m, "role", None) or ""
                if _role in ("ai", "assistant"):
                    continue  # skip the AI message we just inspected
                _c = (_m.get("content", "") if isinstance(_m, dict) else getattr(_m, "content", "")) or ""
                if _c:
                    _query_snippet = str(_c)[:120]
                    break
            _agent_log.warning(
                "potential_sequential_spawn detected: single task() call per step. "
                "LLM may be spawning sub-agents sequentially instead of in a parallel batch. "
                "query_snippet=%r",
                _query_snippet,
            )
            FULL_SUITE_DURATION_HISTOGRAM.labels(agents_count="1").observe(elapsed)

    @staticmethod
    def _extract_error_from_content(content: Any) -> str | None:
        """Return error-string if ToolMessage content carries `{"error": <truthy>}`.

        Handles three content shapes:
          - JSON-encoded string (most common tool output)
          - dict passed directly
          - list of content blocks (multimodal); scan each block
        """
        candidates: list[Any] = []
        if isinstance(content, str):
            try:
                candidates.append(json.loads(content))
            except (ValueError, TypeError):
                return None
        elif isinstance(content, dict):
            candidates.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    candidates.append(block)
                elif isinstance(block, str):
                    try:
                        candidates.append(json.loads(block))
                    except (ValueError, TypeError):
                        continue
        for c in candidates:
            if isinstance(c, dict):
                err = c.get("error")
                if err:  # truthy check — reject {"error": null}
                    return str(err)
        return None

    @staticmethod
    def _classify_error_type(error_msg: str) -> str:
        """Map an error string to a bounded error_type label.

        Uses precise markers (word-boundary regex for HTTP status codes) instead of
        substring matches to avoid misclassifying messages like "5000ms".
        """
        import re

        msg = error_msg.lower()
        # Rate-limit wins when the phrase appears verbatim OR the HTTP 429 code
        if "rate limit" in msg or re.search(r"\b429\b", msg):
            return "rate_limit"
        if "timeout" in msg:
            return "timeout"
        if re.search(r"\b5\d{2}\b", msg) or "server error" in msg or "httpstatuserror" in msg:
            return "server_error"
        if "network" in msg or "networkerror" in msg:
            return "network_error"
        return "unknown"

    def _track_degradation(self, state: Any) -> None:
        """Inspect ToolMessages for agent errors and track degradation metrics.

        Dedupes by `tool_call_id` so each error is counted at most once across the
        repeated middleware invocations that occur throughout a multi-step
        orchestration. Emits `GRACEFUL_DEGRADATION_COUNTER` only when new tool
        messages have arrived this invocation (otherwise the outcome counter
        would inflate by the number of model steps).
        """
        if isinstance(state, dict):
            messages = state.get("messages") or []
        else:
            messages = getattr(state, "messages", None) or []

        # Count newly-arrived ToolMessages (dedupe by tool_call_id).
        new_tool_messages = 0
        new_errors = 0
        total_tool_messages = 0  # across entire state
        total_errors = 0
        for msg in messages:
            if isinstance(msg, dict):
                msg_type = msg.get("type") or msg.get("role") or ""
                tcid = msg.get("tool_call_id") or msg.get("id") or ""
                name = msg.get("name") or "unknown"
                content = msg.get("content", "")
            else:
                msg_type = getattr(msg, "type", None) or getattr(msg, "role", None) or ""
                tcid = getattr(msg, "tool_call_id", None) or getattr(msg, "id", None) or ""
                name = getattr(msg, "name", None) or "unknown"
                content = getattr(msg, "content", "")
            if msg_type != "tool":
                continue
            total_tool_messages += 1
            error_str = self._extract_error_from_content(content)
            if error_str is not None:
                total_errors += 1
            already_counted = bool(tcid) and tcid in self._counted_tool_call_ids
            if already_counted:
                continue
            new_tool_messages += 1
            if error_str is not None:
                error_type = self._classify_error_type(error_str)
                AGENT_ERRORS_COUNTER.labels(
                    agent_name=str(name),
                    error_type=error_type,
                ).inc()
                new_errors += 1
                # Feed rate-limit signal back to the module-level state so
                # ParallelSpawnDirectiveMiddleware degrades the next comprehensive
                # query from parallel-6 to sequential-1 spawn.
                if error_type == "rate_limit":
                    _rate_limit_state.mark_rate_limited()
                    _agent_log.warning(
                        "rate_limit_detected agent=%s — future comprehensive queries "
                        "will spawn sequentially for %.0fs",
                        name, _rate_limit_state.cooldown_seconds,
                    )
            if tcid:
                if len(self._counted_tool_call_ids) >= self._MAX_COUNTED_TOOL_CALLS:
                    self._counted_tool_call_ids.clear()
                self._counted_tool_call_ids.add(tcid)

        # Only emit the outcome counter when something actually changed this step.
        # Without this guard, every model step after orchestration completes would
        # re-emit the same outcome, inflating the rate metric.
        if new_tool_messages == 0:
            return

        if total_errors == 0:
            outcome = "success"
        elif total_errors < total_tool_messages:
            outcome = "partial"
        else:
            outcome = "failed"

        GRACEFUL_DEGRADATION_COUNTER.labels(outcome=outcome).inc()
        _agent_log.debug(
            "degradation_tracking: tool_messages=%d errors=%d new=%d outcome=%s",
            total_tool_messages,
            total_errors,
            new_tool_messages,
            outcome,
        )


# =============================================================================
# Deep Agent Factory
# =============================================================================


async def create_nowing_deep_agent(
    llm: BaseChatModel,
    search_space_id: int,
    db_session: AsyncSession,
    connector_service: ConnectorService,
    checkpointer: Checkpointer,
    user_id: str | None = None,
    thread_id: int | None = None,
    agent_config: AgentConfig | None = None,
    enabled_tools: list[str] | None = None,
    disabled_tools: list[str] | None = None,
    additional_tools: Sequence[BaseTool] | None = None,
    firecrawl_api_key: str | None = None,
    thread_visibility: ChatVisibility | None = None,
    mentioned_document_ids: list[int] | None = None,
):
    """
    Create a Nowing deep agent with configurable tools and prompts.

    The agent comes with built-in tools that can be configured:
    - generate_podcast: Generate audio podcasts from content
    - generate_image: Generate images from text descriptions using AI models
    - scrape_webpage: Extract content from webpages
    - update_memory: Update the user's personal or team memory document

    The agent also includes TodoListMiddleware by default (via create_deep_agent) which provides:
    - write_todos: Create and update planning/todo lists for complex tasks

    The system prompt can be configured via agent_config:
    - Custom system instructions (or use defaults)
    - Citation toggle (enable/disable citation requirements)

    Args:
        llm: ChatLiteLLM instance for the agent's language model
        search_space_id: The user's search space ID
        db_session: Database session for tools that need DB access
        connector_service: Initialized connector service for knowledge base search
        checkpointer: LangGraph checkpointer for conversation state persistence.
                      Use AsyncPostgresSaver for production or MemorySaver for testing.
        user_id: The current user's UUID string (required for memory tools)
        agent_config: Optional AgentConfig from NewLLMConfig for prompt configuration.
                     If None, uses default system prompt with citations enabled.
        enabled_tools: Explicit list of tool names to enable. If None, all default tools
                      are enabled. Use this to limit which tools are available.
        disabled_tools: List of tool names to disable. Applied after enabled_tools.
                       Use this to exclude specific tools from the defaults.
        additional_tools: Extra custom tools to add beyond the built-in ones.
                         These are always added regardless of enabled/disabled settings.
        firecrawl_api_key: Optional Firecrawl API key for premium web scraping.
                          Falls back to Chromium/Trafilatura if not provided.

    Returns:
        CompiledStateGraph: The configured deep agent

    Examples:
        # Create agent with all default tools and default prompt
        agent = create_nowing_deep_agent(llm, search_space_id, db_session, ...)

        # Create agent with custom prompt configuration
        agent = create_nowing_deep_agent(
            llm, search_space_id, db_session, ...,
            agent_config=AgentConfig(
                provider="OPENAI",
                model_name="gpt-4",
                api_key="...",
                system_instructions="Custom instructions...",
                citations_enabled=False,
            )
        )

        # Create agent with only specific tools
        agent = create_nowing_deep_agent(
            llm, search_space_id, db_session, ...,
            enabled_tools=["scrape_webpage"]
        )

        # Create agent without podcast generation
        agent = create_nowing_deep_agent(
            llm, search_space_id, db_session, ...,
            disabled_tools=["generate_podcast"]
        )

        # Add custom tools
        agent = create_nowing_deep_agent(
            llm, search_space_id, db_session, ...,
            additional_tools=[my_custom_tool]
        )
    """
    _t_agent_total = time.perf_counter()

    # Discover available connectors and document types for this search space
    available_connectors: list[str] | None = None
    available_document_types: list[str] | None = None

    _t0 = time.perf_counter()
    try:
        connector_types = await connector_service.get_available_connectors(
            search_space_id
        )
        if connector_types:
            available_connectors = _map_connectors_to_searchable_types(connector_types)

        available_document_types = await connector_service.get_available_document_types(
            search_space_id
        )

    except Exception as e:
        logging.warning(f"Failed to discover available connectors/document types: {e}")
    _perf_log.info(
        "[create_agent] Connector/doc-type discovery in %.3fs",
        time.perf_counter() - _t0,
    )

    # Build dependencies dict for the tools registry
    visibility = thread_visibility or ChatVisibility.PRIVATE

    # Extract the model's context window so tools can size their output.
    _model_profile = getattr(llm, "profile", None)
    _max_input_tokens: int | None = (
        _model_profile.get("max_input_tokens")
        if isinstance(_model_profile, dict)
        else None
    )

    dependencies = {
        "search_space_id": search_space_id,
        "db_session": db_session,
        "connector_service": connector_service,
        "firecrawl_api_key": firecrawl_api_key,
        "user_id": user_id,
        "thread_id": thread_id,
        "thread_visibility": visibility,
        "available_connectors": available_connectors,
        "available_document_types": available_document_types,
        "max_input_tokens": _max_input_tokens,
        "llm": llm,
    }

    # Disable Notion action tools if no Notion connector is configured
    modified_disabled_tools = list(disabled_tools) if disabled_tools else []
    has_notion_connector = (
        available_connectors is not None and "NOTION_CONNECTOR" in available_connectors
    )
    if not has_notion_connector:
        notion_tools = [
            "create_notion_page",
            "update_notion_page",
            "delete_notion_page",
        ]
        modified_disabled_tools.extend(notion_tools)

    # Disable Linear action tools if no Linear connector is configured
    has_linear_connector = (
        available_connectors is not None and "LINEAR_CONNECTOR" in available_connectors
    )
    if not has_linear_connector:
        linear_tools = [
            "create_linear_issue",
            "update_linear_issue",
            "delete_linear_issue",
        ]
        modified_disabled_tools.extend(linear_tools)

    # Disable Google Drive action tools if no Google Drive connector is configured
    has_google_drive_connector = (
        available_connectors is not None and "GOOGLE_DRIVE_FILE" in available_connectors
    )
    if not has_google_drive_connector:
        google_drive_tools = [
            "create_google_drive_file",
            "delete_google_drive_file",
        ]
        modified_disabled_tools.extend(google_drive_tools)

    has_dropbox_connector = (
        available_connectors is not None and "DROPBOX_FILE" in available_connectors
    )
    if not has_dropbox_connector:
        modified_disabled_tools.extend(["create_dropbox_file", "delete_dropbox_file"])

    has_onedrive_connector = (
        available_connectors is not None and "ONEDRIVE_FILE" in available_connectors
    )
    if not has_onedrive_connector:
        modified_disabled_tools.extend(["create_onedrive_file", "delete_onedrive_file"])

    # Disable Google Calendar action tools if no Google Calendar connector is configured
    has_google_calendar_connector = (
        available_connectors is not None
        and "GOOGLE_CALENDAR_CONNECTOR" in available_connectors
    )
    if not has_google_calendar_connector:
        calendar_tools = [
            "create_calendar_event",
            "update_calendar_event",
            "delete_calendar_event",
        ]
        modified_disabled_tools.extend(calendar_tools)

    # Disable Gmail action tools if no Gmail connector is configured
    has_gmail_connector = (
        available_connectors is not None
        and "GOOGLE_GMAIL_CONNECTOR" in available_connectors
    )
    if not has_gmail_connector:
        gmail_tools = [
            "create_gmail_draft",
            "update_gmail_draft",
            "send_gmail_email",
            "trash_gmail_email",
        ]
        modified_disabled_tools.extend(gmail_tools)

    # Disable Jira action tools if no Jira connector is configured
    has_jira_connector = (
        available_connectors is not None and "JIRA_CONNECTOR" in available_connectors
    )
    if not has_jira_connector:
        jira_tools = [
            "create_jira_issue",
            "update_jira_issue",
            "delete_jira_issue",
        ]
        modified_disabled_tools.extend(jira_tools)

    # Disable Confluence action tools if no Confluence connector is configured
    has_confluence_connector = (
        available_connectors is not None
        and "CONFLUENCE_CONNECTOR" in available_connectors
    )
    if not has_confluence_connector:
        confluence_tools = [
            "create_confluence_page",
            "update_confluence_page",
            "delete_confluence_page",
        ]
        modified_disabled_tools.extend(confluence_tools)

    # Remove direct KB search tool; we now pre-seed a scoped filesystem via middleware.
    if "search_knowledge_base" not in modified_disabled_tools:
        modified_disabled_tools.append("search_knowledge_base")

    # Build tools using the async registry (includes MCP tools)
    _t0 = time.perf_counter()
    tools = await build_tools_async(
        dependencies=dependencies,
        enabled_tools=enabled_tools,
        disabled_tools=modified_disabled_tools,
        additional_tools=list(additional_tools) if additional_tools else None,
    )
    _perf_log.info(
        "[create_agent] build_tools_async in %.3fs (%d tools)",
        time.perf_counter() - _t0,
        len(tools),
    )

    # Build system prompt based on agent_config, scoped to the tools actually enabled
    _t0 = time.perf_counter()
    _enabled_tool_names = {t.name for t in tools}
    _user_disabled_tool_names = set(disabled_tools) if disabled_tools else set()
    if agent_config is not None:
        system_prompt = build_configurable_system_prompt(
            custom_system_instructions=agent_config.system_instructions,
            use_default_system_instructions=agent_config.use_default_system_instructions,
            citations_enabled=agent_config.citations_enabled,
            thread_visibility=thread_visibility,
            enabled_tool_names=_enabled_tool_names,
            disabled_tool_names=_user_disabled_tool_names,
        )
    else:
        system_prompt = build_nowing_system_prompt(
            thread_visibility=thread_visibility,
            enabled_tool_names=_enabled_tool_names,
            disabled_tool_names=_user_disabled_tool_names,
        )
    _perf_log.info(
        "[create_agent] System prompt built in %.3fs", time.perf_counter() - _t0
    )

    # -- Build the middleware stack (mirrors create_deep_agent internals) ------
    _memory_middleware = MemoryInjectionMiddleware(
        user_id=user_id,
        search_space_id=search_space_id,
        thread_visibility=visibility,
    )

    # Async Redis client for crypto cache distributed locking (Story 10.3).
    # Reuses the module-level singleton — no per-invocation connection pool leak.
    from app.services.crypto_cache_lock import get_redis_client as _get_crypto_redis
    _crypto_redis_client = _get_crypto_redis()

    # NFR-CS4: each sub-agent gets a *fresh* middleware list with *fresh* instances
    # so that any per-invocation state (todos buffer, summarization cache,
    # filesystem handles) cannot cross-contaminate when sub-agents run in parallel.
    # _memory_middleware is the only intentionally shared instance — it is read-only
    # context injection, no per-call mutation.
    def _build_gp_middleware(agent_name: str = "subagent") -> list[Any]:
        return [
            # Shared global rate gate — every sub-agent LLM call passes through
            # the same token bucket as the main orchestrator (see _global_rate_bucket).
            ProviderRateLimitMiddleware(),
            # Story 9-UX-1 AC3: source attribution + narration events (observational).
            SourceAttributionMiddleware(agent_name=agent_name),
            CryptoDataCacheMiddleware(
                search_space_id=search_space_id, redis_client=_crypto_redis_client
            ),
            TodoListMiddleware(),
            _memory_middleware,
            NowingFilesystemMiddleware(
                search_space_id=search_space_id,
                created_by_id=user_id,
            ),
            create_summarization_middleware(llm, StateBackend),
            PatchToolCallsMiddleware(),
            AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore"),
        ]

    general_purpose_spec: SubAgent = {  # type: ignore[typeddict-unknown-key]
        **GENERAL_PURPOSE_SUBAGENT,
        "model": llm,
        "tools": tools,
        "middleware": _build_gp_middleware(agent_name="general"),
    }

    # Crypto sub-agent tool scoping (allowed sets imported from spec files —
    # single source of truth shared with tests).
    def _scope_tools(allowed: tuple[str, ...], agent_label: str) -> list[BaseTool]:
        scoped = [t for t in tools if t.name in allowed]
        scoped_names = {t.name for t in scoped}
        missing = set(allowed) - scoped_names
        if missing:
            # NFR-CS4: surface silent registry drift (e.g. a tool gated off by env flag).
            _perf_log.warning(
                "[create_agent] sub-agent %s missing tools from registry: %s",
                agent_label,
                sorted(missing),
            )
        return scoped

    defillama_tools = _scope_tools(DEFILLAMA_ALLOWED_TOOLS, DEFILLAMA_ANALYST_NAME)
    sentiment_tools = _scope_tools(SENTIMENT_ALLOWED_TOOLS, SENTIMENT_ANALYST_NAME)
    news_tools = _scope_tools(NEWS_ALLOWED_TOOLS, NEWS_ANALYST_NAME)
    smart_contract_tools = _scope_tools(SMART_CONTRACT_ALLOWED_TOOLS, SMART_CONTRACT_ANALYST_NAME)
    tokenomics_tools = _scope_tools(TOKENOMICS_ALLOWED_TOOLS, TOKENOMICS_ANALYST_NAME)
    yield_optimizer_tools = _scope_tools(YIELD_OPTIMIZER_ALLOWED_TOOLS, YIELD_OPTIMIZER_NAME)
    smart_money_tools = _scope_tools(SMART_MONEY_ALLOWED_TOOLS, SMART_MONEY_ANALYST_NAME)

    # whale_tracker is optional — only built when feature flag is on (Story 9-UX-4 AC5).
    _whale_tracker_enabled = (
        os.getenv("CRYPTO_ORCHESTRA_ENABLE_WHALE_TRACKER", "false").strip().lower()
        in ("1", "true", "yes")
    )
    whale_tracker_tools = (
        _scope_tools(WHALE_TRACKER_ALLOWED_TOOLS, WHALE_TRACKER_NAME)
        if _whale_tracker_enabled
        else []
    )

    # Guard: all 6 crypto prompts (defillama, sentiment, news, smart_contract, tokenomics,
    # yield_optimizer) reference chainlens_deep_research unconditionally. If the feature flag
    # (CHAINLENS_RESEARCH_ENABLED) is off, the tool is silently absent from the registry
    # → LLM will hallucinate tool calls. Escalate to ERROR so this is noticeable in logs
    # instead of buried in per-agent warnings.
    _tool_names = {t.name for t in tools}
    if "chainlens_deep_research" not in _tool_names:
        _perf_log.error(
            "[create_agent] chainlens_deep_research is NOT in the tool registry but all "
            "6 crypto sub-agent prompts reference it. Either enable CHAINLENS_RESEARCH_ENABLED "
            "or update crypto sub-agent prompts to remove chainlens references."
        )

    defillama_analyst_spec: SubAgent = {  # type: ignore[typeddict-unknown-key]
        "name": DEFILLAMA_ANALYST_NAME,
        "description": DEFILLAMA_ANALYST_DESCRIPTION,
        "system_prompt": DEFILLAMA_ANALYST_PROMPT,
        "model": llm,
        "tools": defillama_tools,
        "middleware": _build_gp_middleware(agent_name=DEFILLAMA_ANALYST_NAME),
    }
    sentiment_analyst_spec: SubAgent = {  # type: ignore[typeddict-unknown-key]
        "name": SENTIMENT_ANALYST_NAME,
        "description": SENTIMENT_ANALYST_DESCRIPTION,
        "system_prompt": SENTIMENT_ANALYST_PROMPT,
        "model": llm,
        "tools": sentiment_tools,
        "middleware": _build_gp_middleware(agent_name=SENTIMENT_ANALYST_NAME),
    }
    news_analyst_spec: SubAgent = {  # type: ignore[typeddict-unknown-key]
        "name": NEWS_ANALYST_NAME,
        "description": NEWS_ANALYST_DESCRIPTION,
        "system_prompt": NEWS_ANALYST_PROMPT,
        "model": llm,
        "tools": news_tools,
        "middleware": _build_gp_middleware(agent_name=NEWS_ANALYST_NAME),
    }
    smart_contract_analyst_spec: SubAgent = {  # type: ignore[typeddict-unknown-key]
        "name": SMART_CONTRACT_ANALYST_NAME,
        "description": SMART_CONTRACT_ANALYST_DESCRIPTION,
        "system_prompt": SMART_CONTRACT_ANALYST_PROMPT,
        "model": llm,
        "tools": smart_contract_tools,
        "middleware": _build_gp_middleware(agent_name=SMART_CONTRACT_ANALYST_NAME),
    }
    tokenomics_analyst_spec: SubAgent = {  # type: ignore[typeddict-unknown-key]
        "name": TOKENOMICS_ANALYST_NAME,
        "description": TOKENOMICS_ANALYST_DESCRIPTION,
        "system_prompt": TOKENOMICS_ANALYST_PROMPT,
        "model": llm,
        "tools": tokenomics_tools,
        "middleware": _build_gp_middleware(agent_name=TOKENOMICS_ANALYST_NAME),
    }
    yield_optimizer_spec: SubAgent = {  # type: ignore[typeddict-unknown-key]
        "name": YIELD_OPTIMIZER_NAME,
        "description": YIELD_OPTIMIZER_DESCRIPTION,
        "system_prompt": YIELD_OPTIMIZER_PROMPT,
        "model": llm,
        "tools": yield_optimizer_tools,
        "middleware": _build_gp_middleware(agent_name=YIELD_OPTIMIZER_NAME),
    }
    smart_money_spec: SubAgent = {  # type: ignore[typeddict-unknown-key]
        "name": SMART_MONEY_ANALYST_NAME,
        "description": SMART_MONEY_ANALYST_DESCRIPTION,
        "system_prompt": SMART_MONEY_ANALYST_PROMPT,
        "model": llm,
        "tools": smart_money_tools,
        "middleware": _build_gp_middleware(agent_name=SMART_MONEY_ANALYST_NAME),
    }

    # whale_tracker spec — only built when CRYPTO_ORCHESTRA_ENABLE_WHALE_TRACKER=true (AC5)
    whale_tracker_spec: SubAgent | None = (
        {  # type: ignore[typeddict-unknown-key]
            "name": WHALE_TRACKER_NAME,
            "description": WHALE_TRACKER_DESCRIPTION,
            "system_prompt": WHALE_TRACKER_PROMPT,
            "model": llm,
            "tools": whale_tracker_tools,
            "middleware": _build_gp_middleware(agent_name=WHALE_TRACKER_NAME),
        }
        if _whale_tracker_enabled
        else None
    )

    # Main agent middleware
    deepagent_middleware = [
        # Global token-bucket — runs FIRST so every downstream LLM call passes through.
        # No-op when PROVIDER_RPM_LIMIT == 0 (default).
        ProviderRateLimitMiddleware(),
        # Story 9-UX-1 AC3: source attribution — observational, wraps main agent tool calls.
        # Sub-agent tool calls are covered by their own SourceAttributionMiddleware instance.
        SourceAttributionMiddleware(agent_name="orchestrator"),
        # Sub-agent resilience: retry task() on rate-limit, convert terminal failures
        # to error ToolMessage so main agent synthesizes with whatever succeeded.
        SubAgentResilienceMiddleware(),
        TodoListMiddleware(),
        _memory_middleware,
        KnowledgeBaseSearchMiddleware(
            llm=llm,
            search_space_id=search_space_id,
            available_connectors=available_connectors,
            available_document_types=available_document_types,
            mentioned_document_ids=mentioned_document_ids,
        ),
        NowingFilesystemMiddleware(
            search_space_id=search_space_id,
            created_by_id=user_id,
        ),
        SubAgentMiddleware(
            backend=StateBackend,
            subagents=[
                general_purpose_spec,
                defillama_analyst_spec,
                sentiment_analyst_spec,
                news_analyst_spec,
                smart_contract_analyst_spec,
                tokenomics_analyst_spec,    # Story 9.1
                yield_optimizer_spec,       # Story 9.4
                smart_money_spec,           # Story 10.1
                *([whale_tracker_spec] if whale_tracker_spec is not None else []),  # Story 9-UX-4 AC5
            ],
        ),
        ParallelSpawnDirectiveMiddleware(),
        ParallelismTelemetryMiddleware(),
        create_summarization_middleware(llm, StateBackend),
        PatchToolCallsMiddleware(),
        DedupHITLToolCallsMiddleware(),
        AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore"),
    ]

    # Combine system_prompt with BASE_AGENT_PROMPT (same as create_deep_agent)
    final_system_prompt = system_prompt + "\n\n" + BASE_AGENT_PROMPT

    _t0 = time.perf_counter()
    agent = await asyncio.to_thread(
        create_agent,
        llm,
        system_prompt=final_system_prompt,
        tools=tools,
        middleware=deepagent_middleware,
        context_schema=NowingContextSchema,
        checkpointer=checkpointer,
    )
    agent = agent.with_config(
        {
            "recursion_limit": 10_000,
            "metadata": {
                "ls_integration": "deepagents",
                "versions": {"deepagents": deepagents_version},
            },
        }
    )
    _perf_log.info(
        "[create_agent] Graph compiled (create_agent) in %.3fs",
        time.perf_counter() - _t0,
    )

    _perf_log.info(
        "[create_agent] Total agent creation in %.3fs",
        time.perf_counter() - _t_agent_total,
    )
    return agent
