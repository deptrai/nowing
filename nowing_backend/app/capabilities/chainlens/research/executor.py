"""``chainlens.research`` executor: call ChainLens ``POST /api/v1/search``.

When ChainLens is unavailable, misconfigured, or returns partial/insufficient
results, the executor degrades gracefully and optionally falls back to the
workspace knowledge base so self-hosted installs remain useful.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Literal

import httpx

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


_SourceDict = dict[str, Any]


def _block_type_for(raw: str | None) -> BlockType:
    """Map a raw block-type string to the classifier enum; unknown → UNKNOWN."""
    if not raw:
        return BlockType.UNKNOWN
    try:
        return BlockType(raw)
    except ValueError:
        return BlockType.UNKNOWN


def _parse_sources(raw_sources: list[_SourceDict] | None) -> list[Source]:
    """Normalize a list of ChainLens source blobs into typed ``Source`` objects."""
    if not raw_sources:
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


def _parse_sse(raw: str) -> ResearchOutput:
    """Parse the ChainLens block-based SSE stream into a research output.

    The wire protocol is documented in ``apps/mcp/src/lib/apiClient.ts``:
    - ``event: error`` followed by a ``data:`` line -> surface error.
    - ``data: [DONE]`` / empty data lines are ignored.
    - ``type: block`` creates/replaces a block id.
    - ``type: updateBlock`` applies RFC6902-style patches (we only honor
      ``replace``/``add`` on ``/data``).
    - ``type: done`` carries chatId and webUrl metadata.

    9.1a additions: the engine can also emit ``partial`` and
    ``insufficientEvidence`` data frames (with an embedded ``reason`` and
    optional ``blocked_metadata``). Heartbeats and unknown event types are
    tolerated without raising.
    """
    blocks: dict[str, _Block] = {}
    error_msg: str | None = None
    chat_id: str | None = None
    web_url: str | None = None
    saw_done = False
    saw_heartbeat = False
    saw_unknown = False
    pending_event_type = "message"

    status: _ResearchStatus = "complete"
    answer = ""
    sources: list[Source] = []
    degradation_reason: str | None = None
    engine_reason: str | None = None
    blocked_url_coverage: dict[str, int] = {}

    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line:
            pending_event_type = "message"
            continue

        if line.startswith("event:"):
            pending_event_type = line[len("event:") :].strip()
            continue

        if not line.startswith("data:"):
            continue
        payload = line[len("data:") :].strip()

        if not payload or payload == "[DONE]":
            continue

        if pending_event_type == "error":
            error_msg = payload
            continue

        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            logger.debug("Ignoring malformed SSE JSON payload: %r", payload[:200])
            continue

        if not isinstance(event, dict):
            logger.debug("Ignoring non-object SSE event: %r", type(event))
            continue

        event_type = event.get("type")

        if event_type == "error":
            data = event.get("data")
            error_msg = (
                data
                if isinstance(data, str)
                else (json.dumps(data) if data is not None else "Upstream SSE error")
            )
            continue

        if event_type == "done":
            saw_done = True
            chat_id = event.get("chatId") or event.get("chat_id") or chat_id
            web_url = event.get("webUrl") or web_url
            continue

        if event_type == "block" and isinstance(event.get("block"), dict):
            block = event["block"]
            block_id = block.get("id")
            if isinstance(block_id, str):
                blocks[block_id] = _Block(block.get("type", ""), block.get("data"))
            continue

        if event_type == "updateBlock" and isinstance(event.get("blockId"), str):
            block_id = event["blockId"]
            current = blocks.get(block_id)
            if current is None:
                continue
            for op in event.get("patch") or []:
                if not isinstance(op, dict):
                    continue
                if op.get("path") == "/data" and op.get("op") in {"replace", "add"}:
                    current.data = op.get("value")
            continue

        if event_type == "partial":
            status = "partial"
            degradation_reason = "partial"
            engine_reason = event.get("reason") or engine_reason
            answer = (
                event.get("answer")
                or (event.get("partial") or {}).get("answer")
                or ""
            )
            sources = _parse_sources(
                event.get("sources") or (event.get("partial") or {}).get("sources")
            )
            for entry in event.get("blocked_metadata") or []:
                if not isinstance(entry, dict):
                    continue
                url = str(entry.get("url") or "").strip()
                if not url:
                    continue
                bt = _block_type_for(entry.get("block_type"))
                blocked_url_coverage[bt.value] = (
                    blocked_url_coverage.get(bt.value, 0) + 1
                )
                metrics.record_blocked_url_coverage(url=url, block_type=bt)
            continue

        if event_type == "insufficientEvidence":
            engine_reason = event.get("reason") or engine_reason
            partial_blob = event.get("partial") or {}
            partial_answer = partial_blob.get("answer") or ""
            partial_sources = _parse_sources(partial_blob.get("sources"))
            if partial_answer or partial_sources:
                status = "partial"
                answer = partial_answer
                sources = partial_sources
                degradation_reason = "insufficient_evidence"
            else:
                status = "insufficient_evidence"
                degradation_reason = "insufficient_evidence"
            for entry in event.get("blocked_metadata") or []:
                if not isinstance(entry, dict):
                    continue
                url = str(entry.get("url") or "").strip()
                if not url:
                    continue
                bt = _block_type_for(entry.get("block_type"))
                blocked_url_coverage[bt.value] = (
                    blocked_url_coverage.get(bt.value, 0) + 1
                )
                metrics.record_blocked_url_coverage(url=url, block_type=bt)
            continue

        if event_type == "heartbeat":
            saw_heartbeat = True
            continue

        if event_type not in {"block", "updateBlock", "done"}:
            saw_unknown = True
            continue

    if error_msg:
        raise ChainLensError(error_msg, code="CHAINLENS_UPSTREAM_ERROR")

    text_parts: list[str] = []
    block_sources: list[Source] = []
    for block in blocks.values():
        if block.type == "text" and isinstance(block.data, str):
            text_parts.append(block.data)
        elif block.type == "source" and isinstance(block.data, list):
            block_sources.extend(_parse_sources(block.data))

    if not answer and not sources:
        answer = "\n\n".join(text_parts).strip()
        sources = block_sources

    if status == "complete" and not answer and not sources:
        if saw_done:
            if saw_unknown or saw_heartbeat:
                status = "engine_unavailable"
                degradation_reason = "stream_incomplete"
            else:
                status = "insufficient_evidence"
        elif saw_heartbeat or saw_unknown:
            status = "engine_unavailable"
            degradation_reason = "stream_incomplete"
        else:
            status = "timeout"
            degradation_reason = "stream_incomplete"

    return ResearchOutput(
        answer=answer,
        sources=sources,
        chat_id=chat_id,
        web_url=web_url,
        status=status,
        degradation_reason=degradation_reason,
        engine_reason=engine_reason,
        saw_heartbeat=saw_heartbeat,
        blocked_url_coverage_by_block_type=blocked_url_coverage,
    )


def _engine_unavailable(reason: str) -> ResearchOutput:
    """Return a typed degradation result for an upstream HTTP fault."""
    return ResearchOutput(status="engine_unavailable", degradation_reason=reason)


async def _call_chainlens(payload: ResearchInput) -> ResearchOutput:
    """Make the upstream ChainLens research call and parse the SSE response."""
    if not config.CHAINLENS_API_KEY or not config.CHAINLENS_API_KEY.strip():
        logger.warning("CHAINLENS_API_KEY is not configured; degrading research.")
        return _engine_unavailable("not_configured")

    body: dict[str, Any] = {
        "query": payload.query,
        "optimizationMode": payload.mode,
        "tier": "research",
        "sources": payload.sources,
        "history": payload.history,
        "stream": False,
    }
    if payload.system_instructions:
        body["systemInstructions"] = payload.system_instructions
    if payload.chat_id:
        body["chatId"] = payload.chat_id

    url = f"{config.CHAINLENS_API_URL}/api/v1/search"
    logger.info("Calling ChainLens research at %s", url)

    async with httpx.AsyncClient(
        timeout=config.CHAINLENS_REQUEST_TIMEOUT_SECONDS,
        follow_redirects=True,
    ) as client:
        response = await client.post(
            url,
            headers={
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "Authorization": f"Bearer {config.CHAINLENS_API_KEY}",
            },
            json=body,
        )

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

    return _parse_sse(response.text)


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
    top_k: int = 5,
) -> ResearchOutput:
    """Run research and, when the engine fails, fall back to workspace KB.

    ``fallback_fn`` accepts keyword-only ``query, scope, top_k, session,
    workspace_id`` so it is compatible with :func:`_kb_fallback` and with
    unit tests that inject a fake fallback.
    """
    degradation_reason: str | None = None
    engine_reason: str | None = None

    try:
        output = await search_fn(payload)
        if output.status == "engine_unavailable":
            degradation_reason = output.degradation_reason
            engine_reason = output.engine_reason
    except httpx.TimeoutException:
        degradation_reason = "timeout"
        output = None
    except httpx.RequestError:
        degradation_reason = "unreachable"
        output = None
    except ChainLensError:
        degradation_reason = "upstream_error"
        engine_reason = None
        output = None
    except Exception:
        logger.exception("ChainLens research failed for query: %s", payload.query[:80])
        degradation_reason = "upstream_error"
        output = None

    if output is None:
        output = ResearchOutput(
            status="engine_unavailable",
            degradation_reason=degradation_reason,
            engine_reason=engine_reason,
        )

    fallback_attempted = False
    fallback_used = False
    fallback_hit_count = 0

    if output.status in (
        "engine_unavailable",
        "insufficient_evidence",
        "timeout",
    ) and (ctx is not None and ctx.session is not None):
        fallback_attempted = True
        try:
            hits = await fallback_fn(
                query=payload.query,
                scope=None,
                top_k=min(top_k, 5),
                session=ctx.session,
                workspace_id=ctx.workspace_id,
            )
            if hits:
                fallback_sources: list[Source] = []
                for hit in hits:
                    document_id = hit.document_id
                    title = hit.title or "KB Document"
                    for chunk in hit.chunks:
                        chunk_id = chunk.chunk_id
                        content = chunk.content
                        fallback_sources.append(
                            Source(
                                title=title,
                                url=f"nowing://documents/{document_id}/chunks/{chunk_id}",
                                content=content,
                                source_type="kb",
                                document_id=document_id,
                                chunk_id=chunk_id,
                            )
                        )
                fallback_hit_count = len(fallback_sources)
                if fallback_hit_count:
                    fallback_used = True
                    output = ResearchOutput(
                        status="partial",
                        answer="Deep research engine is unavailable; showing workspace knowledge base results.",
                        sources=fallback_sources,
                        engine_reason=output.degradation_reason
                        or output.engine_reason,
                        degraded=True,
                        degradation_reason="fallback_kb_hits",
                        fallback_hit_count=fallback_hit_count,
                    )
                else:
                    output = ResearchOutput(
                        status="engine_unavailable",
                        degradation_reason="fallback_kb_empty",
                        engine_reason=output.degradation_reason
                        or output.engine_reason,
                    )
            else:
                output = ResearchOutput(
                    status="engine_unavailable",
                    degradation_reason="fallback_kb_empty",
                    engine_reason=output.degradation_reason
                    or output.engine_reason,
                )
        except Exception:
            logger.exception(
                "KB fallback failed for query: %s", payload.query[:80]
            )
            output = ResearchOutput(
                status="engine_unavailable",
                degradation_reason="fallback_kb_error",
                engine_reason=output.degradation_reason
                or output.engine_reason,
            )

    if output.degraded:
        metrics.record_chainlens_degradation(
            degradation_reason=output.degradation_reason,
            final_status=output.status,
            fallback_attempted=fallback_attempted,
            fallback_used=fallback_used,
            fallback_hit_count=output.fallback_hit_count or 0,
            workspace_id=ctx.workspace_id if ctx else None,
            query=payload.query,
            api_key=config.CHAINLENS_API_KEY or "",
            answer=output.answer,
        )
        if fallback_hit_count:
            metrics.record_kb_fallback_hit_count(
                fallback_hit_count,
                workspace_id=ctx.workspace_id if ctx else None,
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
        emit_progress("starting", f"Researching: {payload.query[:80]}...")
        try:
            output = await execute_with_context(
                payload,
                ctx,
                search_fn=search,
                fallback_fn=_kb_fallback,
                top_k=5,
            )
        except Exception:
            logger.exception("ChainLens research failed for query: %s", payload.query[:80])
            output = ResearchOutput(
                status="engine_unavailable",
                degradation_reason="upstream_error",
            )
        emit_progress("done", f"ChainLens returned {len(output.sources)} source(s)")
        return output

    return execute
