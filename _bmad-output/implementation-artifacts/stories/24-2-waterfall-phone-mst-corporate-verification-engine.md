---
story_key: "24-2"
epic: "epic-24"
story: "24.2"
title: "Waterfall Phone & B2B Tax Code (MST) Corporate Verification Engine"
status: "ready-for-dev"
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
