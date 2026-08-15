"""Unit tests for AI Contextual B2B Outreach Draft Engine (Story 21.9 / AC-3)."""

from __future__ import annotations

from app.services.outreach_service import (
    B2BOutreachService,
    OutreachDraftRequest,
    OutreachSignalType,
)


def test_generate_outreach_draft_hiring_signal() -> None:
    """Generate contextual B2B sales email referencing company hiring growth."""
    service = B2BOutreachService()
    request = OutreachDraftRequest(
        executive_name="Nguyen Van B",
        executive_title="CEO",
        company_name="VNTech Solutions",
        signal_type=OutreachSignalType.HIRING_SPIKE,
        signal_details="Đang tuyển dụng 25 kỹ sư phần mềm và chuyên viên AI",
        offering_name="Nowing AI Enterprise Workspace",
        offering_value_prop="Tự động hóa 70% quy trình nghiên cứu thị trường và tuyển dụng",
        sender_name="Le Minh",
        sender_title="Sales Director",
        sender_company="Nowing Inc",
    )

    response = service.generate_outreach_draft(request)
    assert response.subject_line is not None
    assert "VNTech Solutions" in response.subject_line or "tuyển dụng" in response.subject_line.lower() or "hiring" in response.subject_line.lower() or "tăng trưởng" in response.subject_line.lower()
    assert "Nguyen Van B" in response.body_text or "Anh/Chị" in response.body_text
    assert "Nowing AI Enterprise Workspace" in response.body_text
    assert "25 kỹ sư" in response.body_text or "tuyển dụng" in response.body_text
    assert response.call_to_action is not None
    assert response.confidence_score > 0.7


def test_generate_outreach_draft_tender_signal() -> None:
    """Generate contextual B2B sales email referencing a tender win."""
    service = B2BOutreachService()
    request = OutreachDraftRequest(
        executive_name="Tran Thi C",
        executive_title="Managing Director",
        company_name="Bao Viet Construction",
        signal_type=OutreachSignalType.TENDER_WIN,
        signal_details="Vừa trúng gói thầu số TB-2026-001 trị giá 50 tỷ VNĐ",
        offering_name="Nowing Procurement Intelligence",
        offering_value_prop="Giám sát nhà thầu phụ và tối ưu chuỗi cung ứng vật tư",
        sender_name="Pham Duc",
        sender_title="Account Executive",
        sender_company="Nowing Inc",
    )

    response = service.generate_outreach_draft(request)
    assert "Bao Viet Construction" in response.subject_line or "gói thầu" in response.subject_line.lower() or "chúc mừng" in response.subject_line.lower()
    assert "50 tỷ" in response.body_text or "gói thầu" in response.body_text
    assert response.confidence_score >= 0.8
