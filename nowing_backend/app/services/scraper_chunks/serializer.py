"""Normalize heterogeneous scraper output into canonical ``Chunk[]`` objects."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from app.services.pii.redact import redact_job_pii, redact_pii

from .schemas import Chunk, ChunkMetadata, ChunkValidationError

logger = logging.getLogger(__name__)

try:
    import tiktoken
except Exception:  # pragma: no cover - tiktoken may be unavailable in minimal envs
    tiktoken = None  # type: ignore[assignment]

# Domain registry. Unknown domains default to listing-style serialization.
_JOB_DOMAINS = {"vn_jobs", "itviec", "topcv", "vietnamworks"}
_LISTING_DOMAINS = {"bds", "batdongsan", "chotot", "muaban_bds"}

# Canonical wire-domain names exposed in ChunkMetadata.domain (Story 12.3 AC-9).
_DOMAIN_CANONICAL = {
    "itviec": "itviec.com",
    "topcv": "topcv.com",
    "vietnamworks": "vietnamworks.com",
}


def _canonical_domain(domain: str) -> str:
    """Return the canonical domain name for chunk metadata."""
    return _DOMAIN_CANONICAL.get(domain, domain)


def _is_job_domain(domain: str) -> bool:
    """Return True if ``domain`` is a known job domain."""
    return domain in _JOB_DOMAINS


def _is_listing_domain(domain: str) -> bool:
    """Return True if ``domain`` is a known listing domain."""
    return domain in _LISTING_DOMAINS


def _to_dict(data: Mapping[str, Any] | BaseModel | object) -> dict[str, Any]:
    """Coerce a pydantic model or dict into a plain dict."""
    if isinstance(data, BaseModel):
        return data.model_dump()
    if isinstance(data, Mapping):
        return dict(data)
    raise TypeError(f"to_chunks expects a dict or pydantic model, got {type(data)!r}")


def _get(data: dict[str, Any], *keys: str) -> Any:
    """Return the first present key or None."""
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return None


def _url_from_data(data: dict[str, Any]) -> str | None:
    """Return a single canonical URL from a scraper record if available.

    ``detail_urls`` may be a dict of source -> URL; pick the first non-empty string.
    """
    for key in ("detail_url", "source_url", "url", "apply_url"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    detail_urls = data.get("detail_urls")
    if isinstance(detail_urls, dict):
        for v in detail_urls.values():
            if isinstance(v, str) and v.strip():
                return v.strip()
    return None


def _redact_text(text: str | None, *, domain: str, context: str) -> str:
    """Mask PII before it becomes chunk content.

    Raises ``ChunkValidationError`` if the redactor itself fails so that PII is
    never silently emitted.
    """
    if not text:
        return ""
    try:
        if context == "job_data":
            return redact_job_pii(text).text
        return redact_pii(text, context=context).text
    except Exception as exc:
        logger.exception("PII redaction failed for domain %s context %s", domain, context)
        raise ChunkValidationError(
            domain=domain,
            missing=[],
            message=f"redaction failed: {exc}",
        ) from exc


def _required_fields(domain: str) -> list[str]:
    if _is_job_domain(domain):
        return ["title", "company", "location"]
    return ["title", "city", "district", "price"]


def _build_content(domain: str, data: dict[str, Any]) -> str:
    """Create a plain-text representation of a scraper record."""
    parts: list[str] = []

    def _add_part(label: str, value: str) -> None:
        parts.append(f"{label}: {value}")

    if _is_job_domain(domain):
        title = _get(data, "title") or ""
        company = _get(data, "company") or ""
        location = _get(data, "location") or ""
        employment_type = _get(data, "employment_type") or ""
        salary = data.get("salary")
        salary_text = ""
        if isinstance(salary, dict):
            salary_text = json.dumps(salary, ensure_ascii=False)
        elif salary is not None:
            salary_text = str(salary)
        posted_at = _get(data, "posted_at") or ""
        description = _redact_text(
            _get(data, "job_description", "description"),
            domain=domain,
            context="job_data",
        )
        requirement = _redact_text(
            _get(data, "job_requirement", "requirement"),
            domain=domain,
            context="job_data",
        )

        _add_part("Title", title)
        _add_part("Company", company)
        _add_part("Location", location)
        _add_part("Employment Type", employment_type)
        _add_part("Salary", salary_text)
        _add_part("Posted At", posted_at)
        if description:
            _add_part("Description", description)
        if requirement:
            _add_part("Requirements", requirement)
    else:
        # Default real-estate / listing-style serialization.
        title = _get(data, "title") or ""
        price = _get(data, "price") or ""
        area = _get(data, "area") or ""
        location = _get(data, "location") or ""
        district = _get(data, "district") or ""
        ward = _get(data, "ward") or ""
        city = _get(data, "city") or ""
        project = _get(data, "project") or ""
        legal = _get(data, "legal") or ""
        post_date = _get(data, "post_date") or ""
        description = _redact_text(
            _get(data, "description"), domain=domain, context="default"
        )
        detail_urls = data.get("detail_urls", {})

        _add_part("Title", title)
        _add_part("Price", price)
        _add_part("Area", area)
        _add_part("Location", location)
        _add_part("District", district)
        _add_part("Ward", ward)
        _add_part("City", city)
        _add_part("Project", project)
        _add_part("Legal", legal)
        _add_part("Post Date", post_date)
        if description:
            _add_part("Description", description)
        if detail_urls:
            parts.append(
                f"Detail URLs: {json.dumps(detail_urls, ensure_ascii=False, default=str)}"
            )

    return _redact_text(
        "\n".join(part for part in parts if _part_has_value(part)),
        domain=domain,
        context="default",
    )


def _part_has_value(part: str) -> bool:
    """Return True if a label:value part has a non-empty value."""
    if ": " not in part:
        return False
    return bool(part.split(": ", 1)[1].strip())


def _identity_fields(domain: str, data: dict[str, Any]) -> dict[str, Any]:
    """Extract the stable fields that should feed the sourceId fingerprint."""
    canonical_id = _get(data, "canonical_id", "id")
    if canonical_id:
        return {"canonical_id": str(canonical_id)}

    if _is_job_domain(domain):
        # ponytail: stable identity excludes volatile salary/employment_type
        # and includes posted_at for temporal dedupe (AC-3, Story 12.4d).
        return {
            "company": _get(data, "company"),
            "title": _get(data, "title"),
            "location": _get(data, "location"),
            "posted_at": _get(data, "posted_at"),
        }

    return {
        "title": _get(data, "title"),
        "price": _get(data, "price"),
        "area": _get(data, "area"),
        "district": _get(data, "district"),
        "ward": _get(data, "ward"),
        "city": _get(data, "city"),
        "project": _get(data, "project"),
        "legal": _get(data, "legal"),
    }


def _stable_fingerprint(domain: str, data: dict[str, Any]) -> str:
    """Return a deterministic, domain-prefixed fingerprint for a record."""
    identity = _identity_fields(domain, data)
    payload = json.dumps(
        {k: str(v) for k, v in sorted(identity.items()) if v is not None},
        sort_keys=True,
        ensure_ascii=False,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
    return f"{domain}:sha256:{digest}"


def _word_tokens_for_chunk(encoder: Any, word: str, is_first: bool) -> list[int]:
    """Return tokens for ``word`` as it appears inside a joined chunk.

    ``tiktoken`` encodes a leading space as part of the next word, so the first
    word in a chunk does not get a leading-space token.
    """
    tokens = encoder.encode(" " + word)
    if is_first and len(tokens) > 1:
        return tokens[1:]
    return tokens


def _split_tokens(text: str, max_tokens: int = 8000) -> list[str]:
    """Split ``text`` into chunks of at most ``max_tokens`` tokens.

    Falls back to word splitting when ``tiktoken`` is not available.
    """
    if tiktoken is None:
        words = text.split()
        if not words:
            return [text] if text else []
        return [
            " ".join(words[i : i + max_tokens])
            for i in range(0, len(words), max_tokens)
        ]

    encoder = tiktoken.get_encoding("cl100k_base")
    words = text.split()
    if not words:
        return [text] if text else []

    chunks: list[str] = []
    current_words: list[str] = []
    current_token_count = 0

    for word in words:
        is_first = not current_words
        word_tokens = _word_tokens_for_chunk(encoder, word, is_first)
        word_token_count = len(word_tokens)

        # A single word may exceed max_tokens; include it as its own chunk to
        # avoid an infinite loop.
        if word_token_count > max_tokens and not current_words:
            chunks.append(word)
            continue

        if current_words and current_token_count + word_token_count > max_tokens:
            chunks.append(" ".join(current_words))
            current_words = [word]
            current_token_count = len(_word_tokens_for_chunk(encoder, word, True))
        else:
            current_words.append(word)
            current_token_count += word_token_count

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _metadata_from_data(
    domain: str,
    data: dict[str, Any],
    fetched_at: str,
    content_type: str,
    category: str | None,
    source_id: str,
    chunk_index: int,
    chunk_total: int,
) -> ChunkMetadata:
    """Build ChunkMetadata, carrying optional provenance fields from the raw record."""
    canonical_id = _get(data, "canonical_id", "id")
    confidence_score = _get(data, "confidence_score")
    source_count = _get(data, "source_count")
    conflict_flags = data.get("conflict_flags")
    salary = data.get("salary")
    salary_consistency_score = _get(data, "salary_consistency_score")
    title = _get(data, "title")
    url = _url_from_data(data)

    # ponytail: salary is volatile and may be None or negotiable (0 values).
    # Only emit salary metadata when it contains a real range (AC-3).
    clean_salary: dict[str, Any] | None = None
    if salary and isinstance(salary, dict) and (salary.get("min") or salary.get("max")):
        clean_salary = salary

    return ChunkMetadata(
        source="nowing_scraper",
        sourceId=source_id,
        domain=domain,
        fetchedAt=fetched_at,
        contentType=content_type,
        title=title.strip() if isinstance(title, str) and title.strip() else None,
        url=url,
        category=category,
        confidence_score=_safe_float(confidence_score),
        source_count=_safe_int(source_count),
        conflict_flags=conflict_flags if isinstance(conflict_flags, list) else None,
        salary=clean_salary,
        salary_consistency_score=_safe_float(salary_consistency_score),
        chunkIndex=chunk_index,
        chunkTotal=chunk_total,
        canonicalEntityId=str(canonical_id) if canonical_id else None,
    )


def to_chunks(
    *,
    domain: str,
    data: Mapping[str, Any] | BaseModel,
    fetched_at: str,
    content_type: str = "text/markdown",
    category: str | None = None,
) -> list[Chunk]:
    """Normalize one scraper record or aggregated entity into ``Chunk[]``.

    ``content_type`` is the default metadata type; job domains override it to
    ``"job"`` so ChainLens can filter on ``contentType`` (Story 12.3 AC-9).
    ``category`` is an optional domain label (e.g. ``listing``, ``job_posting``)
    used by ChainLens for filtering/ranking.

    The returned chunks have deterministic ``sourceId`` values and split
    oversize content at token boundaries while preserving ``chunkIndex`` /
    ``chunkTotal`` metadata.
    """
    if not _is_job_domain(domain) and not _is_listing_domain(domain):
        logger.warning(
            "Domain %s is not in the scraper_chunks registry; defaulting to listing layout",
            domain,
        )

    data = _to_dict(data)
    required = _required_fields(domain)
    missing = [field for field in required if _get(data, field) in (None, "")]
    if missing:
        raise ChunkValidationError(domain=domain, missing=missing)

    base_source_id = _stable_fingerprint(domain, data)
    full_content = _build_content(domain, data)

    if not full_content.strip():
        raise ChunkValidationError(
            domain=domain,
            missing=["content"],
            message=f"{domain}: serialized content is empty",
        )

    metadata_domain = _canonical_domain(domain)
    metadata_content_type = "job" if _is_job_domain(domain) else content_type
    pieces = _split_tokens(full_content, max_tokens=8000)
    total = len(pieces)
    chunks: list[Chunk] = []
    for index, piece in enumerate(pieces):
        source_id = f"{base_source_id}:chunk-{index}" if total > 1 else base_source_id
        metadata = _metadata_from_data(
            metadata_domain,
            data,
            fetched_at,
            metadata_content_type,
            category,
            source_id,
            index,
            total,
        )
        chunks.append(Chunk(content=piece, metadata=metadata))
    return chunks
