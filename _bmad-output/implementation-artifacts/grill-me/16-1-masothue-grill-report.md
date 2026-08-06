# Grill-Me Report — Story 16.1: masothue.com Company Data

## Q1 — Already implemented? (Duplicate Logic)

**Finding: PARTIAL DUPLICATE - Pattern reuse opportunity**

The story proposes creating `app/services/company_aggregator/` with `fingerprint()`, `merge()`, `search_text()`, and `normalize()` functions. This is a direct duplicate of the existing pattern in:
- `app/services/bds_aggregator/__init__.py` and `dedupe.py`
- `app/services/jobs_aggregator/__init__.py` and `dedupe.py`

**Evidence:**
- `bds_aggregator/dedupe.py` already implements `fingerprint()`, `merge()`, `merge_group()`, `deduplicate()`, and `search_text()` for BĐS listings
- `jobs_aggregator` follows the same pattern for job listings
- Both use SHA256-based fingerprinting with fallback to title+address hash
- Both implement union-find deduplication and merge logic

**Recommendation:** Model `app/services/company_aggregator/dedupe.py` EXACTLY after `bds_aggregator/dedupe.py` structure. New module is correct (different domain), but reuse the established pattern.

## Q2 — Simpler Alternative?

**Finding: NO SIMPLER ALTERNATIVE - New proprietary module is required**

Masothue.com requires:
- Custom HTML parsing (BeautifulSoup + lxml)
- Cloudflare anti-bot handling (`scrapling.AsyncFetcher` with `stealthy_headers`)
- AJAX token flow (`POST /Ajax/Token` → `POST /Ajax/Search`)
- Exact-match redirect handling (302 to detail page)

Vietnamworks (JSON API), cafef (simple HTML), and batdongsan (mobile API) cannot be reused.

**Verdict:** Proceed with new proprietary module `app/proprietary/platforms/masothue/`.

## Q3 — Edge Cases Spec Misses (Pattern 3)

- **Boundary:**
  - `max_pages=0` or `max_items=0` → return empty list without degrading
  - `max_pages=20` and `max_items=100` hard/soft limit not specified
- **Null/empty:**
  - `query=""` or `query=None` behavior not specified
  - Invalid `search_type` value handling not specified
  - Detail page missing `table.table-taxinfo` — skip or degrade?
  - Tax code missing AND name+address missing — fingerprint behavior?
- **Concurrent:**
  - Two users scrape same company → canonical upsert race; executor should catch `ConcurrentUpdateError`
  - Re-fetch same company — merge behavior for conflicting fields not specified
- **Data quality:**
  - Unicode normalization for non-Vietnamese characters
  - Tax code normalization rules (dashes vs no dashes)

## Q4 — Failure Modes Unspecified (Pattern 2, 4)

- **Service down:**
  - `scrapling.AsyncFetcher` unavailable — fallback or degrade?
  - Postgres down during canonical upsert — executor should catch and not charge
  - Embedding service down — affects response or async backfill only?
- **Timeout:**
  - `MASOTHUE_TIMEOUT_S` per-request vs total not specified
  - AJAX token request timeout — fallback to GET search HTML?
- **Money/cost (Pattern 4):**
  - Degraded run with partial items — charge successful page items?
  - Cost calculation timing — before or after canonical upsert?
- **Cloudflare/anti-bot:**
  - Cloudflare JS challenge detection logic
  - IP ban cooldown and user notification
- **Canonical dedup:**
  - Same tax_code from different sources (masothue vs future business.gov.vn) — V1 pass-through is fine, document limitation
  - Fingerprint collision (different companies, same hash) — extremely rare but possible
- **Workspace isolation:**
  - Executor should verify workspace context before canonical upsert
- **Rate limiting:**
  - Adaptive backoff if rate limit detected
  - V1 does not need platform account rotation (unlike batdongsan), document this

## Triage

| Finding | Severity | Action |
|---------|----------|--------|
| Duplicate pattern (Q1) | Non-critical | **REUSE** - Model `company_aggregator` after `bds_aggregator/dedupe.py` structure |
| Simpler alternative (Q2) | — | None - new module required |
| Edge case gaps (Q3) | Non-critical | **ADD TO TEST** - Add test cases for zero/null/concurrent scenarios |
| Failure mode gaps (Q4) | Non-critical | **ADD TO TEST** - Add error path tests for DB/embedding/timeout scenarios |
| **Overall** | — | **CLEAN — PROCEED** (with test additions) |
