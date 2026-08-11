"""Normalize heterogeneous scraper output into canonical ``Chunk[]`` objects."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from app.services.pii.redact import redact_pii

from .schemas import Chunk, ChunkMetadata, ChunkValidationError


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


def _redact_text(text: str | None) -> str:
    """Mask PII before it becomes chunk content."""
    if not text:
        return ""
    return redact_pii(text).text


def _build_content(domain: str, data: dict[str, Any]) -> str:
    """Create a plain-text representation of a scraper record."""
    parts: list[str] = []

    if domain == "vn_jobs" or domain.endswith("_jobs"):
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
        description = _redact_text(_get(data, "job_description", "description"))
        requirement = _redact_text(_get(data, "job_requirement", "requirement"))

        parts.extend(
            [
                f"Title: {title}",
                f"Company: {company}",
                f"Location: {location}",
                f"Employment Type: {employment_type}",
                f"Salary: {salary_text}",
                f"Posted At: {posted_at}",
            ]
        )
        if description:
            parts.append(f"Description: {description}")
        if requirement:
            parts.append(f"Requirements: {requirement}")
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
        description = _redact_text(_get(data, "description"))
        detail_urls = data.get("detail_urls", {})

        parts.extend(
            [
                f"Title: {title}",
                f"Price: {price}",
                f"Area: {area}",
                f"Location: {location}",
                f"District: {district}",
                f"Ward: {ward}",
                f"City: {city}",
                f"Project: {project}",
                f"Legal: {legal}",
                f"Post Date: {post_date}",
            ]
        )
        if description:
            parts.append(f"Description: {description}")
        if detail_urls:
            parts.append(
                f"Detail URLs: {json.dumps(detail_urls, ensure_ascii=False, default=str)}"
            )

    return _redact_text("\n".join(part for part in parts if part.split(": ", 1)[1]))


def _required_fields(domain: str) -> list[str]:
    if domain == "vn_jobs" or domain.endswith("_jobs"):
        return ["title", "company", "location"]
    return ["title", "city", "district", "price"]


def _identity_fields(domain: str, data: dict[str, Any]) -> dict[str, Any]:
    """Extract the stable fields that should feed the sourceId fingerprint."""
    canonical_id = _get(data, "canonical_id", "id")
    if canonical_id:
        return {"canonical_id": str(canonical_id)}

    if domain == "vn_jobs" or domain.endswith("_jobs"):
        return {
            "title": _get(data, "title"),
            "company": _get(data, "company"),
            "location": _get(data, "location"),
            "salary": _get(data, "salary"),
            "employment_type": _get(data, "employment_type"),
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


def _split_words(text: str, max_words: int = 8000) -> list[str]:
    """Split text into chunks of at most ``max_words`` words."""
    words = text.split()
    if not words:
        return [text] if text else []
    return [" ".join(words[i : i + max_words]) for i in range(0, len(words), max_words)]


def _metadata_from_data(
    domain: str,
    data: dict[str, Any],
    fetched_at: str,
    content_type: str,
    source_id: str,
    chunk_index: int,
    chunk_total: int,
) -> ChunkMetadata:
    """Build ChunkMetadata, carrying optional provenance fields from the raw record."""
    canonical_id = _get(data, "canonical_id", "id")
    confidence_score = _get(data, "confidence_score")
    source_count = _get(data, "source_count")
    conflict_flags = data.get("conflict_flags")

    return ChunkMetadata(
        source="nowing_scraper",
        sourceId=source_id,
        domain=domain,
        fetchedAt=fetched_at,
        contentType=content_type,
        confidence_score=float(confidence_score)
        if confidence_score is not None
        else None,
        source_count=int(source_count) if source_count is not None else None,
        conflict_flags=conflict_flags if isinstance(conflict_flags, list) else None,
        chunkIndex=chunk_index,
        chunkTotal=chunk_total,
        canonicalEntityId=str(canonical_id) if canonical_id else None,
    )


def to_chunks(
    *,
    domain: str,
    data: Mapping[str, Any] | BaseModel,
    fetched_at: str,
    content_type: str,
) -> list[Chunk]:
    """Normalize one scraper record or aggregated entity into ``Chunk[]``.

    The returned chunks have deterministic ``sourceId`` values and split
    oversize content at word boundaries while preserving ``chunkIndex`` /
    ``chunkTotal`` metadata.
    """
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

    pieces = _split_words(full_content, max_words=8000)
    total = len(pieces)
    chunks: list[Chunk] = []
    for index, piece in enumerate(pieces):
        source_id = f"{base_source_id}:chunk-{index}" if total > 1 else base_source_id
        metadata = _metadata_from_data(
            domain,
            data,
            fetched_at,
            content_type,
            source_id,
            index,
            total,
        )
        chunks.append(Chunk(content=piece, metadata=metadata))
    return chunks
