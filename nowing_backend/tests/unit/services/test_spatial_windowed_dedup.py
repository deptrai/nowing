"""Unit tests for SpatialWindowedDeduplicator (Story 35.2)."""

from __future__ import annotations

import time

import pytest

from app.services.dedup.spatial_windowed_dedup import (
    SpatialWindowedDeduplicator,
    deduplicate_postings,
    jaccard_similarity,
)

pytestmark = [pytest.mark.unit]


class TestJaccardSimilarity:
    """Test text similarity helper."""

    def test_exact_match(self):
        assert jaccard_similarity({"a", "b"}, {"a", "b"}) == 1.0

    def test_partial_match(self):
        sim = jaccard_similarity({"ban", "nha", "quan", "1"}, {"ban", "nha", "quan", "3"})
        assert 0.4 < sim < 0.8

    def test_empty_sets(self):
        assert jaccard_similarity(set(), {"a"}) == 0.0


class TestSpatialWindowedDeduplicator:
    """Test O(n log n) deduplication."""

    def test_deduplicate_simple_pairs(self):
        """Detect duplicate postings with slight title variation."""
        items = [
            {
                "id": 1,
                "title": "Bán nhà mặt tiền Quận 1 giá tốt",
                "location": "HCM",
                "price": 10_000_000_000,
            },
            {
                "id": 2,
                "title": "Bán nhà mặt tiền Quận 1 giá cực tốt",
                "location": "HCM",
                "price": 10_000_000_000,
            },
            {
                "id": 3,
                "title": "Tuyển dụng lập trình viên Python Hà Nội",
                "location": "HN",
            },
        ]

        unique = deduplicate_postings(items, similarity_threshold=0.75)
        assert len(unique) == 2
        assert any(item["id"] == 3 for item in unique)

    def test_scale_5000_items_performance(self):
        """5,000 items should deduplicate in sub-second time (O(n log n))."""
        # Generate 5,000 postings with 10 duplicate clusters
        items = []
        for i in range(5000):
            cluster_id = i % 100
            items.append(
                {
                    "id": i,
                    "title": f"Bán căn hộ chung cư Vinhomes Central Park {cluster_id} phòng ngủ",
                    "location": f"District_{cluster_id % 5}",
                    "price": 5_000_000_000 + (i % 10) * 10_000,
                }
            )

        start = time.perf_counter()
        unique = deduplicate_postings(items, window_size=50)
        elapsed = time.perf_counter() - start

        # Must finish well under 2.0 seconds
        assert elapsed < 2.0
        assert len(unique) < 5000
