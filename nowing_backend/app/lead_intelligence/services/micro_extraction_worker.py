"""Selective micro-LLM fallback worker for low-confidence leads (Story 21.21)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from app.lead_intelligence.adapters.base import (
    NormalizedLead,
    extract_phones_from_text,
    normalize_vietnamese_phone,
)
from app.lead_intelligence.confidence import ConfidenceGate
from app.lead_intelligence.confidence.numbers import (
    is_thoa_thuan_price,
    normalize_number,
    price_to_float,
)
from app.lead_intelligence.confidence.prompts import (
    build_batch_prompt,
    build_response_schema,
)
from app.proprietary.platforms.batdongsan.parsers import (
    _extract_number_and_unit,
    _parse_area,
    _split_address,
)
from app.proprietary.platforms.xactions.phone_extractor import extract_phone_numbers
from app.schemas.hybrid_llm import HybridLLMRequest
from app.services.hybrid_llm_router import HybridLLMError, HybridLLMRouter

logger = logging.getLogger(__name__)

_DEFAULT_BATCH_SIZE = 5
_DEFAULT_MAX_CONCURRENCY = 20
_PER_CALL_TIMEOUT = 2.0
_MAX_RETRIES = 1
# ponytail: budget per batch, not per call. Approximate; router records actual usage.
_TOKEN_BUDGET = 4000
# per chunk timeout: per-call timeout * (retries + 1) + slack
_CHUNK_TIMEOUT = _PER_CALL_TIMEOUT * (_MAX_RETRIES + 1) + 0.5
_CIRCUIT_BREAKER_THRESHOLD = 3


class MicroExtractionWorker:
    """Lightweight LLM fallback that only enriches missing lead fields."""

    def __init__(
        self,
        router: HybridLLMRouter | None = None,
        batch_size: int = _DEFAULT_BATCH_SIZE,
        max_concurrency: int = _DEFAULT_MAX_CONCURRENCY,
    ) -> None:
        self._router = router or HybridLLMRouter()
        self._batch_size = min(max(batch_size, 2), 10)
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._tokens_used = 0
        self._consecutive_failures = 0
        self._stop_event: asyncio.Event | None = None
        self._token_lock: asyncio.Lock | None = None
        self._batch_state_lock: asyncio.Lock | None = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def micro_batch(
        self,
        records: list[NormalizedLead],
        workspace_id: int,
        user_id: UUID | None = None,
    ) -> list[NormalizedLead]:
        """Enrich low-confidence records with a public-tier micro-LLM.

        Records with no extractable snippet are skipped and marked for later
        async enrichment. The worker fails softly: no exception is raised on
        timeout, 429, or parse errors.
        """
        if not records:
            return []

        # Split into chunks so one LLM call handles 5-10 snippets.
        chunks = self._chunk_records(records, self._batch_size)

        # Reset per-batch state.
        self._tokens_used = 0
        self._consecutive_failures = 0
        self._stop_event = asyncio.Event()
        self._token_lock = asyncio.Lock()
        self._batch_state_lock = asyncio.Lock()

        async def _process_chunk(chunk: list[NormalizedLead]) -> list[NormalizedLead]:
            async with self._semaphore:
                return await self._process_chunk_with_retry(
                    chunk, workspace_id, user_id
                )

        # ponytail: a global gather timeout discards work from already-completed
        # chunks and is shorter than the worst-case retry path. Bound each chunk
        # instead so one slow chunk only degrades its own records.
        results = await asyncio.gather(
            *(
                asyncio.wait_for(_process_chunk(chunk), timeout=_CHUNK_TIMEOUT)
                for chunk in chunks
            ),
            return_exceptions=True,
        )

        # Flatten results and apply any per-chunk degradation.
        for chunk, result in zip(chunks, results, strict=True):
            if isinstance(result, BaseException):
                logger.warning(
                    "Micro-extraction chunk degraded for workspace %s: %s",
                    workspace_id,
                    result,
                )
                for record in chunk:
                    record.needs_enrichment = True

        return records

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _chunk_records(
        self, records: list[NormalizedLead], size: int
    ) -> list[list[NormalizedLead]]:
        return [records[i : i + size] for i in range(0, len(records), size)]

    async def _process_chunk_with_retry(
        self,
        chunk: list[NormalizedLead],
        workspace_id: int,
        user_id: UUID | None,
    ) -> list[NormalizedLead]:
        """Try a chunk once and retry once on transient failure, then degrade."""
        if self._stop_event and self._stop_event.is_set():
            for record in chunk:
                record.needs_enrichment = True
            return chunk

        last_exception: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                return await self._call_and_merge(chunk, workspace_id, user_id)
            except (HybridLLMError, TimeoutError) as exc:
                last_exception = exc
                logger.debug(
                    "Micro-extraction chunk attempt %d failed (%s), retrying...",
                    attempt,
                    exc,
                )

        if last_exception is not None:
            logger.warning(
                "Micro-extraction chunk failed after %d retries: %s",
                _MAX_RETRIES + 1,
                last_exception,
            )
            for record in chunk:
                record.needs_enrichment = True
            if self._batch_state_lock:
                async with self._batch_state_lock:
                    self._consecutive_failures += 1
                    if (
                        self._consecutive_failures >= _CIRCUIT_BREAKER_THRESHOLD
                        and self._stop_event
                    ):
                        self._stop_event.set()
        return chunk

    async def _call_and_merge(
        self,
        chunk: list[NormalizedLead],
        workspace_id: int,
        user_id: UUID | None,
    ) -> list[NormalizedLead]:
        """Build a batch prompt, call the router, merge valid fields, and re-score."""
        if self._stop_event and self._stop_event.is_set():
            for record in chunk:
                record.needs_enrichment = True
            return chunk

        # Keep only records that have an ambiguous snippet worth sending.
        prompt, selected_indices = build_batch_prompt(chunk)
        if not prompt:
            logger.debug("No anchor found for chunk of %d records", len(chunk))
            for record in chunk:
                record.needs_enrichment = True
            return chunk

        selected_records = [chunk[i] for i in selected_indices]
        schema = build_response_schema(batch_size=len(selected_records))

        # ponytail: estimate tokens at ~4 chars/token; actual usage replaces the estimate.
        estimated_tokens = len(prompt) // 4
        if self._token_lock:
            async with self._token_lock:
                if self._tokens_used + estimated_tokens > _TOKEN_BUDGET:
                    logger.warning(
                        "Micro-extraction token budget exceeded for workspace %s; "
                        "degrading %d records",
                        workspace_id,
                        len(chunk),
                    )
                    for record in chunk:
                        record.needs_enrichment = True
                    return chunk
                self._tokens_used += estimated_tokens

        try:
            raw_response = await asyncio.wait_for(
                self._router.ainvoke(
                    HybridLLMRequest(
                        workspace_id=workspace_id,
                        user_id=user_id,
                        task_type="micro_extraction",
                        sensitivity="public",
                        messages=[
                            {"role": "system", "content": self._system_message()},
                            {"role": "user", "content": prompt},
                        ],
                        response_model=schema,
                    )
                ),
                timeout=_PER_CALL_TIMEOUT,
            )
        except Exception:
            logger.exception("Micro-extraction LLM call failed")
            raise
        finally:
            if self._token_lock:
                async with self._token_lock:
                    self._tokens_used = max(0, self._tokens_used - estimated_tokens)

        actual_tokens = len(prompt) // 4
        usage = getattr(raw_response, "_usage", None)
        if usage is not None:
            total = getattr(usage, "total_tokens", 0)
            if isinstance(total, (int, float)) and not isinstance(total, bool):
                actual_tokens = int(total)

        if self._token_lock:
            async with self._token_lock:
                self._tokens_used += actual_tokens

        raw_content = raw_response.content or {}

        for snippet_index, record in enumerate(selected_records):
            key = str(snippet_index)
            result = raw_content.get(key) if isinstance(raw_content, dict) else None

            if result is None:
                # LLM did not return anything for this snippet.
                record.needs_enrichment = True
                continue

            missing = self._missing_fields(record)
            merged = self.parse_and_validate(result, missing)
            self._merge_record(record, merged)
            ConfidenceGate.score(record)

        # Records with no snippet were already marked above.
        return chunk

    def _system_message(self) -> str:
        return (
            "Trích xuất tin rao Việt Nam. "
            "Trả JSON: phone, price, district, area, title. "
            "SĐT 10 số, giá số, quận/huyện tên ngắn."
        )

    # ------------------------------------------------------------------ #
    # Re-validation & merge
    # ------------------------------------------------------------------ #
    @staticmethod
    def _missing_fields(record: NormalizedLead) -> set[str]:
        """Return the set of fields the record is currently missing."""
        missing: set[str] = set()
        if not record.primary_phone or not record.primary_phone.strip():
            missing.add("phone")
        if record.price is None or (
            record.price <= 0 and not is_thoa_thuan_price(record.price, record.raw_data)
        ):
            missing.add("price")

        district, _ = _split_address(record.address)
        if not district or not district.strip():
            missing.add("district")

        if (record.area is None or record.area <= 0) and (
            MicroExtractionWorker._validate_area(record.raw_data.get("area")) is None
        ):
            missing.add("area")

        title = (record.title or "").strip()
        if not title or title in ConfidenceGate.DEFAULT_TITLES:
            missing.add("title")

        return missing

    @staticmethod
    def _merge_record(record: NormalizedLead, merged: dict[str, Any]) -> None:
        """Merge extracted values only into fields that are currently missing."""
        if "phone" in merged:
            record.primary_phone = merged["phone"]
            # Add to contact candidates for downstream deduplication.
            if not any(
                c.channel == "phone" and c.value == merged["phone"]
                for c in record.contact_candidates
            ):
                from app.lead_intelligence.adapters.base import ContactCandidate

                record.contact_candidates.append(
                    ContactCandidate(
                        channel="phone",
                        value=merged["phone"],
                        confidence=0.75,
                        metadata={"source_field": "micro_llm"},
                    )
                )
        if "price" in merged and merged["price"] is not None:
            record.price = merged["price"]
        if "district" in merged:
            record.address = MicroExtractionWorker._inject_district(
                record.address, merged["district"]
            )
            # If city was missing but the district string includes it, _split_address
            # will resolve it on the next re-score.
        if "area" in merged and merged["area"] is not None:
            record.area = merged["area"]
            record.raw_data["area"] = merged["area"]
        if merged.get("title") and (
            not record.title or record.title.strip() in ConfidenceGate.DEFAULT_TITLES
        ):
            record.title = merged["title"]

    @staticmethod
    def _inject_district(address: str | None, district: str) -> str:
        """Return an address string that includes the extracted district."""
        if not address:
            return district
        if district in address:
            return address
        return f"{district}, {address}"

    @classmethod
    def parse_and_validate(
        cls, raw: dict[str, Any], missing_fields: set[str]
    ) -> dict[str, Any]:
        """Re-run Pass 1 parsers on the LLM output and keep only valid missing fields."""
        merged: dict[str, Any] = {}

        if "phone" in missing_fields:
            phone = cls._validate_phone(raw.get("phone"))
            if phone:
                merged["phone"] = phone

        if "price" in missing_fields:
            price = cls._validate_price(raw.get("price"))
            if price is not None and price > 0:
                merged["price"] = price

        if "district" in missing_fields:
            district = cls._validate_district(raw.get("district"))
            if district:
                merged["district"] = district

        if "area" in missing_fields:
            area = cls._validate_area(raw.get("area"))
            if area is not None and area > 0:
                merged["area"] = area

        if "title" in missing_fields:
            title = cls._validate_title(raw.get("title"))
            if title:
                merged["title"] = title

        return merged

    # ------------------------------------------------------------------ #
    # Field validators
    # ------------------------------------------------------------------ #
    @staticmethod
    def _validate_phone(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None

        # Try the robust word-number / homoglyph extractor first, then fall back
        # to the base adapter regex.
        phones = extract_phone_numbers(
            text, timeout_sec=0.05
        ) or extract_phones_from_text(text)
        if not phones:
            return None

        best = normalize_vietnamese_phone(phones[0])
        if not best or len(best) not in (10, 11):
            return None

        # Suppress 1900/1800 service hotlines.
        if best.startswith("1900") or best.startswith("1800"):
            return None

        return best

    @staticmethod
    def _validate_price(value: Any) -> float | None:
        return price_to_float(value)

    @staticmethod
    def _validate_district(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None

        # Prefer a comma-delimited address split.
        district, _ = _split_address(text)
        if district:
            return district

        # Fallback: strip district prefixes and keep the bare name.
        stripped = text
        for prefix in ("Quận", "Huyện", "Thị xã", "TX.", "H."):
            if stripped.lower().startswith(prefix.lower()):
                stripped = stripped[len(prefix) :].strip(" .")
                break
        if not stripped:
            return None
        # Reject all-numeric garbage (e.g. 1900, 1800, long numeric codes).
        if stripped.isdigit() and len(stripped) > 2:
            return None
        if stripped in ("1900", "1800"):
            return None
        return stripped

    @staticmethod
    def _validate_area(value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value) if value > 0 else None

        text = str(value).strip()
        area, _, _ = _parse_area(text)
        if not area:
            area = text

        number = normalize_number(_extract_number_and_unit(area) or area)
        return number if number is not None and number > 0 else None

    @staticmethod
    def _validate_title(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text or len(text) < 3:
            return None
        return text
