"""ATDD Red-Phase Unit Tests: Outlier Detector & Statistical Baseline (Story 21.12 / AC 2)."""

import pytest


@pytest.mark.unit
@pytest.mark.skip(reason="ATDD Red Phase Scaffold: Outlier Detector implementation pending")
def test_calculate_engagement_score():
    """AC 2: Score = Reactions + 2*Comments + 3*Shares."""
    from app.services.social_copilot.outlier_detector import calculate_engagement_score

    score = calculate_engagement_score(reactions=100, comments=20, shares=10)
    # 100 + 2*20 + 3*10 = 100 + 40 + 30 = 170
    assert score == 170


@pytest.mark.unit
@pytest.mark.skip(reason="ATDD Red Phase Scaffold: Outlier Detector implementation pending")
def test_zero_division_guard_on_baseline():
    """AC 2: Baseline = max(author_baseline, 1.0) with min_score threshold >= 10."""
    from app.services.social_copilot.outlier_detector import evaluate_outlier_ratio

    # Baseline 0 must not raise ZeroDivisionError
    is_outlier, ratio = evaluate_outlier_ratio(engagement_score=30, author_baseline=0.0, min_multiplier=3.0)
    assert is_outlier is True
    assert ratio == 30.0

    # Low score (< 10) must not be flagged as outlier even if baseline is 0
    is_outlier_low, ratio_low = evaluate_outlier_ratio(engagement_score=5, author_baseline=0.0, min_multiplier=3.0)
    assert is_outlier_low is False


@pytest.mark.unit
@pytest.mark.skip(reason="ATDD Red Phase Scaffold: Outlier Detector implementation pending")
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
