"""``chainlens.research`` executor: call ChainLens ``POST /api/v1/search``."""

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
from app.config import config
from app.exceptions import ConfigurationError, ExternalServiceError

logger = logging.getLogger(__name__)

SearchFn = Callable[[ResearchInput], Awaitable[ResearchOutput]]

_ResearchStatus = Literal[
    "complete",
    "partial",
    "timeout",
    "insufficient_evidence",
]


class ChainLensError(ExternalServiceError):
    """Upstream ChainLens returned an explicit error."""


class _Block:
    __slots__ = ("data", "type")

    def __init__(self, block_type: str, data: Any) -> None:
        self.type = block_type
        self.data = data


def _parse_sse(raw: str) -> ResearchOutput:
    """Parse the ChainLens block-based SSE stream into a research output.

    The wire protocol is documented in ``apps/mcp/src/lib/apiClient.ts``:
    - ``event: error`` followed by a ``data:`` line -> surface error.
    - ``data: [DONE]`` / empty data lines are ignored.
    - ``type: block`` creates/replaces a block id.
    - ``type: updateBlock`` applies RFC6902-style patches (we only honor
      ``replace``/``add`` on ``/data``).
    - ``type: done`` carries chatId and webUrl metadata.

    We treat each ``event:`` line as setting the type for subsequent ``data:``
    lines until a blank line or a new ``event:`` line resets it. This matches
    the SSE spec and avoids misclassifying multi-line events.
    """
    blocks: dict[str, _Block] = {}
    error_msg: str | None = None
    chat_id: str | None = None
    web_url: str | None = None
    saw_done = False
    pending_event_type = "message"

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

    if error_msg:
        raise ChainLensError(error_msg, code="CHAINLENS_UPSTREAM_ERROR")

    text_parts: list[str] = []
    sources: list[Source] = []
    for block in blocks.values():
        if block.type == "text" and isinstance(block.data, str):
            text_parts.append(block.data)
        elif block.type == "source" and isinstance(block.data, list):
            for raw_source in block.data:
                if not isinstance(raw_source, dict):
                    continue
                meta = raw_source.get("metadata") or raw_source
                if not isinstance(meta, dict):
                    continue
                url = str(meta.get("url") or "")
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

    answer = "\n\n".join(text_parts).strip()
    status: _ResearchStatus = "complete"
    next_action: str | None = None
    if not answer and not sources:
        if saw_done:
            status = "insufficient_evidence"
            next_action = "No relevant sources were found. Try rephrasing the query."
        else:
            status = "timeout"
            next_action = "The ChainLens stream ended before returning a complete result. Try again."

    return ResearchOutput(
        answer=answer,
        sources=sources,
        chat_id=chat_id,
        web_url=web_url,
        status=status,
        next_action=next_action,
    )


def build_research_executor(search_fn: SearchFn | None = None) -> Executor:
    """Build the ``chainlens.research`` executor."""
    search = search_fn or _call_chainlens

    async def execute(payload: ResearchInput) -> ResearchOutput:
        emit_progress("starting", f"Researching: {payload.query[:80]}...")
        try:
            output = await search(payload)
        except httpx.TimeoutException as exc:
            logger.warning(
                "ChainLens research timed out for query: %s", payload.query[:80]
            )
            raise ExternalServiceError(
                f"ChainLens research timed out after {config.CHAINLENS_REQUEST_TIMEOUT_SECONDS}s",
                code="CHAINLENS_TIMEOUT",
            ) from exc
        except httpx.RequestError as exc:
            logger.warning("ChainLens request failed: %s", exc)
            raise ExternalServiceError(
                "ChainLens is unreachable. Please check your network and try again.",
                code="CHAINLENS_UNREACHABLE",
            ) from exc
        emit_progress("done", f"ChainLens returned {len(output.sources)} source(s)")
        return output

    return execute


async def _call_chainlens(payload: ResearchInput) -> ResearchOutput:
    """Make the upstream ChainLens research call and parse the SSE response."""
    if not config.CHAINLENS_API_KEY:
        raise ConfigurationError(
            "CHAINLENS_API_KEY is not configured.",
            code="CHAINLENS_NOT_CONFIGURED",
        )

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
        raise ChainLensError(
            "ChainLens rejected the API key.",
            code="CHAINLENS_AUTH_FAILED",
        )
    if response.status_code == 429:
        raise ChainLensError(
            "ChainLens rate or quota limit exceeded.",
            code="CHAINLENS_RATE_LIMITED",
        )
    if response.status_code >= 400:
        text = response.text[:500]
        logger.warning("ChainLens returned HTTP %s: %s", response.status_code, text)
        raise ChainLensError(
            f"ChainLens returned HTTP {response.status_code}: {text}",
            code="CHAINLENS_UPSTREAM_ERROR",
        )

    return _parse_sse(response.text)
