"""``news.entity_search`` executor: search news articles via ChainLens API."""

from __future__ import annotations

import json
import logging
import math
import re
from typing import Any

import httpx

from app.capabilities.chainlens.research.schemas import Source
from app.capabilities.core import Executor
from app.capabilities.core.types import CapabilityContext
from app.capabilities.news.entity_search.schemas import (
    EntitySearchInput,
    EntitySearchOutput,
)
from app.config import config
from app.services.chainlens.auth import ChainLensServiceAuth

logger = logging.getLogger(__name__)

# Matches standard PII redaction placeholders like <NAME>, <PERSON>, [REDACTED], <NAME_1>, <NAME> (person)
_REDACTED_PATTERN = re.compile(
    r"^(?:<NAME(?:_\d+)?>|<PERSON(?:_\d+)?>|\[REDACTED\]|<REDACTED>)(?:\s*\(.*?\))?$",
    re.IGNORECASE,
)


def _is_redacted_placeholder(entity_name: str) -> bool:
    """Check if the entity name is an anonymized PII placeholder."""
    cleaned = entity_name.strip().strip("'\"")
    return _REDACTED_PATTERN.match(cleaned) is not None


def _parse_entity_sources(raw_data: Any) -> list[Source]:
    """Parse raw ChainLens search response items into Source models."""
    if isinstance(raw_data, dict):
        raw_sources = raw_data.get("results") or raw_data.get("sources") or []
    elif isinstance(raw_data, list):
        raw_sources = raw_data
    else:
        return []

    sources: list[Source] = []
    for item in raw_sources:
        if not isinstance(item, dict):
            continue

        meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else None
        url = str(item.get("url") or (meta or {}).get("url") or "").strip()
        if not url:
            continue

        title = str(item.get("title") or (meta or {}).get("title") or "Tin tức")
        content = (
            item.get("snippet")
            or item.get("content")
            or (meta or {}).get("snippet")
            or (meta or {}).get("content")
        )
        pub_date = (
            item.get("pubDate")
            or item.get("pub_date")
            or (meta or {}).get("pubDate")
            or (meta or {}).get("pub_date")
        )

        sources.append(
            Source(
                title=title,
                url=url,
                content=str(content) if content is not None else None,
                source_type="web",
                pub_date=str(pub_date) if pub_date is not None else None,
            )
        )
    return sources


class EntitySearchExecutor:
    """Executes entity search against ChainLens Research endpoint."""

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._api_url = (api_url or config.CHAINLENS_API_URL or "").rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._auth = ChainLensServiceAuth()

    def _get_headers(self, workspace_id: int) -> dict[str, str] | None:
        """Build outbound headers for ChainLens.

        ChainLens ``ApiKeyGuard`` requires an ``Authorization: Bearer <key>``
        header. ``ChainLensServiceAuth`` is the canonical source for that key;
        an explicit ``api_key`` constructor argument is provided as an override
        for testing and self-host deployments.
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
                content_type="application/json",
            )
            headers["Accept"] = "application/json"
            return headers

        return None

    async def execute(
        self,
        input_data: EntitySearchInput,
        context: CapabilityContext | None = None,
    ) -> EntitySearchOutput:
        """Execute the entity search query."""
        entity_name = input_data.entity_name.strip()
        log_entity = (
            "[REDACTED_PERSON]"
            if input_data.entity_type == "person"
            else entity_name[:50]
        )

        # AD-25 & Redaction check: if entity name is a redacted PII placeholder
        if _is_redacted_placeholder(entity_name):
            logger.info(
                "news_entity_search_redacted_placeholder",
                extra={
                    "entity_type": input_data.entity_type,
                    "entity_name": entity_name[:50],
                },
            )
            return EntitySearchOutput(
                entity_name=entity_name,
                entity_type=input_data.entity_type,
                sources=[],
                total_count=0,
                status="engine_unavailable",
                degraded=True,
                message="Tên thực thể đã bị ẩn (redacted) theo chính sách bảo mật thông tin cá nhân. Vui lòng cung cấp tên công khai để tra cứu.",
            )

        if not self._api_url:
            logger.warning("news_entity_search_unconfigured_api_url")
            return EntitySearchOutput(
                entity_name=entity_name,
                entity_type=input_data.entity_type,
                sources=[],
                total_count=0,
                status="engine_unavailable",
                degraded=True,
                message="Dịch vụ ChainLens Research chưa được cấu hình URL.",
            )

        headers = self._get_headers(input_data.workspace_id)
        if headers is None:
            logger.warning("news_entity_search_unconfigured_auth")
            return EntitySearchOutput(
                entity_name=entity_name,
                entity_type=input_data.entity_type,
                sources=[],
                total_count=0,
                status="engine_unavailable",
                degraded=True,
                message="Dịch vụ ChainLens Research chưa được cấu hình xác thực.",
            )

        # Build search query text tailored for news entity queries
        query_text = entity_name
        if input_data.entity_type != "all":
            query_text = f"{entity_name} ({input_data.entity_type})"

        # Wire payload complying strictly with ChainLens SearchRestRequestDto
        payload: dict[str, Any] = {
            "query": query_text,
            "mode": "fast",
            "sources": ["web"],
            "numResults": input_data.limit,
            "category": "news",
            "output": "search",
        }

        endpoint = f"{self._api_url}/api/v1/search"

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
                            headers = self._get_headers(input_data.workspace_id)
                            continue

                    if response.status_code == 200:
                        try:
                            data = response.json()
                        except json.JSONDecodeError:
                            logger.warning(
                                "news_entity_search_malformed_json",
                                extra={"entity": log_entity},
                            )
                            return EntitySearchOutput(
                                entity_name=entity_name,
                                entity_type=input_data.entity_type,
                                sources=[],
                                total_count=0,
                                status="engine_unavailable",
                                degraded=True,
                                message="Dịch vụ tìm kiếm phản hồi dữ liệu không hợp lệ.",
                            )

                        sources = _parse_entity_sources(data)

                        if isinstance(data, dict):
                            total_raw = data.get("total")
                            num_results_raw = data.get("numResults")
                            total_val = (
                                total_raw if total_raw is not None else num_results_raw
                            )
                        else:
                            total_val = None

                        total_count = (
                            total_val
                            if isinstance(total_val, int) and total_val >= 0
                            else len(sources)
                        )

                        cost_dollars: float | None = None
                        cost_micros: int | None = None
                        cost_basis: str | None = None
                        if isinstance(data, dict):
                            raw_cost = data.get("costDollars")
                            if isinstance(raw_cost, (int, float)):
                                raw_cost = float(raw_cost)
                                if raw_cost >= 0 and math.isfinite(raw_cost):
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
                                            "news_entity_search_unusable_cost",
                                            extra={
                                                "entity": log_entity,
                                                "costDollars": raw_cost,
                                                "error": str(exc),
                                            },
                                        )

                        if cost_micros is None:
                            cost_basis = "fallback"

                        return EntitySearchOutput(
                            entity_name=entity_name,
                            entity_type=input_data.entity_type,
                            sources=sources[: input_data.limit],
                            total_count=total_count,
                            status="complete",
                            degraded=False,
                            cost_dollars=cost_dollars,
                            cost_micros=cost_micros,
                            cost_basis=cost_basis,
                        )

                    logger.warning(
                        "news_entity_search_upstream_error",
                        extra={
                            "status_code": response.status_code,
                            "entity": log_entity,
                        },
                    )
                    return EntitySearchOutput(
                        entity_name=entity_name,
                        entity_type=input_data.entity_type,
                        sources=[],
                        total_count=0,
                        status="engine_unavailable",
                        degraded=True,
                        message=f"Dịch vụ tìm kiếm phản hồi lỗi HTTP {response.status_code}",
                    )

        except httpx.TimeoutException as exc:
            logger.warning(
                "news_entity_search_timeout",
                extra={"entity": log_entity, "error": str(exc)},
            )
            return EntitySearchOutput(
                entity_name=entity_name,
                entity_type=input_data.entity_type,
                sources=[],
                total_count=0,
                status="engine_unavailable",
                degraded=True,
                message="Hết thời gian chờ phản hồi từ dịch vụ tìm kiếm thực thể.",
            )
        except Exception:
            logger.exception(
                "news_entity_search_failed",
                extra={"entity": log_entity},
            )
            return EntitySearchOutput(
                entity_name=entity_name,
                entity_type=input_data.entity_type,
                sources=[],
                total_count=0,
                status="engine_unavailable",
                degraded=True,
                message="Không thể kết nối đến dịch vụ tìm kiếm thực thể tin tức.",
            )


def build_entity_search_executor() -> Executor[EntitySearchInput, EntitySearchOutput]:
    """Factory creating an Executor instance."""
    executor = EntitySearchExecutor()

    async def _execute(
        input_data: EntitySearchInput,
        context: CapabilityContext | None = None,
    ) -> EntitySearchOutput:
        return await executor.execute(input_data, context)

    return _execute
