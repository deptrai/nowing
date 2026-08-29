"""Deterministic confidence gate for ``NormalizedLead`` schema completeness and composite scoring."""

from __future__ import annotations

from typing import Any

from app.lead_intelligence.adapters.base import NormalizedLead
from app.lead_intelligence.confidence.numbers import (
    is_thoa_thuan_price,
    normalize_number,
)
from app.lead_intelligence.confidence.schemas import (
    REQUIRED_FIELDS,
    CompositeConfidenceResult,
    SchemaCompletenessResult,
    SchemaField,
)
from app.proprietary.platforms.batdongsan.parsers import (
    _extract_number_and_unit,
    _parse_area,
    _split_address,
)


class ConfidenceGate:
    """Score a lead record on the presence of required schema fields and composite confidence."""

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
    def evaluate_icp_fit(
        cls,
        normalized: NormalizedLead,
        icp_criteria: Any | None = None,
    ) -> float:
        """
        Evaluate ICP fit score (0.0 - 100.0) based on location, industry, keywords, and negative keywords.
        """
        if normalized.icp_fit_score is not None:
            return max(0.0, min(100.0, float(normalized.icp_fit_score)))

        if icp_criteria is None:
            return 70.0

        # Extract criteria attributes flexibly
        target_locations = [
            loc.lower()
            for loc in (getattr(icp_criteria, "target_locations", []) or [])
        ]
        target_industries = [
            ind.lower()
            for ind in (getattr(icp_criteria, "target_industries", []) or [])
        ]
        target_keywords = [
            kw.lower()
            for kw in (getattr(icp_criteria, "target_keywords", []) or [])
        ]
        negative_keywords = [
            nkw.lower()
            for nkw in (getattr(icp_criteria, "negative_keywords", []) or [])
        ]

        # Gather searchable text from normalized lead
        lead_text_parts = [
            normalized.title or "",
            normalized.company_name or "",
            normalized.address or "",
            normalized.city or "",
            str(normalized.raw_data.get("description", "")),
            str(normalized.raw_data.get("industry", "")),
        ]
        lead_text = " ".join(lead_text_parts).lower()

        # Check negative keywords first
        if any(nkw in lead_text for nkw in negative_keywords if nkw):
            return 0.0

        # Calculate matching scores
        score = 50.0  # baseline
        has_criteria = False

        if target_locations:
            has_criteria = True
            loc_matched = any(
                loc in (normalized.city or "").lower()
                or loc in (normalized.address or "").lower()
                or loc in lead_text
                for loc in target_locations
                if loc
            )
            score += 20.0 if loc_matched else -15.0

        if target_industries:
            has_criteria = True
            ind_matched = any(
                ind in lead_text for ind in target_industries if ind
            )
            score += 20.0 if ind_matched else -10.0

        if target_keywords:
            has_criteria = True
            kw_matches = sum(1 for kw in target_keywords if kw and kw in lead_text)
            kw_score = min(25.0, (kw_matches / max(1, len(target_keywords))) * 25.0)
            score += kw_score

        if not has_criteria:
            return 70.0

        return max(0.0, min(100.0, round(score, 2)))

    @classmethod
    def evaluate_intent_signal(
        cls,
        normalized: NormalizedLead,
        intent_tags: list[str] | None = None,
        signal_events: list[Any] | None = None,
    ) -> float:
        """
        Evaluate intent signal score (0.0 - 100.0) from signal events and intent tags.
        """
        if normalized.intent_signal_score is not None:
            return max(0.0, min(100.0, float(normalized.intent_signal_score)))

        if signal_events:
            total = 0.0
            for sig in signal_events:
                conf = float(getattr(sig, "confidence", 70.0))
                total += conf
            avg_conf = total / len(signal_events)
            return max(0.0, min(100.0, round(avg_conf, 2)))

        if intent_tags:
            lead_text = (
                f"{normalized.title or ''} {normalized.company_name or ''} "
                f"{normalized.raw_data.get('description', '')}"
            ).lower()
            tag_matches = sum(
                1 for tag in intent_tags if tag.lower() in lead_text
            )
            if tag_matches > 0:
                return min(100.0, 60.0 + tag_matches * 15.0)
            return 60.0

        return 70.0

    @classmethod
    def evaluate_composite(
        cls,
        normalized: NormalizedLead,
        icp_criteria: Any | None = None,
        intent_tags: list[str] | None = None,
        signal_events: list[Any] | None = None,
        icp_fit_score: float | None = None,
        intent_signal_score: float | None = None,
    ) -> CompositeConfidenceResult:
        """
        Evaluate composite confidence score combining schema completeness, ICP fit, and intent signals.

        Formula:
            confidence_score = 0.4 * (schema_completeness * 100) + 0.4 * icp_fit + 0.2 * intent_signal
        """
        schema_result = cls.score(normalized)
        schema_percent = schema_result.score * 100.0

        if icp_fit_score is not None:
            icp_score = max(0.0, min(100.0, float(icp_fit_score)))
        else:
            icp_score = cls.evaluate_icp_fit(normalized, icp_criteria)

        if intent_signal_score is not None:
            intent_score = max(0.0, min(100.0, float(intent_signal_score)))
        else:
            intent_score = cls.evaluate_intent_signal(
                normalized, intent_tags, signal_events
            )

        composite_score = round(
            0.4 * schema_percent + 0.4 * icp_score + 0.2 * intent_score, 2
        )
        composite_score = max(0.0, min(100.0, composite_score))

        normalized.icp_fit_score = icp_score
        normalized.intent_signal_score = intent_score
        normalized.confidence_score = composite_score

        return CompositeConfidenceResult(
            confidence_score=composite_score,
            schema_completeness_score=schema_result.score,
            icp_fit_score=icp_score,
            intent_signal_score=intent_score,
            needs_enrichment=schema_result.needs_enrichment,
            critical_missing=schema_result.critical_missing,
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
        parsed, _ = _parse_area(raw_area_str)
        if parsed:
            number = _extract_number_and_unit(parsed) or parsed
            return normalize_number(number) is not None
        return normalize_number(raw_area_str) is not None

    @classmethod
    def _has_title(cls, normalized: NormalizedLead) -> bool:
        if not normalized.title or not normalized.title.strip():
            return False
        return normalized.title.strip() not in cls.DEFAULT_TITLES

