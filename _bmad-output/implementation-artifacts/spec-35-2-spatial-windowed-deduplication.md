# Story 35.2 Spec: O(n log n) Spatial/Windowed Deduplication for Mass Entity Datasets

## Intent

As a Data Pipeline Engineer, I want cross-source deduplication of job and real estate postings to use windowed title/location sorting, so that company groupings with thousands of items do not suffer O(n²) performance degradation.

## Acceptance Criteria

- **Given** a cluster of 5,000+ postings for a single enterprise, **When** deduplication runs, **Then** pairwise comparisons are bounded to sliding date/title windows in O(n log n) time.
- **And** memory usage remains bounded via generator/iterator streaming.

## Technical Design

### 1. Algorithm Design

1. **Bucket By Spatial / Domain Key**: Group by coarse geo-bucket (e.g., district / city) or organization domain.
2. **Sort Within Bucket**: Sort items by `(normalized_title, posted_date)` in O(k log k) time per bucket.
3. **Sliding Window Comparison**:
   - Slide a window of size `W` (default 50 items or 7 days) over the sorted list.
   - Only compare items within the sliding window using Levenshtein / Jaccard similarity.
   - Total complexity across N items: O(N log N) for sort + O(N * W) for window comparisons ≈ O(N log N).

### 2. Implementation File

- `app/services/dedup/spatial_windowed_dedup.py`:
  - `SpatialWindowedDeduplicator`: class providing batch and streaming dedup
  - `deduplicate_postings(items, window_size=50, similarity_threshold=0.85)`
  - Similarity functions: title token Jaccard + price/area delta tolerance
