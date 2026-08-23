"""Unit tests for the deterministic confidence gate (Story 21.21)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.lead_intelligence.adapters.base import NormalizedLead
from app.lead_intelligence.confidence import (
    ConfidenceGate,
    SchemaCompletenessResult,
    SchemaField,
)

pytestmark = pytest.mark.unit


def _lead(
    primary_phone: str | None = "0912345678",
    price: float | None = 5_000_000_000,
    address: str | None = "Phường 1, Quận 7, TP.HCM",
    area: float | None = 75.0,
    title: str | None = "Bán nhà Quận 7",
    raw_area: str | None = None,
) -> NormalizedLead:
    return NormalizedLead(
        source_name="test",
        source_id="1",
        primary_phone=primary_phone,
        price=price,
        address=address,
        area=area,
        title=title,
        raw_data={"area": raw_area} if raw_area else {},
    )


class TestConfidenceGate:
    def test_perfect_record_score_one(self) -> None:
        lead = _lead()
        result = ConfidenceGate.score(lead)
        assert result.score == 1.0
        assert not result.critical_missing
        assert not result.needs_enrichment
        assert lead.schema_completeness_score == 1.0

    def test_missing_title_in_enrichment_band(self) -> None:
        lead = _lead(title=None)
        result = ConfidenceGate.score(lead)
        assert result.score == 0.8
        assert not result.critical_missing
        assert result.needs_enrichment is True

    def test_missing_critical_phone_forces_micro(self) -> None:
        lead = _lead(primary_phone=None)
        result = ConfidenceGate.score(lead)
        assert SchemaField.PHONE in result.missing_fields
        assert result.critical_missing is True
        # Critical missing records are handled by MicroExtractionWorker, not
        # the async enrichment queue.
        assert result.needs_enrichment is False

    def test_missing_price_is_critical(self) -> None:
        lead = _lead(price=None)
        result = ConfidenceGate.score(lead)
        assert SchemaField.PRICE in result.missing_fields
        assert result.critical_missing is True

    def test_zero_or_negative_price_counts_missing(self) -> None:
        lead = _lead(price=0.0)
        result = ConfidenceGate.score(lead)
        assert SchemaField.PRICE in result.missing_fields

    def test_thoa_thuan_price_counts_present(self) -> None:
        lead = _lead(price=0.0, raw_area=None)
        lead.raw_data["price_raw"] = "Thỏa thuận"
        result = ConfidenceGate.score(lead)
        assert SchemaField.PRICE in result.present_fields

    def test_missing_district_is_critical(self) -> None:
        lead = _lead(address="Hà Nội")
        result = ConfidenceGate.score(lead)
        assert SchemaField.DISTRICT in result.missing_fields
        assert result.critical_missing is True

    def test_low_score_without_critical_goes_to_micro(self) -> None:
        # Missing area and title: 0.6 score, but phone/price/district present.
        lead = _lead(area=None, title=None)
        result = ConfidenceGate.score(lead)
        assert result.score == 0.6
        assert not result.critical_missing
        assert result.needs_enrichment is False

    def test_default_title_counts_missing(self) -> None:
        lead = _lead(title="Bất động sản rao bán")
        result = ConfidenceGate.score(lead)
        assert SchemaField.TITLE in result.missing_fields

    def test_area_from_raw_data(self) -> None:
        lead = _lead(area=None, raw_area="75 m²")
        result = ConfidenceGate.score(lead)
        assert SchemaField.AREA in result.present_fields

    def test_district_parsed_from_address(self) -> None:
        lead = _lead(address="Dự án X, Phường Tân Phú, Quận 9, TP.HCM")
        result = ConfidenceGate.score(lead)
        assert SchemaField.DISTRICT in result.present_fields


def _route(result: SchemaCompletenessResult) -> str:
    if result.score >= 0.85 and not result.critical_missing:
        return "direct"
    if 0.70 <= result.score < 0.85 and not result.critical_missing:
        return "enrichment"
    return "micro"


class TestGoldenConfidenceGate:
    def test_golden_fixture_scores_and_routes(self) -> None:
        fixture = Path(__file__).with_name("fixtures") / "golden_confidence_gate.json"
        cases = json.loads(fixture.read_text())
        for case in cases:
            lead = NormalizedLead(**case)
            result = ConfidenceGate.score(lead)
            assert result.score == case["expected_score"], (
                f"{case['source_id']}: expected score {case['expected_score']}, "
                f"got {result.score}"
            )
            assert _route(result) == case["expected_route"], (
                f"{case['source_id']}: expected route {case['expected_route']}, "
                f"got {_route(result)} (score={result.score})"
            )
