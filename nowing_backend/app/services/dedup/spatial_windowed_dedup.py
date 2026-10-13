"""O(n log n) Spatial & Windowed Deduplication for Mass Entity Postings (Story 35.2)."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any

from app.services.location_normalize import remove_diacritics

_ABBREV_PATTERN = re.compile(r"\b(q|quan|p|phuong)[.\s]*(\d+)\b", re.IGNORECASE)


def _normalize_text(text: str | None) -> str:
    """Normalize text by removing diacritics, lowercasing, and normalizing location abbreviations."""
    if not text:
        return ""
    cleaned = remove_diacritics(text).lower()
    return _ABBREV_PATTERN.sub(
        lambda m: f"{'q' if m.group(1).lower().startswith('q') else 'p'}{m.group(2)}",
        cleaned,
    )


def _tokenize(text: str | None) -> set[str]:
    """Tokenize text into lowercase alphanumeric word tokens without Vietnamese diacritics."""
    if not text:
        return set()
    cleaned = _normalize_text(text)
    return set(re.findall(r"\w+", cleaned))


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
        """Coarse spatial/domain bucket: city or location or district or domain."""
        raw = str(
            item.get("location")
            or item.get("city")
            or item.get("district")
            or item.get("domain")
            or "global"
        ).strip()
        cleaned = _normalize_text(raw).strip()
        return cleaned or "global"

    @staticmethod
    def _default_sort_key_fn(item: dict[str, Any]) -> tuple[str, str]:
        """Sort key: (normalized_title, posted_date)."""
        raw_title = str(item.get("title") or item.get("company_name") or "")
        title = _normalize_text(raw_title).strip()
        date = str(
            item.get("posted_at")
            or item.get("created_at")
            or item.get("post_date")
            or ""
        )
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

    def _deduplicate_bucket(
        self,
        bucket_items: list[dict[str, Any]],
    ) -> Iterator[DeduplicatedGroup]:
        """Sort and slide window within a single bucket."""
        if not bucket_items:
            return

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

            yield DeduplicatedGroup(
                canonical=canonical,
                duplicates=duplicates,
            )

    def deduplicate_stream(
        self,
        items: Iterable[dict[str, Any]],
        *,
        pre_sorted_by_bucket: bool = True,
    ) -> Iterator[DeduplicatedGroup]:
        """Yield deduplicated groups as a generator stream.

        Memory Bound Contract:
        - When ``pre_sorted_by_bucket=True`` (default): input ``items`` is assumed to
          yield items grouped/sorted contiguously by bucket key (e.g. from an SQL
          ``ORDER BY location`` or partitioned stream). In this mode, items for each
          bucket are buffered only until the bucket key changes, deduplicated, yielded,
          and immediately discarded. Peak memory is strictly bounded to
          O(largest bucket) rather than O(dataset).
        - When ``pre_sorted_by_bucket=False``: input ``items`` can arrive in arbitrary
          unsorted order. Items are accumulated into a bucket mapping (O(N) peak
          memory), and each bucket is popped and yielded sequentially, releasing
          bucket memory as iteration proceeds.
        """
        if pre_sorted_by_bucket:
            current_bucket_key: str | None = None
            current_bucket: list[dict[str, Any]] = []

            for item in items:
                bucket_key = self.bucket_fn(item)
                if current_bucket_key is None:
                    current_bucket_key = bucket_key
                    current_bucket.append(item)
                elif bucket_key == current_bucket_key:
                    current_bucket.append(item)
                else:
                    yield from self._deduplicate_bucket(current_bucket)
                    current_bucket = [item]
                    current_bucket_key = bucket_key

            if current_bucket:
                yield from self._deduplicate_bucket(current_bucket)
        else:
            buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for item in items:
                buckets[self.bucket_fn(item)].append(item)

            for key in list(buckets.keys()):
                bucket_items = buckets.pop(key)
                yield from self._deduplicate_bucket(bucket_items)

    iter_deduplicate = deduplicate_stream

    def deduplicate(
        self,
        items: Sequence[dict[str, Any]],
    ) -> list[DeduplicatedGroup]:
        """Deduplicate a sequence of items in O(N log N) time."""
        if not items:
            return []
        return list(self.deduplicate_stream(items, pre_sorted_by_bucket=False))


def deduplicate_postings_stream(
    items: Iterable[dict[str, Any]],
    *,
    window_size: int = 50,
    similarity_threshold: float = 0.80,
    pre_sorted_by_bucket: bool = True,
) -> Iterator[dict[str, Any]]:
    """Convenience streaming generator returning unique canonical postings."""
    deduplicator = SpatialWindowedDeduplicator(
        window_size=window_size,
        similarity_threshold=similarity_threshold,
    )
    for group in deduplicator.deduplicate_stream(
        items, pre_sorted_by_bucket=pre_sorted_by_bucket
    ):
        yield group.canonical


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
