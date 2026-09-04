"""Unit tests for Hierarchical Location Pre-filter and Word-boundary Token Matching (Story 26.26)."""

from __future__ import annotations

from app.lead_intelligence.adapters.base import RawLeadRecord
from app.lead_intelligence.campaign.schemas import ICPCriteria
from app.lead_intelligence.schemas import LocationProfilePayload
from app.lead_intelligence.scoring.rubric import blend_location_fit_score
from app.lead_intelligence.services.lead_gen_orchestrator import (
    LeadGenOrchestrator,
)


def test_word_boundary_token_matching_prevents_false_positives() -> None:
    """AC-3: Word-boundary matching distinguishes 'Quận 1' from 'Quận 10', 'Quận 11', 'Quận 12'."""
    text_q1 = "Bán nhà mặt tiền đường Lê Lợi, Quận 1, TP. Hồ Chí Minh"
    text_q10 = "Bán chung cư Kingdom 101, đường Tô Hiến Thành, Quận 10, Sài Gòn"
    text_q12 = "Cho thuê kho xưởng tại Quận 12 giá rẻ"

    # Match "Quận 1" on text containing only "Quận 1"
    assert (
        LeadGenOrchestrator._contains_word_boundary_token(
            text_q1.lower(), "Quận 1"
        )
        is True
    )

    # "Quận 1" must NOT match in text containing "Quận 10" or "Quận 12"
    assert (
        LeadGenOrchestrator._contains_word_boundary_token(
            text_q10.lower(), "Quận 1"
        )
        is False
    )
    assert (
        LeadGenOrchestrator._contains_word_boundary_token(
            text_q12.lower(), "Quận 1"
        )
        is False
    )


def test_hierarchical_location_matching_precedence() -> None:
    """AC-3 & AC-4: Matching follows hierarchical precedence (Ward=100 -> District=90 -> Province=75)."""
    hcm_ward_profile = LocationProfilePayload(
        province_code="SG",
        province_name="TP. Hồ Chí Minh",
        district_codes=["760"],
        district_names=["Quận 1"],
        ward_names=["Phường Bến Nghé"],
    )

    # Lead matches exact ward
    lead_ward_text = "Căn hộ Vinhomes Golden River, Phường Bến Nghé, Quận 1, HCM"
    matched, score = LeadGenOrchestrator.evaluate_hierarchical_location_match(
        lead_ward_text, hcm_ward_profile
    )
    assert matched is True
    assert score == 100.0

    # Lead matches district only (no ward mention)
    lead_district_text = "Bán nhà phố Quận 1 gần chợ Bến Thành"
    matched_d, score_d = (
        LeadGenOrchestrator.evaluate_hierarchical_location_match(
            lead_district_text, hcm_ward_profile
        )
    )
    assert matched_d is True
    assert score_d == 90.0

    # Lead matches province only when no district is requested
    broad_hn_profile = LocationProfilePayload(
        province_code="HN",
        province_name="Hà Nội",
    )
    lead_hn_text = "Dự án mới mở bán tại khu đô thị phía Tây Hà Nội"
    matched_p, score_p = (
        LeadGenOrchestrator.evaluate_hierarchical_location_match(
            lead_hn_text, broad_hn_profile
        )
    )
    assert matched_p is True
    assert score_p == 75.0

    # Out of area lead fails match
    lead_dn_text = "Đất nền ven biển Mỹ Khê, Sơn Trà, Đà Nẵng"
    matched_fail, score_fail = (
        LeadGenOrchestrator.evaluate_hierarchical_location_match(
            lead_dn_text, broad_hn_profile
        )
    )
    assert matched_fail is False
    assert score_fail == 0.0


def test_pre_filter_by_icp_with_location_profile() -> None:
    """AC-3: Out-of-location leads are rejected during pre-filtering."""
    hcm_profile = LocationProfilePayload(
        province_code="SG",
        province_name="TP. Hồ Chí Minh",
        district_codes=["760"],
        district_names=["Quận 1"],
    )

    valid_record = RawLeadRecord(
        source_name="batdongsan",
        source_id="bds-1",
        data={
            "title": "Nhà phố Quận 1",
            "city": "TP. Hồ Chí Minh",
            "address": "Nguyễn Huệ, Quận 1",
        },
    )

    out_of_area_record = RawLeadRecord(
        source_name="batdongsan",
        source_id="bds-2",
        data={
            "title": "Biệt thự Cầu Giấy",
            "city": "Hà Nội",
            "address": "Trần Duy Hưng, Cầu Giấy",
        },
    )

    icp = ICPCriteria()

    # Valid lead passes
    assert (
        LeadGenOrchestrator.pre_filter_by_icp(
            valid_record, icp, location_profile=hcm_profile
        )
        is True
    )

    # Out-of-area lead rejected
    assert (
        LeadGenOrchestrator.pre_filter_by_icp(
            out_of_area_record, icp, location_profile=hcm_profile
        )
        is False
    )


def test_blend_location_fit_score() -> None:
    """AC-4: Blending formula calculates final_fit_score = round(base * 0.7 + loc * 0.3, 1)."""
    # Base fit score 80.0, exact ward match 100.0: 80 * 0.7 + 100 * 0.3 = 56 + 30 = 86.0
    assert blend_location_fit_score(80.0, 100.0, location_weight=0.3) == 86.0

    # Base fit score 90.0, district match 90.0: 90 * 0.7 + 90 * 0.3 = 90.0
    assert blend_location_fit_score(90.0, 90.0, location_weight=0.3) == 90.0

    # Base fit score 70.0, broad province match 75.0: 70 * 0.7 + 75 * 0.3 = 49 + 22.5 = 71.5
    assert blend_location_fit_score(70.0, 75.0, location_weight=0.3) == 71.5
