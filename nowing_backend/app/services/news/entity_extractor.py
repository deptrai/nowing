"""News Named Entity Extractor (Story 14.2a / AC-1, AC-3, AC-4, AD-25, AD-27).

Extracts people, organizations, and locations from news articles, enforces
confidence and type quality gates, applies person PII redaction, and gates
LLM execution with cost controls and Redis caching.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from threading import Lock
from typing import TYPE_CHECKING, Any

from langchain_core.messages import HumanMessage

from app.config import config
from app.services.llm_service import get_agent_llm, get_vision_llm
from app.services.news.entities import VALID_ENTITY_TYPES, NewsEntity, NewsEntityList
from app.services.news.extract_budget import (
    check_news_entity_extraction_allowed,
    record_news_entity_extraction,
)
from app.services.pii.redact import redact_pii
from app.services.quota_checked_vision_llm import QuotaCheckedVisionLLM
from app.services.scraper_chunks.schemas import ChunkValidationError
from app.services.token_tracking_service import UsageType, scoped_turn

try:
    import tiktoken
except Exception:  # pragma: no cover
    tiktoken = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Max context length for extraction: approx 8,000 tokens.
# Vietnamese and mixed text can be denser than 4 chars/token, so we count
# tokens when tiktoken is available and fall back to a worst-case 3
# chars/token reserve (8000 * 3 = 24000) for safe truncation.
MAX_CONTEXT_TOKENS: int = 8000
_FALLBACK_CHARS_PER_TOKEN: int = 3
MAX_CONTEXT_CHARS: int = MAX_CONTEXT_TOKENS * _FALLBACK_CHARS_PER_TOKEN

_CACHE_TTL_SECONDS: int = 3600  # 1 hour
_LOCK_TTL_SECONDS: int = 30  # 30 seconds

_redis = None
_local_cache: dict[str, tuple[float, str]] = {}
_local_locks: dict[str, float] = {}
_lock_mutex = Lock()


def _trim_text_to_token_budget(text: str, max_tokens: int = MAX_CONTEXT_TOKENS) -> str:
    """Trim text to a token budget, falling back to a worst-case char reserve."""
    if not text:
        return text
    if tiktoken is not None:
        try:
            enc = tiktoken.get_encoding("cl100k_base")
            token_count = len(enc.encode(text))
            if token_count <= max_tokens:
                return text
            # Truncate at the last token inside the budget.
            encoded = enc.encode(text)[:max_tokens]
            return enc.decode(encoded)
        except Exception:
            logger.warning("tiktoken trim failed, using char fallback")
    # Worst-case reserve: assume max ~chars per token.
    return text[: max_tokens * _FALLBACK_CHARS_PER_TOKEN]


def _sanitize_prompt_text(text: str) -> str:
    """Redact phone/email and other non-name PII before NER prompt."""
    if not text:
        return text
    try:
        return redact_pii(text, context="news_ner").text
    except Exception:
        logger.warning("news_ner pre-redaction failed, using raw text")
        return text


def _redis_client():
    """Lazily build and cache the sync Redis client."""
    global _redis
    if _redis is None:
        import redis

        _redis = redis.from_url(
            config.REDIS_APP_URL,
            decode_responses=True,
            socket_connect_timeout=0.2,
            socket_timeout=0.2,
        )
    return _redis


def _get_cached_entities(cache_key: str) -> list[NewsEntity] | None:
    """Retrieve cached entities from Redis or local memory fallback."""
    try:
        raw = _redis_client().get(cache_key)
        if raw is not None:
            data = json.loads(raw)
            return [NewsEntity(**item) for item in data]
    except Exception:
        now = time.monotonic()
        with _lock_mutex:
            if cache_key in _local_cache:
                exp, raw = _local_cache[cache_key]
                if now < exp:
                    try:
                        data = json.loads(raw)
                        return [NewsEntity(**item) for item in data]
                    except Exception:
                        pass
    return None


def _set_cached_entities(
    cache_key: str, entities: list[NewsEntity], ttl: int = _CACHE_TTL_SECONDS
) -> None:
    """Save entities into Redis or local memory cache."""
    payload = json.dumps([e.model_dump() for e in entities], ensure_ascii=False)
    try:
        _redis_client().set(cache_key, payload, ex=ttl)
    except Exception:
        now = time.monotonic()
        with _lock_mutex:
            _local_cache[cache_key] = (now + ttl, payload)


def _acquire_lock(lock_key: str, ttl: int = _LOCK_TTL_SECONDS) -> bool:
    """Acquire a lock via Redis SET NX or in-memory fallback."""
    try:
        res = _redis_client().set(lock_key, "1", ex=ttl, nx=True)
        return bool(res)
    except Exception:
        now = time.monotonic()
        with _lock_mutex:
            if lock_key in _local_locks:
                exp = _local_locks[lock_key]
                if now < exp:
                    return False
            _local_locks[lock_key] = now + ttl
            return True


def _release_lock(lock_key: str) -> None:
    """Release extraction lock."""
    try:
        _redis_client().delete(lock_key)
    except Exception:
        with _lock_mutex:
            _local_locks.pop(lock_key, None)


def _build_name_pattern(name: str) -> re.Pattern | None:
    """Build a case-insensitive regex that matches a multi-word name phrase.

    Tokens are escaped and joined by flexible whitespace, then wrapped with
    negative lookarounds so the match only fires at whole-phrase boundaries.
    Leading/trailing punctuation is stripped from the name so the pattern
    masks the words without consuming the surrounding punctuation.
    """
    cleaned = re.sub(r"^[^\w\s]+|[^\w\s]+$", "", name.strip(), flags=re.UNICODE)
    if not cleaned:
        return None
    tokens = [re.escape(t) for t in re.split(r"\s+", cleaned) if t]
    if not tokens:
        return None
    phrase = r"\s+".join(tokens)
    return re.compile(rf"(?i)(?<!\w){phrase}(?!\w)")


def _redact_person_names_in_text(text: str, names: set[str] | list[str]) -> str:
    """Mask every whole-phrase occurrence of each person name with <NAME>."""
    if not text or not names:
        return text
    for name in sorted(
        {n.strip() for n in names if n and n.strip() and n.strip() != "<NAME>"},
        key=len,
        reverse=True,
    ):
        pattern = _build_name_pattern(name)
        if pattern:
            text = pattern.sub("<NAME>", text)
    return text


def _clean_json_snippet(raw_text: str) -> str:
    """Strip markdown code blocks or preamble to isolate the first JSON value."""
    if not raw_text:
        return ""
    text = raw_text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()

    def _extract_balanced(s: str, open_char: str, close_char: str) -> str | None:
        start = s.find(open_char)
        if start == -1:
            return None
        depth = 0
        for i, ch in enumerate(s[start:], start=start):
            if ch == open_char:
                depth += 1
            elif ch == close_char:
                depth -= 1
                if depth == 0:
                    return s[start : i + 1]
        return None

    for open_char, close_char in (("{", "}"), ("[", "]")):
        extracted = _extract_balanced(text, open_char, close_char)
        if extracted:
            return extracted
    return text


def mask_person_entities_in_text(raw_text: str, entities: list[NewsEntity]) -> str:
    """Mask all person surface forms to <NAME> and run PII redaction.

    Order:
    1. Replace person surface forms in text with <NAME> (case-insensitive,
       whole-phrase only, longest phrase first).
    2. Run redact_pii(masked, context="default").
    3. If redaction fails, raise ChunkValidationError.
    """
    if not raw_text:
        return ""

    person_mentions: set[str] = set()
    for e in entities:
        if e.type == "person":
            if e.text and e.text.strip() and e.text.strip() != "<NAME>":
                person_mentions.add(e.text.strip())
            for form in e.surface_forms:
                if form and form.strip() and form.strip() != "<NAME>":
                    person_mentions.add(form.strip())

    masked_text = _redact_person_names_in_text(raw_text, person_mentions)

    try:
        redacted = redact_pii(masked_text, context="default")
        return redacted.text
    except Exception as exc:
        logger.exception("PII redaction failed for news text")
        raise ChunkValidationError(
            domain="news",
            missing=[],
            message=f"unredacted PII: {exc}",
        ) from exc


def redact_entities_metadata(entities: list[NewsEntity]) -> list[dict[str, Any]]:
    """Redact person names in metadata.entities for downstream indexers."""
    person_names: set[str] = set()
    for e in entities:
        if e.type == "person":
            if e.text and e.text.strip() and e.text.strip() != "<NAME>":
                person_names.add(e.text.strip())
            for form in e.surface_forms:
                if form and form.strip() and form.strip() != "<NAME>":
                    person_names.add(form.strip())

    sorted_persons = sorted(person_names, key=len, reverse=True)

    result: list[dict[str, Any]] = []
    for e in entities:
        if e.type == "person":
            result.append(
                {
                    "text": "<NAME>",
                    "type": "person",
                    "confidence": e.confidence,
                    "surface_forms": ["<NAME>"],
                }
            )
        else:
            redacted_text = _redact_person_names_in_text(e.text, sorted_persons)

            redacted_forms = [
                _redact_person_names_in_text(form, sorted_persons)
                for form in e.surface_forms
            ]

            result.append(
                {
                    "text": redacted_text,
                    "type": e.type,
                    "confidence": e.confidence,
                    "surface_forms": redacted_forms,
                }
            )
    return result


class NewsEntityExtractor:
    """Extract named entities from news text with quality gates and cost controls."""

    async def extract(
        self,
        article_text: str,
        workspace_id: int,
        session: AsyncSession,
        *,
        user_id: Any | None = None,
        article_link: str | None = None,
    ) -> list[NewsEntity]:
        """Extract typed named entities (person, organization, location) from article text."""
        if not article_text or not article_text.strip():
            return []

        # 1. Cost-control gate check
        gate = await check_news_entity_extraction_allowed(
            session,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        if not gate.allowed:
            return []

        # 2. Prepare text and context truncation
        # First apply a worst-case char reserve, then count/decode tokens if
        # tiktoken is available so Vietnamese/mixed text does not overflow.
        rough_text = article_text.strip()[:MAX_CONTEXT_CHARS]
        trimmed_text = _trim_text_to_token_budget(rough_text, MAX_CONTEXT_TOKENS)
        # Redact phone/email/ID-style PII before sending to the NER prompt.
        # Names must remain visible so the LLM can extract them.
        trimmed_text = _sanitize_prompt_text(trimmed_text)
        if article_link and article_link.strip():
            identity_hash = hashlib.sha256(
                article_link.strip().encode("utf-8")
            ).hexdigest()
        else:
            identity_hash = hashlib.sha256(trimmed_text.encode("utf-8")).hexdigest()
        cache_key = f"news_entity:{workspace_id}:{identity_hash}"
        lock_key = f"news_entity:lock:{workspace_id}:{identity_hash}"

        # 3. Check Redis cache
        cached = await asyncio.to_thread(_get_cached_entities, cache_key)
        if cached is not None:
            return cached

        # 4. Acquire deduplication lock
        has_lock = await asyncio.to_thread(_acquire_lock, lock_key)
        if not has_lock:
            # Another worker is extracting; check cache again or return []
            await asyncio.sleep(0.5)
            cached = await asyncio.to_thread(_get_cached_entities, cache_key)
            if cached is not None:
                return cached
            return []

        try:
            # 5. Resolve LLM instance
            try:
                model = await get_vision_llm(
                    session, workspace_id, usage_type=UsageType.ENTITY_EXTRACTION
                )
                if model is None:
                    model = await get_agent_llm(session, workspace_id)
            except Exception as exc:
                logger.warning(
                    "news_entity_extraction_degraded workspace_id=%s error=%s",
                    workspace_id,
                    type(exc).__name__,
                    exc_info=True,
                )
                return []

            if model is None:
                return []

            # 6. Build prompt and invoke LLM
            prompt = (
                "Bạn là chuyên gia nhận diện thực thể tên riêng (Named Entity Recognition) cho tin tức tiếng Việt.\n"
                "Hãy trích xuất tất cả các thực thể thuộc 3 loại sau:\n"
                "1. person: Tên người (VD: 'Phạm Minh Chính', 'Joe Biden', 'Elon Musk')\n"
                "2. organization: Tên cơ quan, tổ chức, trường học, công ty, tập đoàn (VD: 'Bộ Y tế', 'Apple', 'Viettel')\n"
                "3. location: Địa danh, tỉnh thành, quận huyện, quốc gia, sân bay, địa điểm (VD: 'Hà Nội', 'Đồng Nai', 'sân bay Long Thành')\n\n"
                "Yêu cầu định dạng đầu ra DUY NHẤT là JSON theo cấu trúc sau:\n"
                "{\n"
                '  "entities": [\n'
                "    {\n"
                '      "text": "Tên thực thể chuẩn",\n'
                '      "type": "person" | "organization" | "location",\n'
                '      "confidence": 0.95,\n'
                '      "surface_forms": ["dạng xuất hiện 1", "dạng xuất hiện 2"]\n'
                "    }\n"
                "  ]\n"
                "}\n\n"
                f"Văn bản tin tức:\n{trimmed_text}"
            )

            is_premium = isinstance(model, QuotaCheckedVisionLLM)
            try:
                if is_premium:
                    response = await model.ainvoke([HumanMessage(content=prompt)])
                else:
                    async with scoped_turn() as acc:
                        response = await model.ainvoke([HumanMessage(content=prompt)])
            except TimeoutError:
                logger.warning(
                    "news_entity_extraction_degraded workspace_id=%s error=TimeoutError",
                    workspace_id,
                )
                return []
            except Exception as exc:
                err_type = type(exc).__name__
                if "RateLimit" in err_type:
                    logger.warning(
                        "news_entity_extraction_degraded workspace_id=%s error=%s",
                        workspace_id,
                        err_type,
                    )
                elif "Quota" in err_type or "Insufficient" in err_type:
                    logger.warning(
                        "news_entity_extraction_quota_exhausted workspace_id=%s error=%s",
                        workspace_id,
                        err_type,
                    )
                else:
                    logger.warning(
                        "news_entity_extraction_degraded workspace_id=%s error=%s",
                        workspace_id,
                        err_type,
                        exc_info=True,
                    )
                return []

            if response is None or response.content is None:
                logger.info(
                    "news_entity_extraction_fallback workspace_id=%s reason=empty",
                    workspace_id,
                )
                return []

            if isinstance(response.content, list):
                raw_content = "".join(
                    str(b.get("text", b) if isinstance(b, dict) else b)
                    for b in response.content
                ).strip()
            else:
                raw_content = str(response.content).strip()

            if not raw_content:
                logger.info(
                    "news_entity_extraction_fallback workspace_id=%s reason=empty",
                    workspace_id,
                )
                return []

            json_str = _clean_json_snippet(raw_content)
            try:
                parsed = json.loads(json_str)
                if isinstance(parsed, list):
                    entity_list = NewsEntityList.model_validate({"entities": parsed})
                elif (
                    isinstance(parsed, dict)
                    and "entities" in parsed
                    and parsed["entities"] is not None
                ):
                    entity_list = NewsEntityList.model_validate(parsed)
                else:
                    logger.info(
                        "news_entity_extraction_fallback workspace_id=%s reason=empty snippet=%s",
                        workspace_id,
                        json_str[:100],
                    )
                    return []
            except Exception:
                logger.info(
                    "news_entity_extraction_fallback workspace_id=%s reason=malformed_json snippet=%s",
                    workspace_id,
                    json_str[:100],
                )
                return []

            raw_entities = entity_list.entities
            if not raw_entities:
                return []

            # 7. Quality Gates: Confidence threshold & Type filtering
            min_confidence = config.NEWS_ENTITY_EXTRACTION_CONFIDENCE
            valid_entities: list[NewsEntity] = []

            for entity in raw_entities:
                if entity.type not in VALID_ENTITY_TYPES:
                    logger.info(
                        "news_entity_unknown_type_dropped workspace_id=%s unknown_type=%s",
                        workspace_id,
                        entity.type,
                    )
                    continue

                if entity.confidence < min_confidence:
                    continue

                valid_entities.append(entity)

            # 8. Deduplicate by (type, normalized_text) keeping highest confidence
            dedup_map: dict[tuple[str, str], NewsEntity] = {}
            for entity in valid_entities:
                key = (entity.type, entity.normalized_text)
                if key not in dedup_map:
                    dedup_map[key] = entity
                else:
                    existing = dedup_map[key]
                    merged_surfaces = list(
                        dict.fromkeys(existing.surface_forms + entity.surface_forms)
                    )
                    if entity.confidence > existing.confidence:
                        dedup_map[key] = NewsEntity(
                            text=entity.text,
                            type=entity.type,
                            confidence=entity.confidence,
                            surface_forms=merged_surfaces,
                        )
                    else:
                        dedup_map[key] = NewsEntity(
                            text=existing.text,
                            type=existing.type,
                            confidence=existing.confidence,
                            surface_forms=merged_surfaces,
                        )

            final_entities = list(dedup_map.values())

            # 9. Record cost tracking
            if is_premium:
                # QuotaCheckedVisionLLM records TokenUsage via billable_call
                # with the correct usage_type; only the rate counter needs
                # to be incremented here.
                await record_news_entity_extraction(
                    session,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    record_usage=False,
                )
            else:
                usage_meta = getattr(response, "usage_metadata", None) or {}
                if acc.calls:
                    prompt_tokens = acc.total_prompt_tokens
                    completion_tokens = acc.total_completion_tokens
                    total_tokens = acc.grand_total
                    cost_micros = acc.total_cost_micros
                    model_breakdown = acc.per_message_summary()
                    model_name = next(iter(model_breakdown), None)
                else:
                    prompt_tokens = int(usage_meta.get("prompt_tokens") or 0)
                    completion_tokens = int(usage_meta.get("completion_tokens") or 0)
                    total_tokens = int(usage_meta.get("total_tokens") or 0)
                    cost_micros = 0
                    model_breakdown = None
                    model_name = None

                await record_news_entity_extraction(
                    session,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    cost_micros=cost_micros,
                    model=model_name,
                    model_breakdown=model_breakdown,
                    call_details={"model": model_name} if model_name else None,
                )

            # 10. Cache in Redis
            await asyncio.to_thread(_set_cached_entities, cache_key, final_entities)

            return final_entities

        finally:
            await asyncio.to_thread(_release_lock, lock_key)


def clear_entity_cache() -> None:
    """Clear in-memory cache and Redis keys for testing."""
    with _lock_mutex:
        _local_cache.clear()
        _local_locks.clear()
    try:
        r = _redis_client()
        for key in r.scan_iter("news_entity*"):
            r.delete(key)
    except Exception:
        pass


__all__ = [
    "MAX_CONTEXT_CHARS",
    "NewsEntityExtractor",
    "clear_entity_cache",
    "mask_person_entities_in_text",
    "redact_entities_metadata",
]
