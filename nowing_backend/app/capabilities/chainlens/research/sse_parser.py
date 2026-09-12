"""Incremental SSE parser for the ChainLens ``POST /api/v1/search`` stream.

Split from ``executor.py``: feed each ``data:`` line as it arrives and call
:meth:`_SSEParser.finalize` once the stream ends. This keeps memory bounded
for long research streams.
"""

from __future__ import annotations

import json
import logging
import math
import time
from collections.abc import AsyncIterable, AsyncIterator, Awaitable
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal

from app.capabilities.chainlens.research.schemas import (
    ResearchOutput,
    Source,
)
from app.capabilities.core.progress import emit_progress
from app.exceptions import ExternalServiceError
from app.observability import metrics
from app.services.chainlens.auth import ChainLensServiceAuth
from app.utils.crawl.classifier import BlockType

logger = logging.getLogger(__name__)

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
    if value is None:
        return None
    if isinstance(value, bool):
        logger.warning("Ignoring bool progress counter: %r", value)
        return None
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, float) and value.is_integer() and value >= 0:
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    logger.warning("Ignoring malformed progress counter: %r", value)
    return None


def _parse_engine_ts(value: Any) -> int | None:
    """Parse an engine timestamp to epoch milliseconds.

    Accepts ISO-8601 strings or numeric epoch-millisecond values.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        logger.warning("Ignoring bool engine timestamp: %r", value)
        return None
    if isinstance(value, (int, float)):
        if not math.isfinite(value) or value < 0:
            logger.warning("Ignoring non-finite/negative engine timestamp: %r", value)
            return None
        return int(value)
    if not isinstance(value, str):
        logger.warning("Ignoring malformed engine timestamp: %r", value)
        return None
    try:
        # ponytail: fromisoformat handles 'Z' in Python 3.11+; fallback for older versions.
        ts = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.UTC)
        return int(dt.timestamp() * 1000)
    except Exception:
        logger.warning("Ignoring unparseable engine timestamp: %r", value)
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
        "cost_breakdown",
        "cost_dollars",
        "cost_source",
        "degradation_reason",
        "engine_reason",
        "error_msg",
        "estimated",
        "evidence_ready_at",
        "first_factual_chunk_at",
        "first_progress_at",
        "first_token_time_ms",
        "gap_fill_needed",
        "insufficient_evidence_flag",
        "model",
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
        "structured_output",
        "suggested_domains",
        "tokens_completion",
        "tokens_prompt",
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
        self.cost_source: str | None = None
        self.resolved_mode: str | None = None
        self.model: str | None = None
        self.estimated: bool | None = None
        self.tokens_total: int | None = None
        self.tokens_prompt: int | None = None
        self.tokens_completion: int | None = None
        self.first_token_time_ms: int | None = None
        self.request_accepted_at: int | None = None
        self.first_progress_at: int | None = None
        self.evidence_ready_at: int | None = None
        self.first_factual_chunk_at: int | None = None
        self.gap_fill_needed = False
        self.suggested_domains: list[str] = []
        self.insufficient_evidence_flag: bool | None = None
        self.cost_breakdown: dict[str, Any] | None = None
        self.structured_output: dict[str, Any] | None = None
        self.start_time = start_time

    def _record_first_token(self) -> None:
        """Capture TTFB and surface it as a progress event.

        Prefer the engine's own ``firstFactualChunkAt - requestAcceptedAt``
        milestones; fall back to the local Nowing clock only when the engine
        does not publish them.
        """
        if self.saw_first_token:
            return
        if (
            self.request_accepted_at is not None
            and self.first_factual_chunk_at is not None
        ):
            self.saw_engine_first_token = True
            self.saw_first_token = True
            _diff_ms = self.first_factual_chunk_at - self.request_accepted_at
            if _diff_ms < 0:
                logger.warning(
                    "Engine timestamps out of order: firstFactualChunkAt=%d < requestAcceptedAt=%d",
                    self.first_factual_chunk_at,
                    self.request_accepted_at,
                )
            self.first_token_time_ms = max(0, _diff_ms)
            emit_progress(
                "first_token",
                message="First token received",
                ttfb_ms=self.first_token_time_ms,
            )
            return
        if self.start_time is not None:
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

    def _set_structured_output(self, raw_output: Any) -> None:
        """Capture structured output from any SSE frame that carries one.

        ChainLens may emit the table as a JSON object, a JSON string, or inside
        an ``output`` block. We normalise all of those to a dict when possible.
        """
        if isinstance(raw_output, str):
            try:
                raw_output = json.loads(raw_output)
            except json.JSONDecodeError:
                return
        if isinstance(raw_output, dict):
            self.structured_output = raw_output

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

        if event_type == "gap-fill-needed":
            self.gap_fill_needed = True
            self.insufficient_evidence_flag = bool(
                self.insufficient_evidence_flag or event.get("insufficient_evidence")
            )
            domains = (
                event.get("suggested_domains")
                or event.get("suggestedDomains")
                or event.get("domains")
            )
            if isinstance(domains, list):
                self.suggested_domains = [
                    str(d) for d in domains if isinstance(d, str) and d
                ]
            self._extract_gap_fill(event)
            return

        if event_type in {"done", "usage"}:
            self.saw_done = True
            usage = event.get("usage")
            if not isinstance(usage, dict):
                usage = None
            self.chat_id = event.get("chatId") or event.get("chat_id") or self.chat_id
            self.web_url = event.get("webUrl") or self.web_url
            self._extract_cost(event)
            self._extract_gap_fill(event)
            self._set_structured_output(event.get("output"))
            return

        if event_type == "block" and isinstance(event.get("block"), dict):
            block = event["block"]
            block_id = block.get("id")
            if isinstance(block_id, str):
                self.blocks[block_id] = _Block(block.get("type", ""), block.get("data"))
                if block.get("type") == "text":
                    self._maybe_record_text_first_token(block.get("data"))
                if block.get("type") == "output":
                    self._set_structured_output(block.get("data"))
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
                    if current.type == "output":
                        self._set_structured_output(op.get("value"))
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
                self.insufficient_evidence_flag = True
            else:
                self.status = "partial"
                self.degradation_reason = "partial"
            self._extract_suggested_domains(event)
            self._extract_gap_fill(event)
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
                self.insufficient_evidence_flag = True
            self._extract_suggested_domains(event)
            self._extract_gap_fill(event)
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

        The terminal ``done`` frame's ``usage`` object is authoritative.
        Earlier ``usage`` events are recorded but may be overwritten by a
        later ``done`` event. Malformed, negative, and non-finite values are
        ignored.
        """
        event_type = event.get("type")
        if self.cost_dollars is not None and self.cost_source == "done":
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
        if not math.isfinite(raw_cost):
            logger.warning("Ignoring non-finite costDollars: %r", raw_cost)
            return
        if raw_cost < 0:
            logger.warning("Ignoring negative costDollars: %r", raw_cost)
            return

        self.cost_dollars = float(raw_cost)
        self.cost_source = event_type
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

        self.model = (
            (usage.get("model") if usage else None) or event.get("model") or self.model
        )

        tokens = (usage.get("tokens") if usage else None) or event.get("tokens")
        total = None
        if isinstance(tokens, dict):
            total = tokens.get("total")
        if usage is not None and total is None:
            total = usage.get("totalTokens")
        total_int = _to_int(total)
        if total_int is not None:
            self.tokens_total = total_int

        if usage is not None:
            prompt_int = _to_int(usage.get("promptTokens"))
            if prompt_int is not None:
                self.tokens_prompt = prompt_int
            completion_int = _to_int(usage.get("completionTokens"))
            if completion_int is not None:
                self.tokens_completion = completion_int

        if self.estimated is True:
            self.cost_basis = "estimated"
        else:
            self.cost_basis = "actual"

    def _extract_suggested_domains(self, event: dict[str, Any]) -> None:
        """Normalize ``suggested_domains`` from any SSE frame."""
        domains = (
            event.get("suggested_domains")
            or event.get("suggestedDomains")
            or event.get("domains")
        )
        if isinstance(domains, list) and domains:
            self.suggested_domains = [
                str(d) for d in domains if isinstance(d, str) and d
            ]
            self.gap_fill_needed = True

    def _extract_gap_fill(self, event: dict[str, Any]) -> None:
        """Extract gap-fill signals and per-operation cost breakdown.

        A terminal ``done`` frame may carry ``status: insufficient_evidence``
        and ``suggested_domains``; treat that as a gap-fill trigger per AC-1.
        ``insufficient_evidence_flag`` is set only when the engine itself
        reports ``insufficient_evidence``, not when only ``suggested_domains``
        are present.  If the engine supplies a ``costBreakdown`` map, keep it
        for later cost allocation (search / gap-fill / scraper).
        """
        event_status = event.get("status")
        if event_status == "insufficient_evidence":
            self.status = "insufficient_evidence"
            self.insufficient_evidence_flag = True

        domains = event.get("suggested_domains") or event.get("suggestedDomains")
        if isinstance(domains, list) and domains:
            self.suggested_domains = [
                str(d) for d in domains if isinstance(d, str) and d
            ]
            self.gap_fill_needed = True

        if event_status == "insufficient_evidence" or self.suggested_domains:
            self.gap_fill_needed = True

        breakdown = event.get("costBreakdown") or event.get("cost_breakdown")
        self.cost_breakdown = self._normalize_cost_breakdown(breakdown or event)

    def _normalize_cost_breakdown(self, data: dict[str, Any]) -> dict[str, Any] | None:
        """Convert per-operation cost fields to a canonical micros map.

        Accepts either a ``costBreakdown`` object or a raw event with top-level
        ``searchCostDollars`` / ``searchCostMicros`` style keys.  Missing or
        malformed values are stored as ``None`` so billing can fall back.
        """
        if not isinstance(data, dict):
            return None

        # If the caller already supplied a normalized micros map, prefer it.
        if all(
            k in data for k in ("search_micros", "gap_fill_micros", "scraper_micros")
        ):
            return {
                "search_micros": _to_int(data.get("search_micros")),
                "gap_fill_micros": _to_int(data.get("gap_fill_micros")),
                "scraper_micros": _to_int(data.get("scraper_micros")),
                "scraper_id": data.get("scraper_id") or data.get("scraperId"),
            }

        def _cost(key_dollars: str, key_micros: str) -> int | None:
            micros_raw = data.get(key_micros)
            if micros_raw is not None:
                micros_int = _to_int(micros_raw)
                if micros_int is not None:
                    return micros_int
                # Non-integer micros (e.g. float 12345.6) round half-up.
                try:
                    return int(
                        (Decimal(str(micros_raw))).to_integral_value(ROUND_HALF_UP)
                    )
                except Exception as exc:
                    logger.debug("Suppressed %r", exc)
            dollars_raw = data.get(key_dollars)
            if dollars_raw is not None:
                try:
                    return ChainLensServiceAuth.cost_dollars_to_micros(
                        float(dollars_raw)
                    )
                except Exception:
                    return None
            return None

        search = _cost("searchCostDollars", "searchCostMicros")
        gap_fill = _cost("gapFillCostDollars", "gapFillCostMicros")
        scraper = _cost("scraperCostDollars", "scraperCostMicros")

        if search is None and gap_fill is None and scraper is None:
            return None

        return {
            "search_micros": search,
            "gap_fill_micros": gap_fill,
            "scraper_micros": scraper,
            "scraper_id": data.get("scraper_id") or data.get("scraperId"),
        }

    def _cost_micros(self) -> int | None:
        """Convert stored ``cost_dollars`` to micro-USD with half-up rounding."""
        if self.cost_dollars is None:
            return None
        try:
            return ChainLensServiceAuth.cost_dollars_to_micros(self.cost_dollars)
        except ValueError as exc:
            logger.warning(
                "Ignoring unusable costDollars %r: %s", self.cost_dollars, exc
            )
            return None

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
            cost_dollars=self.cost_dollars,
            cost_micros=self._cost_micros(),
            cost_basis=self.cost_basis,
            cost_breakdown=self.cost_breakdown,
            resolved_mode=self.resolved_mode,
            model=self.model,
            tokens_total=self.tokens_total,
            tokens_prompt=self.tokens_prompt,
            tokens_completion=self.tokens_completion,
            first_token_time_ms=self.first_token_time_ms,
            gap_fill_needed=self.gap_fill_needed,
            suggested_domains=self.suggested_domains,
            insufficient_evidence=self.insufficient_evidence_flag,
            structured_output=self.structured_output,
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
    - ``type: gap-fill-needed`` signals that the engine needs on-demand
      indexing and carries ``suggested_domains``.

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
