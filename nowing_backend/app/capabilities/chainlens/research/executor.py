"""``chainlens.research`` executor: call ChainLens ``POST /api/v1/search``.

When ChainLens is unavailable, misconfigured, or returns partial/insufficient
results, the executor degrades gracefully and optionally falls back to the
workspace knowledge base so self-hosted installs remain useful.

The incremental SSE parser lives in ``sse_parser.py``; its public surface is
re-exported here so existing ``executor`` imports keep working.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app.capabilities.chainlens.research.schemas import (
    ResearchInput,
    ResearchOutput,
    Source,
)
from app.capabilities.chainlens.research.sse_parser import (
    ChainLensError,
    _block_type_for,
    _parse_engine_ts,
    _parse_sources,
    _parse_sse,
    _SSEParser,
    _to_int,
)
from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.capabilities.core.types import CapabilityContext
from app.config import config
from app.observability import metrics
from app.services.chainlens.auth import ChainLensServiceAuth

logger = logging.getLogger(__name__)

SearchFn = Callable[[ResearchInput], Awaitable[ResearchOutput]]

__all__ = [
    "ChainLensError",
    "SearchFn",
    "_SSEParser",
    "_block_type_for",
    "_call_chainlens",
    "_engine_unavailable",
    "_kb_fallback",
    "_parse_engine_ts",
    "_parse_sources",
    "_parse_sse",
    "_to_int",
    "build_research_executor",
    "execute_with_context",
]


def _engine_unavailable(reason: str) -> ResearchOutput:
    """Return a typed degradation result for an upstream HTTP fault."""
    return ResearchOutput(status="engine_unavailable", degradation_reason=reason)


async def _call_chainlens(payload: ResearchInput) -> ResearchOutput:
    """Make the upstream ChainLens research call and parse the SSE response.

    The SSE body is parsed incrementally from ``response.aiter_lines()`` so
    that long research streams do not have to be buffered into one string.
    """
    auth = ChainLensServiceAuth(config_obj=config)
    if not auth.configured:
        logger.warning("ChainLens service token not configured; degrading research.")
        return _engine_unavailable("not_configured")

    body: dict[str, Any] = {
        "query": payload.query,
        "optimizationMode": payload.mode,
        "tier": payload.tier,
        "sources": payload.sources,
        "history": payload.history,
        "stream": True,
    }
    if payload.system_instructions:
        body["systemInstructions"] = payload.system_instructions
    if payload.chat_id:
        body["chatId"] = payload.chat_id
    if payload.output:
        body["output"] = payload.output
    if payload.output_schema:
        body["outputSchema"] = payload.output_schema

    workspace_id = payload.workspace_id or 0
    url = f"{config.CHAINLENS_API_URL}/api/v1/search"
    timeout = config.CHAINLENS_REQUEST_TIMEOUT_SECONDS

    logger.info("Calling ChainLens research")
    start_time = time.perf_counter()

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        for attempt in range(2):
            headers = auth.get_outbound_headers(
                workspace_id, content_type="application/json"
            )
            headers["Accept"] = "text/event-stream"
            async with client.stream(
                "POST",
                url,
                headers=headers,
                json=body,
            ) as response:
                if response.status_code == 401 and attempt == 0:
                    rotated = auth.rotate(
                        workspace_id=workspace_id, reason="401_response"
                    )
                    if rotated:
                        continue

                if response.status_code in (401, 403):
                    failure_reason = (
                        "rotation_failed" if attempt > 0 else "invalid_token"
                    )
                    metrics.record_chainlens_auth_failed(
                        workspace_id=workspace_id,
                        reason=failure_reason,
                    )
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

    return _engine_unavailable("upstream_error")


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

    if ctx is not None and payload.workspace_id is None:
        payload.workspace_id = ctx.workspace_id

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
    except Exception as exc:
        if isinstance(exc, asyncio.CancelledError):
            raise
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
        except Exception as exc:
            if isinstance(exc, asyncio.CancelledError):
                raise
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
            kb_fallback_duration_ms = max(
                0, int((time.perf_counter() - kb_fallback_started) * 1000)
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
