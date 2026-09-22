"""O(n log n) Spatial & Windowed Deduplication for Mass Entity Postings (Story 35.2)."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Iterable, Sequence


def _tokenize(text: str | None) -> set[str]:
    """Tokenize text into lowercase alphanumeric word tokens."""
    if not text:
        return set()
    return set(re.findall(r"\w+", text.lower()))


def jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    """Compute Jaccard similarity coefficient between two sets."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))
    return intersection / union if union > 0 else 0.0


@dataclass
class DeduplicatedGroup:
    """Group of duplicated items with a canonical representative."""

    canonical: dict[str, Any]
    duplicates: list[dict[str, Any]]


class SpatialWindowedDeduplicator:
    """Sub-quadratic deduplication using spatial bucketing and sliding window sorting."""

    def __init__(
        self,
        *,
        window_size: int = 50,
        similarity_threshold: float = 0.80,
        bucket_fn: Callable[[dict[str, Any]], str] | None = None,
        sort_key_fn: Callable[[dict[str, Any]], Any] | None = None,
    ) -> None:
        self.window_size = window_size
        self.similarity_threshold = similarity_threshold
        self.bucket_fn = bucket_fn or self._default_bucket_fn
        self.sort_key_fn = sort_key_fn or self._default_sort_key_fn

    @staticmethod
    def _default_bucket_fn(item: dict[str, Any]) -> str:
        """Coarse spatial/domain bucket: city or location or domain."""
        return str(
            item.get("location")
            or item.get("city")
            or item.get("domain")
            or "global"
        ).strip().lower()

    @staticmethod
    def _default_sort_key_fn(item: dict[str, Any]) -> tuple[str, str]:
        """Sort key: (normalized_title, posted_date)."""
        title = str(item.get("title") or item.get("company_name") or "").strip().lower()
        date = str(item.get("posted_at") or item.get("created_at") or "")
        return (title, date)

    def _are_duplicates(self, a: dict[str, Any], b: dict[str, Any]) -> bool:
        """Check if two items are duplicates within the window."""
        tokens_a = _tokenize(a.get("title") or a.get("company_name"))
        tokens_b = _tokenize(b.get("title") or b.get("company_name"))

        sim = jaccard_similarity(tokens_a, tokens_b)
        if sim < self.similarity_threshold:
            return False

        # If both specify price, verify price delta tolerance (e.g. within 10%)
        price_a = a.get("price")
        price_b = b.get("price")
        if (
            isinstance(price_a, (int, float))
            and isinstance(price_b, (int, float))
            and price_a > 0
            and price_b > 0
        ):
            delta = abs(price_a - price_b) / max(price_a, price_b)
            if delta > 0.15:
                return False

        return True

    def deduplicate(
        self,
        items: Sequence[dict[str, Any]],
    ) -> list[DeduplicatedGroup]:
        """Deduplicate a sequence of items in O(N log N) time."""
        if not items:
            return []

        # 1. Bucket by spatial / domain key: O(N)
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in items:
            bucket_key = self.bucket_fn(item)
            buckets[bucket_key].append(item)

        groups: list[DeduplicatedGroup] = []

        # 2. Sort and slide window within each bucket: O(K log K + K * W)
        for _key, bucket_items in buckets.items():
            bucket_items.sort(key=self.sort_key_fn)

            consumed_indices = set()
            n = len(bucket_items)

            for i in range(n):
                if i in consumed_indices:
                    continue

                canonical = bucket_items[i]
                duplicates = []

                # Slide window of size W
                window_end = min(n, i + self.window_size + 1)
                for j in range(i + 1, window_end):
                    if j in consumed_indices:
                        continue
                    if self._are_duplicates(canonical, bucket_items[j]):
                        duplicates.append(bucket_items[j])
                        consumed_indices.add(j)

                groups.append(
                    DeduplicatedGroup(
                        canonical=canonical,
                        duplicates=duplicates,
                    )
                )

        return groups


def deduplicate_postings(
    items: Sequence[dict[str, Any]],
    *,
    window_size: int = 50,
    similarity_threshold: float = 0.80,
) -> list[dict[str, Any]]:
    """Convenience function returning only unique canonical postings."""
    deduplicator = SpatialWindowedDeduplicator(
        window_size=window_size,
        similarity_threshold=similarity_threshold,
    )
    groups = deduplicator.deduplicate(items)
    return [g.canonical for g in groups]
