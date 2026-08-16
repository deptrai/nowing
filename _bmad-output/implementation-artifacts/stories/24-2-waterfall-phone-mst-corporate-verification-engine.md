---
story_key: "24-2"
epic: "epic-24"
story: "24.2"
title: "Waterfall Phone & B2B Tax Code (MST) Corporate Verification Engine"
status: "in-progress"
baseline_commit: "6ac305274"
---

# Story 24.2: Waterfall Phone & B2B Tax Code (MST) Corporate Verification Engine

## Story Overview

As a B2B sales development representative or data sourcer,
I want scraped entity leads to be automatically enriched with verified corporate tax IDs (Mã Số Thuế - MST), legal representatives, charter capital, and phone number validation,
So that outreach teams target legitimate companies with high purchasing power and reach actual decision-makers.

---

## Architectural Invariants (INV-24.3, INV-21.3)
- **INV-24.3 (Waterfall Phone & Tax Code Isolation):** Caching kết quả tra cứu MST và Zalo UID trên Redis (TTL 7 ngày cho MST, 24h cho Phone) kèm Circuit Breaker (`circuit_breaker:scraper:masothue`) và Rotating Proxy Pool.
- **INV-21.3 (Privacy & PII Vault):** Mã hóa SĐT bằng HMAC và mã hóa đối xứng khi lưu trữ, phân quyền hiển thị theo Role.

---

## Acceptance Criteria

1. **B2B Corporate Tax Registry Integration & Multi-Attribute Match:**
   - **Given** raw lead records with business names or addresses,
   - **When** enrichment is triggered,
   - **Then** `CorporateVerificationService` queries official business registries / masothue API, applying Multi-attribute Fuzzy Matching (`Levenshtein Ratio * 0.5 + City Match * 0.3 + District Match * 0.2`). Only matches with confidence >= 0.85 are auto-linked; lower scores are flagged `requires_manual_confirmation`.

2. **3-Tier Waterfall Phone Validation & Legacy 11-Digit Conversion:**
   - **Given** raw contact phone strings,
   - **When** normalized,
   - **Then** legacy 11-digit prefixes (2018 telecom conversion: `0168` ➔ `038`, `0123` ➔ `083`, etc.) are converted to standard 10-digit E.164 (`+84...`).
   - **When** the 3-tier Waterfall runs (Tier 1: Listing Phone ➔ Tier 2: Zalo UID Check ➔ Tier 3: Masothue Rep Phone),
   - **Then** it validates carrier format, active Zalo status, and cross-checks with `workspace_dnc_records` and `global_dnc_records` (Fail-closed).

3. **Circuit Breaker & Redis Caching Resilience:**
   - **Given** upstream registry API rate-limiting or Cloudflare anti-bot challenges,
   - **When** 3 consecutive requests fail,
   - **Then** the circuit breaker trips for 10 minutes, serving cached entries from Redis (TTL 7d) and enqueuing new requests to a background retry queue.

4. **Verified Badges in Split-View Table Matrix:**
   - **Given** an enriched lead in Nowing,
   - **When** rendered on the Table Matrix,
   - **Then** it displays interactive badges (`MST Verified` in Emerald green and `Zalo Active`), showing company legal details and capital in a hover card.

---

## Technical Tasks

### Backend Implementation
- [ ] Backend: Xây dựng `CorporateVerificationService` (`nowing_backend/app/services/corporate_verification_service.py`) kết nối API tra cứu MST với Proxy Pool và Circuit Breaker.
- [ ] Backend: Nâng cấp `PhoneWaterfallService` hỗ trợ bảng chuyển đổi đầu số 11 số sang 10 số (2018 mapping) và Tier 3 MST Rep Phone.
- [ ] Database: Thêm các cột `tax_id`, `legal_representative`, `charter_capital_vnd`, `company_status`, `is_zalo_active` vào bảng `leads`.

### Frontend Implementation
- [ ] Components: Cập nhật `NowingLeadMatrix.tsx` hiển thị badge MST và Zalo status cùng tooltip chi tiết pháp lý.

---

## Verification Commands

```bash
# Backend unit & integration tests
cd nowing_backend
uv run ruff check app/services/corporate_verification_service.py app/services/phone_waterfall_service.py tests/unit/services/test_corporate_verification.py
uv run pytest tests/unit/services/test_corporate_verification.py tests/unit/services/test_phone_waterfall_service.py -q
uv run pytest tests/integration/services/test_corporate_verification_pipeline.py -q

# Frontend check
cd ../nowing_web
pnpm tsc --noEmit
pnpm exec biome check components/leads/NowingLeadMatrix.tsx
```

---

## Review Findings

### Decision needed

- [ ] [Review][Decision] No real Zalo UID check and `is_zalo_active` is never populated — `nowing_backend/app/services/phone_waterfall_service.py:318-384,412-425` — Tier 2 is still the Chợ Tốt API, Tier 3 HLR hard-codes `zalo_verified: True`, and no service writes `lead.is_zalo_active`, so the "Zalo Active" badge is dead code. Product must decide whether to integrate a real Zalo UID API or remove the badge.
- [ ] [Review][Decision] `global_dnc_records` cross-check is not implemented — `nowing_backend/app/lead_intelligence/dnc/service.py:154-234` — AC-2/INV-24.3 require checking both `workspace_dnc_records` and `global_dnc_records`, but no `GlobalDncRecord` model or query exists. Product must decide whether to add a global DNC table.
- [ ] [Review][Decision] Phone and corporate Redis caches store plaintext PII and bypass DNC/billing — `nowing_backend/app/services/phone_waterfall_service.py:526-561,766-791` and `nowing_backend/app/services/corporate_verification_service.py:427-428,605-617` — Caches return `phone` before DNC and wallet checks, store raw phones/addresses with no HMAC/signature, and ignore DNC changes for 30 days. Product must decide cache PII, re-validation, and integrity policy.
- [ ] [Review][Decision] Tax-ID exact match bypasses the fuzzy confidence threshold — `nowing_backend/app/services/corporate_verification_service.py:484-489` — `is_ver` is true if `score >= 0.85 OR profile.tax_id == clean_tax`, forcing confidence to `0.98` even when the company name and location do not match. Product must decide whether tax-id alone should auto-link.
- [ ] [Review][Decision] Corporate verification is not wired to the enrichment trigger — `nowing_backend/app/lead_intelligence/enrichment/service.py:157-298` — `CorporateVerificationService` is only used as a Tier 3 phone fallback and in tests; the main `EnrichmentService._run_waterfall` never invokes it. Product must decide the trigger point.
- [ ] [Review][Decision] Cross-contamination with Story 24.3/24.4 — `nowing_backend/app/db.py:1892,2828-2844,4574-4605,4674-4837` and `nowing_web/contracts/types/leads.types.ts:46-48` — The diff adds Workspace credit, membership spend/lead-distribution, Lead CRM columns, and full CRM pipeline/assignment/activity tables labeled as 24.3/24.4, plus related frontend types. Product must decide whether to keep or move them to their own story branches.
- [ ] [Review][Decision] Rotating proxy pool and background retry queue are not implemented — `nowing_backend/app/services/corporate_verification_service.py:256-274` — `search_company` accepts a `proxy` parameter but never passes it to `scrape_masothue`, and AC-3's background retry queue/Celery enqueue logic is absent. Product must decide proxy and retry architecture.
- [ ] [Review][Decision] Spec/code contradiction on 10-digit phone output format — `nowing_backend/app/services/phone_waterfall_service.py:129-169` and Story 24.2 spec AC-2 — The spec says legacy 11-digit numbers are converted to "standard 10-digit E.164 (`+84...`)", but `normalize_vn_phone` and the tests return domestic `0...` format. Product must align the contract.
- [ ] [Review][Decision] Phone-resolution concurrency can double-resolve and double-bill — `nowing_backend/app/services/phone_waterfall_service.py:526-561,590-598,758-761` — No lead-level distributed lock exists; concurrent requests for the same `lead_id` can both miss the 30-day cache, execute tiers, and create `PhoneWaterfallLog`/`BillingEvent` entries. Product must decide concurrency control.

### Patch

- [ ] [Review][Patch] ORM `Lead` model is missing the corporate/Zalo columns the migration adds — `nowing_backend/app/db.py:4483-4608` — Migration 220 adds `tax_id`, `legal_representative`, `charter_capital_vnd`, `company_status`, and `is_zalo_active`, but the `Lead` class only has the 24.3/24.4 CRM columns.
- [ ] [Review][Patch] `LeadRead` API schema and mapper do not expose the new corporate/Zalo fields — `nowing_backend/app/lead_intelligence/schemas.py:38-78` and `nowing_backend/app/routes/leads_routes.py:117-145` — The backend never serializes `tax_id`, `legal_representative`, `charter_capital_vnd`, `company_status`, or `is_zalo_active`, so the `NowingLeadMatrix` badges have no data.
- [ ] [Review][Patch] Composite-PK lead lookup is not tenant-scoped — `nowing_backend/app/services/corporate_verification_service.py:640` and `nowing_backend/app/services/phone_waterfall_service.py:501` — Both services call `session.get(Lead, lead_id)` for a composite primary key `(id, workspace_id)`, which will raise `InvalidRequestError` or load without a SQL tenant filter.
- [ ] [Review][Patch] `DefaultMasothueClient` and the masothue parser/schema cannot produce the data the service expects — `nowing_backend/app/services/corporate_verification_service.py:277-293`, `nowing_backend/app/proprietary/platforms/masothue/schemas.py:50-69`, `nowing_backend/app/proprietary/platforms/masothue/parsers.py:15-31` — The client reads `representative`, `charter_capital`, `city`, `district`, `rep_phone`, `main_business`, and `founding_date`, but the schema and parser do not produce those keys.
- [ ] [Review][Patch] DNC service fails open when DB or Redis is unavailable — `nowing_backend/app/lead_intelligence/dnc/service.py:87-109,154-234` — `_get_workspace_dnc_set` catches all exceptions and returns an empty `members` set, so `is_blocked` returns `False` whenever the DNC registry cannot be loaded.
- [ ] [Review][Patch] Wallet credit `check_balance` → `apply_debit` is not atomic — `nowing_backend/app/services/wallet_credit.py:50-104` and `nowing_backend/app/services/phone_waterfall_service.py:564-588,758-761` — `check_balance` and `apply_debit` read and write `User.credit_micros_balance` in separate transactions with no row-level lock; concurrent phone resolutions can overdraw.
- [ ] [Review][Patch] Circuit breaker is per-instance and miscounts failures — `nowing_backend/app/services/corporate_verification_service.py:322,359-385,412-417,559-565` and `nowing_backend/app/proprietary/platforms/masothue/scraper.py:108-114` — `consecutive_failures` lives in process memory (resets per request), `_record_success()` is called on degraded/empty `MasothueScrapeOutput`, and a tax-ID failure followed by name-search failure can double-increment the counter.
- [ ] [Review][Patch] `get_company_by_tax_id` returns the first candidate when there is no exact match — `nowing_backend/app/services/corporate_verification_service.py:296-303` — If the upstream search returns results but none match the requested tax ID, the method returns `res[0]`, which can link the lead to an unrelated company.
- [ ] [Review][Patch] DNC phone normalizer omits legacy 11-digit conversion — `nowing_backend/app/lead_intelligence/dnc/normalizer.py:14-48` and `nowing_backend/app/proprietary/platforms/xactions/phone_extractor.py:73-82` — `normalize_phone_e164` converts `01234567890` to `+841234567890` without applying `convert_legacy_11_digit`, so a DNC record with a legacy number will not block the converted 10-digit number.
- [ ] [Review][Patch] DNC HMAC falls back to a hard-coded, public secret — `nowing_backend/app/lead_intelligence/dnc/normalizer.py:53-55` and `nowing_backend/app/lead_intelligence/dnc/service.py:58-61` — When `SECRET_KEY` is unset the HMAC key is `nowing-dnc-secret-fallback`, letting an attacker precompute acceptable phone hashes and bypass the DNC list.
- [ ] [Review][Patch] Phone cache TTL and phone hashing do not follow invariants — `nowing_backend/app/services/phone_waterfall_service.py:53,185-189` — `PHONE_CACHE_TTL_SECONDS` is 30 days instead of the 24h in INV-24.3, and `hash_phone` uses plain SHA-256 instead of the HMAC required by INV-21.3.
- [ ] [Review][Patch] Fuzzy matching algorithm deviates from the spec and is too permissive — `nowing_backend/app/services/corporate_verification_service.py:62-112,144-157` — The spec calls for `Levenshtein Ratio`, but the code uses `difflib.SequenceMatcher`; corporate-prefix normalization is limited, and `_match_admin_unit` returns `1.0` on substring containment.
- [ ] [Review][Patch] Location and charter-capital parsing are fragile — `nowing_backend/app/services/corporate_verification_service.py:160-208,348-357` — `_parse_location` assumes "district, city" and does not validate actual city/district; `parse_charter_capital_vnd` misses shorthands like `tỉ`/`ngàn` and uses `float` then `int`.
- [ ] [Review][Patch] Migrations 220 and 221 create duplicate Alembic heads — `nowing_backend/alembic/versions/220_add_corporate_and_zalo_lead_columns.py:15` and `nowing_backend/alembic/versions/221_add_multi_seat_crm_and_credit_pooling.py:20` — Both revisions set `down_revision = "218"`, producing two heads in `alembic history`.
- [ ] [Review][Patch] `company_status` badge is always emerald green — `nowing_web/components/leads/NowingLeadMatrix.tsx:588-592` — Company status is rendered with `text-emerald-700` regardless of value, so a dissolved/closed company still appears as verified/success.
- [ ] [Review][Patch] Ruff lint and format checks fail on changed files — `nowing_backend/tests/unit/services/test_corporate_verification.py`, `nowing_backend/tests/unit/services/test_phone_waterfall_service.py`, `nowing_backend/app/services/corporate_verification_service.py`, `nowing_backend/app/services/phone_waterfall_service.py`, `nowing_backend/app/lead_intelligence/dnc/service.py`, `nowing_backend/app/proprietary/platforms/xactions/phone_extractor.py` — `ruff check` reports 11+ unused/unsorted import errors and `ruff format --check` would reformat six files.

### Deferred

- [x] [Review][Defer] PII vault lacks key-rotation and encryption-failure handling — `nowing_backend/app/services/pii/verified_contact_encryption.py:40-55` and `nowing_backend/app/services/phone_waterfall_service.py:692` — Verified-contact encryption relies on a single `SECRET_KEY` with no rotation plan, and `resolve_lead_phone` calls `encrypt()` without guarding against transient failures. Cross-cutting PII-vault hardening; revisit in a dedicated PII security story.
