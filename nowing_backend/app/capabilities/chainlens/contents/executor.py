"""``chainlens.contents`` executor: clean page extraction via ChainLens API."""

from __future__ import annotations

import json
import logging
import math
from typing import Any

import httpx

from app.capabilities.chainlens.contents.schemas import (
    ContentItem,
    ContentsInput,
    ContentsOutput,
)
from app.capabilities.chainlens.research.schemas import Source
from app.capabilities.core import Executor
from app.capabilities.core.types import CapabilityContext
from app.config import config
from app.services.chainlens.auth import ChainLensServiceAuth
from app.services.pii.redact import redact_pii

logger = logging.getLogger(__name__)

MAX_COMBINED_CONTENT_CHARS = 50_000
"""Cap on the concatenated ``content`` field so large batches can't dump
megabytes into agent context."""


def _parse_contents_results(raw_data: Any) -> list[ContentItem]:
    """Parse the ChainLens ``output=contents`` ``results`` array into items.

    The upstream contract is ``{results:[{url,title,content,summary,
    highlights:[{excerpt}],status}]}``; non-dict or url-less entries are
    skipped because they cannot be attributed to a requested page.
    """
    if not isinstance(raw_data, dict):
        return []

    raw_results = raw_data.get("results")
    if not isinstance(raw_results, list):
        return []

    items: list[ContentItem] = []
    for entry in raw_results:
        if not isinstance(entry, dict):
            continue

        url = str(entry.get("url") or "").strip()
        if not url:
            continue

        raw_highlights = entry.get("highlights")
        highlights: list[str] = []
        if isinstance(raw_highlights, list):
            for h in raw_highlights:
                if isinstance(h, dict):
                    excerpt = h.get("excerpt")
                    if excerpt is not None:
                        highlights.append(str(excerpt))
                elif h is not None:
                    highlights.append(str(h))
        elif isinstance(raw_highlights, str):
            highlights.append(raw_highlights)

        content = (
            str(entry.get("content"))
            if entry.get("content") is not None
            else None
        )
        summary = (
            str(entry.get("summary"))
            if entry.get("summary") is not None
            else None
        )
        status = str(entry.get("status") or "ok")
        # An "ok" item with neither content nor summary is an empty page
        # masquerading as success; treat it as a failed extraction.
        if status == "ok" and not (content or "").strip() and not (
            summary or ""
        ).strip():
            status = "error"

        items.append(
            ContentItem(
                url=url,
                title=(
                    str(entry.get("title")).strip()
                    if entry.get("title") is not None
                    else None
                ),
                content=content,
                summary=summary,
                highlights=highlights,
                status=status,
                error=(
                    str(entry.get("error")).strip()
                    if entry.get("error") is not None
                    else None
                ),
            )
        )
    return items


class ContentsExecutor:
    """Executes URL contents extraction against the ChainLens search endpoint."""

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self._api_url = (api_url or config.CHAINLENS_API_URL or "").rstrip("/")
        self._api_key = api_key
        # Extraction is slower than search: the engine crawls each URL.
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
            headers["Accept"] = "application/json"
            return headers

        return None

    def _build_payload(self, input_data: ContentsInput) -> dict[str, Any]:
        """Build the ``output=contents`` request body.

        ``query`` defaults to the joined URLs per the upstream contract. The
        outbound query is PII-redacted before leaving Nowing because callers
        may paste focus text containing personal data.
        """
        if input_data.query:
            # User-supplied focus text may contain PII -> redact before send.
            try:
                query = redact_pii(input_data.query).text
            except Exception:  # redaction failure must not block extraction
                logger.warning("chainlens_contents_query_redaction_failed")
                query = input_data.query
        else:
            # Default URL-join query: redacting would corrupt digits/emails
            # inside URLs, so send it verbatim.
            query = "\n".join(input_data.urls)

        payload: dict[str, Any] = {
            "output": "contents",
            "urls": input_data.urls,
            "query": query,
            "stream": False,
        }

        if input_data.sources is not None:
            payload["sources"] = input_data.sources
        if input_data.optimizationMode is not None:
            payload["optimizationMode"] = input_data.optimizationMode
        if input_data.subpages is not None:
            payload["subpages"] = input_data.subpages
        if input_data.subpageTarget is not None:
            payload["subpageTarget"] = input_data.subpageTarget
        if input_data.livecrawl is not None:
            payload["livecrawl"] = input_data.livecrawl
        if input_data.maxAgeHours is not None:
            payload["maxAgeHours"] = input_data.maxAgeHours
        if input_data.summary is not None:
            payload["summary"] = input_data.summary
        if input_data.highlights is not None:
            payload["highlights"] = input_data.highlights

        return payload

    def _degraded(self, message: str) -> ContentsOutput:
        return ContentsOutput(
            items=[],
            sources=[],
            content="",
            status="engine_unavailable",
            degraded=True,
            message=message,
        )

    async def execute(
        self,
        input_data: ContentsInput,
        context: CapabilityContext | None = None,
    ) -> ContentsOutput:
        """Execute the contents extraction request."""
        if not self._api_url:
            logger.warning("chainlens_contents_unconfigured_api_url")
            return self._degraded(
                "Dịch vụ ChainLens chưa được cấu hình URL."
            )

        headers = self._get_headers(
            input_data.workspace_id,
            correlation_id=input_data.correlation_id,
        )
        if headers is None:
            logger.warning("chainlens_contents_unconfigured_auth")
            return self._degraded(
                "Dịch vụ ChainLens chưa được cấu hình xác thực."
            )

        # Dedupe requested URLs preserving order so repeats don't inflate
        # billing units or produce duplicate result entries upstream.
        seen: set[str] = set()
        deduped_urls: list[str] = []
        for u in input_data.urls:
            if u not in seen:
                seen.add(u)
                deduped_urls.append(u)
        if len(deduped_urls) != len(input_data.urls):
            input_data = input_data.model_copy(update={"urls": deduped_urls})

        payload = self._build_payload(input_data)
        endpoint = f"{self._api_url}/api/v1/search"
        log_url_count = len(input_data.urls)

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=True,
            ) as client:
                for attempt in range(2):
                    response = await client.post(
                        endpoint, json=payload, headers=headers
                    )

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
                            continue

                    if response.status_code == 200:
                        try:
                            data = response.json()
                        except json.JSONDecodeError:
                            logger.warning(
                                "chainlens_contents_malformed_json",
                                extra={"url_count": log_url_count},
                            )
                            return self._degraded(
                                "Dịch vụ đọc trang phản hồi dữ liệu không hợp lệ."
                            )

                        items = _parse_contents_results(data)

                        # Detect requested URLs that upstream returned nothing
                        # attributable for; they count as missing results.
                        returned_urls = {item.url for item in items}
                        missing_urls = [
                            u for u in input_data.urls if u not in returned_urls
                        ]
                        if missing_urls:
                            logger.warning(
                                "chainlens_contents_missing_results",
                                extra={
                                    "url_count": log_url_count,
                                    "missing_urls": missing_urls,
                                    "correlation_id": input_data.correlation_id,
                                },
                            )

                        has_failure = (
                            any(item.status != "ok" for item in items)
                            or bool(missing_urls)
                        )
                        auth_walled = any(
                            item.status == "unsupported_auth_wall"
                            for item in items
                        )

                        sources = [
                            Source(
                                title=item.title or item.url,
                                url=item.url,
                                content=item.summary or item.content,
                                source_type="web",
                            )
                            for item in items
                            if item.status == "ok"
                        ]
                        combined_content = "\n\n".join(
                            item.content for item in items if item.content
                        )
                        if len(combined_content) > MAX_COMBINED_CONTENT_CHARS:
                            combined_content = (
                                combined_content[:MAX_COMBINED_CONTENT_CHARS]
                                + "\n\n…[truncated]"
                            )

                        cost_dollars: float | None = None
                        cost_micros: int | None = None
                        cost_basis: str | None = None
                        if isinstance(data, dict):
                            raw_cost = data.get("costDollars")
                            if isinstance(raw_cost, (int, float)):
                                raw_cost = float(raw_cost)
                                if not (raw_cost >= 0 and math.isfinite(raw_cost)):
                                    logger.warning(
                                        "chainlens_contents_unusable_cost",
                                        extra={
                                            "url_count": log_url_count,
                                            "costDollars": raw_cost,
                                            "reason": "non_finite_or_negative",
                                        },
                                    )
                                elif raw_cost >= 0 and math.isfinite(raw_cost):
                                    try:
                                        cost_micros = (
                                            ChainLensServiceAuth.cost_dollars_to_micros(
                                                raw_cost
                                            )
                                        )
                                        cost_dollars = raw_cost
                                        cost_basis = "actual"
                                    except ValueError as exc:
                                        logger.warning(
                                            "chainlens_contents_unusable_cost",
                                            extra={
                                                "url_count": log_url_count,
                                                "costDollars": raw_cost,
                                                "error": str(exc),
                                            },
                                        )

                        if cost_micros is None:
                            cost_basis = "fallback"

                        message: str | None = None
                        if not items:
                            # Upstream returned nothing attributable; never
                            # report "complete" with an empty result set.
                            has_failure = True
                            message = (
                                "Dịch vụ đọc trang không trả về nội dung nào "
                                "cho các URL đã yêu cầu."
                            )
                        elif auth_walled:
                            message = (
                                "Một hoặc nhiều trang yêu cầu đăng nhập; hãy "
                                "chuyển các URL đó sang Browser Operator."
                            )
                        elif missing_urls:
                            message = (
                                "Dịch vụ đọc trang không trả về nội dung cho "
                                f"{len(missing_urls)} URL đã yêu cầu."
                            )
                        elif has_failure:
                            message = (
                                "Một số trang không trích xuất được nội dung."
                            )

                        # Surface per-item upstream error details so logs and
                        # the caller see *why* a page failed (e.g. extractor
                        # "Unable to extract content") instead of a bare count.
                        item_errors = [
                            {"url": it.url, "status": it.status, "error": it.error}
                            for it in items
                            if it.status != "ok" or it.error
                        ]
                        if item_errors:
                            logger.warning(
                                "chainlens_contents_item_errors",
                                extra={
                                    "url_count": log_url_count,
                                    "correlation_id": input_data.correlation_id,
                                    "item_errors": item_errors,
                                },
                            )
                            # Append upstream error detail to the user-facing
                            # message when we have one — keeps "some pages
                            # failed" honest about the underlying cause.
                            detail = next(
                                (e["error"] for e in item_errors if e["error"]),
                                None,
                            )
                            if detail and message:
                                message = f"{message} ({detail})"
                            elif detail:
                                message = detail

                        return ContentsOutput(
                            items=items,
                            sources=sources,
                            content=combined_content,
                            status="partial" if has_failure else "complete",
                            degraded=False,
                            message=message,
                            cost_dollars=cost_dollars,
                            cost_micros=cost_micros,
                            cost_basis=cost_basis,
                        )

                    logger.warning(
                        "chainlens_contents_upstream_error",
                        extra={
                            "status_code": response.status_code,
                            "url_count": log_url_count,
                        },
                    )
                    return self._degraded(
                        f"Dịch vụ đọc trang phản hồi lỗi HTTP {response.status_code}"
                    )

        except httpx.TimeoutException as exc:
            logger.warning(
                "chainlens_contents_timeout",
                extra={"url_count": log_url_count, "error": str(exc)},
            )
            return self._degraded(
                "Hết thời gian chờ phản hồi từ dịch vụ đọc trang."
            )
        except Exception:  # extraction error → structured degraded response
            logger.exception(
                "chainlens_contents_failed",
                extra={"url_count": log_url_count},
            )
            return self._degraded(
                "Không thể kết nối đến dịch vụ đọc trang."
            )


def build_contents_executor() -> Executor[ContentsInput, ContentsOutput]:
    """Factory creating an Executor instance."""
    executor = ContentsExecutor()

    async def _execute(
        input_data: ContentsInput,
        context: CapabilityContext | None = None,
    ) -> ContentsOutput:
        return await executor.execute(input_data, context)

    return _execute
