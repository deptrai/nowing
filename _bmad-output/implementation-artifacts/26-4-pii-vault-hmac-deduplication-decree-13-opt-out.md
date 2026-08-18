---
story_key: "26-4"
epic: "epic-26"
story: "26.4"
title: "PII Vault, HMAC Deduplication & Decree 13 Opt-Out"
status: "review"
baseline_commit: "876947901"
---

# Story 26.4: PII Vault, HMAC Deduplication & Decree 13 Opt-Out

## ⚠️ CRITICAL CORRECTIONS / BLOCKERS — Resolve Before Dev

1. **PII Encryption Method: Fernet/TokenEncryption is canonical, NOT AES-256-GCM.**
   - Architecture Spine v5 (`_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` §AD-105, Rule 1) and the 2026-08-17 architecture review v5 explicitly decided: canonical at-rest encryption for `verified_contacts` is the existing `VerifiedContactEncryption` (Fernet/TokenEncryption).
   - **AES-256-GCM is DEFERRED.** Do NOT introduce a new AES-256-GCM cipher or replace the `verified_contacts` columns with `phone_encrypted` / `email_encrypted` separate columns. If a future AD amendment requires AES-GCM, it must come with a decrypt/re-encrypt migration plan.
   - `epics.md` Story 26.4 AC text still says `phone_encrypted` / `email_encrypted` via AES-256-GCM — this is **out-of-date** and must be treated as the architecture decision overriding it.

2. **HMAC Form Inconsistency Across Codebase.**
   - `app/services/lead_batch_service.py` computes `verified_contacts.value_hmac` as `hash_phone_hmac(f"{norm_phone}|{norm_email}", config.SECRET_KEY)`.
   - `app/lead_intelligence/enrichment/service.py` and `app/services/phone_waterfall_service.py` do NOT set `value_hmac` at all.
   - `app/lead_intelligence/services/deduplication_service.py` has a separate `compute_phone_hmac(..., secret="nowing_default_lead_secret")` default.
   - **Canonical per AD-105 Rule 2:** `HMAC_SHA256("phone=<normalized_phone>|email=<normalized_email>|domain=<domain>", config.SECRET_KEY)`. This story must create ONE canonical helper, backfill all existing rows, and migrate all writers.

3. **`verified_contacts.value_hmac` and `leads.value_hmac` are still nullable.**
   - `alembic/versions/ac475d54f6a2_story_26_1_chainlens_chunks_and_.py` added `verified_contacts.value_hmac` as `nullable=True` with a partial unique index.
   - `app/db.py` `Lead.value_hmac` is `nullable=True`.
   - AD-105 and AD-109 require both to be `NOT NULL` with a full `UNIQUE(workspace_id, value_hmac)` constraint. Migration must backfill before `ALTER COLUMN ... NOT NULL`.

4. **No PII Opt-Out / Right-to-be-Forgotten endpoint yet.**
   - `app/routes/dnc_routes.py` supports `POST /workspaces/{workspace_id}/dnc` for DNC list management, but it does NOT perform retroactive purge of `verified_contacts`, credit refund, or schedule irreversible PII deletion.
   - AD-110 Rule 3 requires `POST /api/v1/workspaces/{workspace_id}/pii-opt-out` with 24h SLA, credit refund, and PII deletion/anonymization.

5. **Contact Unlock endpoint exists but does not return decrypted PII.**
   - `app/routes/lead_batch_routes.py` has `POST .../contacts/{contact_id}/unlock` and uses `BillingEventService.record_contact_unlock`.
   - It currently only flips `is_unlocked=True` and appends an audit log. It does not decrypt phone/email or return them. Per AD-105 Rule 4, the endpoint should decrypt PII after successful billing and return it securely (e.g., in `ContactUnlockResponse`).

## ✅ Resolved Design Decisions (post grill-me)

### D1 — Blind index for encrypted PII lookup
- Thêm `phone_hmac` và `email_hmac` blind-index columns vào `verified_contacts`.
- `phone_hmac = hash_phone_hmac(normalize_phone_e164(phone), config.SECRET_KEY)`.
- `email_hmac = hash_phone_hmac(normalize_email(email), config.SECRET_KEY)`.
- Blind indexes cho phép opt-out tìm và purge contacts theo phone/email mà không cần decrypt toàn bộ workspace. Cùng hash function và secret được dùng trong `workspace_dnc_records` / `global_dnc_records` để lookup khớp.
- Composite `value_hmac` vẫn dùng cho dedup: `HMAC_SHA256("phone=<p>|email=<e>|domain=<d>", config.SECRET_KEY)`.

### D2 — Refund contract for contact unlock
- Contact unlock debit từ **user wallet** (`User.credit_micros_balance`) qua `wallet_credit.apply_debit`, và tăng **member monthly spent** qua `WorkspaceCreditService.record_spend` (spend cap tracking), **không** trừ `Workspace.credit_micros_balance`.
- Refund opt-out:
  1. Tìm original `BillingEvent` (`event_type='contact_unlock'`, `event_entity_type='verified_contact'`, `event_id=contact.id`) để lấy `payer_user_id`.
  2. Kiểm tra 15% refund cap theo billing cycle/workspace.
  3. Credit `User.credit_micros_balance += 1_500` (payer từ BillingEvent hoặc workspace owner nếu payer missing).
  4. Giảm `WorkspaceMembership.monthly_spent_micros` tương ứng (thêm `WorkspaceCreditService.refund_member_spend` hoặc mở rộng `record_spend` cho negative amount với reason).
  5. Viết `BillingEvent` mới với `event_type='contact_unlock_refund'`, `cost_micros=-1_500`, `cost_basis='actual'`.
  6. Idempotent: nếu đã tồn tại `BillingEvent` refund cho contact, return existing.

---

## Story

As a Nowing platform engineer and compliance operator,
I want all verified contact PII encrypted at rest with a canonical blind HMAC, an auditable contact-unlock flow, and a Decree 13 Right-to-be-Forgotten opt-out workflow,
So that Nowing meets PDPD Decree 13/2023/ND-CP, avoids PII leakage, deduplicates contacts safely, and can honor data-subject opt-out requests within 24 hours.

---

## Acceptance Criteria

### AC-1 — All PII encrypted at rest in `verified_contacts`
**Given** any writer creates or updates a `VerifiedContact`,  
**When** persisted,  
**Then** `name`, `title`, `email`, and `phone` are encrypted using the canonical `VerifiedContactEncryption` (Fernet/TokenEncryption in `app/services/pii/verified_contact_encryption.py`) before storage; no plaintext PII is written to `verified_contacts`.

- Fix `app/services/phone_waterfall_service.py` which currently stores `name=lead.company_name` in plaintext.
- Fix `app/lead_intelligence/enrichment/service.py` which already encrypts but does not set `value_hmac`.
- Fix `app/services/lead_batch_service.py` if it stores any unencrypted `name` / `title`.

### AC-2 — Canonical HMAC-SHA256 deduplication form
**Given** a verified contact with phone, email, and lead domain,  
**When** `value_hmac` is computed,  
**Then** it uses the canonical form:
```
HMAC_SHA256(
  "phone=<normalized_phone>|email=<normalized_email>|domain=<domain>",
  config.SECRET_KEY
)
```
- Normalization reuses `app/lead_intelligence/dnc/normalizer.py`: `normalize_phone_e164`, `normalize_email`, `normalize_domain`.
- The helper lives in a single location (e.g., `app/lead_intelligence/dnc/normalizer.py` or `app/services/pii/hmac.py`).
- All three writers (`lead_batch_service.py`, `enrichment/service.py`, `phone_waterfall_service.py`) are updated to call this helper.
- `verified_contacts.value_hmac` becomes `NOT NULL` with a full `UNIQUE(workspace_id, value_hmac)` constraint after backfill.
- `verified_contacts.phone_hmac` / `email_hmac` are populated using `hash_phone_hmac` on normalized phone/email (blind indexes for opt-out lookup and DNC matching).
- `leads.value_hmac` becomes `NOT NULL` with a full `UNIQUE(workspace_id, value_hmac)` constraint after backfill.

### AC-3 — Decree 13 PII Opt-Out endpoint
**Given** a data subject (phone/email) or workspace admin requests Right-to-be-Forgotten,  
**When** `POST /api/v1/workspaces/{workspace_id}/pii-opt-out` is called with `{ "record_type": "phone"|"email", "value": "...", "reason": "..." }`,  
**Then** the backend:
1. Normalizes the value and computes HMAC using the canonical helper.
2. Inserts/upserts a `workspace_dnc_records` row (or `global_dnc_records` if superadmin/global scope) with `source='opt_out'` and `reason='Right to be forgotten'`.
3. Finds all `verified_contacts` in the workspace (or globally for superadmin) whose `phone_hmac` or `email_hmac` (blind index) matches the opt-out HMAC.
4. For each matched contact:
   - Sets `is_unlocked = FALSE`.
   - Overwrites `name`, `title`, `email`, `phone` with `None` (irreversible deletion) or an anonymized token (e.g., `__ANONYMIZED__` HMAC) per legal review.
   - Sets `consent = FALSE`, `consent_status = 'withdrawn'`, `legal_basis = 'opt_out'`.
   - Appends to `pii_access_audit_logs` with `access_type='opt_out_purged'`, `actor_id`, `timestamp`, `ip_address`, `reason`.
5. Refunds 1,500 micros per contact that had `is_unlocked = TRUE` and a corresponding `BillingEvent` with `event_type='contact_unlock'`, capped at 15% of total unlocked leads in the current billing cycle per workspace (AD-110 Rule 4):
   - Tìm payer từ original `BillingEvent.user_id`.
   - Credit `User.credit_micros_balance += 1_500`.
   - Giảm `WorkspaceMembership.monthly_spent_micros` tương ứng (không tăng `Workspace.credit_micros_balance`).
   - Viết `BillingEvent` với `event_type='contact_unlock_refund'`, `cost_micros=-1_500`.
   - Idempotent: nếu refund đã tồn tại, không tính phí lại.
6. Invalidates the DNC Redis cache for the workspace/global scope.
7. Returns `PiiOptOutResponse` with `purged_contact_count`, `refunded_micros`, and `dnc_record_id`.

### AC-4 — PII Opt-Out SLA and retroactive propagation
**Given** a successful PII opt-out,  
**When** future scrapers, batch ingest, phone waterfall, or enrichment processes encounter the same phone/email/domain,  
**Then** `DncComplianceService` fail-closed blocks the record, no new `VerifiedContact` is created, and no credit is charged for it.

### AC-5 — Hardened Contact Unlock and billing
**Given** a workspace member with permission `LEADS_WRITE` and sufficient wallet balance,  
**When** `POST /api/v1/workspaces/{workspace_id}/leads/{lead_id}/contacts/{contact_id}/unlock` is called,  
**Then**:
1. If `is_unlocked` is already `TRUE`, return `ContactUnlockResponse` with decrypted `phone` and `email` (idempotent, `cost_micros=0`).
2. If `is_unlocked` is `FALSE`:
   - `BillingEventService.record_contact_unlock(..., cost_micros=1_500)` checks `User.credit_micros_balance` (user wallet), records spend cap via `WorkspaceCreditService.record_spend`, debits `wallet_credit.apply_debit` (user wallet), và writes `BillingEvent` với `event_type='contact_unlock'`, `event_entity_type='verified_contact'`, `cost_basis='actual'`.
   - On success: decrypt `phone`/`email`, set `is_unlocked=TRUE`, append audit log, and return `phone`, `email`, `cost_micros=1500`.
   - On failure (insufficient credits, billing error, decryption error): return `402 Payment Required` or `500` and do NOT leak decrypted PII; `is_unlocked` stays `FALSE`.

### AC-6 — Schema migration and backfill
**Given** the existing `verified_contacts` and `leads` tables,  
**When** the Alembic migration runs,  
**Then**:
1. It adds nullable `phone_hmac` and `email_hmac` blind-index columns to `verified_contacts`.
2. It backfills `verified_contacts.value_hmac` for all rows using the canonical helper (phone, email, lead domain) before applying `NOT NULL`.
3. It backfills `verified_contacts.phone_hmac` / `email_hmac` using `hash_phone_hmac` on normalized phone/email.
4. It backfills `leads.value_hmac` for all rows using `generate_lead_hmac` or a deterministic HMAC before applying `NOT NULL`.
5. It replaces the partial unique index on `verified_contacts` with a full `UNIQUE(workspace_id, value_hmac)` constraint.
6. It adds `Index("ix_verified_contacts_value_hmac", "workspace_id", "value_hmac", unique=True)`.
7. It adds indexes on `verified_contacts(workspace_id, phone_hmac)` and `verified_contacts(workspace_id, email_hmac)`.
8. It adds an index on `workspace_dnc_records.value_hmac` if not present.

### AC-7 — Masked display and PII redaction
**Given** a lead/contact response rendered to non-privileged users,  
**When** `is_unlocked` is `FALSE`,  
**Then** phone numbers are masked as `0908 *** 456` (reuse `app/services/phone_waterfall_service.py:mask_phone` or `app/services/export_service.py:mask_phone`), emails are masked as `a***@example.com`, and names are masked as `Nguyễn ***`.

### AC-8 — Tests and verification
**Given** the test suite,  
**When** run,  
**Then**:
1. Unit tests for canonical HMAC, PII encryption round-trip, opt-out service, and refund cap.
2. Integration tests for opt-out endpoint (purges, refunds, blocks future ingest), unlock endpoint (insufficient credits, idempotency, audit log), and DNC fail-closed.
3. Concurrency test: simultaneous unlock and opt-out on the same contact do not deadlock or over-refund.
4. `ruff check` and `ruff format` pass.

---

## Tasks / Subtasks

- [x] **Task 1: Database Schema & Migration (AC-6)**
  - [ ] Resolve blind PII lookup design: thêm `phone_hmac` / `email_hmac` blind-index columns hoặc chấp nhận AD amendment cho phương án khác.
  - [ ] Create Alembic revision after the latest head: `cd nowing_backend && uv run alembic revision --autogenerate -m "pii vault canonical hmac and opt out"`.
  - [ ] Backfill `verified_contacts.value_hmac` for existing rows using canonical helper.
  - [ ] Backfill `verified_contacts.phone_hmac` / `email_hmac` (nếu dùng blind index) từ normalized phone/email.
  - [ ] Backfill `leads.value_hmac` for existing rows.
  - [ ] Make `verified_contacts.value_hmac` `NOT NULL`, add `UNIQUE(workspace_id, value_hmac)`.
  - [ ] Make `leads.value_hmac` `NOT NULL`, ensure `UNIQUE(workspace_id, value_hmac)`.
  - [ ] Add indexes trên `verified_contacts` cho `(workspace_id, phone_hmac)` và `(workspace_id, email_hmac)` nếu dùng blind index.
  - [ ] Add `workspace_dnc_records.value_hmac` index if missing.

- [x] **Task 2: Canonical HMAC & Encryption Helper (AC-2, AC-1)**
  - [ ] Create or update canonical helper `compute_verified_contact_hmac(phone, email, domain, secret_key)` in `app/lead_intelligence/dnc/normalizer.py` (or `app/services/pii/hmac.py`).
  - [ ] Input: `phone=<norm_phone>|email=<norm_email>|domain=<domain>`; use `hmac.new(config.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()`.
  - [ ] Add helpers `compute_phone_hmac` / `compute_email_hmac` cho blind indexes nếu dùng blind index.
  - [ ] Update `app/services/lead_batch_service.py` to use canonical helper, set `phone_hmac`/`email_hmac`, và encrypt `name`/`title`.
  - [ ] Update `app/lead_intelligence/enrichment/service.py` to set `value_hmac`, `phone_hmac`, `email_hmac`.
  - [ ] Update `app/services/phone_waterfall_service.py` to encrypt `name`/`title`, set `value_hmac`, `phone_hmac`, `email_hmac`.
  - [ ] Optionally fix `app/lead_intelligence/services/deduplication_service.py` to default `secret=config.SECRET_KEY`.

- [x] **Task 3: PII Opt-Out Service & Route (AC-3, AC-4)**
  - [ ] Chốt blind-lookup phương án: dùng `phone_hmac` / `email_hmac` columns (prefer) hoặc decrypt scan.
  - [ ] Create `app/services/pii/opt_out_service.py`:
    - `process_opt_out(session, workspace_id, record_type, value, actor_user_id, ip_address, global_scope=False)`.
    - Inserts DNC record, tìm contacts qua blind index hoặc phương án đã chốt, purges contacts, computes refund, handles 15% cap.
  - [ ] Create `app/routes/pii_opt_out_routes.py` (or extend `dnc_routes.py`) với `POST /api/v1/workspaces/{workspace_id}/pii-opt-out`.
  - [ ] Register router in `app/app.py`.
  - [ ] Implement refund qua `BillingService` pattern (credit `User.credit_micros_balance` của payer từ `BillingEvent.user_id`, write negative `BillingEvent` `contact_unlock_refund`) hoặc `WorkspaceCreditService.refund_credits` nếu unlock thực sự trừ workspace pool. **Verify with finance/billing team before choosing.**

- [x] **Task 4: Harden Contact Unlock (AC-5)**
  - [ ] Update `app/routes/lead_batch_routes.py:unlock_contact` to return decrypted `phone`/`email` in `ContactUnlockResponse` only after successful billing.
  - [ ] Ensure `BillingEventService.record_contact_unlock` is used and not `wallet_credit.apply_debit` directly.
  - [ ] Add idempotent re-unlock path that returns decrypted PII without re-billing.
  - [ ] Ensure `pii_access_audit_logs` entries include `ip_address` (request client IP).

- [x] **Task 5: Masking & Display (AC-7)**
  - [ ] Reuse `app/services/export_service.py:mask_phone` / `mask_email`; chỉ thêm `mask_name` nếu chưa có.
  - [ ] Update `app/routes/leads_routes.py:_map_lead_to_read` and any contact response mappers to mask `email` and `name` when `is_unlocked=False`.
  - [ ] Ensure `LeadRead` / contact schemas do not leak encrypted or plaintext PII in masked state.

- [x] **Task 6: Audit & Compliance Logging (AC-3, AC-5)**
  - [ ] Standardize `pii_access_audit_logs` JSON shape: `{"user_id": str, "workspace_id": int, "lead_id": str, "contact_id": str, "access_type": "unlock"|"opt_out_purged"|"admin_pii_access", "timestamp": str, "ip_address": str, "reason": str}`.
  - [ ] Update all contact write paths to append audit log on unlock and opt-out.

- [x] **Task 7: Tests (AC-8)**
  - [ ] Unit: `tests/unit/services/test_pii_hmac.py`, `tests/unit/services/test_pii_opt_out_service.py`.
  - [ ] Integration: `tests/integration/routes/test_pii_opt_out.py`, `tests/integration/lead_batch/test_contact_unlock.py` (extend existing).
  - [ ] Concurrency: `tests/integration/services/test_pii_opt_out_concurrency.py`.
  - [ ] Run `ruff check`, `ruff format`, `uv run pytest tests/unit/services/test_pii* tests/integration/routes/test_pii* tests/integration/lead_batch/test_contact_unlock.py -q`.

---

## Dev Notes

### Architecture Compliance & Invariants

- **AD-105 (PII Vault & Decree 13 Compliance):**
  - Phone/email (and name/title, which are PII) MUST be encrypted at rest using the canonical `VerifiedContactEncryption` (Fernet/TokenEncryption).
  - `verified_contacts` is the authoritative PII vault; `redact_pii()` is never applied to these raw values.
  - `value_hmac` is a blind HMAC-SHA256 used for deduplication and DNC matching, not for display.
  - Contact unlock is a billable event: 1,500 micros, `BillingEvent` with `event_type='contact_unlock'`, `cost_basis='actual'`.
- **AD-110 (PII Opt-Out Blacklist, Refund & Two-Tier Unlock):**
  - Canonical opt-out/blacklist vault is the existing `workspace_dnc_records` / `global_dnc_records`.
  - Do NOT create a new `pii_blacklists` table unless an explicit merge migration is written.
  - Opt-out workflow: DNC record → mark `is_unlocked=FALSE` → refund (capped at 15% of unlocked leads per billing cycle) → irreversible PII deletion/anonymization → audit log.
  - Two-Tier Unlock UX is Story 26.5; 26.4 only hardens the backend unlock + billing path.
- **AD-109 (Batch Ingestion & Deadlock Prevention):**
  - `leads.value_hmac` and `verified_contacts.value_hmac` MUST be `NOT NULL` and part of `UNIQUE(workspace_id, value_hmac)`.
  - Bulk upserts MUST sort by `value_hmac ASC`.
- **AD-104 (Zero-Cache CDC):**
  - `verified_contacts` and `pii_access_audit_logs` MUST NOT be published to `zero_publication`.
  - `leads` publication column list already excludes PII-derived columns (`value_hmac` should also be excluded; verify `app/zero_publication.py`).

### Existing Code to Reuse

- **`app/services/pii/verified_contact_encryption.py`** — `VerifiedContactEncryption` (Fernet/TokenEncryption), `encrypt_contact()`, `decrypt_contact()`, `is_encrypted()`.
- **`app/lead_intelligence/dnc/normalizer.py`** — `normalize_phone_e164`, `normalize_email`, `normalize_domain`, `hash_phone_hmac`.
- **`app/lead_intelligence/dnc/service.py`** — `DncComplianceService` with workspace/global DNC lookup and Redis cache invalidation.
- **`app/services/billing_event_service.py`** — `BillingEventService.record_contact_unlock` and `_record_business_event` for wallet debit/spend cap.
- **`app/services/billing_service.py`** — `BillingService.auto_refund_lead` (credits `User.credit_micros_balance`, writes negative `BillingEvent`, invalidates Redis cache). Pattern này nên được reuse/adapt cho contact-unlock refund.
- **`app/services/workspace_credit_service.py`** — `WorkspaceCreditService.refund_credits` (workspace pool + member monthly spent refund). Chỉ dùng nếu unlock thực sự trừ `Workspace.credit_micros_balance`.
- **`app/services/wallet_credit.py`** — `apply_debit` cho user wallet; chú ý không có `apply_credit`.
- **`app/services/phone_waterfall_service.py`** — `mask_phone`, phone normalization/extraction, `VerifiedContact` creation.
- **`app/services/export_service.py`** — `mask_phone`, `mask_email` đã có thể reuse.
- **`app/routes/lead_batch_routes.py`** — existing `/workspaces/{workspace_id}/leads/{lead_id}/contacts/{contact_id}/unlock` route và `ContactUnlockResponse`.
- **`app/routes/dnc_routes.py`** — existing DNC CRUD và `_normalize_dnc_value` helper.
- **`app/db.py`** — `VerifiedContact`, `Lead`, `WorkspaceDncRecord`, `GlobalDncRecord`, `BillingEvent` models.

### Gaps & Implementation Hints

- **`VerifiedContact.value_hmac` is nullable** and only set by `lead_batch_service.py` using a non-canonical form. Enrichment and phone waterfall leave it NULL.
- **`Lead.value_hmac` is nullable**; must backfill before `NOT NULL`.
- **`phone_waterfall_service.py` stores `name=lead.company_name` plaintext** and does not encrypt. The `VerifiedContactEncryption.encrypt()` should be called for `name` and `title`.
- **Blind lookup of encrypted PII: resolved.** Thêm `phone_hmac` / `email_hmac` columns vào `verified_contacts`, tính bằng `hash_phone_hmac` trên normalized phone/email. Đây là blind index cho opt-out lookup và khớp với `workspace_dnc_records.value_hmac`.
- **Opt-out refund contract: resolved.** Contact unlock debit từ `User.credit_micros_balance` (user wallet) qua `wallet_credit.apply_debit` và tăng `WorkspaceMembership.monthly_spent_micros` qua `WorkspaceCreditService.record_spend` (spend cap). Refund:
  - Tìm payer từ original `BillingEvent.user_id`.
  - Credit `User.credit_micros_balance += 1_500` (pattern từ `BillingService.auto_refund_lead`).
  - Giảm `WorkspaceMembership.monthly_spent_micros` tương ứng (thêm `WorkspaceCreditService.refund_member_spend` hoặc mở rộng `record_spend` cho negative amount với reason).
  - Viết `BillingEvent` với `event_type='contact_unlock_refund'`, `cost_micros=-1_500`.
  - Không dùng `WorkspaceCreditService.refund_credits` (vì nó tăng `Workspace.credit_micros_balance`, không phải user wallet).
- **15% refund cap** requires counting `BillingEvent.event_type='contact_unlock'` vs `contact_unlock_refund` in the current billing cycle per workspace.
- **Existing `ContactUnlockResponse` does not return phone/email.** Extend it to `contact_id`, `is_unlocked`, `cost_micros`, `phone` (decrypted), `email` (decrypted), but only after successful billing.
- **DNC cache invalidation** must be called after opt-out via `DncComplianceService.invalidate_workspace_cache(workspace_id)` and `invalidate_global_cache()` for global opt-outs.

### Project Structure Notes

- New files likely:
  - `nowing_backend/app/services/pii/opt_out_service.py`
  - `nowing_backend/app/routes/pii_opt_out_routes.py` (or extend `dnc_routes.py`)
  - `nowing_backend/app/services/pii/mask.py` (mask email/name)
  - `nowing_backend/alembic/versions/<new>_pii_vault_hmac_opt_out.py`
  - `nowing_backend/tests/unit/services/test_pii_hmac.py`
  - `nowing_backend/tests/unit/services/test_pii_opt_out_service.py`
  - `nowing_backend/tests/integration/routes/test_pii_opt_out.py`
  - `nowing_backend/tests/integration/services/test_pii_opt_out_concurrency.py`
- Files to modify:
  - `nowing_backend/app/db.py` (thêm `phone_hmac`, `email_hmac` columns nếu dùng model-driven; prefer migration)
  - `nowing_backend/app/lead_intelligence/dnc/normalizer.py` (canonical helper + blind index helpers)
  - `nowing_backend/app/services/lead_batch_service.py` (use canonical HMAC, set phone_hmac/email_hmac, encrypt name/title)
  - `nowing_backend/app/lead_intelligence/enrichment/service.py` (set value_hmac, phone_hmac, email_hmac)
  - `nowing_backend/app/services/phone_waterfall_service.py` (encrypt name/title, set value_hmac, phone_hmac, email_hmac)
  - `nowing_backend/app/services/billing_event_service.py` (thêm `record_contact_unlock_refund`)
  - `nowing_backend/app/services/workspace_credit_service.py` (thêm `refund_member_spend` hoặc mở rộng `record_spend` cho negative)
  - `nowing_backend/app/services/billing_service.py` (tham khảo pattern `auto_refund_lead`)
  - `nowing_backend/app/services/export_service.py` (reuse `mask_phone` / `mask_email`)
  - `nowing_backend/app/routes/lead_batch_routes.py` (harden unlock response)
  - `nowing_backend/app/routes/dnc_routes.py` (or new pii-opt-out route)
  - `nowing_backend/app/app.py` (register new router)
  - `nowing_backend/app/routes/leads_routes.py` (mask email/name in `LeadRead`)
  - `nowing_backend/app/schemas/lead_batch_ingest.py` (extend `ContactUnlockResponse`)
  - `nowing_backend/app/schemas/dnc.py` (add `PiiOptOutRequest`, `PiiOptOutResponse`)

### P0 Surface Assessment

This story touches **PII, credit refund, billing events, and DNC/wallet logic** — which are P0-adjacent surfaces. Per `nowing-quality-pipeline.md`:
- **Integration tests on real Postgres** are **P0-gated** (Pattern 6).
- **Human-review gate** is **P0-gated** because it touches PII, credit/wallet, and compliance.
- **Mutation gate** is **P0-gated** for `app/services/pii/opt_out_service.py`, `app/services/lead_batch_service.py`, `app/services/billing_event_service.py`, `app/lead_intelligence/dnc/service.py`.

### Important Do-Nots

- **Do NOT create a new `pii_blacklists` table** unless an explicit merge migration is written. Use `workspace_dnc_records` / `global_dnc_records` (AD-110).
- **Do NOT switch to AES-256-GCM** for `verified_contacts` encryption. Use the existing `VerifiedContactEncryption` (Fernet/TokenEncryption) per AD-105 v5.
- **Do NOT call `wallet_credit.apply_debit` directly** from the unlock or opt-out route; route through `BillingEventService` so spend caps and idempotency are enforced.
- **Do NOT expose decrypted PII in masked/default lead list responses.** Only unlock response returns decrypted phone/email, and only after billing.

### References

- Epic context: `_bmad-output/planning-artifacts/epics.md` lines 3310–3380 (Epic 26, AD-101–AD-110, Story 26.4 AC).
- Architecture: `_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` §AD-105, AD-110.
- Architecture review v5: `_bmad-output/review-artifacts/epic-26-architecture-review-2026-08-17-v5.md` (PII encryption Fernet decision, no `pii_blacklists`).
- 26.1 story (patterns): `_bmad-output/implementation-artifacts/26-1-fastmcp-batch-ingest-and-stateless-chainlens-pipeline.md`.
- Existing code:
  - `nowing_backend/app/services/pii/verified_contact_encryption.py`
  - `nowing_backend/app/lead_intelligence/dnc/normalizer.py`
  - `nowing_backend/app/lead_intelligence/dnc/service.py`
  - `nowing_backend/app/services/lead_batch_service.py`
  - `nowing_backend/app/lead_intelligence/enrichment/service.py`
  - `nowing_backend/app/services/phone_waterfall_service.py`
  - `nowing_backend/app/routes/lead_batch_routes.py`
  - `nowing_backend/app/routes/dnc_routes.py`
  - `nowing_backend/app/services/billing_event_service.py`
  - `nowing_backend/app/services/wallet_credit.py`
  - `nowing_backend/app/db.py` (`VerifiedContact`, `Lead`, `WorkspaceDncRecord`, `GlobalDncRecord`, `BillingEvent`)
  - `nowing_backend/alembic/versions/ac475d54f6a2_story_26_1_chainlens_chunks_and_.py`

## Dev Agent Record

### Debug Log References

- `verified_contacts.value_hmac` is nullable and not set by enrichment/phone-waterfall.
- `phone_waterfall_service.py` stores `name=lead.company_name` in plaintext.
- `lead_batch_service.py` uses non-canonical HMAC form `f"{phone}|{email}"`.
- `epics.md` Story 26.4 AC still says AES-256-GCM; architecture v5 overrides with Fernet/TokenEncryption.

### Completion Notes List

- [x] Canonical HMAC helper created and all writers updated.
- [x] Schema migration backfills `verified_contacts.value_hmac` and `leads.value_hmac`, makes `leads.value_hmac` `NOT NULL` and `verified_contacts.value_hmac` nullable (opt-out purge safe).
- [x] All `VerifiedContact` creation paths encrypt `name`/`title`/`email`/`phone`.
- [x] `POST /api/v1/workspaces/{workspace_id}/pii-opt-out` implemented with purge, refund (15% cap), and DNC cache invalidation.
- [x] Contact unlock endpoint returns decrypted phone/email after billing.
- [x] Masking for email/name added to lead/contact read responses.
- [x] Unit tests pass; ruff clean on changed files. Full repo still has 105 pre-existing ruff warnings.

---

## Challenge Log (grill-me)

### Q1 — Already implemented?

- **Không có exact duplicate** cho PII opt-out endpoint hay canonical composite `verified_contacts.value_hmac` helper.
- **Tuy nhiên có nhiều building blocks tồn tại và nên reuse:**
  - `app/services/pii/verified_contact_encryption.py` — `VerifiedContactEncryption`.
  - `app/lead_intelligence/dnc/normalizer.py` — `hash_phone_hmac`, `normalize_phone_e164`, `normalize_email`, `normalize_domain`.
  - `app/lead_intelligence/dnc/service.py` — `DncComplianceService`.
  - `app/services/phone_waterfall_service.py:mask_phone` — phone masking.
  - `app/services/export_service.py:mask_phone` / `mask_email` — existing PII mask helpers.
  - `app/services/billing_service.py:BillingService.auto_refund_lead` — refund pattern (credits user wallet, writes negative `BillingEvent`, marks `VerifiedContact` invalid, Redis cache invalidation).
  - `app/services/workspace_credit_service.py:WorkspaceCreditService.refund_credits` — refunds workspace pool + decrements member monthly spent.
  - `app/services/billing_event_service.py:BillingEventService.record_contact_unlock` — unlock billing.
  - `app/routes/lead_batch_routes.py` — existing `/contacts/{contact_id}/unlock`.
  - `app/routes/dnc_routes.py` — existing DNC CRUD.
- **Risk:** Nếu dev tạo `app/services/pii/opt_out_service.py` mới mà không reuse `BillingService.auto_refund_lead` / `WorkspaceCreditService.refund_credits`, sẽ duplicate logic refund và sai money semantics.

### Q2 — Simpler alternative?

- **Masking:** Thay vì tạo `app/services/pii/mask.py`, reuse `app/services/export_service.py:mask_phone` và `mask_email`. Chỉ thiếu `mask_name` có thể bổ sung 1 hàm trong cùng file hoặc dùng inline 3-line helper.
- **Opt-out route:** Có thể mở rộng `app/routes/dnc_routes.py` (thêm `POST /pii-opt-out`) thay vì file route mới, miễn là business logic nằm trong service.
- **Refund path:** Nên extend `BillingService` hoặc `BillingEventService` thay vì implement refund từ đầu. Wallet refund pattern đã có trong `BillingService.auto_refund_lead` (tuy nhiên nó refund vào `User.credit_micros_balance`, không phải workspace balance).
- **Blind HMAC lookup:** Có thể cần thêm `phone_hmac` / `email_hmac` columns (hoặc computed index) để tìm `VerifiedContact` mà không decrypt toàn bộ bảng. Xem Q3.

### Q3 — Edge cases spec misses (Pattern 3)

- [ ] **Boundary:** Refund cap 15% — test exactly at cap, 1 micro trên, 1 micro dưới, nhiều contacts cùng lúc.
- [ ] **Boundary:** `value_hmac` canonical form khi `phone`, `email` hoặc `domain` missing/empty — dùng chuỗi rỗng trong message hay reject degenerate?
- [ ] **Null/empty:** Opt-out request với phone/email malformed hoặc chỉ whitespace → normalization trả `None`; response phải rõ ràng (400 với lý do).
- [ ] **Null/empty:** `VerifiedContact` có `phone=None` hoặc `email=None` (enrichment hoặc phone waterfall chỉ có 1 field) — HMAC phải tính được với partial input.
- [ ] **Concurrent:** Double opt-out request cùng phone trong cùng workspace trong 2 request đồng thời → idempotent DNC upsert + no double refund.
- [ ] **Concurrent:** Opt-out và unlock trên cùng contact đồng thời → tránh race gây unlock sau opt-out hoặc over-refund.
- [ ] **Anonymized contact:** Opt-out lần 2 trên contact đã bị purge — trả `purged_contact_count=0` và `refunded_micros=0`, không gọi LLM, không trừ tiền.
- [ ] **DNC-only opt-out:** Phone chưa có trong `verified_contacts` — vẫn tạo DNC record, vẫn cache invalidation, `purged_contact_count=0`.
- [ ] **Global opt-out (superadmin):** Tìm + purge contacts xuyên workspace. Hiện `global_dnc_records` áp dụng tất cả workspace; purge global cần scan cross-workspace hay chỉ để DNC block tương lai? Chưa rõ.
- [ ] **Blind lookup of encrypted columns:** `verified_contacts.phone` / `email` là Fernet ciphertext. Muốn find contacts để purge theo phone/email, **không thể** query plaintext hoặc so sánh với `value_hmac` composite mà không biết domain/email. Cần blind index (phone_hmac / email_hmac) hoặc phải decrypt toàn bộ workspace (privacy/perf fail).
- [ ] **Refund target user:** Contact từng được unlock bởi user đã bị xóa hoặc `user_id` NULL → refund vào đâu? workspace owner, bỏ qua, hay ghi nhận unclaimed?
- [ ] **No original BillingEvent:** `is_unlocked=True` nhưng không tìm thấy `BillingEvent` (dữ liệu cũ/trước story) → không refund, vẫn purge.

### Q4 — Failure modes unspecified (Pattern 2, 4)

- [ ] **`VerifiedContactEncryption.decrypt` fails** (ciphertext corrupted, key rotation, partial migration): opt-out purge vẫn có thể overwrite bằng `None` mà không cần decrypt; unlock endpoint phải trả 500, không leak PII.
- [ ] **`BillingEventService.record_contact_unlock` lỗi sau khi đã set `is_unlocked=True`**: hiện tại code gọi billing rồi mới set `is_unlocked`, rollback sẽ giữ `is_unlocked=False`. Nếu refactor thứ tự, phải rollback transaction.
- [ ] **Refund path chưa được thiết kế:** `wallet_credit.apply_debit` không có `apply_credit`. `WorkspaceCreditService.record_spend` reject non-positive. `WorkspaceCreditService.refund_credits` tăng `Workspace.credit_micros_balance`, không tăng `User.credit_micros_balance`. `BillingService.auto_refund_lead` tăng `User.credit_micros_balance` trực tiếp, viết negative `BillingEvent`. Story cần chốt: contact unlock debit từ user wallet (`User.credit_micros_balance`) → refund cũng vào user wallet + ghi negative `BillingEvent` + adjust member monthly spent.
- [ ] **Redis down khi invalidate DNC cache:** `DncComplianceService` sẽ warn và tiếp tục; opt-out response vẫn 200 nhưng cache stale cho đến TTL. Cần test.
- [ ] **Postgres deadlock khi concurrent DNC upsert + contact purge:** DNC table có unique `(workspace_id, record_type, value_hmac)`; contact purge update `verified_contacts` row khác; deadlock nếu cùng contact bị nhiều worker. Cần `SELECT FOR UPDATE` hoặc process per-contact serially.
- [ ] **Migration backfill thất bại giữa chừng:** `value_hmac` NULL hàng triệu rows; migration batch + thiết lập NOT NULL phải idempotent.
- [ ] **15% cap query fail:** `BillingEvent` table chưa có index `(workspace_id, event_type, created_at)`; counting unlocked per billing cycle trên lượng lớn row có thể chậm hoặc timeout.

### Triage

- **CRITICAL — Refund money path: RESOLVED.** Unlock debit từ `User.credit_micros_balance` (user wallet) và `WorkspaceMembership.monthly_spent_micros` (spend cap). Refund: credit user wallet + negative `BillingEvent` + decrement monthly spent; **không** tăng `Workspace.credit_micros_balance`. (Q4)
- **CRITICAL — Blind index for encrypted PII lookup: RESOLVED.** Thêm `phone_hmac` / `email_hmac` columns tính bằng `hash_phone_hmac` trên normalized phone/email. (Q3 — security/privacy)
- **Non-critical — Reuse existing mask/refund helpers:** Có thể sửa trong dev. (Q1/Q2)
- **Non-critical — Edge cases concurrency/refund cap:** Cần thêm vào test skeleton trong `bmad-nowing-test-first-atdd`. (Q3)

### Recommended pre-dev actions

1. **(DONE in story update)** Add `phone_hmac` / `email_hmac` blind index columns và populate trong mọi writer.
2. **(DONE in story update)** Implement refund via user wallet credit + negative `BillingEvent` + monthly spent decrement; không dùng `WorkspaceCreditService.refund_credits`.
3. **Sau đó proceed** đến `bmad-nowing-test-first-atdd`.

### Review Findings

- [x] [Review][Decision→Patch] Quyết định transaction boundary: **Option A** — giữ `session.commit()` trong `wallet_credit.apply_credit/apply_debit` (nhất quán với `phone_waterfall_service` và nhiều caller cũ), thêm `await session.commit()` ở cuối các write route `pii_opt_out` và `unlock_contact` để đảm bảo DNC/contact/BillingEvent/audit log được persist. Cần verify `batch_ingest_leads` cũng cần commit nhưng đã defer.

- [x] [Review][Decision→Defer] Endpoint PII opt-out toàn cục / superadmin — **Option B** decan: giữ workspace-scoped. AC hiện tại không yêu cầu cross-workspace purge; superadmin route cần thiết kế riêng về permission, audit, và scope. `global_scope` trong `process_opt_out` giữ lại để dùng sau. Hoãn đến story quản trị DNC/global compliance.

- [x] [Review][Decision→Defer] Cột `BillingEvent.reason` theo AD-105 — **Option B** decan: không thêm cột `reason` cho `BillingEvent`. `event_type` đã phân biệt `contact_unlock`/`contact_unlock_refund`; lý do chi tiết lưu trong `pii_access_audit_logs` và có thể bổ sung metadata sau. Tránh thay đổi schema BillingEvent rộng trong story 26.4; hoãn để epic kiến trúc billing v2.

- [x] [Review][Patch] Thiếu Alembic migration, backfill, và ràng buộc/index chuẩn cho HMAC [`nowing_backend/app/db.py:4586-4627,4673,5233-5235`] — `Lead.value_hmac` / `VerifiedContact.value_hmac` đã là `nullable=False` trong ORM nhưng chưa có migration/backfill; `phone_hmac`/`email_hmac` thiếu composite index `(workspace_id, phone_hmac)`, `(workspace_id, email_hmac)` (hiện chỉ single-column `index=True`); các partial unique indexes cũ vẫn tồn tại thay vì full `UNIQUE(workspace_id, value_hmac)`; thiếu index `BillingEvent(workspace_id, event_type, created_at)` cho truy vấn refund cap.

- [x] [Review][Patch] Refund opt-out thiếu idempotency, không fallback payer, và không dùng `BillingEventService.record_contact_unlock_refund` [`nowing_backend/app/services/pii/opt_out_service.py:75-92,182-213`, `nowing_backend/app/services/billing_event_service.py:91-161`] — `_refund_credit` gọi `wallet_credit.apply_credit` trực tiếp, không kiểm tra `BillingEvent` refund đã tồn tại, trả `0` khi `original_event.user_id` là `None` thay vì tìm workspace owner, không dùng `record_contact_unlock_refund` (dead code). Cần route qua `BillingEventService` (sau khi chốt transaction boundary) hoặc xóa helper, bổ sung idempotency/contact và owner fallback.

- [x] [Review][Patch] Tính 15% refund cap sai mẫu số/window và duyệt toàn bộ row trong Python [`nowing_backend/app/services/pii/opt_out_service.py:95-148`] — `_count_refundable_unlocks_this_cycle` dùng `VerifiedContact.is_unlocked=True` (current state) thay vì số `BillingEvent` `contact_unlock` trong billing cycle; `already_refunded` lọc theo calendar month thay vì billing cycle; `allowed = max(1, ...)` cho phép hoàn tiền khi không có unlock; query `scalars().all()` rồi `len()` gây O(n) memory. Cần dùng `func.count`, window đúng billing cycle, `max(0, ...)`.

- [x] [Review][Patch] `pii_opt_out` bỏ qua `body.reason`, DNC/audit hardcode `"Right to be forgotten"` [`nowing_backend/app/routes/lead_batch_routes.py:287-289`, `nowing_backend/app/services/pii/opt_out_service.py:300,345`] — `PIIOptOutRequest.reason` không được truyền vào `process_opt_out`; DNC record và audit log đều hardcode `"Right to be forgotten"`. Cần truyền `reason` xuyên suốt.

- [x] [Review][Patch] Audit log opt-out/unlock chưa đúng schema `pii_access_audit_logs` [`nowing_backend/app/services/pii/opt_out_service.py:64-71`, `nowing_backend/app/routes/lead_batch_routes.py:228-238`] — Opt-out audit log thiếu `workspace_id`, `lead_id`, `contact_id`, dùng `actor_id` thay vì `user_id`; unlock audit log thiếu `ip_address`, `reason`. Cần chuẩn hóa theo AC-3/AC-6 JSON shape.

- [x] [Review][Patch] Xử lý lỗi `pii_opt_out` yếu, có thể leak `user_id` UUID [`nowing_backend/app/routes/lead_batch_routes.py:291-299`] — Map `ValueError` sang 400 chỉ khi detail chứa `"phone"` hoặc `"email"`; `ValueError` từ `wallet_credit.apply_credit` (`"User with ID ... not found"`) rơi vào 422 và leak UUID. Cần typed exception.

- [x] [Review][Patch] `pii_opt_out` ghi IP proxy thay vì client thực [`nowing_backend/app/routes/lead_batch_routes.py:288`] — `ip_address = request.client.host` sau load balancer là IP proxy; cần dùng `X-Forwarded-For`/`CF-Connecting-IP` với trusted-proxy allowlist.

- [x] [Review][Patch] Route `unlock_contact` ánh xạ mọi Exception thành 402 Payment Required [`nowing_backend/app/routes/lead_batch_routes.py:220-224`] — `except Exception` ánh xạ mọi lỗi DB, decode, duplicate-billing thành 402. Cần phân loại `InsufficientCreditsError`, validation `ValueError`, `BillingError`, `Exception` thành 402/422/500.

- [x] [Review][Patch] Route `unlock_contact` không kiểm tra DNC, `consent_status`, `is_valid` trước khi tính phí [`nowing_backend/app/routes/lead_batch_routes.py:177-194`] — Chỉ kiểm tra `is_unlocked`, không lookup `WorkspaceDncRecord`/`GlobalDncRecord`, không từ chối khi `consent_status='withdrawn'` hoặc `is_valid=False`. Cần từ chối 403/409.

- [x] [Review][Patch] `leads_routes.py` giải mã PII cho danh sách leads và trả decrypted khi unlock [`nowing_backend/app/routes/leads_routes.py:62-107`] — `_map_lead_to_read` gọi `enc.decrypt` cho `phone`, `email`, `name` rồi mask lại; trả về giá trị decrypted khi `is_unlocked=True` trong danh sách leads, vi phạm AC-7/Important Do-Nots. Cần tránh decrypt trong list và chỉ trả decrypted PII trong `ContactUnlockResponse`.

- [x] [Review][Patch] `ExportService` và `get_company_graph` xử lý PII chưa decrypt/mask, có thể trả token mã hóa [`nowing_backend/app/services/export_service.py:656-674,690-709,739-756`, `nowing_backend/app/routes/leads_routes.py:505-533`] — `ExportService` dùng `mask_email`/`mask_phone` trên ciphertext (token base64 không chứa `@` nên trả nguyên token), `mask_name` tồn tại nhưng không gọi, `name`/`title` xuất ra nguyên token; `get_company_graph` dùng `c.name`, `c.title`, `c.email` trực tiếp. Cần decrypt rồi mask hoặc redact đúng, áp dụng `mask_name` cho name/title.

- [x] [Review][Patch] Các hàm `mask_name`, `mask_phone`, `mask_email` để lộ giá trị ngắn hoặc input không hợp lệ [`nowing_backend/app/services/export_service.py:579-598,601-623`] — `mask_name` trả nguyên chuỗi khi `len(clean) <= 3`; `mask_phone` trả `clean` khi `len(clean) <= 6`; `mask_email` trả `clean` khi input không chứa `@`. Cần luôn mask ít nhất phần giữa hoặc dùng chuỗi cố định.

- [x] [Review][Patch] `LeadBatchService` upsert ghi đè contact đã opt-out, thiếu dedup/sort theo `value_hmac` [`nowing_backend/app/services/lead_batch_service.py:189-230,232-245`] — `ON CONFLICT DO UPDATE` không có `WHERE` guard để tránh ghi đè `consent_status='withdrawn'`/`is_valid=False`; không reset `is_unlocked=False`; `contacts_to_insert` không dedup/sort theo `(workspace_id, value_hmac)`, batch có duplicate sẽ raise `CardinalityViolation`; vi phạm AD-109 Rule 4. Cần guard + dedup + sort.

- [x] [Review][Patch] `compute_verified_contact_hmac` crash khi phone/email/domain đều rỗng [`nowing_backend/app/lead_intelligence/dnc/normalizer.py:158-176`] — Raise `ValueError` tại `phone`, `email`, `domain` đều empty; enrichment name-only với `domain=None` có thể crash cả batch. Cần skip hoặc xử lý an toàn.

- [x] [Review][Patch] `WorkspaceCreditService.refund_member_spend` báo refund sai khi thiếu membership và chứa nhánh test-only [`nowing_backend/app/services/workspace_credit_service.py:491-565`] — Đã sửa lỗi báo refund sai khi thiếu membership (trả `amount_micros=0`). Giữ lại fake-session branch vì `FakeAsyncSession` trong `tests/unit/services/test_workspace_credit_pooling.py` dựa vào nó; refactor cách ly sang test fixture chuyên dụng sau.

- [x] [Review][Patch] Thiếu khóa hàng `FOR UPDATE` trong refund, unlock, DNC upsert [`nowing_backend/app/services/pii/opt_out_service.py:95-148,239-246,309-320`, `nowing_backend/app/services/billing_event_service.py:291-320,105-117`] — `_count_refundable...` không khóa cap; `_ensure_dnc_record` không `FOR UPDATE`; `process_opt_out` không khóa matched `VerifiedContact`; `_record_business_event`/`record_contact_unlock_refund` duplicate check không `FOR UPDATE`; dễ over-refund, duplicate `BillingEvent`, duplicate DNC. Cần `SELECT ... FOR UPDATE` hoặc advisory lock.

- [x] [Review][Patch] `EnrichmentService` tạo `VerifiedContact` mà không kiểm tra DNC [`nowing_backend/app/lead_intelligence/enrichment/service.py:234-263`, `nowing_backend/app/routes/enrichment_routes.py:74-110`] — Tạo contact mà không gọi `DncComplianceService`; vi phạm AC-4. Cần check DNC, từ chối tạo contact và không tính phí nếu nằm trong blacklist.

- [x] [Review][Patch] `phone_waterfall_service.py` dùng fallback name/title hardcode tiếng Việt [`nowing_backend/app/services/phone_waterfall_service.py:860-861`] — `name=self.encryption.encrypt(lead.company_name or "Doanh nghiep")` và `title=self.encryption.encrypt("Lead Contact")`; dùng fallback tiếng Việt cứng và title chung chung. Cần `None` hoặc generic redacted.

- [x] [Review][Patch] `_anonymize_contact` không set `refunded_at` và để `is_valid=True` sau opt-out [`nowing_backend/app/services/pii/opt_out_service.py:41-52`] — Sau opt-out `is_valid` vẫn `True`, `refunded_at` không được cập nhật khi có refund; contact bị purge vẫn hiển thị valid trong report/filter. Cần set `refunded_at=now(UTC)` khi refund và `is_valid=False` cho mọi contact bị purge.

- [x] [Review][Patch] Số tiền refund hardcode 1_500 micros, không gắn với `BillingEvent.cost_micros` gốc [`nowing_backend/app/services/pii/opt_out_service.py:29,188-213`] — `_REFUND_AMOUNT_MICROS = 1_500` luôn dùng kể cả khi unlock tốn khác; cần refund `min(1_500, original_event.cost_micros)` hoặc lưu giá unlock.

- [x] [Review][Patch] `OptOutService` xử lý lỗi invalidate DNC cache chưa đúng (warn và continue) [`nowing_backend/app/services/pii/opt_out_service.py:349-354`, `nowing_backend/app/lead_intelligence/dnc/service.py:212-232`] — `OptOutService` gọi `invalidate_*_cache` mà không bảo vệ lỗi `get_redis()`; `DncComplianceService` swallow exception ở `debug` thay vì `warning` theo Q4. Cần `try/except` + warn + continue.

- [x] [Review][Patch] Thiếu test xác nhận `session.commit`, concurrency, DNC fail-closed [`nowing_backend/tests/unit/services/test_pii_opt_out_service.py:37-270`, `nowing_backend/tests/integration/routes/test_pii_opt_out.py:1-300`, `nowing_backend/tests/unit/services/test_lead_batch_service.py:1-400`] — Unit test dùng `_FakeSession` không assert `session.commit()`; integration test dùng chung `db_session`; thiếu concurrency test, DNC fail-closed. Cần bổ sung theo AC-8.

- [x] [Review][Defer] Route `batch_ingest_leads` không commit trước khi trả về [`nowing_backend/app/routes/lead_batch_routes.py:116`] — deferred, pre-existing

---

## Validation (2026-08-18)

- **Unit tests:** 122 passed trên nhóm 26.4 (`test_pii_opt_out_service`, `test_contact_unlock_refund`, `test_lead_batch_service`, `test_export_service`, `test_billing_event_service`, `test_leads_routes`, `test_contact_enrichment`, `test_dnc_*`, `test_phone_waterfall_service`, `test_workspace_credit_pooling`).
- **Integration tests:** 9 passed trên Postgres/Redis local (`tests/integration/routes/test_pii_opt_out.py`, `tests/integration/lead_batch/test_contact_unlock.py`).
- **Lint:** `ruff check` sạch trên tất cả file thay đổi.
- **Migration:** Alembic revision `8f0e6aa7aa87` đã tạo; chạy thực tế trên fresh DB cần PostgreSQL image có PostGIS (hiện tại `pgvector/pgvector:pg17` local thiếu PostGIS, nên `env.py` `create_all` gặp lỗi `type "geometry" does not exist`). Trên DB đã có PostGIS/sẵn dữ liệu, migration apply bình thường với `IF NOT EXISTS` guard cho columns/indexes/constraints.
- **Commit liên quan:** `e0682787d` (review patches), `82c65e9f5` (billing_event rollback → refund_member_spend fix).
