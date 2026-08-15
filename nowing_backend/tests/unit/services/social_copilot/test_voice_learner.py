"""ATDD Red-Phase Unit Tests: Voice Profile Learning Engine (Story 21.12 / AC 1)."""

import pytest
from pydantic import ValidationError


@pytest.mark.unit
def test_voice_learner_rejects_sample_under_100_words():
    """AC 1: Must validate min_words=100 and raise error/return 422 if sample text is too short."""
    from app.schemas.voice_profile import VoiceAnalysisRequest

    with pytest.raises(ValidationError) as exc_info:
        VoiceAnalysisRequest(
            sample_text="This is a short sample under one hundred words.",
            profile_name="Short Persona",
        )
    assert "at least 100 words" in str(exc_info.value).lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_voice_learner_extracts_structured_profile():
    """AC 1: Analyzes tone, sentence length, cadence, hooks, and formatting style in JSON."""
    from app.services.social_copilot.voice_learner import VoiceProfileLearner

    sample = (
        "Hầu hết các môi giới BĐS đang đốt tiền vô ích vào Facebook Ads. "
        "Thực tế 90% giao dịch phân khúc cao cấp năm nay đến từ mạng lưới quan hệ ngầm "
        "và định vị cá nhân qua nội dung chuyên sâu. "
        "Dưới đây là quy trình 3 bước tôi dùng để chốt 4 căn biệt thự mà không tốn 1 đồng quảng cáo: "
        "1. Xác định tệp khách hàng mua kín qua dữ liệu đăng ký doanh nghiệp. "
        "2. Viết bài phân tích dòng tiền chuyên sâu thay vì đăng tin bán nhà rác. "
        "3. Tiếp cận riêng tư qua tin nhắn trực tiếp kèm báo cáo định giá độc quyền. "
        "Comment 'BÁO CÁO' để nhận file phân tích dòng tiền mẫu chi tiết nhất hôm nay. "
        "Hãy nhớ rằng uy tín cá nhân là đòn bẩy mạnh nhất trong chu kỳ thị trường hiện tại. "
        "Đừng chạy theo đám đông nếu bạn muốn dẫn đầu phân khúc triệu đô."
    )

    learner = VoiceProfileLearner()
    profile = await learner.extract_voice_profile(
        sample_text=sample,
        profile_name="BĐS Chuyên gia",
        platform="facebook",
    )

    assert profile.profile_name == "BĐS Chuyên gia"
    assert "authoritative" in profile.tone.lower() or "direct" in profile.tone.lower()
    assert profile.average_sentence_length > 0
    assert (
        "contrarian" in profile.hook_preference.lower()
        or "numbers" in profile.hook_preference.lower()
    )
    assert len(profile.vocabulary) > 0
    assert profile.formatting_quirks.bullet_style in ["numbered_list", "bullet", "none"]


@pytest.mark.unit
def test_voice_profile_json_schema_compliance():
    """AC 1: Strict Pydantic JSON schema compliance with multi-persona attributes."""
    from app.schemas.voice_profile import VoiceProfile

    data = {
        "profile_name": "Tech Founder",
        "tone": "pragmatic, technical",
        "average_sentence_length": 15.2,
        "paragraph_cadence": "short paragraphs, high whitespace",
        "hook_preference": "contrarian data hook",
        "vocabulary": ["ROI", "pipeline", "automation"],
        "formatting_quirks": {
            "emoji_density": "low",
            "bullet_style": "bullet",
            "line_break_frequency": "high",
        },
        "is_active": True,
    }

    profile = VoiceProfile(**data)
    assert profile.profile_name == "Tech Founder"
    assert profile.is_active is True
    assert profile.vocabulary == ["ROI", "pipeline", "automation"]
