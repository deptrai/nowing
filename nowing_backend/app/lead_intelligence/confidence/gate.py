"""Deterministic confidence gate for ``NormalizedLead`` schema completeness."""

from __future__ import annotations

from app.lead_intelligence.adapters.base import NormalizedLead
from app.lead_intelligence.confidence.numbers import (
    is_thoa_thuan_price,
    normalize_number,
)
from app.lead_intelligence.confidence.schemas import (
    REQUIRED_FIELDS,
    SchemaCompletenessResult,
    SchemaField,
)
from app.proprietary.platforms.batdongsan.parsers import (
    _extract_number_and_unit,
    _parse_area,
    _split_address,
)


class ConfidenceGate:
    """Score a lead record on the presence of required schema fields."""

    CRITICAL_FIELDS = frozenset(
        {SchemaField.PHONE, SchemaField.PRICE, SchemaField.DISTRICT}
    )

    # Default titles that adapters fall back to when no real title is available.
    # ponytail: keep a small hard-coded list; expand if more adapters introduce
    # similar placeholders.
    DEFAULT_TITLES = frozenset({"Bất động sản rao bán", "Doanh nghiệp"})

    @classmethod
    def score(cls, normalized: NormalizedLead) -> SchemaCompletenessResult:
        """Return the schema-completeness result and annotate ``normalized`` in place."""
        present: set[SchemaField] = set()

        if cls._has_phone(normalized):
            present.add(SchemaField.PHONE)
        if cls._has_price(normalized):
            present.add(SchemaField.PRICE)
        if cls._has_district(normalized):
            present.add(SchemaField.DISTRICT)
        if cls._has_area(normalized):
            present.add(SchemaField.AREA)
        if cls._has_title(normalized):
            present.add(SchemaField.TITLE)

        missing = REQUIRED_FIELDS - present
        critical_missing = bool(missing & cls.CRITICAL_FIELDS)

        # Score is the ratio of present required fields (0.0-1.0).
        score = round(len(present) / len(REQUIRED_FIELDS), 4)

        # A record in the 0.70-0.85 band needs non-blocking async enrichment,
        # unless a critical field is already missing (that record goes to the
        # micro-extraction worker instead).
        needs_enrichment = 0.70 <= score < 0.85 and not critical_missing

        normalized.schema_completeness_score = score
        normalized.needs_enrichment = needs_enrichment

        return SchemaCompletenessResult(
            score=score,
            present_fields=frozenset(present),
            missing_fields=frozenset(missing),
            critical_missing=critical_missing,
            needs_enrichment=needs_enrichment,
        )

    @classmethod
    def _has_phone(cls, normalized: NormalizedLead) -> bool:
        return bool(normalized.primary_phone and normalized.primary_phone.strip())

    @classmethod
    def _has_price(cls, normalized: NormalizedLead) -> bool:
        if normalized.price is None:
            return False
        if normalized.price > 0:
            return True
        return is_thoa_thuan_price(normalized.price, normalized.raw_data)

    @classmethod
    def _has_district(cls, normalized: NormalizedLead) -> bool:
        district, _ = _split_address(normalized.address)
        return bool(district and district.strip())

    @classmethod
    def _has_area(cls, normalized: NormalizedLead) -> bool:
        if normalized.area is not None and normalized.area > 0:
            return True
        raw_area_str = normalized.raw_data.get("area")
        parsed, _, _ = _parse_area(raw_area_str)
        if parsed:
            number = _extract_number_and_unit(parsed) or parsed
            return normalize_number(number) is not None
        return normalize_number(raw_area_str) is not None

    @classmethod
    def _has_title(cls, normalized: NormalizedLead) -> bool:
        if not normalized.title or not normalized.title.strip():
            return False
        return normalized.title.strip() not in cls.DEFAULT_TITLES
