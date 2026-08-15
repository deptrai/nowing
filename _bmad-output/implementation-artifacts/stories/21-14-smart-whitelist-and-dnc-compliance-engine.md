# Story 21.14: Smart Whitelist & Do-Not-Call (DNC) Compliance Engine

Status: ready-for-dev

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

- [ ] Task 1: Database Schema & Alembic Migration (AC: 1, 4, 5)
  - [ ] 1.1 Tạo model `WorkspaceDncRecord` trong `nowing_backend/app/db.py` (`id: UUID`, `workspace_id: Integer`, `record_type: Enum('phone', 'email', 'domain', 'tax_id')`, `value: String`, `value_hmac: String`, `reason: String`, `source: String`, `created_at`, `updated_at`).
  - [ ] 1.2 Tạo Alembic migration `alembic/versions/210_add_workspace_dnc_records.py`.
  - [ ] 1.3 Tạo composite index `ix_workspace_dnc_lookup` trên `(workspace_id, record_type, value_hmac)` để tra cứu sub-millisecond.
- [ ] Task 2: DNC Compliance Core Service & Normalizer (AC: 2, 3, 5)
  - [ ] 2.1 Xây dựng `nowing_backend/app/lead_intelligence/dnc/service.py` với `DncComplianceService` (`is_blocked(workspace_id, candidate)`, `batch_filter_leads(workspace_id, leads)`).
  - [ ] 2.2 Xây dựng E.164 Phone Normalizer & HMAC Hasher (`normalize_and_hash_phone`) trong `app/lead_intelligence/dnc/normalizer.py`.
  - [ ] 2.3 Tích hợp DNC check vào `PhoneWaterfallEngine` (`app/services/phone_waterfall_engine.py`) để dừng giải mã và hoàn trả 0 credit khi gặp số DNC.
- [ ] Task 3: REST API Endpoints & PII Hard Purge (AC: 1, 4)
  - [ ] 3.1 Tạo `nowing_backend/app/routes/dnc_routes.py` (`GET`, `POST`, `DELETE /workspaces/{id}/dnc`, `POST /workspaces/{id}/dnc/import-csv`).
  - [ ] 3.2 Xây dựng endpoint `DELETE /api/leads/{id}/pii` trong `app/routes/leads_routes.py` xóa vĩnh viễn PII trong DB và thêm vào DNC set.
  - [ ] 3.3 Định nghĩa Pydantic schemas tại `nowing_backend/app/schemas/dnc.py`.
  - [ ] 3.4 Đăng ký router vào `app/routes/__init__.py`.
- [ ] Task 4: Frontend DNC Management Modal & In-stream Indicators (AC: 1, 2)
  - [ ] 4.1 Xây dựng modal `nowing_web/components/leads/DncManagementModal.tsx` cho phép xem danh sách DNC, tìm kiếm và kéo thả file CSV.
  - [ ] 4.2 Xây dựng `nowing_web/lib/apis/dnc-api.service.ts` và hook `use-dnc.ts`.
  - [ ] 4.3 Cập nhật `LeadsContent.tsx` và `OrigamiLeadMatrix.tsx` hiển thị badge `🚫 DNC` đỏ xám và vô hiệu hóa nút gửi Zalo/SMS đối với các lead bị chặn.
- [ ] Task 5: Testing & Quality Verification (AC: 1-5)
  - [ ] 5.1 Unit tests: `tests/unit/dnc/test_dnc_normalizer.py` & `tests/unit/dnc/test_dnc_service.py` (Verify E.164 normalizer, wildcard domain matching, HMAC hashing).
  - [ ] 5.2 Integration tests: `tests/integration/routes/test_dnc_routes.py` (Verify CSV import 5000 lines, PII purge endpoint, zero credit debit verification).
  - [ ] 5.3 Linter & Typecheck: `uv run ruff check`, `pnpm tsc --noEmit`, `pnpm exec biome check`.

## Dev Notes

- **Decree 91/2020/NĐ-CP:** Chặn tuyệt đối gửi tin nhắn và cuộc gọi đến danh sách DNC.
- **Decree 13/2023/NĐ-CP (PDPD):** DNC hash sử dụng Keyed HMAC-SHA256 với `SECRET_KEY`, không lưu plaintext phone number trong index công khai.
- **In-stream Filter:** `DncComplianceService` sử dụng Redis Set cache `dnc:{workspace_id}:{type}` với TTL 1 giờ để đạt tốc độ tra cứu $< 1$ms trên mỗi batch 100 leads.

### References
- [Architecture Spine: epic21-architecture-update.md (AD-31, AD-42, AD-49)]
- [PRD Requirement: epics.md FR-84]
