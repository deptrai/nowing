"""ATDD Red-Phase Unit Tests: Voice-Matched Draft Generator & Multi-Platform Constraints (Story 21.12 / AC 4)."""

import pytest


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_drafts_respects_twitter_length_limit():
    """AC 4: Twitter platform constraint enforces <= 280 characters for standard tweet or thread."""
    from app.schemas.voice_profile import VoiceProfile
    from app.services.social_copilot.draft_generator import ViralDraftGenerator

    voice = VoiceProfile(
        profile_name="Tech Founder",
        tone="direct, punchy",
        average_sentence_length=10.0,
        paragraph_cadence="one sentence per line",
        hook_preference="contrarian data hook",
        vocabulary=["pipeline", "growth", "SaaS"],
        formatting_quirks={
            "emoji_density": "low",
            "bullet_style": "bullet",
            "line_break_frequency": "high",
        },
    )

    generator = ViralDraftGenerator()
    drafts = await generator.generate_drafts(
        topic="SaaS Inbound Marketing",
        hook_taxonomy="contrarian_hook",
        voice_profile=voice,
        target_platform="twitter",
        n_variations=3,
    )

    assert len(drafts) == 3
    for draft in drafts:
        # Standard single tweet or thread structure
        if draft.is_thread:
            assert all(len(t) <= 280 for t in draft.thread_tweets)
        else:
            assert len(draft.content) <= 280
        assert draft.angle in ["contrarian", "framework", "case_study"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_drafts_incorporates_voice_vocabulary():
    """AC 4: Ensure generated draft uses user's learned tone and vocabulary."""
    from app.schemas.voice_profile import VoiceProfile
    from app.services.social_copilot.draft_generator import ViralDraftGenerator

    voice = VoiceProfile(
        profile_name="Real Estate Pro",
        tone="authoritative",
        average_sentence_length=15.0,
        paragraph_cadence="short paragraphs",
        hook_preference="data reveal",
        vocabulary=["dòng tiền", "bất động sản triệu đô", "định giá"],
        formatting_quirks={
            "emoji_density": "none",
            "bullet_style": "numbered_list",
            "line_break_frequency": "high",
        },
    )

    generator = ViralDraftGenerator()
    drafts = await generator.generate_drafts(
        topic="Đầu tư BĐS ven đô",
        hook_taxonomy="value_list",
        voice_profile=voice,
        target_platform="facebook",
        n_variations=3,
    )

    assert len(drafts) == 3
    # Check that vocabulary tokens appear across generated variations
    all_content = " ".join([d.content for d in drafts])
    assert any(w in all_content for w in ["dòng tiền", "bất động sản", "định giá"])
