---
title: 'Resolve RRF ranking tie-break tests and 21.8/14.1 deferred test findings'
type: 'chore'
created: '2026-09-11'
status: 'completed'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Four deferred QA findings remain open:
1. RRF ranking tie-break tests lack exhaustive coverage in `MemoryHybridSearch` (Story 3.14).
2. SQL query structure validation was reported deferred in `test_social_search_leads.py`.
3. ReDoS safety 50ms bound was reported deferred in `test_phone_regex_redos_safety.py`.
4. Integration test database persistence was reported deferred in `test_social_redis_stream.py`.

**Approach:** Make embedding dimension dynamic in `test_hybrid_search_scope_and_bounds.py`, add exhaustive tie-break integration tests for RRF score, similarity, created_at, and id tie-breaks. Verify and resolve the 3 social search/ReDoS/stream findings in `deferred-work.md`.

## Boundaries & Constraints

**Always:**
- Keep `_EMBEDDING_DIM = config.embedding_model_instance.dimension` to support both 384 and 768 dim models.
- Tie-break tests must test:
  - Higher similarity wins when RRF score is identical.
  - Newer `created_at` wins when RRF score and similarity are identical.
  - Lower `id` wins when RRF score, similarity, and `created_at` are identical.
- All existing tests in `test_hybrid_search_scope_and_bounds.py` must pass.

**Never:**
- Do not alter production RRF ordering logic in `MemoryHybridSearch.search`.
- Do not add external dependencies.

## Code Map

- `nowing_backend/app/services/memory/search.py` -- MemoryHybridSearch RRF query and ordering.
- `nowing_backend/tests/integration/memory/test_hybrid_search_scope_and_bounds.py` -- Memory hybrid search integration tests.
- `nowing_backend/tests/unit/capabilities/test_social_search_leads.py` -- Social search SQL validation tests.
- `nowing_backend/tests/unit/platforms/test_phone_regex_redos_safety.py` -- ReDoS safety 50ms test.
- `nowing_backend/tests/integration/platforms/test_social_redis_stream.py` -- Social redis stream persistence integration test.
- `_bmad-output/implementation-artifacts/deferred-work.md` -- deferred work tracking.

## Tasks & Acceptance

**Execution:**
- [x] `nowing_backend/tests/integration/memory/test_hybrid_search_scope_and_bounds.py` -- use `_EMBEDDING_DIM = config.embedding_model_instance.dimension` and add exhaustive tie-break test suite.
- [x] Verify `test_social_search_leads.py`, `test_phone_regex_redos_safety.py`, and `test_social_redis_stream.py` tests pass.
- [x] `_bmad-output/implementation-artifacts/deferred-work.md` -- mark 3-14 RRF tie-break finding and the three 21.8/14.1 findings as Resolved.

**Acceptance Criteria:**
- Given `test_hybrid_search_scope_and_bounds.py` runs against the test DB, when testing tie-breaks, then similarity tie-break, created_at tie-break, and id tie-break are proven.
- All 4 findings are marked `Resolved` in `deferred-work.md`.

## Verification

**Commands:**
- `cd nowing_backend && uv run pytest tests/integration/memory/test_hybrid_search_scope_and_bounds.py -q` -- expected: all GREEN.
- `cd nowing_backend && uv run pytest tests/unit/capabilities/test_social_search_leads.py tests/unit/platforms/test_phone_regex_redos_safety.py -q` -- expected: all GREEN.
