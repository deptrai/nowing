"""``news.entity_search`` executor: search news articles via ChainLens API."""

from __future__ import annotations

import json
import logging
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
    if _REDACTED_PATTERN.match(cleaned):
        return True
    upper = cleaned.upper()
    return "<NAME>" in upper or "<PERSON>" in upper or "[REDACTED]" in upper


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
        meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else item
        url = str(meta.get("url") or item.get("url") or "").strip()
        if not url:
            continue
        title = str(meta.get("title") or item.get("title") or "Tin tức")
        content = item.get("content") or item.get("snippet") or meta.get("snippet")
        sources.append(
            Source(
                title=title,
                url=url,
                content=str(content) if content is not None else None,
                source_type="web",
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
        self._api_key = api_key or config.CHAINLENS_API_KEY
        self._timeout = timeout
        self._auth = ChainLensServiceAuth()

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
                extra={"entity_type": input_data.entity_type},
            )
            return EntitySearchOutput(
                entity_name=entity_name,
                entity_type=input_data.entity_type,
                sources=[],
                total_count=0,
                status="engine_unavailable",
                degraded=True,
                cost_micros=0,
                cost_basis="actual",
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
                cost_micros=0,
                cost_basis="actual",
                message="Dịch vụ ChainLens Research chưa được cấu hình URL.",
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
        workspace_id = input_data.workspace_id

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=True,
            ) as client:
                for attempt in range(2):
                    if self._api_key:
                        headers = {
                            "Content-Type": "application/json",
                            "Accept": "application/json",
                            "x-api-key": self._api_key,
                            "X-Workspace-Id": str(workspace_id),
                        }
                    elif self._auth.configured:
                        headers = self._auth.get_outbound_headers(
                            workspace_id=workspace_id,
                            content_type="application/json",
                        )
                        headers["Accept"] = "application/json"
                    else:
                        headers = {
                            "Content-Type": "application/json",
                            "Accept": "application/json",
                            "X-Workspace-Id": str(workspace_id),
                        }

                    response = await client.post(
                        endpoint, json=payload, headers=headers
                    )

                    if response.status_code == 401 and attempt == 0:
                        rotated = self._auth.rotate(
                            workspace_id=workspace_id, reason="401_response"
                        )
                        if rotated:
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
                                cost_micros=0,
                                message="Dịch vụ tìm kiếm phản hồi dữ liệu không hợp lệ.",
                            )

                        sources = _parse_entity_sources(data)
                        total_val = (
                            data.get("total")
                            if isinstance(data, dict)
                            else data.get("numResults")
                            if isinstance(data, dict)
                            else None
                        )
                        total_count = (
                            total_val
                            if isinstance(total_val, int) and total_val >= 0
                            else len(sources)
                        )

                        cost_dollars = (
                            float(data.get("costDollars", 0.0))
                            if isinstance(data, dict)
                            and isinstance(data.get("costDollars"), (int, float))
                            else 0.0
                        )
                        cost_micros = int(cost_dollars * 1_000_000)

                        return EntitySearchOutput(
                            entity_name=entity_name,
                            entity_type=input_data.entity_type,
                            sources=sources[: input_data.limit],
                            total_count=total_count,
                            status="complete",
                            degraded=False,
                            cost_micros=cost_micros,
                            cost_basis="actual",
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
                        cost_micros=0,
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
                cost_micros=0,
                message="Hết thời gian chờ phản hồi từ dịch vụ tìm kiếm thực thể.",
            )
        except Exception as exc:
            logger.error(
                "news_entity_search_failed",
                extra={"entity": log_entity, "error": str(exc)},
                exc_info=True,
            )
            return EntitySearchOutput(
                entity_name=entity_name,
                entity_type=input_data.entity_type,
                sources=[],
                total_count=0,
                status="engine_unavailable",
                degraded=True,
                cost_micros=0,
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
