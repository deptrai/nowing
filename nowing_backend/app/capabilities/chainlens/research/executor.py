"""``chainlens.research`` executor: call ChainLens ``POST /api/v1/search``.

When ChainLens is unavailable, misconfigured, or returns partial/insufficient
results, the executor degrades gracefully and optionally falls back to the
workspace knowledge base so self-hosted installs remain useful.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable
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
        "resolved_mode",
        "saw_done",
        "saw_heartbeat",
        "saw_unknown",
        "sources",
        "status",
        "tokens_total",
        "web_url",
    )

    def __init__(self) -> None:
        self.blocks: dict[str, _Block] = {}
        self.error_msg: str | None = None
        self.chat_id: str | None = None
        self.web_url: str | None = None
        self.saw_done = False
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

        if event_type not in {"block", "updateBlock", "done", "usage"}:
            self.saw_unknown = True
            return

    def _extract_cost(self, event: dict[str, Any]) -> None:
        """Extract ``costDollars`` and related metadata from an engine event.

        Overwrites any previous value so the last valid ``usage``/``done``
        event wins. Malformed/negative values are ignored and logged.
        """
        raw_cost = event.get("costDollars")
        if raw_cost is None:
            return
        if not isinstance(raw_cost, (int, float)):
            logger.warning(
                "Ignoring malformed costDollars in SSE event: %r", raw_cost
            )
            return
        if raw_cost < 0:
            logger.warning("Ignoring negative costDollars: %r", raw_cost)
            return
        if raw_cost != raw_cost:  # NaN
            logger.warning("Ignoring NaN costDollars")
            return

        self.cost_dollars = float(raw_cost)
        self.resolved_mode = (
            event.get("resolvedMode")
            or event.get("resolved_mode")
            or self.resolved_mode
        )
        self.estimated = event.get("estimated")

        tokens = event.get("tokens")
        if isinstance(tokens, dict):
            total = tokens.get("total")
            if isinstance(total, int):
                self.tokens_total = total

        if isinstance(self.estimated, bool) and self.estimated:
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
        )


def _parse_sse(
    source: str | AsyncIterator[str] | AsyncIterable[str],
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

    9.1a additions: the engine can also emit ``partial`` and
    ``insufficientEvidence`` data frames (with an embedded ``reason`` and
    optional ``blocked_metadata``). Heartbeats and unknown event types are
    tolerated without raising.

    ``source`` may be a complete response string (for tests and local parsing)
    or an async iterator of lines from a streaming response.
    """
    parser = _SSEParser()

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

    async with httpx.AsyncClient(
        timeout=config.CHAINLENS_REQUEST_TIMEOUT_SECONDS,
        follow_redirects=True,
    ) as client:
        response = await client.post(
            f"{config.CHAINLENS_API_URL}/api/v1/search",
            headers={
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "Authorization": f"Bearer {config.CHAINLENS_API_KEY}",
            },
            json=body,
            stream=True,
        )

        try:
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

            return await _parse_sse(response.aiter_lines())
        finally:
            await response.aclose()


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
    if output.status in ("engine_unavailable", "timeout") and (
        ctx is not None and ctx.session is not None
    ):
        fallback_attempted = True
        clamped_top_k = max(1, min(top_k, 5))
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
                    )
                else:
                    output = ResearchOutput(
                        status="engine_unavailable",
                        degradation_reason="fallback_kb_empty",
                        engine_reason=output.engine_reason or output.degradation_reason,
                    )
            else:
                output = ResearchOutput(
                    status="engine_unavailable",
                    degradation_reason="fallback_kb_empty",
                    engine_reason=output.engine_reason or output.degradation_reason,
                )
        except (SQLAlchemyError, RuntimeError, OSError, httpx.RequestError):
            logger.exception("KB fallback failed")
            output = ResearchOutput(
                status="engine_unavailable",
                degradation_reason="fallback_kb_error",
                engine_reason=output.degradation_reason or output.engine_reason,
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
