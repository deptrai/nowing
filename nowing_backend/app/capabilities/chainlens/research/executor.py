"""``chainlens.research`` executor: call ChainLens ``POST /api/v1/search``.

When ChainLens is unavailable, misconfigured, or returns partial/insufficient
results, the executor degrades gracefully and optionally falls back to the
workspace knowledge base so self-hosted installs remain useful.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal

import httpx
from sqlalchemy.exc import SQLAlchemyError

from app.capabilities.chainlens.research.schemas import (
    ResearchInput,
    ResearchOutput,
    Source,
)
from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.capabilities.core.types import CapabilityContext
from app.config import config
from app.exceptions import ExternalServiceError
from app.observability import metrics
from app.utils.crawl.classifier import BlockType

logger = logging.getLogger(__name__)

SearchFn = Callable[[ResearchInput], Awaitable[ResearchOutput]]

_ResearchStatus = Literal[
    "complete",
    "partial",
    "timeout",
    "insufficient_evidence",
    "engine_unavailable",
]


class ChainLensError(ExternalServiceError):
    """Upstream ChainLens returned an explicit error."""


class _Block:
    __slots__ = ("data", "type")

    def __init__(self, block_type: str, data: Any) -> None:
        self.type = block_type
        self.data = data


def _block_type_for(raw: str | None) -> BlockType:
    """Map a raw block-type string to the classifier enum; unknown → UNKNOWN."""
    if not raw:
        return BlockType.UNKNOWN
    try:
        return BlockType(raw)
    except ValueError:
        return BlockType.UNKNOWN


def _parse_sources(raw_sources: Any) -> list[Source]:
    """Normalize a list of ChainLens source blobs into typed ``Source`` objects."""
    if not isinstance(raw_sources, list):
        return []
    sources: list[Source] = []
    for raw_source in raw_sources:
        if not isinstance(raw_source, dict):
            continue
        meta = raw_source.get("metadata") or raw_source
        if not isinstance(meta, dict):
            continue
        url = str(meta.get("url") or "").strip()
        if not url:
            continue
        content = raw_source.get("content")
        if content is None:
            content = raw_source.get("pageContent")
        sources.append(
            Source(
                title=str(meta.get("title") or meta.get("name") or "Source"),
                url=url,
                content=str(content) if content is not None else None,
            )
        )
    return sources


def _to_int(value: Any) -> int | None:
    """Normalize a progress counter to a non-negative int."""
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, float) and value.is_integer() and value >= 0:
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _parse_engine_ts(value: Any) -> int | None:
    """Parse an engine ISO-8601 timestamp to epoch milliseconds."""
    if not isinstance(value, str):
        return None
    try:
        # ponytail: fromisoformat handles 'Z' in Python 3.11+; fallback for older versions.
        ts = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.UTC)
        return int(dt.timestamp() * 1000)
    except Exception:
        return None


class _SSEParser:
    """Incremental SSE parser for the ChainLens research stream.

    Feed each line as it arrives and call :meth:`finalize` once the stream
    ends. This keeps memory bounded for long research streams.
    """

    __slots__ = (
        "answer",
        "blocked_url_coverage",
        "blocks",
        "chat_id",
        "cost_basis",
        "cost_dollars",
        "degradation_reason",
        "engine_reason",
        "error_msg",
        "estimated",
        "evidence_ready_at",
        "first_factual_chunk_at",
        "first_progress_at",
        "first_token_time_ms",
        "request_accepted_at",
        "resolved_mode",
        "saw_done",
        "saw_engine_first_token",
        "saw_first_token",
        "saw_heartbeat",
        "saw_unknown",
        "sources",
        "start_time",
        "status",
        "tokens_total",
        "web_url",
    )

    def __init__(self, start_time: float | None = None) -> None:
        self.blocks: dict[str, _Block] = {}
        self.error_msg: str | None = None
        self.chat_id: str | None = None
        self.web_url: str | None = None
        self.saw_done = False
        self.saw_engine_first_token = False
        self.saw_first_token = False
        self.saw_heartbeat = False
        self.saw_unknown = False
        self.status: _ResearchStatus = "complete"
        self.answer = ""
        self.sources: list[Source] = []
        self.degradation_reason: str | None = None
        self.engine_reason: str | None = None
        self.blocked_url_coverage: dict[str, int] = {}
        self.cost_dollars: float | None = None
        self.cost_basis: Literal["actual", "estimated", "fallback"] | None = None
        self.resolved_mode: str | None = None
        self.estimated: bool | None = None
        self.tokens_total: int | None = None
        self.first_token_time_ms: int | None = None
        self.request_accepted_at: int | None = None
        self.first_progress_at: int | None = None
        self.evidence_ready_at: int | None = None
        self.first_factual_chunk_at: int | None = None
        self.start_time = start_time

    def _record_first_token(self) -> None:
        """Capture TTFB and surface it as a progress event.

        Prefer the engine's own ``firstFactualChunkAt - requestAcceptedAt``
        milestones; fall back to the local Nowing clock only when the engine
        does not publish them.
        """
        if (
            self.request_accepted_at is not None
            and self.first_factual_chunk_at is not None
        ):
            ttfb = max(0, self.first_factual_chunk_at - self.request_accepted_at)
            if self.saw_engine_first_token and self.first_token_time_ms == ttfb:
                return
            self.saw_engine_first_token = True
            self.saw_first_token = True
            self.first_token_time_ms = ttfb
            emit_progress(
                "first_token",
                message="First token received",
                ttfb_ms=self.first_token_time_ms,
            )
            return
        if (
            self.start_time is not None
            and not self.saw_first_token
            and not self.saw_engine_first_token
        ):
            self.saw_first_token = True
            self.first_token_time_ms = int(
                (time.perf_counter() - self.start_time) * 1000
            )
            emit_progress(
                "first_token",
                message="First token received",
                ttfb_ms=self.first_token_time_ms,
            )

    def _maybe_record_text_first_token(self, text: Any) -> None:
        if isinstance(text, str) and text.strip():
            self._record_first_token()

    def feed_line(self, raw_line: str) -> None:
        """Ingest one raw ``data:`` SSE line and update parser state.

        The ChainLens contract uses data-only frames; ``event:`` lines and
        ``[DONE]`` markers are ignored.
        """
        line = raw_line.strip()
        if not line:
            return

        if not line.startswith("data:"):
            return
        payload = line[len("data:") :].strip()

        if not payload or payload == "[DONE]":
            return

        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            logger.debug("Ignoring malformed SSE JSON payload: %r", payload[:200])
            return

        if not isinstance(event, dict):
            logger.debug("Ignoring non-object SSE event: %r", type(event))
            return

        event_type = event.get("type")

        if event_type == "error":
            data = event.get("data")
            self.error_msg = (
                data
                if isinstance(data, str)
                else (json.dumps(data) if data is not None else "Upstream SSE error")
            )
            return

        if event_type in {"done", "usage"}:
            if event_type == "done":
                self.saw_done = True
            self.chat_id = event.get("chatId") or event.get("chat_id") or self.chat_id
            self.web_url = event.get("webUrl") or self.web_url
            self._extract_cost(event)
            return

        if event_type == "block" and isinstance(event.get("block"), dict):
            block = event["block"]
            block_id = block.get("id")
            if isinstance(block_id, str):
                self.blocks[block_id] = _Block(block.get("type", ""), block.get("data"))
                if block.get("type") == "text":
                    self._maybe_record_text_first_token(block.get("data"))
            return

        if event_type == "updateBlock" and isinstance(event.get("blockId"), str):
            block_id = event["blockId"]
            current = self.blocks.get(block_id)
            if current is None:
                return
            for op in event.get("patch") or []:
                if not isinstance(op, dict):
                    continue
                if op.get("path") == "/data" and op.get("op") in {"replace", "add"}:
                    current.data = op.get("value")
                    if current.type == "text":
                        self._maybe_record_text_first_token(op.get("value"))
            return

        if event_type == "partial":
            self.engine_reason = event.get("reason") or self.engine_reason
            partial_blob = event.get("partial")
            if not isinstance(partial_blob, dict):
                partial_blob = {}
            answer = event.get("answer")
            if not isinstance(answer, str):
                answer = partial_blob.get("answer")
            if not isinstance(answer, str):
                answer = ""
            self._maybe_record_text_first_token(answer)
            self.answer = answer
            self.sources = _parse_sources(
                event.get("sources")
                if isinstance(event.get("sources"), list)
                else partial_blob.get("sources")
            )
            state = event.get("state")
            if state == "insufficient_evidence" and not answer and not self.sources:
                self.status = "insufficient_evidence"
                self.degradation_reason = "insufficient_evidence"
            else:
                self.status = "partial"
                self.degradation_reason = "partial"
            blocked_metadata = event.get("blocked_metadata")
            if isinstance(blocked_metadata, list):
                for entry in blocked_metadata:
                    if not isinstance(entry, dict):
                        continue
                    url = str(entry.get("url") or "").strip()
                    if not url:
                        continue
                    bt = _block_type_for(entry.get("block_type"))
                    self.blocked_url_coverage[bt.value] = (
                        self.blocked_url_coverage.get(bt.value, 0) + 1
                    )
                    metrics.record_blocked_url_coverage(block_type=bt)
            return

        if event_type == "insufficientEvidence":
            self.engine_reason = event.get("reason") or self.engine_reason
            partial_blob = event.get("partial")
            if not isinstance(partial_blob, dict):
                partial_blob = {}
            partial_answer = partial_blob.get("answer")
            if not isinstance(partial_answer, str):
                partial_answer = ""
            self._maybe_record_text_first_token(partial_answer)
            partial_sources = _parse_sources(partial_blob.get("sources"))
            if partial_answer or partial_sources:
                self.status = "partial"
                self.answer = partial_answer
                self.sources = partial_sources
                self.degradation_reason = "insufficient_evidence"
            else:
                self.status = "insufficient_evidence"
                self.degradation_reason = "insufficient_evidence"
            blocked_metadata = event.get("blocked_metadata")
            if isinstance(blocked_metadata, list):
                for entry in blocked_metadata:
                    if not isinstance(entry, dict):
                        continue
                    url = str(entry.get("url") or "").strip()
                    if not url:
                        continue
                    bt = _block_type_for(entry.get("block_type"))
                    self.blocked_url_coverage[bt.value] = (
                        self.blocked_url_coverage.get(bt.value, 0) + 1
                    )
                    metrics.record_blocked_url_coverage(block_type=bt)
            return

        if event_type == "heartbeat":
            self.saw_heartbeat = True
            return

        if event_type == "progress":
            self.request_accepted_at = (
                _parse_engine_ts(event.get("requestAcceptedAt"))
                or self.request_accepted_at
            )
            self.first_progress_at = (
                _parse_engine_ts(event.get("firstProgressAt")) or self.first_progress_at
            )
            self.evidence_ready_at = (
                _parse_engine_ts(event.get("evidenceReadyAt")) or self.evidence_ready_at
            )
            first_factual_chunk_at = _parse_engine_ts(event.get("firstFactualChunkAt"))
            if first_factual_chunk_at is not None:
                self.first_factual_chunk_at = first_factual_chunk_at
                self._record_first_token()
            emit_progress(
                event.get("phase", "progress"),
                message=event.get("message") or None,
                current=_to_int(event.get("current")),
                total=_to_int(event.get("total")),
                unit=event.get("unit") or None,
            )
            return

        if event_type == "evidence_ready":
            self.evidence_ready_at = (
                _parse_engine_ts(event.get("evidenceReadyAt")) or self.evidence_ready_at
            )
            emit_progress(
                "evidence_ready",
                message=event.get("message") or "Evidence ready",
                current=_to_int(event.get("current")),
                total=_to_int(event.get("total")),
                unit=event.get("unit") or None,
            )
            return

        if event_type == "synthesizing":
            emit_progress(
                "synthesizing",
                message=event.get("message") or "Synthesizing answer",
                current=_to_int(event.get("current")),
                total=_to_int(event.get("total")),
                unit=event.get("unit") or None,
            )
            return

        if event_type == "researchComplete":
            emit_progress(
                "research_complete",
                message=event.get("message") or "Research complete",
                current=_to_int(event.get("current")),
                total=_to_int(event.get("total")),
                unit=event.get("unit") or None,
            )
            return

        if event_type not in {"block", "updateBlock", "done", "usage"}:
            self.saw_unknown = True
            return

    def _extract_cost(self, event: dict[str, Any]) -> None:
        """Extract ``costDollars`` and related metadata from an engine event.

        The first valid ``costDollars`` wins. ChainLens 42-1 places it inside
        the terminal ``done`` frame's ``usage`` object, but we also accept the
        older top-level location and a standalone ``usage`` event defensively.
        Later events are ignored so ``done`` does not overwrite an earlier
        ``usage`` and vice versa. Malformed/negative values are ignored.
        """
        if self.cost_dollars is not None:
            return

        usage = event.get("usage")
        if not isinstance(usage, dict):
            usage = None

        raw_cost = None
        if usage is not None:
            raw_cost = usage.get("costDollars")
        if raw_cost is None:
            raw_cost = event.get("costDollars")
        if raw_cost is None:
            return

        if not isinstance(raw_cost, (int, float)):
            logger.warning("Ignoring malformed costDollars in SSE event: %r", raw_cost)
            return
        if raw_cost < 0:
            logger.warning("Ignoring negative costDollars: %r", raw_cost)
            return
        if raw_cost != raw_cost:  # NaN
            logger.warning("Ignoring NaN costDollars")
            return

        self.cost_dollars = float(raw_cost)
        self.resolved_mode = (
            (usage.get("resolvedMode") if usage else None)
            or event.get("resolvedMode")
            or event.get("resolved_mode")
            or self.resolved_mode
        )

        estimated = (usage.get("estimated") if usage else None) or event.get(
            "estimated"
        )
        self.estimated = estimated if isinstance(estimated, bool) else None

        tokens = (usage.get("tokens") if usage else None) or event.get("tokens")
        total = None
        if isinstance(tokens, dict):
            total = tokens.get("total")
        if usage is not None:
            total = total or usage.get("totalTokens")
        if isinstance(total, int):
            self.tokens_total = total

        if self.estimated is True:
            self.cost_basis = "estimated"
        else:
            self.cost_basis = "actual"

    def _cost_micros(self) -> int | None:
        """Convert stored ``cost_dollars`` to micro-USD with half-up rounding."""
        if self.cost_dollars is None:
            return None
        micros = (
            Decimal(str(self.cost_dollars)) * Decimal("1000000")
        ).to_integral_value(ROUND_HALF_UP)
        return int(micros)

    def finalize(self) -> ResearchOutput:
        """Return the parsed research output after all lines have been fed."""
        if self.error_msg:
            raise ChainLensError(self.error_msg, code="CHAINLENS_UPSTREAM_ERROR")

        text_parts: list[str] = []
        block_sources: list[Source] = []
        for block in self.blocks.values():
            if block.type == "text" and isinstance(block.data, str):
                text_parts.append(block.data)
            elif block.type == "source" and isinstance(block.data, list):
                block_sources.extend(_parse_sources(block.data))

        if not self.answer and not self.sources:
            self.answer = "\n\n".join(text_parts).strip()
            self.sources = block_sources

        if self.status == "complete" and not self.answer and not self.sources:
            if self.saw_done or self.saw_heartbeat or self.saw_unknown:
                self.status = "engine_unavailable"
                self.degradation_reason = "stream_incomplete"
            else:
                self.status = "timeout"
                self.degradation_reason = "stream_incomplete"

        return ResearchOutput(
            answer=self.answer,
            sources=self.sources,
            chat_id=self.chat_id,
            web_url=self.web_url,
            status=self.status,
            degradation_reason=self.degradation_reason,
            engine_reason=self.engine_reason,
            saw_heartbeat=self.saw_heartbeat,
            blocked_url_coverage_by_block_type=self.blocked_url_coverage,
            cost_micros=self._cost_micros(),
            cost_basis=self.cost_basis,
            resolved_mode=self.resolved_mode,
            tokens_total=self.tokens_total,
            first_token_time_ms=self.first_token_time_ms,
        )


def _parse_sse(
    source: str | AsyncIterator[str] | AsyncIterable[str],
    start_time: float | None = None,
) -> ResearchOutput | Awaitable[ResearchOutput]:
    """Parse the ChainLens block-based SSE stream into a research output.

    The wire protocol uses data-only SSE frames (one JSON payload per
    ``data:`` line, no ``event:`` line):
    - ``data: [DONE]`` / empty data lines are ignored.
    - ``type: block`` creates/replaces a block id.
    - ``type: updateBlock`` applies RFC6902-style patches (we only honor
      ``replace``/``add`` on ``/data``).
    - ``type: done`` carries chatId and webUrl metadata and marks the
      terminal frame.
    - ``type: error`` surfaces as a ``ChainLensError``.
    - ``type: progress`` is relayed to the run progress bus (T4).

    9.1a additions: the engine can also emit ``partial`` and
    ``insufficientEvidence`` data frames (with an embedded ``reason`` and
    optional ``blocked_metadata``). Heartbeats and unknown event types are
    tolerated without raising.

    ``source`` may be a complete response string (for tests and local parsing)
    or an async iterator of lines from a streaming response.
    """
    parser = _SSEParser(start_time=start_time)

    if isinstance(source, str):
        for raw_line in source.splitlines():
            parser.feed_line(raw_line)
        return parser.finalize()

    if isinstance(source, (AsyncIterator, AsyncIterable)) or hasattr(
        source, "__aiter__"
    ):

        async def _consume() -> ResearchOutput:
            async for raw_line in source:
                parser.feed_line(raw_line)
            return parser.finalize()

        return _consume()

    raise TypeError(
        f"_parse_sse expects str or an async iterator of lines, got {type(source)!r}"
    )


def _engine_unavailable(reason: str) -> ResearchOutput:
    """Return a typed degradation result for an upstream HTTP fault."""
    return ResearchOutput(status="engine_unavailable", degradation_reason=reason)


async def _call_chainlens(payload: ResearchInput) -> ResearchOutput:
    """Make the upstream ChainLens research call and parse the SSE response.

    The SSE body is parsed incrementally from ``response.aiter_lines()`` so
    that long research streams do not have to be buffered into one string.
    """
    if not config.CHAINLENS_API_KEY or not config.CHAINLENS_API_KEY.strip():
        logger.warning("CHAINLENS_API_KEY is not configured; degrading research.")
        return _engine_unavailable("not_configured")

    body: dict[str, Any] = {
        "query": payload.query,
        "optimizationMode": payload.mode,
        "tier": "research",
        "sources": payload.sources,
        "history": payload.history,
        "stream": True,
    }
    if payload.system_instructions:
        body["systemInstructions"] = payload.system_instructions
    if payload.chat_id:
        body["chatId"] = payload.chat_id

    logger.info("Calling ChainLens research")
    start_time = time.perf_counter()

    async with (
        httpx.AsyncClient(
            timeout=config.CHAINLENS_REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
        ) as client,
        client.stream(
            "POST",
            f"{config.CHAINLENS_API_URL}/api/v1/search",
            headers={
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "Authorization": f"Bearer {config.CHAINLENS_API_KEY}",
            },
            json=body,
        ) as response,
    ):
        if response.status_code == 401:
            return _engine_unavailable("auth_failed")
        if response.status_code == 403:
            return _engine_unavailable("auth_failed")
        if response.status_code == 429:
            return _engine_unavailable("rate_limited")
        if response.status_code >= 500:
            return _engine_unavailable("upstream_error")
        if response.status_code >= 400:
            return _engine_unavailable("upstream_error")
        if response.status_code != 200:
            return _engine_unavailable("upstream_error")

        return await _parse_sse(response.aiter_lines(), start_time=start_time)


def _embedding_token_count(query: str) -> int | None:
    """Best-effort token count for the query-embedding call.

    Local sentence-transformer models report token counts via ``count_tokens``
    when available. Cloud embedding models may not expose this; fall back to
    None and record cost as ``n/a``. The cost of the local call is treated as
    zero infra; cloud calls would be metered by the provider and added here.
    """
    inst = getattr(config, "embedding_model_instance", None)
    if inst is None:
        return None
    count_fn = getattr(inst, "count_tokens", None)
    if count_fn is None:
        return None
    try:
        return int(count_fn(query))
    except Exception:
        logger.debug("embedding_model.count_tokens failed for telemetry")
        return None


async def _kb_fallback(
    *,
    query: str,
    scope: Any,
    top_k: int,
    session: Any,
    workspace_id: int,
) -> list[Any]:
    """Knowledge-base fallback: run hybrid chunk search within the workspace."""
    from app.agents.chat.multi_agent_chat.shared.retrieval.hybrid_search import (
        search_chunks,
    )
    from app.agents.chat.multi_agent_chat.shared.retrieval.models import SearchScope

    return await search_chunks(
        session,
        workspace_id=workspace_id,
        query=query,
        scope=scope if scope is not None else SearchScope(),
        top_k=top_k,
    )


async def execute_with_context(
    payload: ResearchInput,
    ctx: CapabilityContext | None,
    *,
    search_fn: SearchFn,
    fallback_fn: Callable[..., Awaitable[list[Any]]] = _kb_fallback,
    top_k: int = 6,
) -> ResearchOutput:
    """Run research and, when the engine fails, fall back to workspace KB.

    ``fallback_fn`` accepts keyword-only ``query, scope, top_k, session,
    workspace_id`` so it is compatible with :func:`_kb_fallback` and with
    unit tests that inject a fake fallback.
    """
    started = time.perf_counter()
    degradation_reason: str | None = None
    engine_reason: str | None = None
    output: ResearchOutput | None = None

    try:
        output = await search_fn(payload)
        if output.status == "engine_unavailable":
            degradation_reason = output.degradation_reason
            engine_reason = output.engine_reason
    except httpx.TimeoutException:
        degradation_reason = "timeout"
    except httpx.RequestError:
        degradation_reason = "unreachable"
    except ChainLensError as exc:
        degradation_reason = "upstream_error"
        engine_reason = str(exc)
    except Exception:
        logger.exception("ChainLens research failed")
        degradation_reason = "upstream_error"

    if output is None:
        output = ResearchOutput(
            status="engine_unavailable",
            degradation_reason=degradation_reason,
            engine_reason=engine_reason,
        )

    fallback_attempted = False
    fallback_used = False
    fallback_hit_count = 0

    # Only engine failures and stream timeouts trigger the KB fallback.
    # Explicit ``insufficient_evidence`` or engine ``partial`` are not
    # silently backfilled; they preserve the engine's own conclusion.
    kb_fallback_duration_ms: int | None = None
    kb_fallback_embedding_tokens: int | None = None

    if output.status in ("engine_unavailable", "timeout") and (
        ctx is not None and ctx.session is not None
    ):
        fallback_attempted = True
        clamped_top_k = max(1, min(top_k, 5))
        kb_fallback_embedding_tokens = _embedding_token_count(payload.query)
        kb_fallback_embedding_cost_basis = (
            "local" if kb_fallback_embedding_tokens is not None else "n/a"
        )
        kb_fallback_started = time.perf_counter()
        try:
            hits = await fallback_fn(
                query=payload.query,
                scope=None,
                top_k=clamped_top_k,
                session=ctx.session,
                workspace_id=ctx.workspace_id,
            )
            if hits:
                fallback_sources: list[Source] = []
                for hit in hits:
                    if len(fallback_sources) >= clamped_top_k:
                        break
                    document_id = hit.document_id
                    title = hit.title or "KB Document"
                    for chunk in hit.chunks:
                        if len(fallback_sources) >= clamped_top_k:
                            break
                        chunk_id = chunk.chunk_id
                        fallback_sources.append(
                            Source(
                                title=title,
                                url=f"nowing://documents/{document_id}/chunks/{chunk_id}",
                                content=chunk.content,
                                source_type="kb",
                                document_id=document_id,
                                chunk_id=chunk_id,
                            )
                        )
                fallback_hit_count = len(fallback_sources)
                if fallback_hit_count:
                    fallback_used = True
                    summary_lines = [
                        "Deep research engine is unavailable. Showing workspace knowledge base results:"
                    ]
                    for src in fallback_sources:
                        summary_lines.append(
                            f"- {src.title}: {src.content or '(no preview)'}"
                        )
                    output = ResearchOutput(
                        status="partial",
                        answer="\n".join(summary_lines),
                        sources=fallback_sources,
                        engine_reason=output.engine_reason or output.degradation_reason,
                        degraded=True,
                        degradation_reason="fallback_kb_hits",
                        kb_fallback_embedding_tokens=kb_fallback_embedding_tokens,
                        kb_fallback_embedding_cost_basis=kb_fallback_embedding_cost_basis,
                        kb_fallback_embedding_cost_micros=0,
                        kb_fallback_search_cost_micros=0,
                    )
                else:
                    output = ResearchOutput(
                        status="engine_unavailable",
                        degradation_reason="fallback_kb_empty",
                        engine_reason=output.engine_reason or output.degradation_reason,
                        kb_fallback_embedding_tokens=kb_fallback_embedding_tokens,
                        kb_fallback_embedding_cost_basis=kb_fallback_embedding_cost_basis,
                        kb_fallback_embedding_cost_micros=0,
                        kb_fallback_search_cost_micros=0,
                    )
            else:
                output = ResearchOutput(
                    status="engine_unavailable",
                    degradation_reason="fallback_kb_empty",
                    engine_reason=output.engine_reason or output.degradation_reason,
                    kb_fallback_embedding_tokens=kb_fallback_embedding_tokens,
                    kb_fallback_embedding_cost_basis=kb_fallback_embedding_cost_basis,
                    kb_fallback_embedding_cost_micros=0,
                    kb_fallback_search_cost_micros=0,
                )
        except (SQLAlchemyError, RuntimeError, OSError, httpx.RequestError):
            logger.exception("KB fallback failed")
            output = ResearchOutput(
                status="engine_unavailable",
                degradation_reason="fallback_kb_error",
                engine_reason=output.degradation_reason or output.engine_reason,
                kb_fallback_embedding_tokens=kb_fallback_embedding_tokens,
                kb_fallback_embedding_cost_basis=kb_fallback_embedding_cost_basis,
                kb_fallback_embedding_cost_micros=0,
                kb_fallback_search_cost_micros=0,
            )
        finally:
            kb_fallback_duration_ms = int(
                (time.perf_counter() - kb_fallback_started) * 1000
            )
            # Record duration even on empty or failed fallback so telemetry
            # shows the attempt cost.
            object.__setattr__(
                output, "kb_fallback_duration_ms", kb_fallback_duration_ms
            )

    if output.degraded:
        metrics.record_chainlens_degradation(
            degradation_reason=output.degradation_reason,
            final_status=output.status,
            fallback_attempted=fallback_attempted,
            fallback_used=fallback_used,
            fallback_hit_count=output.fallback_hit_count or 0,
            engine_reason=output.engine_reason,
        )
        if fallback_hit_count:
            metrics.record_kb_fallback_hit_count(fallback_hit_count)

    if output.mode_requested is None:
        output.mode_requested = payload.mode
    if output.duration_ms is None:
        output.duration_ms = int((time.perf_counter() - started) * 1000)
    if output.duration_ms is not None:
        metrics.record_chainlens_latency(
            duration_ms=output.duration_ms,
            metric="e2e",
            mode=output.mode_requested or payload.mode,
        )
    if output.first_token_time_ms is not None:
        metrics.record_chainlens_latency(
            duration_ms=output.first_token_time_ms,
            metric="ttfb",
            mode=output.mode_requested or payload.mode,
        )
    return output


def build_research_executor(
    search_fn: SearchFn | None = None,
) -> Executor:
    """Build the ``chainlens.research`` executor."""
    search = search_fn or _call_chainlens

    async def execute(
        payload: ResearchInput, ctx: CapabilityContext | None = None
    ) -> ResearchOutput:
        emit_progress("starting", "Researching...")
        output = await execute_with_context(
            payload,
            ctx,
            search_fn=search,
            fallback_fn=_kb_fallback,
            top_k=5,
        )
        emit_progress("done", f"ChainLens returned {len(output.sources)} source(s)")
        return output

    return execute
