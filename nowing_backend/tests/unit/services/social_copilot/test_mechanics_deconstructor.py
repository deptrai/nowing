"""ATDD Red-Phase Unit Tests: Viral Mechanics Deconstruction & Taxonomy (Story 21.12 / AC 3)."""

import pytest


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pii_sanitization_on_viral_post():
    """AC 3: Ensure phone numbers and emails in viral posts are redacted per AD-25."""
    from app.services.social_copilot.mechanics_deconstructor import (
        ViralMechanicsDeconstructor,
    )

    raw_content = (
        "Bán gấp lô đất Thảo Điền view sông 500m2 giá 45 tỷ. "
        "Liên hệ chính chủ SĐT: 0912.345.678 hoặc email: ceo@landinvest.vn. "
        "Cơ hội duy nhất trong tuần!"
    )

    deconstructor = ViralMechanicsDeconstructor()
    sanitized = await deconstructor.sanitize_and_redact(raw_content)

    assert "0912.345.678" not in sanitized
    assert "ceo@landinvest.vn" not in sanitized
    assert (
        "[REDACTED_PHONE]" in sanitized or "[PHONE]" in sanitized or "09xx" in sanitized
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_classify_hook_taxonomy_contrarian():
    """AC 3: Categorize hook into contrarian_hook, story_shift, value_list, data_reveal."""
    from app.services.social_copilot.mechanics_deconstructor import (
        ViralMechanicsDeconstructor,
    )

    contrarian_text = (
        "Hầu hết các founder SaaS đang làm marketing sai cách. "
        "Việc cố gắng tối ưu SEO ngay từ ngày đầu chỉ làm bạn cạn kiệt runway."
    )

    deconstructor = ViralMechanicsDeconstructor()
    mechanics = await deconstructor.deconstruct(contrarian_text)

    assert mechanics.taxonomy == "contrarian_hook"
    assert mechanics.hook is not None
    assert "why_it_worked" in mechanics.analysis.lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_deconstruct_4_structural_elements():
    """AC 3: Break down post into hook, re_hook, body, cta."""
    from app.services.social_copilot.mechanics_deconstructor import (
        ViralMechanicsDeconstructor,
    )

    full_post = (
        "Dừng chạy ads nếu bạn chưa biết điều này.\n\n"
        "90% ngân sách đang bị lãng phí vì landing page không có hook giữ chân 3 giây đầu.\n\n"
        "Dưới đây là 3 bước khắc phục:\n"
        "1. Đổi tiêu đề sang dạng tranh biện\n"
        "2. Thêm social proof ngay trên fold\n"
        "3. Tối ưu tốc độ tải trang dưới 1.2s\n\n"
        "Thả tim và comment 'AUDIT' để nhận checklist chi tiết."
    )

    deconstructor = ViralMechanicsDeconstructor()
    elements = await deconstructor.deconstruct(full_post)

    assert "Dừng chạy ads" in elements.hook
    assert "90% ngân sách" in elements.re_hook
    assert "3 bước khắc phục" in elements.body
    assert (
        "comment 'AUDIT'" in elements.cta.lower() or "thả tim" in elements.cta.lower()
    )
