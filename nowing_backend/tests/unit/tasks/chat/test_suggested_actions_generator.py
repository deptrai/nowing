"""Unit tests for Suggested Action Pills Generator (Story 21.11 / AC: 1, 4)."""

import pytest
from pydantic import ValidationError

from app.schemas.new_chat import SuggestedAction, SuggestedActionList
from app.services.chat.suggested_actions_generator import (
    _detect_masked_phone_count,
    generate_suggested_actions,
)
from app.services.new_streaming_service import VercelStreamingService


@pytest.mark.unit
def test_suggested_action_schema_validation():
    """Verify SuggestedAction and SuggestedActionList validate schema correctly."""
    action = SuggestedAction(
        id="decode_phones",
        label="📱 Giải mã 9 SĐT (13.5 credits)",
        icon="phone",
        action_type="decode_phones",
        prompt_template="Giải mã 9 số điện thoại.",
        cost_credits=13.5,
        payload={"selection_count": 9, "cost_credits": 13.5},
    )
    assert action.id == "decode_phones"
    assert action.cost_credits == 13.5

    # Max 3 actions in list
    action_list = SuggestedActionList(actions=[action, action, action])
    assert len(action_list.actions) == 3

    # Exceeding 3 should raise ValidationError
    with pytest.raises(ValidationError):
        SuggestedActionList(actions=[action, action, action, action])


@pytest.mark.unit
def test_detect_masked_phone_count():
    text = (
        "1. Nhà phố Q7 - SĐT: 0903***888\n"
        "2. Đất nền Nhà Bè - SĐT: 0918***777\n"
        "3. Căn hộ Vinhomes - Liên hệ: 0989***999"
    )
    assert _detect_masked_phone_count(text) == 3
    assert _detect_masked_phone_count("Không có số điện thoại ở đây.") == 0


@pytest.mark.unit
def test_generate_suggested_actions_with_scraper_and_selection_count():
    """AC 4: Dynamic selection count N reflects exact count and 1.5 * N credit projection."""
    actions = generate_suggested_actions(
        user_query="Tìm nhà phố quận 7 giá dưới 5 tỷ",
        assistant_text="Đã tìm thấy 9 bất động sản phù hợp.",
        tool_names=["batdongsan_search"],
        selection_count=9,
    )
    assert len(actions) <= 3
    decode_action = next((a for a in actions if a.id == "decode_phones"), None)
    assert decode_action is not None
    assert decode_action.label == "📱 Giải mã 9 SĐT (13.5 credits)"
    assert decode_action.cost_credits == 13.5
    assert decode_action.payload == {"selection_count": 9, "cost_per_unit": 1.5, "total_cost": 13.5}


@pytest.mark.unit
def test_generate_suggested_actions_with_masked_phones_in_text():
    assistant_text = (
        "Danh sách liên hệ:\n"
        "- Nguyễn Văn A: 0901***123\n"
        "- Trần Thị B: 0912***456"
    )
    actions = generate_suggested_actions(
        user_query="Tìm chủ nhà cho thuê",
        assistant_text=assistant_text,
    )
    decode_action = next((a for a in actions if a.id == "decode_phones"), None)
    assert decode_action is not None
    assert "2 SĐT" in decode_action.label
    assert decode_action.cost_credits == 3.0


@pytest.mark.unit
def test_generate_suggested_actions_b2b_outreach_zalo_draft():
    actions = generate_suggested_actions(
        user_query="Tìm danh sách giám đốc công ty B2B ngành logistic",
        assistant_text="Dưới đây là 5 giám đốc doanh nghiệp logistic tiềm năng.",
        tool_names=["masothue_company_search"],
    )
    assert any(a.id == "zalo_draft" for a in actions)
    assert any(a.id == "find_similar" for a in actions)
    assert len(actions) <= 3


@pytest.mark.unit
def test_generate_suggested_actions_fallback_deep_research():
    actions = generate_suggested_actions(
        user_query="Tổng quan thị trường AI agent 2026",
        assistant_text="Thị trường AI Agent đang tăng trưởng mạnh mẽ.",
    )
    assert len(actions) >= 1
    assert len(actions) <= 3
    assert any(a.id == "deep_research" for a in actions)


@pytest.mark.unit
def test_streaming_service_format_suggested_actions():
    service = VercelStreamingService()
    action = SuggestedAction(
        id="test_action",
        label="Test Action",
        icon="sparkles",
        action_type="test",
        prompt_template="Execute test",
    )
    sse_output = service.format_suggested_actions([action])
    assert sse_output.startswith("data: ")
    assert '"type": "data-suggested-actions"' in sse_output
    assert '"label": "Test Action"' in sse_output
