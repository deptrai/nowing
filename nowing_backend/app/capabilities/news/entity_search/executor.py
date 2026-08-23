"""``news.entity_search`` executor: search news articles via ChainLens API."""

from __future__ import annotations

import logging
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
        meta = item.get("metadata") or item
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

        # AD-25 & Redaction check: if entity name is the redacted placeholder `<NAME>`
        if entity_name == "<NAME>" or entity_name.upper() == "<NAME>":
            logger.info(
                "news_entity_search_redacted_placeholder",
                extra={"entity_name": entity_name},
            )
            return EntitySearchOutput(
                entity_name=entity_name,
                entity_type=input_data.entity_type,
                articles=[],
                total_count=0,
                degraded=True,
                message="Tên thực thể đã bị ẩn (redacted) theo chính sách bảo mật thông tin cá nhân. Vui lòng cung cấp tên công khai để tra cứu.",
            )

        if not self._api_url:
            logger.warning("news_entity_search_unconfigured_api_url")
            return EntitySearchOutput(
                entity_name=entity_name,
                entity_type=input_data.entity_type,
                articles=[],
                total_count=0,
                degraded=True,
                message="Dịch vụ ChainLens Research chưa được cấu hình URL.",
            )

        # Build search query payload
        query_text = entity_name
        if input_data.entity_type != "all":
            query_text = f"{entity_name} ({input_data.entity_type})"

        payload = {
            "query": query_text,
            "mode": "speed",
            "sources": ["web"],
            "tier": "search",
            "limit": input_data.limit,
            "category": "news",
            "filters": {
                "entity": entity_name,
                "entity_type": input_data.entity_type
                if input_data.entity_type != "all"
                else None,
                "contentType": "news",
            },
        }

        endpoint = f"{self._api_url}/api/v1/search"
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._api_key:
            headers["x-api-key"] = self._api_key
        elif self._auth.configured:
            import contextlib

            with contextlib.suppress(Exception):
                headers["Authorization"] = f"Bearer {self._auth.current_token}"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(endpoint, json=payload, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    articles = _parse_entity_sources(data)
                    total_count = (
                        data.get("total")
                        if isinstance(data, dict) and "total" in data
                        else len(articles)
                    )
                    return EntitySearchOutput(
                        entity_name=entity_name,
                        entity_type=input_data.entity_type,
                        articles=articles[: input_data.limit],
                        total_count=total_count,
                        degraded=False,
                    )
                else:
                    logger.warning(
                        "news_entity_search_upstream_error",
                        extra={
                            "status_code": response.status_code,
                            "body": response.text[:200],
                        },
                    )
                    return EntitySearchOutput(
                        entity_name=entity_name,
                        entity_type=input_data.entity_type,
                        articles=[],
                        total_count=0,
                        degraded=True,
                        message=f"Dịch vụ tìm kiếm phản hồi lỗi HTTP {response.status_code}",
                    )
        except httpx.TimeoutException as exc:
            logger.warning(
                "news_entity_search_timeout",
                extra={"entity_name": entity_name, "error": str(exc)},
            )
            return EntitySearchOutput(
                entity_name=entity_name,
                entity_type=input_data.entity_type,
                articles=[],
                total_count=0,
                degraded=True,
                message="Hết thời gian chờ phản hồi từ dịch vụ tìm kiếm thực thể.",
            )
        except Exception as exc:
            logger.error(
                "news_entity_search_failed",
                extra={"entity_name": entity_name, "error": str(exc)},
                exc_info=True,
            )
            return EntitySearchOutput(
                entity_name=entity_name,
                entity_type=input_data.entity_type,
                articles=[],
                total_count=0,
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
