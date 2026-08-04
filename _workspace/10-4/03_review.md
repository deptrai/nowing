# Code Review Report — Story 10.4

**Status:** ✅ PASS

All high and medium severity findings from the initial review have been addressed. Unit and integration tests for the changed code pass.

## Findings Addressed

### H1 — `muaban_bds.scrape` not registered at startup
- **File:** `nowing_backend/app/capabilities/muaban_bds/__init__.py`
- **Fix:** Added `from .scrape import definition as _scrape` so the capability is auto-registered when `app.capabilities.muaban_bds` is imported.

### H2 — Dedupe was not transitive
- **File:** `nowing_backend/app/services/bds_aggregator/dedupe.py`
- **Fix:** Replaced the order-dependent group-matching algorithm with a union-find structure, so listings linked by any shared key (phone, address, image) are merged into a single canonical group.

### M1 — `to_batdongsan_city_code` alias table too small and case-sensitive
- **File:** `nowing_backend/app/services/bds_aggregator/normalize.py`
- **Fix:** Added a full Batdongsan city code/slug table, generated aliases for slugs, unhyphenated slugs and lower-case codes, and common user overrides. The first pass now accepts any known code case-insensitively (e.g. `bd` → `BD`).

### M2 — `freshness_score` used exponential decay instead of documented step function
- **File:** `nowing_backend/app/services/bds_aggregator/scoring.py`
- **Fix:** Implemented piecewise linear scoring: 1.0 for ≤7 days, 0.0 for ≥90 days, linear between.

### M3 — `image_key` was never populated
- **File:** `nowing_backend/app/services/bds_aggregator/normalize.py`
- **Fix:** Added `_image_key()` helper that hashes and normalizes the listing image URL; `normalize_listing()` now stores it on the output model so image-based deduplication is active.

### M4 — Duplicate `sources` not rejected
- **File:** `nowing_backend/app/services/bds_aggregator/schemas.py`
- **Fix:** Added uniqueness validation in `VnBdsAggregateInput._sources_must_be_nonempty_and_known` to prevent double fan-out and double billing.

## Verification

- `pytest tests/unit/services/bds_aggregator tests/unit/capabilities/vn_bds -q` — 33 passed
- `pytest tests/integration/capabilities/vn_bds/aggregate -q` — 3 passed

## Verdict

Story 10.4 implementation is approved to proceed to Stage 4 (end-to-end testing).
