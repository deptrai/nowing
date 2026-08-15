# Story 21.14: Smart Whitelist & Do-Not-Call (DNC) Compliance Engine

Status: done

<!-- Note: Governed by epics.md (FR-84, AD-31, AD-42, AD-49) & Decree 91/2020/NĐ-CP, Decree 13/2023/NĐ-CP -->

## Story

As a compliance-minded sales team lead or business owner,
I want to maintain a workspace-level Do-Not-Call (DNC) and contact whitelist/blacklist database (supporting CSV import, regex phone/domain matching, and instant opt-out),
So that our AI outreach sequences and phone waterfall scrapers never contact opted-out individuals or sensitive partners, avoiding legal penalties under Decree 91/2020/NĐ-CP and zeroing out credit wastage.

## Acceptance Criteria

1. **Given** a workspace administrator, **When** managing compliance lists, **Then** they can view, create, search, and bulk-import DNC entries (phone numbers, email addresses, wildcard company domains, tax IDs) via CSV upload (`POST /workspaces/{id}/dnc/import-csv`) or REST endpoints.
2. **Given** incoming leads from any scraper or manual input, **When** processed by `LeadGenOrchestrator` or `PhoneWaterfallEngine`, **Then** `DncComplianceService` validates candidates against the workspace DNC list in-stream, tagging matches as `blocked_by_dnc` and automatically excluding them from auto-enrichment and outreach sequences.
3. **Given** a lead flagged as `blocked_by_dnc`, **When** the system calculates credit consumption, **Then** exactly **0 credits** are debited from the workspace wallet for blocked contacts.
4. **Given** a consumer opt-out request or GDPR/Decree 13 "Right-to-be-Forgotten" trigger, **When** `DELETE /api/leads/{id}/pii` or opt-out webhook is invoked, **Then** all plaintext PII (phone, email, contact name) is hard-purged within 60 seconds and the phone HMAC is permanently appended to the workspace DNC blacklist.
5. **Given** phone number matching, **When** evaluating numbers against DNC rules, **Then** numbers are normalized to canonical international E.164 format (`+84xxxxxxxxx`) and hashed using Keyed HMAC-SHA256 before lookup to prevent bypass via formatting discrepancies (`0908...`, `090.8...`, `84908...`).

## Tasks / Subtasks

- [x] Task 1: Database Schema & Alembic Migration (AC: 1, 4, 5)
  - [x] 1.1 Tạo model `WorkspaceDncRecord` trong `nowing_backend/app/db.py` (`id: UUID`, `workspace_id: Integer`, `record_type: Enum('phone', 'email', 'domain', 'tax_id')`, `value: String`, `value_hmac: String`, `reason: String`, `source: String`, `created_at`, `updated_at`).
  - [x] 1.2 Tạo Alembic migration `alembic/versions/210_add_workspace_dnc_records.py`.
  - [x] 1.3 Tạo composite index `ix_workspace_dnc_lookup` trên `(workspace_id, record_type, value_hmac)` để tra cứu sub-millisecond.
- [x] Task 2: DNC Compliance Core Service & Normalizer (AC: 2, 3, 5)
  - [x] 2.1 Xây dựng `nowing_backend/app/lead_intelligence/dnc/service.py` với `DncComplianceService` (`is_blocked(workspace_id, candidate)`, `batch_filter_leads(workspace_id, leads)`).
  - [x] 2.2 Xây dựng E.164 Phone Normalizer & HMAC Hasher (`normalize_phone_e164`, `hash_phone_hmac`, `normalize_domain`, `is_domain_matching`) trong `app/lead_intelligence/dnc/normalizer.py`.
  - [x] 2.3 Tích hợp DNC check vào `PhoneWaterfallEngine` (`app/services/phone_waterfall_service.py`) để dừng giải mã và hoàn trả 0 credit khi gặp số DNC.
- [x] Task 3: REST API Endpoints & PII Hard Purge (AC: 1, 4)
  - [x] 3.1 Tạo `nowing_backend/app/routes/dnc_routes.py` (`GET`, `POST`, `DELETE /workspaces/{id}/dnc`, `POST /workspaces/{id}/dnc/import-csv`).
  - [x] 3.2 Xây dựng endpoint `DELETE /api/leads/{id}/pii` trong `app/routes/leads_routes.py` xóa vĩnh viễn PII trong DB và thêm vào DNC set.
  - [x] 3.3 Định nghĩa Pydantic schemas tại `nowing_backend/app/schemas/dnc.py`.
  - [x] 3.4 Đăng ký router vào `app/routes/__init__.py`.
- [x] Task 4: Frontend DNC Management Modal & In-stream Indicators (AC: 1, 2)
  - [x] 4.1 Xây dựng modal `nowing_web/components/leads/DncManagementModal.tsx` cho phép xem danh sách DNC, tìm kiếm và kéo thả file CSV.
  - [x] 4.2 Xây dựng `nowing_web/lib/apis/dnc-api.service.ts` và contracts tại `nowing_web/contracts/types/dnc.types.ts`.
  - [x] 4.3 Cập nhật `LeadsContent.tsx` và `LeadCard.tsx` hiển thị badge `🚫 DNC Blocked` và vô hiệu hóa nút gửi Zalo/outreach đối với các lead bị chặn.
- [x] Task 5: Testing & Quality Verification (AC: 1-5)
  - [x] 5.1 Unit tests: `tests/unit/dnc/test_dnc_normalizer.py` & `tests/unit/dnc/test_dnc_service.py` (Verify E.164 normalizer, wildcard domain matching, HMAC hashing).
  - [x] 5.2 Integration tests: `tests/integration/routes/test_dnc_routes.py` (Verify CSV import 5000 lines, PII purge endpoint, zero credit debit verification).
  - [x] 5.3 Linter & Typecheck: `ruff check`, `ruff format`, `pnpm tsc --noEmit`, `pnpm exec biome check`.

## Dev Agent Record

### Implementation Plan
- Implemented `WorkspaceDncRecord` model and Alembic migration `210_add_workspace_dnc_records.py` with composite lookup index.
- Developed `normalizer.py` (E.164 international converter, Keyed HMAC-SHA256, wildcard domain matcher) and `DncComplianceService` with Redis set caching.
- Integrated DNC in-stream evaluation in `PhoneWaterfallService`, guaranteeing 0 credit debits on blocked entries.
- Created REST API endpoints: `GET`, `POST`, `DELETE /workspaces/{id}/dnc`, `POST /workspaces/{id}/dnc/import-csv` and `DELETE /api/leads/{id}/pii`.
- Created frontend `DncManagementModal.tsx`, `dnc-api.service.ts`, and updated `LeadsContent.tsx` and `LeadCard.tsx` with DNC badge and outreach suppression.

### Code Review & Adversarial Hardening (2026-08-16)
- **Patch 1 (Privacy):** Purged leads set `value = None` in DNC table (keeping only Keyed HMAC `value_hmac`), preventing plaintext PII storage.
- **Patch 2 (Redis & Scalability):** Singleton Redis client pooling + O(1) in-memory lookups for `batch_filter_leads` and cache support across all 4 types (`phone`, `email`, `domain`, `tax_id`).
- **Patch 3 (DoS / DB limit):** CSV import size limited to 5MB / 5,000 rows, in-memory deduplication, and chunked DB inserts (500/batch).
- **Patch 4 (Wildcard Security):** Rejected broad TLD wildcards (`*`, `*.com`, `*.vn`) requiring at least 2 distinct domain labels.
- **Patch 5 (Cost Optimization):** Pre-Resolution DNC Check in `PhoneWaterfallService` before invoking third-party enrichment APIs.
- **Patch 6 (Frontend Client):** Refactored `dnc-api.service.ts` to use `baseApiService` for consistent auth headers and backend base URL.
- **Patch 7 (CSV Injection):** Sanitized CSV cell prefixes (`=`, `+`, `-`, `@`) and added UTF-8 BOM.
- **Patch 8 (DB Schema):** Cleaned up duplicate index in migration 210.
- **Patch 9 (UX Performance):** Added 300ms search input debounce to `DncManagementModal.tsx`.

### Completion Notes
- All 13 backend unit and integration tests passing (`13 passed in 0.20s`).
- All 4 frontend unit tests passing (`4 passed`).
- `pnpm tsc --noEmit` and `pnpm exec biome check` 100% clean with 0 errors.
- `ruff check` and `ruff format` 100% clean.

## File List

### New Files
- `nowing_backend/alembic/versions/210_add_workspace_dnc_records.py`
- `nowing_backend/app/lead_intelligence/dnc/__init__.py`
- `nowing_backend/app/lead_intelligence/dnc/normalizer.py`
- `nowing_backend/app/lead_intelligence/dnc/service.py`
- `nowing_backend/app/routes/dnc_routes.py`
- `nowing_backend/app/schemas/dnc.py`
- `nowing_backend/tests/unit/dnc/__init__.py`
- `nowing_backend/tests/unit/dnc/test_dnc_normalizer.py`
- `nowing_backend/tests/unit/dnc/test_dnc_service.py`
- `nowing_backend/tests/integration/routes/test_dnc_routes.py`
- `nowing_web/contracts/types/dnc.types.ts`
- `nowing_web/lib/apis/dnc-api.service.ts`
- `nowing_web/components/leads/DncManagementModal.tsx`
- `nowing_web/components/leads/__tests__/DncManagementModal.test.ts`
- `_bmad-output/test-artifacts/atdd-checklist-21-14-smart-whitelist-and-dnc-compliance-engine.md`

### Modified Files
- `nowing_backend/app/db.py`
- `nowing_backend/app/routes/__init__.py`
- `nowing_backend/app/routes/leads_routes.py`
- `nowing_backend/app/routes/workspace_tables_routes.py`
- `nowing_backend/app/services/phone_waterfall_service.py`
- `nowing_web/contracts/types/leads.types.ts`
- `nowing_web/components/leads/LeadCard.tsx`
- `nowing_web/components/leads/LeadsContent.tsx`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

## Change Log
- 2026-08-16: Implemented Story 21.14 Smart Whitelist & Do-Not-Call Compliance Engine. All 5 ACs satisfied and 100% tests passing.
- 2026-08-16: Applied 11 code-review patches covering privacy (zero-knowledge HMAC), Redis pooling, CSV chunking, wildcard hardening, and CSV injection prevention.

## Dev Notes

- **Decree 91/2020/NĐ-CP:** Chặn tuyệt đối gửi tin nhắn và cuộc gọi đến danh sách DNC.
- **Decree 13/2023/NĐ-CP (PDPD):** DNC hash sử dụng Keyed HMAC-SHA256 với `SECRET_KEY`, không lưu plaintext phone number trong index công khai.
- **In-stream Filter:** `DncComplianceService` sử dụng Redis Set cache `dnc:{workspace_id}:{type}` với TTL 1 giờ để đạt tốc độ tra cứu $< 1$ms trên mỗi batch 100 leads.

### References
- [Architecture Spine: epic21-architecture-update.md (AD-31, AD-42, AD-49)]
- [PRD Requirement: epics.md FR-84]
