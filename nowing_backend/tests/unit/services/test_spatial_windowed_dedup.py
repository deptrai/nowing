"""Unit tests for SpatialWindowedDeduplicator (Story 35.2)."""

from __future__ import annotations

import time

import pytest

from app.services.dedup.spatial_windowed_dedup import (
    SpatialWindowedDeduplicator,
    _tokenize,
    deduplicate_postings,
    deduplicate_postings_stream,
    jaccard_similarity,
)

pytestmark = [pytest.mark.unit]


class TestJaccardSimilarity:
    """Test text similarity helper."""

    def test_exact_match(self):
        assert jaccard_similarity({"a", "b"}, {"a", "b"}) == 1.0

    def test_partial_match(self):
        sim = jaccard_similarity(
            {"ban", "nha", "quan", "1"}, {"ban", "nha", "quan", "3"}
        )
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

    def test_vietnamese_diacritics_and_abbreviations(self):
        """Strip diacritics and normalize abbreviations for Vietnamese locations."""
        # Tokenizer equality
        tokens_hn_accent = _tokenize("Hà Nội")
        tokens_hn_plain = _tokenize("Ha Noi")
        assert tokens_hn_accent == tokens_hn_plain == {"ha", "noi"}

        tokens_q1_accent = _tokenize("Bán nhà Quận 1")
        tokens_q1_abbrev = _tokenize("Ban nha q.1")
        tokens_q1_upper = _tokenize("ban nha Q1")
        tokens_q1_plain = _tokenize("ban nha quan 1")
        tokens_q1_space = _tokenize("ban nha q 1")
        assert (
            tokens_q1_accent
            == tokens_q1_abbrev
            == tokens_q1_upper
            == tokens_q1_plain
            == tokens_q1_space
        )

        tokens_p1_accent = _tokenize("Phường 1")
        tokens_p1_dot = _tokenize("p. 1")
        tokens_p1_space = _tokenize("p 1")
        tokens_p1_plain = _tokenize("p1")
        assert (
            tokens_p1_accent
            == tokens_p1_dot
            == tokens_p1_space
            == tokens_p1_plain
            == {"p1"}
        )

        # Bucket function equality
        bucket_fn = SpatialWindowedDeduplicator._default_bucket_fn
        assert bucket_fn({"location": "Quận 1"}) == bucket_fn({"location": "quan 1"})
        assert bucket_fn({"location": "q.1"}) == bucket_fn({"location": "Q1"})
        assert bucket_fn({"location": "Quận 1"}) == bucket_fn({"location": "q.1"})
        assert bucket_fn({"location": "Quận 1"}) == bucket_fn({"location": "q 1"})
        assert bucket_fn({"location": "Phường 1"}) == bucket_fn({"location": "p 1"})
        assert bucket_fn({"location": "Hà Nội"}) == bucket_fn({"location": "Ha Noi"})

        # Sort key equality and normalization
        sort_key_fn = SpatialWindowedDeduplicator._default_sort_key_fn
        assert (
            sort_key_fn({"title": "Bán nhà Quận 1"})[0]
            == sort_key_fn({"title": "Ban nha q 1"})[0]
        )
        assert (
            sort_key_fn({"title": "Bán nhà Phường 1"})[0]
            == sort_key_fn({"title": "ban nha p.1"})[0]
        )

    def test_deduplicate_cross_diacritic_items(self):
        """Cross-diacritic postings should deduplicate into one group."""
        items = [
            {
                "id": 10,
                "title": "Bán căn hộ cao cấp Quận 1 view sông",
                "location": "Quận 1",
                "price": 5_000_000_000,
            },
            {
                "id": 11,
                "title": "Ban can ho cao cap Q1 view song",
                "location": "q.1",
                "price": 5_000_000_000,
            },
        ]
        unique = deduplicate_postings(items, similarity_threshold=0.8)
        assert len(unique) == 1

    def test_deduplicate_stream_matches_deduplicate(self):
        """Streaming deduplication produces identical groups to batch deduplicate."""
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
            {
                "id": 4,
                "title": "Tuyển dụng kỹ sư Python Hà Nội kinh nghiệm",
                "location": "HN",
            },
        ]
        deduplicator = SpatialWindowedDeduplicator(similarity_threshold=0.75)

        batch_groups = deduplicator.deduplicate(items)
        stream_groups = list(
            deduplicator.deduplicate_stream(items, pre_sorted_by_bucket=False)
        )

        assert len(batch_groups) == len(stream_groups)
        for bg, sg in zip(batch_groups, stream_groups, strict=True):
            assert bg.canonical["id"] == sg.canonical["id"]
            assert [d["id"] for d in bg.duplicates] == [d["id"] for d in sg.duplicates]

    def test_deduplicate_stream_lazy_evaluation(self):
        """deduplicate_stream evaluates input lazily rather than loading all up-front."""
        consumed_count = 0

        def item_generator():
            nonlocal consumed_count
            for i in range(20):
                consumed_count += 1
                # Buckets: 0..9 in 'HCM', 10..19 in 'HN'
                loc = "HCM" if i < 10 else "HN"
                yield {
                    "id": i,
                    "title": f"Tin đăng bất động sản {i}",
                    "location": loc,
                }

        deduplicator = SpatialWindowedDeduplicator()
        stream = deduplicator.deduplicate_stream(
            item_generator(), pre_sorted_by_bucket=True
        )

        # Before pulling from stream, generator must not be consumed
        assert consumed_count == 0

        # Pull first group (from 'HCM' bucket)
        first_group = next(stream)
        assert first_group is not None
        # Generator was evaluated only up to the first item of next bucket ('HN'),
        # which triggered the bucket transition (10 items of HCM + 1 item of HN = 11)
        assert consumed_count == 11

    def test_deduplicate_stream_bounded_memory_contract(self):
        """Stream with pre_sorted_by_bucket=True correctly processes partitioned streams."""
        buckets_order = ["Ba Đình", "Hoàn Kiếm", "Cầu Giấy"]
        items = []
        for b in buckets_order:
            for j in range(5):
                items.append(
                    {
                        "id": f"{b}_{j}",
                        "title": f"Bán chung cư {b} căn số {j}",
                        "location": b,
                    }
                )

        deduplicator = SpatialWindowedDeduplicator()
        groups = list(
            deduplicator.deduplicate_stream(iter(items), pre_sorted_by_bucket=True)
        )
        assert len(groups) == 15

    def test_deduplicate_postings_stream_convenience(self):
        """deduplicate_postings_stream yields canonical postings matching deduplicate_postings."""
        items = [
            {"id": 1, "title": "Bán nhà Ba Đình", "location": "HN"},
            {"id": 2, "title": "Bán nhà Ba Đình giá tốt", "location": "HN"},
        ]
        unique_batch = deduplicate_postings(items, similarity_threshold=0.7)
        unique_stream = list(
            deduplicate_postings_stream(
                items, similarity_threshold=0.7, pre_sorted_by_bucket=False
            )
        )
        assert [u["id"] for u in unique_batch] == [u["id"] for u in unique_stream]
