"""Reverse Ideal Customer Profile (ICP) Service Engine (Story 21.10)."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any

from app.config import config
from app.lead_intelligence.schemas import (
    ReverseIcpResponse,
)
from app.proprietary.platforms.crawler.fast_crawler import (
    FastCrawler,
    normalize_target_url,
)

logger = logging.getLogger(__name__)

REVERSE_ICP_SYSTEM_PROMPT = """Bạn là Chuyên gia Chiến lược Săn Lead & Định hình Chân dung Khách hàng Mục tiêu (Lead Intelligence & Reverse-ICP Specialist).
Nhiệm vụ của bạn là phân tích dữ liệu website (OpenGraph tags, Schema JSON-LD, tiêu đề, đề mục và nội dung giới thiệu) để xác định chính xác:
1. Giá trị cốt lõi / Tuyên ngôn giá trị (Value Proposition).
2. Phân loại ngành dọc / Lĩnh vực kinh doanh chính (Industry).
3. 3 Nhóm chân dung khách hàng mục tiêu lý tưởng (Buyer Personas) có khả năng chuyển đổi cao nhất.
4. 5 Truy vấn tìm kiếm (Search Queries) tối ưu cho các công cụ quét lead và mạng xã hội.
5. Từ khóa loại trừ (Negative Keywords) để lọc bỏ lead rác / không liên quan.
6. Bộ lọc đề xuất (Filter Presets: nền tảng nguồn, nhãn ý định MUA/BÁN/TUYỂN DỤNG/ĐẤU THẦU, địa điểm).
7. 3 Câu lệnh mẫu (Chat Starter Prompts) để người dùng bấm 1-click kích hoạt trợ lý AI săn lead.

YÊU CẦU ĐẦU RA:
- BẮT BUỘC trả về cú pháp JSON hợp lệ 100%, KHÔNG thêm giải thích râu ria ngoài JSON.
- Cấu trúc JSON tuân thủ chính xác schema ReverseIcpResponse.
"""


class ReverseIcpService:
    """Service analyzing website/landing page metadata to produce structured ICP insights."""

    def __init__(self, *, crawler: FastCrawler | None = None) -> None:
        self.crawler = crawler or FastCrawler()

    def _get_cache_key(
        self, url: str, custom_instructions: str | None = None, model: str | None = None
    ) -> str:
        """Compute stable SHA256 cache key for normalized URL, instructions, and model."""
        norm_url = normalize_target_url(url)
        composite = f"{norm_url}::{custom_instructions or ''}::{model or ''}"
        url_hash = hashlib.sha256(composite.encode("utf-8")).hexdigest()
        return f"icp:cache:{url_hash}"

    async def _get_from_cache(
        self, url: str, custom_instructions: str | None = None, model: str | None = None
    ) -> dict[str, Any] | None:
        """Fetch cached ReverseIcpResponse dictionary from Redis if available."""
        cache_key = self._get_cache_key(url, custom_instructions, model)
        try:
            import redis.asyncio as aioredis

            redis_client = aioredis.from_url(
                config.REDIS_APP_URL, decode_responses=True
            )
            cached_val = await redis_client.get(cache_key)
            await redis_client.aclose()
            if cached_val:
                return json.loads(cached_val)
        except Exception as exc:
            logger.debug(
                "[ReverseIcpService] Redis cache lookup failed (skipping cache): %s",
                exc,
            )
        return None

    async def _save_to_cache(
        self,
        url: str,
        data: dict[str, Any],
        custom_instructions: str | None = None,
        model: str | None = None,
        ttl: int = 3600,
    ) -> None:
        """Store ReverseIcpResponse payload in Redis cache."""
        cache_key = self._get_cache_key(url, custom_instructions, model)
        try:
            import redis.asyncio as aioredis

            redis_client = aioredis.from_url(
                config.REDIS_APP_URL, decode_responses=True
            )
            await redis_client.set(
                cache_key, json.dumps(data, ensure_ascii=False), ex=ttl
            )
            await redis_client.aclose()
        except Exception as exc:
            logger.debug("[ReverseIcpService] Redis cache write failed: %s", exc)

    async def _fetch_and_parse_crawl(self, url: str) -> dict[str, Any]:
        """Fetch and parse metadata from target website."""
        meta = await self.crawler.fetch_and_parse(url)
        from urllib.parse import urlparse

        domain = urlparse(meta.final_url or meta.url).netloc
        return {
            "url": meta.url,
            "final_url": meta.final_url,
            "domain": domain,
            "title": meta.title,
            "meta_description": meta.description,
            "keywords": meta.keywords,
            "og_tags": meta.og_tags,
            "json_ld": meta.json_ld,
            "headings": meta.headings,
            "clean_text": meta.clean_text,
            "crawl_latency_ms": meta.latency_ms,
        }

    def _parse_llm_json_response(self, raw_text: str) -> dict[str, Any]:
        """Robustly extract and parse JSON payload from LLM text."""
        cleaned = raw_text.strip()
        # Strip markdown ```json ... ``` codeblocks
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Regex search for outer curly braces
            match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError as exc:
                    logger.warning(
                        "[ReverseIcpService] Fallback regex JSON parsing failed: %s",
                        exc,
                    )
            raise ValueError(
                f"Could not parse valid JSON from LLM response: {raw_text[:200]}"
            ) from None

    def _build_user_prompt(
        self, crawl_data: dict[str, Any], custom_instructions: str | None = None
    ) -> str:
        """Format extracted website context into a compact LLM prompt."""
        domain = crawl_data.get("domain", "")
        title = crawl_data.get("title", "")
        meta_desc = crawl_data.get("meta_description", "")
        og_tags = crawl_data.get("og_tags", {})
        json_ld = crawl_data.get("json_ld", [])
        headings = crawl_data.get("headings", [])
        clean_text = crawl_data.get("clean_text", "")

        prompt_parts = [
            f"Tên miền / URL: {crawl_data.get('url', '')} (Domain: {domain})",
            f"Tiêu đề trang: {title}",
            f"Mô tả meta: {meta_desc}",
        ]

        if og_tags:
            prompt_parts.append(
                f"OpenGraph tags: {json.dumps(og_tags, ensure_ascii=False)}"
            )

        if json_ld:
            # Summary of schema types
            schemas_snippet = json.dumps(json_ld[:3], ensure_ascii=False)
            prompt_parts.append(f"Schema JSON-LD trích xuất: {schemas_snippet}")

        if headings:
            prompt_parts.append(f"Đề mục chính: {' | '.join(headings)}")

        if clean_text:
            prompt_parts.append(f"Nội dung tiêu biểu:\n{clean_text}")

        if custom_instructions:
            prompt_parts.append(
                f"\nYêu cầu tùy chỉnh bổ sung từ người dùng:\n{custom_instructions}"
            )

        prompt_parts.append("""
Vui lòng xuất kết quả theo định dạng JSON với cấu trúc:
{
  "company_name": "Tên thương hiệu / công ty",
  "domain": "domain.vn",
  "value_proposition": "Tuyên ngôn giá trị chính (1-2 câu)",
  "industry": "Ngành nghề chính",
  "target_buyer_personas": [
    {
      "title": "Chức danh mục tiêu",
      "industry": "Ngành nghề của họ",
      "company_size": "Quy mô",
      "pain_points": ["Nỗi đau 1", "Nỗi đau 2"],
      "buying_triggers": ["Tín hiệu mua hàng 1", "Tín hiệu mua hàng 2"]
    }
  ],
  "suggested_search_queries": ["query 1", "query 2", "query 3", "query 4", "query 5"],
  "negative_keywords": ["từ loại trừ 1", "từ loại trừ 2"],
  "filter_presets": {
    "platforms": ["batdongsan", "facebook", "linkedin"],
    "intent": "BÁN",
    "target_industries": ["Ngành 1", "Ngành 2"],
    "locations": ["Hà Nội", "TP.HCM"],
    "company_size_range": "Mô tả quy mô"
  },
  "chat_starter_prompts": ["Prompt 1", "Prompt 2", "Prompt 3"]
}
""")
        return "\n".join(prompt_parts)

    async def _call_llm_for_icp(
        self,
        crawl_data: dict[str, Any],
        custom_instructions: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Invoke LLM to generate ICP response structure via the global Auto-mode router."""
        import litellm

        from app.services.llm_router_service import LLMRouterService

        litellm.drop_params = True

        user_prompt = self._build_user_prompt(crawl_data, custom_instructions)
        messages = [
            {"role": "system", "content": REVERSE_ICP_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        router = LLMRouterService.get_router()
        if router is None:
            raise ValueError(
                "LLM Router is not initialized. Check GLOBAL_LLM_CONFIG configuration."
            )

        target_model = model or "auto"
        response = await router.acompletion(
            model=target_model,
            messages=messages,
            temperature=0.2,
            max_tokens=2000,
            timeout=25.0,
            response_format={"type": "json_object"},
        )

        choice = response.choices[0]
        content = choice.message.content or ""
        return self._parse_llm_json_response(content)

    async def analyze_url(
        self,
        url: str,
        custom_instructions: str | None = None,
        model: str | None = None,
    ) -> ReverseIcpResponse:
        """Run complete 1-Click Reverse-ICP pipeline with caching, crawling, and AI reasoning."""
        # 1. Check Cache
        cached_data = await self._get_from_cache(
            url, custom_instructions=custom_instructions, model=model
        )
        if cached_data:
            logger.info(
                "[ReverseIcpService] Returning cached Reverse-ICP result for %s", url
            )
            return ReverseIcpResponse.model_validate(cached_data)

        # 2. Fast Crawl
        crawl_data = await self._fetch_and_parse_crawl(url)

        # 3. Call LLM Reasoning
        icp_dict = await self._call_llm_for_icp(
            crawl_data, custom_instructions, model=model
        )

        # 4. Attach metadata
        if "raw_metadata" not in icp_dict or not icp_dict["raw_metadata"]:
            icp_dict["raw_metadata"] = {
                "crawl_latency_ms": crawl_data.get("crawl_latency_ms", 0),
                "og_tags_found": list(crawl_data.get("og_tags", {}).keys()),
                "json_ld_count": len(crawl_data.get("json_ld", [])),
            }

        # Ensure domain is present
        if not icp_dict.get("domain"):
            icp_dict["domain"] = crawl_data.get("domain", "")

        # 5. Save to Cache
        await self._save_to_cache(
            url,
            icp_dict,
            custom_instructions=custom_instructions,
            model=model,
            ttl=3600,
        )

        # 6. Validate & Return
        return ReverseIcpResponse.model_validate(icp_dict)
