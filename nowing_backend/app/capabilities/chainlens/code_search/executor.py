"""``chainlens.code_search`` executor: code-context search via ChainLens API."""

from __future__ import annotations

import logging
import math
from typing import Any

import httpx

from app.capabilities.chainlens.code_search.schemas import (
    CodeSearchInput,
    CodeSearchOutput,
    CodeSnippet,
)
from app.capabilities.chainlens.research.schemas import Source
from app.capabilities.chainlens.research.sse_parser import (
    ChainLensError,
    _parse_sse,
)
from app.capabilities.core import Executor
from app.capabilities.core.types import CapabilityContext
from app.config import config
from app.services.chainlens.auth import ChainLensServiceAuth
from app.services.pii.redact import redact_pii

logger = logging.getLogger(__name__)

MAX_SNIPPET_CONTENT_CHARS = 50_000
"""Cap on each snippet's ``content`` so an oversized upstream payload can't
dump megabytes into agent context (same ceiling as chainlens.contents)."""

MAX_UPSTREAM_QUERY_CHARS = 1000
"""The upstream API rejects queries longer than 1000 chars; ``language`` is
appended post-validation, so truncate the combined string."""


def _parse_code_snippets(raw_data: Any) -> list[CodeSnippet]:
    """Parse the ChainLens ``output=code_context`` ``sources`` array.

    The upstream contract is ``{sources:[{url,title,content,metadata:
    {source,sourceId,score}}]}``; entries without string content are skipped
    because they carry no usable code context.
    """
    if not isinstance(raw_data, dict):
        return []

    raw_sources = raw_data.get("sources")
    if not isinstance(raw_sources, list):
        return []

    snippets: list[CodeSnippet] = []
    for entry in raw_sources:
        if not isinstance(entry, dict):
            continue

        raw_content = entry.get("content")
        # Only string content is usable; dict/list payloads would serialize
        # to garbage if coerced.
        if not isinstance(raw_content, str) or not raw_content.strip():
            continue
        content = raw_content
        if len(content) > MAX_SNIPPET_CONTENT_CHARS:
            content = content[:MAX_SNIPPET_CONTENT_CHARS] + "\n\n…[truncated]"

        metadata = entry.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        raw_score = metadata.get("score")
        score: float | None = None
        # bool is a subclass of int — True/False are not valid scores.
        if (
            isinstance(raw_score, (int, float))
            and not isinstance(raw_score, bool)
            and math.isfinite(raw_score)
        ):
            score = float(raw_score)

        snippets.append(
            CodeSnippet(
                source=(
                    str(metadata.get("source")).strip()
                    if metadata.get("source") is not None
                    else None
                ),
                source_id=(
                    str(metadata.get("sourceId")).strip()
                    if metadata.get("sourceId") is not None
                    else None
                ),
                title=(
                    str(entry.get("title")).strip()
                    if entry.get("title") is not None
                    else None
                ),
                url=(
                    str(entry.get("url")).strip()
                    if entry.get("url") is not None
                    else None
                ),
                content=content,
                score=score,
            )
        )
    return snippets


class CodeSearchExecutor:
    """Executes a code-context search against the ChainLens search endpoint."""

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self._api_url = (api_url or config.CHAINLENS_API_URL or "").rstrip("/")
        self._api_key = api_key
        # Matches the upstream MCP timeoutMs of 120_000.
        self._timeout = timeout
        self._auth = ChainLensServiceAuth()

    def _get_headers(
        self,
        workspace_id: int,
        correlation_id: str | None = None,
    ) -> dict[str, str] | None:
        """Build outbound headers for ChainLens.

        ``ChainLensServiceAuth`` is the canonical source for the service bearer
        token; the ``api_key`` constructor override exists for tests and
        self-host deployments.
        """
        if self._api_key:
            return {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {self._api_key}",
                "X-Workspace-Id": str(workspace_id),
            }

        if self._auth.configured:
            headers = self._auth.get_outbound_headers(
                workspace_id=workspace_id,
                correlation_id=correlation_id,
                content_type="application/json",
            )
            headers["Accept"] = "text/event-stream"
            return headers

        return None

    def _build_payload(self, input_data: CodeSearchInput) -> dict[str, Any]:
        """Build the ``output=code_context`` request body.

        The outbound query is PII-redacted before leaving Nowing because the
        caller's question may contain personal data. ``language`` is appended
        to the query string (``"{query} {language}"``) per the upstream MCP
        contract — it is NOT a separate request field. The combined query is
        truncated to the upstream 1000-char limit.
        """
        try:
            query = redact_pii(input_data.query).text
        except Exception:  # redaction failure must not block the search
            logger.warning("chainlens_code_search_query_redaction_failed")
            query = input_data.query

        if input_data.language:
            query = f"{query} {input_data.language}"

        if len(query) > MAX_UPSTREAM_QUERY_CHARS:
            query = query[:MAX_UPSTREAM_QUERY_CHARS]

        # NOTE: upstream rejects a top-level ``mode`` for output=code_context
        # ("property mode should not exist"); the latency hint is not sent.
        return {
            "query": query,
            "output": "code_context",
            "dataSources": ["code"],
            "numResults": input_data.maxResults,
            "sources": ["web"],
            "stream": True,
        }


    @staticmethod
    def _research_output_to_dict(research_output: Any) -> dict[str, Any]:
        """Convert the SSE-parsed ``ResearchOutput`` to the dict shape
        ``_parse_code_snippets`` expects.

        The SSE stream delivers ``source`` blocks whose metadata already
        carries ``source``, ``sourceId``, ``score``, ``url``, ``title``, and
        ``content`` — the same shape the non-stream ``{sources:[...]}``
        response used.
        """
        sources: list[dict[str, Any]] = []
        for src in getattr(research_output, "sources", []):
            entry: dict[str, Any] = {
                "url": getattr(src, "url", None),
                "title": getattr(src, "title", None),
                "content": getattr(src, "content", None),
                "metadata": {
                    "source": getattr(src, "source_type", None),
                    "sourceId": getattr(src, "source_id", None)
                    or getattr(src, "url", None),
                    "score": getattr(src, "score", None),
                },
            }
            sources.append(entry)

        return {
            "sources": sources,
            "status": getattr(research_output, "status", None),
            "message": getattr(research_output, "message", None)
            or getattr(research_output, "degradation_reason", None),
            "nextAction": getattr(research_output, "next_action", None),
            "costDollars": getattr(research_output, "cost_dollars", None),
            "estimated": getattr(research_output, "cost_basis", None)
            == "estimated",
        }

    def _degraded(self, message: str, reason: str) -> CodeSearchOutput:
        return CodeSearchOutput(
            items=[],
            sources=[],
            status="engine_unavailable",
            degraded=True,
            degradation_reason=reason,
            message=message,
        )


    async def execute(
        self,
        input_data: CodeSearchInput,
        ctx: CapabilityContext | None = None,
    ) -> CodeSearchOutput:
        """Execute the code-context search request."""
        if not self._api_url:
            logger.warning("chainlens_code_search_unconfigured_api_url")
            return self._degraded(
                "Dịch vụ ChainLens chưa được cấu hình URL.",
                reason="missing_api_url",
            )

        headers = self._get_headers(
            input_data.workspace_id,
            correlation_id=input_data.correlation_id,
        )
        if headers is None:
            logger.warning("chainlens_code_search_unconfigured_auth")
            return self._degraded(
                "Dịch vụ ChainLens chưa được cấu hình xác thực.",
                reason="missing_auth",
            )

        payload = self._build_payload(input_data)
        endpoint = f"{self._api_url}/api/v1/search"

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=True,
            ) as client:
                # Only the 401-rotation path loops; every other status returns
                # on first response (no backoff needed for a single retry).
                for attempt in range(2):
                    headers["Accept"] = "text/event-stream"
                    async with client.stream(
                        "POST",
                        endpoint,
                        json=payload,
                        headers=headers,
                    ) as response:
                        if (
                            response.status_code == 401
                            and attempt == 0
                            and self._auth.configured
                        ):
                            rotated = self._auth.rotate(
                                workspace_id=input_data.workspace_id,
                                reason="401_response",
                            )
                            if rotated:
                                # rebuild headers with the rotated token
                                headers = self._get_headers(
                                    input_data.workspace_id,
                                    correlation_id=input_data.correlation_id,
                                )
                                if headers is None:
                                    return self._degraded(
                                        "Dịch vụ ChainLens chưa được cấu hình xác thực.",
                                        reason="missing_auth",
                                    )
                                continue

                        if response.status_code == 200:
                            # Parse SSE stream into a research-shaped output,
                            # then extract code snippets from the sources.
                            research_output = await _parse_sse(
                                response.aiter_lines()
                            )
                            data = self._research_output_to_dict(research_output)
                        else:
                            data = {}

                        if response.status_code != 200:
                            logger.warning(
                                "chainlens_code_search_upstream_error",
                                extra={"status_code": response.status_code},
                            )
                            return self._degraded(
                                f"Dịch vụ tìm kiếm code phản hồi lỗi HTTP {response.status_code}",
                                reason="upstream_error",
                            )

                        snippets = _parse_code_snippets(data)

                        upstream_status: str | None = None
                        next_action: str | None = None
                        upstream_message: str | None = None
                        cost_dollars: float | None = None
                        cost_micros: int | None = None
                        cost_basis: str | None = None
                        if isinstance(data, dict):
                            raw_status = data.get("status")
                            if isinstance(raw_status, str) and raw_status:
                                upstream_status = raw_status
                            raw_next = data.get("nextAction")
                            if isinstance(raw_next, str) and raw_next.strip():
                                next_action = raw_next.strip()
                            raw_msg = data.get("message")
                            if isinstance(raw_msg, str) and raw_msg.strip():
                                upstream_message = raw_msg.strip()

                            raw_cost = data.get("costDollars")
                            if isinstance(raw_cost, (int, float)):
                                raw_cost = float(raw_cost)
                                if not (raw_cost >= 0 and math.isfinite(raw_cost)):
                                    logger.warning(
                                        "chainlens_code_search_unusable_cost",
                                        extra={
                                            "costDollars": raw_cost,
                                            "reason": "non_finite_or_negative",
                                        },
                                    )
                                else:
                                    try:
                                        cost_micros = (
                                            ChainLensServiceAuth.cost_dollars_to_micros(
                                                raw_cost
                                            )
                                        )
                                        cost_dollars = raw_cost
                                        # Upstream may flag the dollar figure
                                        # as estimated rather than metered.
                                        cost_basis = (
                                            "estimated"
                                            if data.get("estimated") is True
                                            else "actual"
                                        )
                                    except ValueError as exc:
                                        logger.warning(
                                            "chainlens_code_search_unusable_cost",
                                            extra={
                                                "costDollars": raw_cost,
                                                "error": str(exc),
                                            },
                                        )

                        if cost_micros is None:
                            cost_basis = "fallback"

                        sources = [
                            Source(
                                title=snip.title or snip.url or "",
                                url=snip.url,
                                content=snip.content,
                                source_type="web",
                            )
                            for snip in snippets
                            if snip.url
                        ]

                        # Upstream timeout: surface status + nextAction hint
                        # verbatim; do NOT auto-retry (caller decides).
                        if upstream_status == "timeout":
                            return CodeSearchOutput(
                                items=snippets,
                                sources=sources,
                                status="timeout",
                                degraded=False,
                                next_action=next_action,
                                message=upstream_message,
                                cost_dollars=cost_dollars,
                                cost_micros=cost_micros,
                                cost_basis=cost_basis,
                            )

                        message: str | None = upstream_message
                        status = "complete"
                        if not snippets:
                            # Zero usable content: never report "complete"
                            # with an empty result set.
                            status = "partial"
                            if message is None:
                                message = (
                                    "Dịch vụ tìm kiếm code không trả về snippet nào "
                                    "cho truy vấn đã yêu cầu."
                                )

                        return CodeSearchOutput(
                            items=snippets,
                            sources=sources,
                            status=status,
                            degraded=False,
                            next_action=next_action,
                            message=message,
                            cost_dollars=cost_dollars,
                            cost_micros=cost_micros,
                            cost_basis=cost_basis,
                        )

        except httpx.TimeoutException as exc:
            logger.warning(
                "chainlens_code_search_timeout",
                extra={"error": str(exc)},
            )
            return self._degraded(
                "Hết thời gian chờ phản hồi từ dịch vụ tìm kiếm code.",
                reason="timeout",
            )
        except ChainLensError as exc:
            # Upstream emitted a `type:"error"` SSE frame (e.g. engine model
            # load failure). Surface the verbatim message so logs distinguish
            # an engine fault from a transport timeout or a dropped conn.
            logger.warning(
                "chainlens_code_search_upstream_sse_error",
                extra={
                    "error": exc.message,
                    "code": exc.code,
                    "correlation_id": input_data.correlation_id,
                },
            )
            return self._degraded(
                f"Dịch vụ tìm kiếm code báo lỗi: {exc.message}",
                reason="upstream_error",
            )
        except Exception:  # search error → structured degraded response
            logger.exception("chainlens_code_search_failed")
            return self._degraded(
                "Không thể kết nối đến dịch vụ tìm kiếm code.",
                reason="connection_error",
            )


def build_code_search_executor() -> Executor[CodeSearchInput, CodeSearchOutput]:
    """Factory creating an Executor instance."""
    executor = CodeSearchExecutor()

    async def _execute(
        input_data: CodeSearchInput,
        ctx: CapabilityContext | None = None,
    ) -> CodeSearchOutput:
        return await executor.execute(input_data, ctx)

    return _execute
