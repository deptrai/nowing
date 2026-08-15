"""ATDD Red-Phase Unit Tests: Outlier Detector & Statistical Baseline (Story 21.12 / AC 2)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db import SocialPost


@pytest.fixture
def mock_social_posts_session():
    session = AsyncMock()
    # Mock post 1: 100 reactions, 20 comments, 10 shares -> score 170 (baseline 50 -> ratio 3.4x -> Outlier)
    post1 = MagicMock(spec=SocialPost)
    post1.id = 1
    post1.platform = "facebook"
    post1.external_post_id = "fb_123"
    post1.author_name = "Test Author"
    post1.author_id = "author_1"
    post1.author_url = "https://facebook.com/author_1"
    post1.post_url = "https://facebook.com/post/1"
    post1.content = "Bất động sản đầu tư sinh lời cao 2026."
    post1.reactions_count = 100
    post1.comments_count = 20
    post1.shares_count = 10
    post1.published_at = None

    # Mock post 2: 5 reactions -> score 5 -> Not an outlier (< 10)
    post2 = MagicMock(spec=SocialPost)
    post2.id = 2
    post2.platform = "facebook"
    post2.external_post_id = "fb_456"
    post2.author_name = "Test Author"
    post2.author_id = "author_1"
    post2.author_url = "https://facebook.com/author_1"
    post2.post_url = "https://facebook.com/post/2"
    post2.content = "Đầu tư bất động sản an toàn."
    post2.reactions_count = 5
    post2.comments_count = 0
    post2.shares_count = 0
    post2.published_at = None

    # First call to execute returns posts list, second call (for baseline) returns avg 50
    posts_res = MagicMock()
    posts_res.scalars.return_value.all.return_value = [post1, post2]

    baseline_res = MagicMock()
    baseline_res.scalar_one_or_none.return_value = 50.0

    session.execute.side_effect = [posts_res, baseline_res]
    return session


@pytest.mark.unit
def test_calculate_engagement_score():
    """AC 2: Score = Reactions + 2*Comments + 3*Shares."""
    from app.services.social_copilot.outlier_detector import calculate_engagement_score

    score = calculate_engagement_score(reactions=100, comments=20, shares=10)
    # 100 + 2*20 + 3*10 = 100 + 40 + 30 = 170
    assert score == 170


@pytest.mark.unit
def test_zero_division_guard_on_baseline():
    """AC 2: Baseline = max(author_baseline, 1.0) with min_score threshold >= 10."""
    from app.services.social_copilot.outlier_detector import evaluate_outlier_ratio

    # Baseline 0 must not raise ZeroDivisionError
    is_outlier, ratio = evaluate_outlier_ratio(
        engagement_score=30, author_baseline=0.0, min_multiplier=3.0
    )
    assert is_outlier is True
    assert ratio == 30.0

    # Low score (< 10) must not be flagged as outlier even if baseline is 0
    is_outlier_low, _ratio_low = evaluate_outlier_ratio(
        engagement_score=5, author_baseline=0.0, min_multiplier=3.0
    )
    assert is_outlier_low is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_outlier_detection_filtering(mock_social_posts_session):
    """AC 2: Filter outlier posts with engagement >= 3x baseline from DB."""
    from app.services.social_copilot.outlier_detector import OutlierDetector

    detector = OutlierDetector(session=mock_social_posts_session)
    outliers = await detector.find_outliers(
        workspace_id=1,
        client_id="default",
        target_keywords=["bất động sản", "đầu tư"],
        min_multiplier=3.0,
    )

    assert isinstance(outliers, list)
    for post in outliers:
        assert post.engagement_score >= 10
        assert post.baseline_ratio >= 3.0
        assert post.external_post_id is not None
