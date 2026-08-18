diff --git a/_bmad-output/implementation-artifacts/26-4-pii-vault-hmac-deduplication-decree-13-opt-out.md b/_bmad-output/implementation-artifacts/26-4-pii-vault-hmac-deduplication-decree-13-opt-out.md
new file mode 100644
index 000000000..149f07650
--- /dev/null
+++ b/_bmad-output/implementation-artifacts/26-4-pii-vault-hmac-deduplication-decree-13-opt-out.md
@@ -0,0 +1,410 @@
+---
+story_key: "26-4"
+epic: "epic-26"
+story: "26.4"
+title: "PII Vault, HMAC Deduplication & Decree 13 Opt-Out"
+status: "review"
+baseline_commit: "876947901"
+---
+
+# Story 26.4: PII Vault, HMAC Deduplication & Decree 13 Opt-Out
+
+## ⚠️ CRITICAL CORRECTIONS / BLOCKERS — Resolve Before Dev
+
+1. **PII Encryption Method: Fernet/TokenEncryption is canonical, NOT AES-256-GCM.**
+   - Architecture Spine v5 (`_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` §AD-105, Rule 1) and the 2026-08-17 architecture review v5 explicitly decided: canonical at-rest encryption for `verified_contacts` is the existing `VerifiedContactEncryption` (Fernet/TokenEncryption).
+   - **AES-256-GCM is DEFERRED.** Do NOT introduce a new AES-256-GCM cipher or replace the `verified_contacts` columns with `phone_encrypted` / `email_encrypted` separate columns. If a future AD amendment requires AES-GCM, it must come with a decrypt/re-encrypt migration plan.
+   - `epics.md` Story 26.4 AC text still says `phone_encrypted` / `email_encrypted` via AES-256-GCM — this is **out-of-date** and must be treated as the architecture decision overriding it.
+
+2. **HMAC Form Inconsistency Across Codebase.**
+   - `app/services/lead_batch_service.py` computes `verified_contacts.value_hmac` as `hash_phone_hmac(f"{norm_phone}|{norm_email}", config.SECRET_KEY)`.
+   - `app/lead_intelligence/enrichment/service.py` and `app/services/phone_waterfall_service.py` do NOT set `value_hmac` at all.
+   - `app/lead_intelligence/services/deduplication_service.py` has a separate `compute_phone_hmac(..., secret="nowing_default_lead_secret")` default.
+   - **Canonical per AD-105 Rule 2:** `HMAC_SHA256("phone=<normalized_phone>|email=<normalized_email>|domain=<domain>", config.SECRET_KEY)`. This story must create ONE canonical helper, backfill all existing rows, and migrate all writers.
+
+3. **`verified_contacts.value_hmac` and `leads.value_hmac` are still nullable.**
+   - `alembic/versions/ac475d54f6a2_story_26_1_chainlens_chunks_and_.py` added `verified_contacts.value_hmac` as `nullable=True` with a partial unique index.
+   - `app/db.py` `Lead.value_hmac` is `nullable=True`.
+   - AD-105 and AD-109 require both to be `NOT NULL` with a full `UNIQUE(workspace_id, value_hmac)` constraint. Migration must backfill before `ALTER COLUMN ... NOT NULL`.
+
+4. **No PII Opt-Out / Right-to-be-Forgotten endpoint yet.**
+   - `app/routes/dnc_routes.py` supports `POST /workspaces/{workspace_id}/dnc` for DNC list management, but it does NOT perform retroactive purge of `verified_contacts`, credit refund, or schedule irreversible PII deletion.
+   - AD-110 Rule 3 requires `POST /api/v1/workspaces/{workspace_id}/pii-opt-out` with 24h SLA, credit refund, and PII deletion/anonymization.
+
+5. **Contact Unlock endpoint exists but does not return decrypted PII.**
+   - `app/routes/lead_batch_routes.py` has `POST .../contacts/{contact_id}/unlock` and uses `BillingEventService.record_contact_unlock`.
+   - It currently only flips `is_unlocked=True` and appends an audit log. It does not decrypt phone/email or return them. Per AD-105 Rule 4, the endpoint should decrypt PII after successful billing and return it securely (e.g., in `ContactUnlockResponse`).
+
+## ✅ Resolved Design Decisions (post grill-me)
+
+### D1 — Blind index for encrypted PII lookup
+- Thêm `phone_hmac` và `email_hmac` blind-index columns vào `verified_contacts`.
+- `phone_hmac = hash_phone_hmac(normalize_phone_e164(phone), config.SECRET_KEY)`.
+- `email_hmac = hash_phone_hmac(normalize_email(email), config.SECRET_KEY)`.
+- Blind indexes cho phép opt-out tìm và purge contacts theo phone/email mà không cần decrypt toàn bộ workspace. Cùng hash function và secret được dùng trong `workspace_dnc_records` / `global_dnc_records` để lookup khớp.
+- Composite `value_hmac` vẫn dùng cho dedup: `HMAC_SHA256("phone=<p>|email=<e>|domain=<d>", config.SECRET_KEY)`.
+
+### D2 — Refund contract for contact unlock
+- Contact unlock debit từ **user wallet** (`User.credit_micros_balance`) qua `wallet_credit.apply_debit`, và tăng **member monthly spent** qua `WorkspaceCreditService.record_spend` (spend cap tracking), **không** trừ `Workspace.credit_micros_balance`.
+- Refund opt-out:
+  1. Tìm original `BillingEvent` (`event_type='contact_unlock'`, `event_entity_type='verified_contact'`, `event_id=contact.id`) để lấy `payer_user_id`.
+  2. Kiểm tra 15% refund cap theo billing cycle/workspace.
+  3. Credit `User.credit_micros_balance += 1_500` (payer từ BillingEvent hoặc workspace owner nếu payer missing).
+  4. Giảm `WorkspaceMembership.monthly_spent_micros` tương ứng (thêm `WorkspaceCreditService.refund_member_spend` hoặc mở rộng `record_spend` cho negative amount với reason).
+  5. Viết `BillingEvent` mới với `event_type='contact_unlock_refund'`, `cost_micros=-1_500`, `cost_basis='actual'`.
+  6. Idempotent: nếu đã tồn tại `BillingEvent` refund cho contact, return existing.
+
+---
+
+## Story
+
+As a Nowing platform engineer and compliance operator,
+I want all verified contact PII encrypted at rest with a canonical blind HMAC, an auditable contact-unlock flow, and a Decree 13 Right-to-be-Forgotten opt-out workflow,
+So that Nowing meets PDPD Decree 13/2023/ND-CP, avoids PII leakage, deduplicates contacts safely, and can honor data-subject opt-out requests within 24 hours.
+
+---
+
+## Acceptance Criteria
+
+### AC-1 — All PII encrypted at rest in `verified_contacts`
+**Given** any writer creates or updates a `VerifiedContact`,  
+**When** persisted,  
+**Then** `name`, `title`, `email`, and `phone` are encrypted using the canonical `VerifiedContactEncryption` (Fernet/TokenEncryption in `app/services/pii/verified_contact_encryption.py`) before storage; no plaintext PII is written to `verified_contacts`.
+
+- Fix `app/services/phone_waterfall_service.py` which currently stores `name=lead.company_name` in plaintext.
+- Fix `app/lead_intelligence/enrichment/service.py` which already encrypts but does not set `value_hmac`.
+- Fix `app/services/lead_batch_service.py` if it stores any unencrypted `name` / `title`.
+
+### AC-2 — Canonical HMAC-SHA256 deduplication form
+**Given** a verified contact with phone, email, and lead domain,  
+**When** `value_hmac` is computed,  
+**Then** it uses the canonical form:
+```
+HMAC_SHA256(
+  "phone=<normalized_phone>|email=<normalized_email>|domain=<domain>",
+  config.SECRET_KEY
+)
+```
+- Normalization reuses `app/lead_intelligence/dnc/normalizer.py`: `normalize_phone_e164`, `normalize_email`, `normalize_domain`.
+- The helper lives in a single location (e.g., `app/lead_intelligence/dnc/normalizer.py` or `app/services/pii/hmac.py`).
+- All three writers (`lead_batch_service.py`, `enrichment/service.py`, `phone_waterfall_service.py`) are updated to call this helper.
+- `verified_contacts.value_hmac` becomes `NOT NULL` with a full `UNIQUE(workspace_id, value_hmac)` constraint after backfill.
+- `verified_contacts.phone_hmac` / `email_hmac` are populated using `hash_phone_hmac` on normalized phone/email (blind indexes for opt-out lookup and DNC matching).
+- `leads.value_hmac` becomes `NOT NULL` with a full `UNIQUE(workspace_id, value_hmac)` constraint after backfill.
+
+### AC-3 — Decree 13 PII Opt-Out endpoint
+**Given** a data subject (phone/email) or workspace admin requests Right-to-be-Forgotten,  
+**When** `POST /api/v1/workspaces/{workspace_id}/pii-opt-out` is called with `{ "record_type": "phone"|"email", "value": "...", "reason": "..." }`,  
+**Then** the backend:
+1. Normalizes the value and computes HMAC using the canonical helper.
+2. Inserts/upserts a `workspace_dnc_records` row (or `global_dnc_records` if superadmin/global scope) with `source='opt_out'` and `reason='Right to be forgotten'`.
+3. Finds all `verified_contacts` in the workspace (or globally for superadmin) whose `phone_hmac` or `email_hmac` (blind index) matches the opt-out HMAC.
+4. For each matched contact:
+   - Sets `is_unlocked = FALSE`.
+   - Overwrites `name`, `title`, `email`, `phone` with `None` (irreversible deletion) or an anonymized token (e.g., `__ANONYMIZED__` HMAC) per legal review.
+   - Sets `consent = FALSE`, `consent_status = 'withdrawn'`, `legal_basis = 'opt_out'`.
+   - Appends to `pii_access_audit_logs` with `access_type='opt_out_purged'`, `actor_id`, `timestamp`, `ip_address`, `reason`.
+5. Refunds 1,500 micros per contact that had `is_unlocked = TRUE` and a corresponding `BillingEvent` with `event_type='contact_unlock'`, capped at 15% of total unlocked leads in the current billing cycle per workspace (AD-110 Rule 4):
+   - Tìm payer từ original `BillingEvent.user_id`.
+   - Credit `User.credit_micros_balance += 1_500`.
+   - Giảm `WorkspaceMembership.monthly_spent_micros` tương ứng (không tăng `Workspace.credit_micros_balance`).
+   - Viết `BillingEvent` với `event_type='contact_unlock_refund'`, `cost_micros=-1_500`.
+   - Idempotent: nếu refund đã tồn tại, không tính phí lại.
+6. Invalidates the DNC Redis cache for the workspace/global scope.
+7. Returns `PiiOptOutResponse` with `purged_contact_count`, `refunded_micros`, and `dnc_record_id`.
+
+### AC-4 — PII Opt-Out SLA and retroactive propagation
+**Given** a successful PII opt-out,  
+**When** future scrapers, batch ingest, phone waterfall, or enrichment processes encounter the same phone/email/domain,  
+**Then** `DncComplianceService` fail-closed blocks the record, no new `VerifiedContact` is created, and no credit is charged for it.
+
+### AC-5 — Hardened Contact Unlock and billing
+**Given** a workspace member with permission `LEADS_WRITE` and sufficient wallet balance,  
+**When** `POST /api/v1/workspaces/{workspace_id}/leads/{lead_id}/contacts/{contact_id}/unlock` is called,  
+**Then**:
+1. If `is_unlocked` is already `TRUE`, return `ContactUnlockResponse` with decrypted `phone` and `email` (idempotent, `cost_micros=0`).
+2. If `is_unlocked` is `FALSE`:
+   - `BillingEventService.record_contact_unlock(..., cost_micros=1_500)` checks `User.credit_micros_balance` (user wallet), records spend cap via `WorkspaceCreditService.record_spend`, debits `wallet_credit.apply_debit` (user wallet), và writes `BillingEvent` với `event_type='contact_unlock'`, `event_entity_type='verified_contact'`, `cost_basis='actual'`.
+   - On success: decrypt `phone`/`email`, set `is_unlocked=TRUE`, append audit log, and return `phone`, `email`, `cost_micros=1500`.
+   - On failure (insufficient credits, billing error, decryption error): return `402 Payment Required` or `500` and do NOT leak decrypted PII; `is_unlocked` stays `FALSE`.
+
+### AC-6 — Schema migration and backfill
+**Given** the existing `verified_contacts` and `leads` tables,  
+**When** the Alembic migration runs,  
+**Then**:
+1. It adds nullable `phone_hmac` and `email_hmac` blind-index columns to `verified_contacts`.
+2. It backfills `verified_contacts.value_hmac` for all rows using the canonical helper (phone, email, lead domain) before applying `NOT NULL`.
+3. It backfills `verified_contacts.phone_hmac` / `email_hmac` using `hash_phone_hmac` on normalized phone/email.
+4. It backfills `leads.value_hmac` for all rows using `generate_lead_hmac` or a deterministic HMAC before applying `NOT NULL`.
+5. It replaces the partial unique index on `verified_contacts` with a full `UNIQUE(workspace_id, value_hmac)` constraint.
+6. It adds `Index("ix_verified_contacts_value_hmac", "workspace_id", "value_hmac", unique=True)`.
+7. It adds indexes on `verified_contacts(workspace_id, phone_hmac)` and `verified_contacts(workspace_id, email_hmac)`.
+8. It adds an index on `workspace_dnc_records.value_hmac` if not present.
+
+### AC-7 — Masked display and PII redaction
+**Given** a lead/contact response rendered to non-privileged users,  
+**When** `is_unlocked` is `FALSE`,  
+**Then** phone numbers are masked as `0908 *** 456` (reuse `app/services/phone_waterfall_service.py:mask_phone` or `app/services/export_service.py:mask_phone`), emails are masked as `a***@example.com`, and names are masked as `Nguyễn ***`.
+
+### AC-8 — Tests and verification
+**Given** the test suite,  
+**When** run,  
+**Then**:
+1. Unit tests for canonical HMAC, PII encryption round-trip, opt-out service, and refund cap.
+2. Integration tests for opt-out endpoint (purges, refunds, blocks future ingest), unlock endpoint (insufficient credits, idempotency, audit log), and DNC fail-closed.
+3. Concurrency test: simultaneous unlock and opt-out on the same contact do not deadlock or over-refund.
+4. `ruff check` and `ruff format` pass.
+
+---
+
+## Tasks / Subtasks
+
+- [ ] **Task 1: Database Schema & Migration (AC-6)**
+  - [ ] Resolve blind PII lookup design: thêm `phone_hmac` / `email_hmac` blind-index columns hoặc chấp nhận AD amendment cho phương án khác.
+  - [ ] Create Alembic revision after the latest head: `cd nowing_backend && uv run alembic revision --autogenerate -m "pii vault canonical hmac and opt out"`.
+  - [ ] Backfill `verified_contacts.value_hmac` for existing rows using canonical helper.
+  - [ ] Backfill `verified_contacts.phone_hmac` / `email_hmac` (nếu dùng blind index) từ normalized phone/email.
+  - [ ] Backfill `leads.value_hmac` for existing rows.
+  - [ ] Make `verified_contacts.value_hmac` `NOT NULL`, add `UNIQUE(workspace_id, value_hmac)`.
+  - [ ] Make `leads.value_hmac` `NOT NULL`, ensure `UNIQUE(workspace_id, value_hmac)`.
+  - [ ] Add indexes trên `verified_contacts` cho `(workspace_id, phone_hmac)` và `(workspace_id, email_hmac)` nếu dùng blind index.
+  - [ ] Add `workspace_dnc_records.value_hmac` index if missing.
+
+- [ ] **Task 2: Canonical HMAC & Encryption Helper (AC-2, AC-1)**
+  - [ ] Create or update canonical helper `compute_verified_contact_hmac(phone, email, domain, secret_key)` in `app/lead_intelligence/dnc/normalizer.py` (or `app/services/pii/hmac.py`).
+  - [ ] Input: `phone=<norm_phone>|email=<norm_email>|domain=<domain>`; use `hmac.new(config.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()`.
+  - [ ] Add helpers `compute_phone_hmac` / `compute_email_hmac` cho blind indexes nếu dùng blind index.
+  - [ ] Update `app/services/lead_batch_service.py` to use canonical helper, set `phone_hmac`/`email_hmac`, và encrypt `name`/`title`.
+  - [ ] Update `app/lead_intelligence/enrichment/service.py` to set `value_hmac`, `phone_hmac`, `email_hmac`.
+  - [ ] Update `app/services/phone_waterfall_service.py` to encrypt `name`/`title`, set `value_hmac`, `phone_hmac`, `email_hmac`.
+  - [ ] Optionally fix `app/lead_intelligence/services/deduplication_service.py` to default `secret=config.SECRET_KEY`.
+
+- [ ] **Task 3: PII Opt-Out Service & Route (AC-3, AC-4)**
+  - [ ] Chốt blind-lookup phương án: dùng `phone_hmac` / `email_hmac` columns (prefer) hoặc decrypt scan.
+  - [ ] Create `app/services/pii/opt_out_service.py`:
+    - `process_opt_out(session, workspace_id, record_type, value, actor_user_id, ip_address, global_scope=False)`.
+    - Inserts DNC record, tìm contacts qua blind index hoặc phương án đã chốt, purges contacts, computes refund, handles 15% cap.
+  - [ ] Create `app/routes/pii_opt_out_routes.py` (or extend `dnc_routes.py`) với `POST /api/v1/workspaces/{workspace_id}/pii-opt-out`.
+  - [ ] Register router in `app/app.py`.
+  - [ ] Implement refund qua `BillingService` pattern (credit `User.credit_micros_balance` của payer từ `BillingEvent.user_id`, write negative `BillingEvent` `contact_unlock_refund`) hoặc `WorkspaceCreditService.refund_credits` nếu unlock thực sự trừ workspace pool. **Verify with finance/billing team before choosing.**
+
+- [ ] **Task 4: Harden Contact Unlock (AC-5)**
+  - [ ] Update `app/routes/lead_batch_routes.py:unlock_contact` to return decrypted `phone`/`email` in `ContactUnlockResponse` only after successful billing.
+  - [ ] Ensure `BillingEventService.record_contact_unlock` is used and not `wallet_credit.apply_debit` directly.
+  - [ ] Add idempotent re-unlock path that returns decrypted PII without re-billing.
+  - [ ] Ensure `pii_access_audit_logs` entries include `ip_address` (request client IP).
+
+- [ ] **Task 5: Masking & Display (AC-7)**
+  - [ ] Reuse `app/services/export_service.py:mask_phone` / `mask_email`; chỉ thêm `mask_name` nếu chưa có.
+  - [ ] Update `app/routes/leads_routes.py:_map_lead_to_read` and any contact response mappers to mask `email` and `name` when `is_unlocked=False`.
+  - [ ] Ensure `LeadRead` / contact schemas do not leak encrypted or plaintext PII in masked state.
+
+- [ ] **Task 6: Audit & Compliance Logging (AC-3, AC-5)**
+  - [ ] Standardize `pii_access_audit_logs` JSON shape: `{"user_id": str, "workspace_id": int, "lead_id": str, "contact_id": str, "access_type": "unlock"|"opt_out_purged"|"admin_pii_access", "timestamp": str, "ip_address": str, "reason": str}`.
+  - [ ] Update all contact write paths to append audit log on unlock and opt-out.
+
+- [ ] **Task 7: Tests (AC-8)**
+  - [ ] Unit: `tests/unit/services/test_pii_hmac.py`, `tests/unit/services/test_pii_opt_out_service.py`.
+  - [ ] Integration: `tests/integration/routes/test_pii_opt_out.py`, `tests/integration/lead_batch/test_contact_unlock.py` (extend existing).
+  - [ ] Concurrency: `tests/integration/services/test_pii_opt_out_concurrency.py`.
+  - [ ] Run `ruff check`, `ruff format`, `uv run pytest tests/unit/services/test_pii* tests/integration/routes/test_pii* tests/integration/lead_batch/test_contact_unlock.py -q`.
+
+---
+
+## Dev Notes
+
+### Architecture Compliance & Invariants
+
+- **AD-105 (PII Vault & Decree 13 Compliance):**
+  - Phone/email (and name/title, which are PII) MUST be encrypted at rest using the canonical `VerifiedContactEncryption` (Fernet/TokenEncryption).
+  - `verified_contacts` is the authoritative PII vault; `redact_pii()` is never applied to these raw values.
+  - `value_hmac` is a blind HMAC-SHA256 used for deduplication and DNC matching, not for display.
+  - Contact unlock is a billable event: 1,500 micros, `BillingEvent` with `event_type='contact_unlock'`, `cost_basis='actual'`.
+- **AD-110 (PII Opt-Out Blacklist, Refund & Two-Tier Unlock):**
+  - Canonical opt-out/blacklist vault is the existing `workspace_dnc_records` / `global_dnc_records`.
+  - Do NOT create a new `pii_blacklists` table unless an explicit merge migration is written.
+  - Opt-out workflow: DNC record → mark `is_unlocked=FALSE` → refund (capped at 15% of unlocked leads per billing cycle) → irreversible PII deletion/anonymization → audit log.
+  - Two-Tier Unlock UX is Story 26.5; 26.4 only hardens the backend unlock + billing path.
+- **AD-109 (Batch Ingestion & Deadlock Prevention):**
+  - `leads.value_hmac` and `verified_contacts.value_hmac` MUST be `NOT NULL` and part of `UNIQUE(workspace_id, value_hmac)`.
+  - Bulk upserts MUST sort by `value_hmac ASC`.
+- **AD-104 (Zero-Cache CDC):**
+  - `verified_contacts` and `pii_access_audit_logs` MUST NOT be published to `zero_publication`.
+  - `leads` publication column list already excludes PII-derived columns (`value_hmac` should also be excluded; verify `app/zero_publication.py`).
+
+### Existing Code to Reuse
+
+- **`app/services/pii/verified_contact_encryption.py`** — `VerifiedContactEncryption` (Fernet/TokenEncryption), `encrypt_contact()`, `decrypt_contact()`, `is_encrypted()`.
+- **`app/lead_intelligence/dnc/normalizer.py`** — `normalize_phone_e164`, `normalize_email`, `normalize_domain`, `hash_phone_hmac`.
+- **`app/lead_intelligence/dnc/service.py`** — `DncComplianceService` with workspace/global DNC lookup and Redis cache invalidation.
+- **`app/services/billing_event_service.py`** — `BillingEventService.record_contact_unlock` and `_record_business_event` for wallet debit/spend cap.
+- **`app/services/billing_service.py`** — `BillingService.auto_refund_lead` (credits `User.credit_micros_balance`, writes negative `BillingEvent`, invalidates Redis cache). Pattern này nên được reuse/adapt cho contact-unlock refund.
+- **`app/services/workspace_credit_service.py`** — `WorkspaceCreditService.refund_credits` (workspace pool + member monthly spent refund). Chỉ dùng nếu unlock thực sự trừ `Workspace.credit_micros_balance`.
+- **`app/services/wallet_credit.py`** — `apply_debit` cho user wallet; chú ý không có `apply_credit`.
+- **`app/services/phone_waterfall_service.py`** — `mask_phone`, phone normalization/extraction, `VerifiedContact` creation.
+- **`app/services/export_service.py`** — `mask_phone`, `mask_email` đã có thể reuse.
+- **`app/routes/lead_batch_routes.py`** — existing `/workspaces/{workspace_id}/leads/{lead_id}/contacts/{contact_id}/unlock` route và `ContactUnlockResponse`.
+- **`app/routes/dnc_routes.py`** — existing DNC CRUD và `_normalize_dnc_value` helper.
+- **`app/db.py`** — `VerifiedContact`, `Lead`, `WorkspaceDncRecord`, `GlobalDncRecord`, `BillingEvent` models.
+
+### Gaps & Implementation Hints
+
+- **`VerifiedContact.value_hmac` is nullable** and only set by `lead_batch_service.py` using a non-canonical form. Enrichment and phone waterfall leave it NULL.
+- **`Lead.value_hmac` is nullable**; must backfill before `NOT NULL`.
+- **`phone_waterfall_service.py` stores `name=lead.company_name` plaintext** and does not encrypt. The `VerifiedContactEncryption.encrypt()` should be called for `name` and `title`.
+- **Blind lookup of encrypted PII: resolved.** Thêm `phone_hmac` / `email_hmac` columns vào `verified_contacts`, tính bằng `hash_phone_hmac` trên normalized phone/email. Đây là blind index cho opt-out lookup và khớp với `workspace_dnc_records.value_hmac`.
+- **Opt-out refund contract: resolved.** Contact unlock debit từ `User.credit_micros_balance` (user wallet) qua `wallet_credit.apply_debit` và tăng `WorkspaceMembership.monthly_spent_micros` qua `WorkspaceCreditService.record_spend` (spend cap). Refund:
+  - Tìm payer từ original `BillingEvent.user_id`.
+  - Credit `User.credit_micros_balance += 1_500` (pattern từ `BillingService.auto_refund_lead`).
+  - Giảm `WorkspaceMembership.monthly_spent_micros` tương ứng (thêm `WorkspaceCreditService.refund_member_spend` hoặc mở rộng `record_spend` cho negative amount với reason).
+  - Viết `BillingEvent` với `event_type='contact_unlock_refund'`, `cost_micros=-1_500`.
+  - Không dùng `WorkspaceCreditService.refund_credits` (vì nó tăng `Workspace.credit_micros_balance`, không phải user wallet).
+- **15% refund cap** requires counting `BillingEvent.event_type='contact_unlock'` vs `contact_unlock_refund` in the current billing cycle per workspace.
+- **Existing `ContactUnlockResponse` does not return phone/email.** Extend it to `contact_id`, `is_unlocked`, `cost_micros`, `phone` (decrypted), `email` (decrypted), but only after successful billing.
+- **DNC cache invalidation** must be called after opt-out via `DncComplianceService.invalidate_workspace_cache(workspace_id)` and `invalidate_global_cache()` for global opt-outs.
+
+### Project Structure Notes
+
+- New files likely:
+  - `nowing_backend/app/services/pii/opt_out_service.py`
+  - `nowing_backend/app/routes/pii_opt_out_routes.py` (or extend `dnc_routes.py`)
+  - `nowing_backend/app/services/pii/mask.py` (mask email/name)
+  - `nowing_backend/alembic/versions/<new>_pii_vault_hmac_opt_out.py`
+  - `nowing_backend/tests/unit/services/test_pii_hmac.py`
+  - `nowing_backend/tests/unit/services/test_pii_opt_out_service.py`
+  - `nowing_backend/tests/integration/routes/test_pii_opt_out.py`
+  - `nowing_backend/tests/integration/services/test_pii_opt_out_concurrency.py`
+- Files to modify:
+  - `nowing_backend/app/db.py` (thêm `phone_hmac`, `email_hmac` columns nếu dùng model-driven; prefer migration)
+  - `nowing_backend/app/lead_intelligence/dnc/normalizer.py` (canonical helper + blind index helpers)
+  - `nowing_backend/app/services/lead_batch_service.py` (use canonical HMAC, set phone_hmac/email_hmac, encrypt name/title)
+  - `nowing_backend/app/lead_intelligence/enrichment/service.py` (set value_hmac, phone_hmac, email_hmac)
+  - `nowing_backend/app/services/phone_waterfall_service.py` (encrypt name/title, set value_hmac, phone_hmac, email_hmac)
+  - `nowing_backend/app/services/billing_event_service.py` (thêm `record_contact_unlock_refund`)
+  - `nowing_backend/app/services/workspace_credit_service.py` (thêm `refund_member_spend` hoặc mở rộng `record_spend` cho negative)
+  - `nowing_backend/app/services/billing_service.py` (tham khảo pattern `auto_refund_lead`)
+  - `nowing_backend/app/services/export_service.py` (reuse `mask_phone` / `mask_email`)
+  - `nowing_backend/app/routes/lead_batch_routes.py` (harden unlock response)
+  - `nowing_backend/app/routes/dnc_routes.py` (or new pii-opt-out route)
+  - `nowing_backend/app/app.py` (register new router)
+  - `nowing_backend/app/routes/leads_routes.py` (mask email/name in `LeadRead`)
+  - `nowing_backend/app/schemas/lead_batch_ingest.py` (extend `ContactUnlockResponse`)
+  - `nowing_backend/app/schemas/dnc.py` (add `PiiOptOutRequest`, `PiiOptOutResponse`)
+
+### P0 Surface Assessment
+
+This story touches **PII, credit refund, billing events, and DNC/wallet logic** — which are P0-adjacent surfaces. Per `nowing-quality-pipeline.md`:
+- **Integration tests on real Postgres** are **P0-gated** (Pattern 6).
+- **Human-review gate** is **P0-gated** because it touches PII, credit/wallet, and compliance.
+- **Mutation gate** is **P0-gated** for `app/services/pii/opt_out_service.py`, `app/services/lead_batch_service.py`, `app/services/billing_event_service.py`, `app/lead_intelligence/dnc/service.py`.
+
+### Important Do-Nots
+
+- **Do NOT create a new `pii_blacklists` table** unless an explicit merge migration is written. Use `workspace_dnc_records` / `global_dnc_records` (AD-110).
+- **Do NOT switch to AES-256-GCM** for `verified_contacts` encryption. Use the existing `VerifiedContactEncryption` (Fernet/TokenEncryption) per AD-105 v5.
+- **Do NOT call `wallet_credit.apply_debit` directly** from the unlock or opt-out route; route through `BillingEventService` so spend caps and idempotency are enforced.
+- **Do NOT expose decrypted PII in masked/default lead list responses.** Only unlock response returns decrypted phone/email, and only after billing.
+
+### References
+
+- Epic context: `_bmad-output/planning-artifacts/epics.md` lines 3310–3380 (Epic 26, AD-101–AD-110, Story 26.4 AC).
+- Architecture: `_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` §AD-105, AD-110.
+- Architecture review v5: `_bmad-output/review-artifacts/epic-26-architecture-review-2026-08-17-v5.md` (PII encryption Fernet decision, no `pii_blacklists`).
+- 26.1 story (patterns): `_bmad-output/implementation-artifacts/26-1-fastmcp-batch-ingest-and-stateless-chainlens-pipeline.md`.
+- Existing code:
+  - `nowing_backend/app/services/pii/verified_contact_encryption.py`
+  - `nowing_backend/app/lead_intelligence/dnc/normalizer.py`
+  - `nowing_backend/app/lead_intelligence/dnc/service.py`
+  - `nowing_backend/app/services/lead_batch_service.py`
+  - `nowing_backend/app/lead_intelligence/enrichment/service.py`
+  - `nowing_backend/app/services/phone_waterfall_service.py`
+  - `nowing_backend/app/routes/lead_batch_routes.py`
+  - `nowing_backend/app/routes/dnc_routes.py`
+  - `nowing_backend/app/services/billing_event_service.py`
+  - `nowing_backend/app/services/wallet_credit.py`
+  - `nowing_backend/app/db.py` (`VerifiedContact`, `Lead`, `WorkspaceDncRecord`, `GlobalDncRecord`, `BillingEvent`)
+  - `nowing_backend/alembic/versions/ac475d54f6a2_story_26_1_chainlens_chunks_and_.py`
+
+## Dev Agent Record
+
+### Debug Log References
+
+- `verified_contacts.value_hmac` is nullable and not set by enrichment/phone-waterfall.
+- `phone_waterfall_service.py` stores `name=lead.company_name` in plaintext.
+- `lead_batch_service.py` uses non-canonical HMAC form `f"{phone}|{email}"`.
+- `epics.md` Story 26.4 AC still says AES-256-GCM; architecture v5 overrides with Fernet/TokenEncryption.
+
+### Completion Notes List
+
+- [ ] Canonical HMAC helper created and all writers updated.
+- [ ] Schema migration backfills `verified_contacts.value_hmac` and `leads.value_hmac`, makes both `NOT NULL`.
+- [ ] All `VerifiedContact` creation paths encrypt `name`/`title`/`email`/`phone`.
+- [ ] `POST /api/v1/workspaces/{workspace_id}/pii-opt-out` implemented with purge, refund (15% cap), and DNC cache invalidation.
+- [ ] Contact unlock endpoint returns decrypted phone/email after billing.
+- [ ] Masking for email/name added to lead/contact read responses.
+- [ ] Unit + integration tests pass; ruff/format clean.
+
+---
+
+## Challenge Log (grill-me)
+
+### Q1 — Already implemented?
+
+- **Không có exact duplicate** cho PII opt-out endpoint hay canonical composite `verified_contacts.value_hmac` helper.
+- **Tuy nhiên có nhiều building blocks tồn tại và nên reuse:**
+  - `app/services/pii/verified_contact_encryption.py` — `VerifiedContactEncryption`.
+  - `app/lead_intelligence/dnc/normalizer.py` — `hash_phone_hmac`, `normalize_phone_e164`, `normalize_email`, `normalize_domain`.
+  - `app/lead_intelligence/dnc/service.py` — `DncComplianceService`.
+  - `app/services/phone_waterfall_service.py:mask_phone` — phone masking.
+  - `app/services/export_service.py:mask_phone` / `mask_email` — existing PII mask helpers.
+  - `app/services/billing_service.py:BillingService.auto_refund_lead` — refund pattern (credits user wallet, writes negative `BillingEvent`, marks `VerifiedContact` invalid, Redis cache invalidation).
+  - `app/services/workspace_credit_service.py:WorkspaceCreditService.refund_credits` — refunds workspace pool + decrements member monthly spent.
+  - `app/services/billing_event_service.py:BillingEventService.record_contact_unlock` — unlock billing.
+  - `app/routes/lead_batch_routes.py` — existing `/contacts/{contact_id}/unlock`.
+  - `app/routes/dnc_routes.py` — existing DNC CRUD.
+- **Risk:** Nếu dev tạo `app/services/pii/opt_out_service.py` mới mà không reuse `BillingService.auto_refund_lead` / `WorkspaceCreditService.refund_credits`, sẽ duplicate logic refund và sai money semantics.
+
+### Q2 — Simpler alternative?
+
+- **Masking:** Thay vì tạo `app/services/pii/mask.py`, reuse `app/services/export_service.py:mask_phone` và `mask_email`. Chỉ thiếu `mask_name` có thể bổ sung 1 hàm trong cùng file hoặc dùng inline 3-line helper.
+- **Opt-out route:** Có thể mở rộng `app/routes/dnc_routes.py` (thêm `POST /pii-opt-out`) thay vì file route mới, miễn là business logic nằm trong service.
+- **Refund path:** Nên extend `BillingService` hoặc `BillingEventService` thay vì implement refund từ đầu. Wallet refund pattern đã có trong `BillingService.auto_refund_lead` (tuy nhiên nó refund vào `User.credit_micros_balance`, không phải workspace balance).
+- **Blind HMAC lookup:** Có thể cần thêm `phone_hmac` / `email_hmac` columns (hoặc computed index) để tìm `VerifiedContact` mà không decrypt toàn bộ bảng. Xem Q3.
+
+### Q3 — Edge cases spec misses (Pattern 3)
+
+- [ ] **Boundary:** Refund cap 15% — test exactly at cap, 1 micro trên, 1 micro dưới, nhiều contacts cùng lúc.
+- [ ] **Boundary:** `value_hmac` canonical form khi `phone`, `email` hoặc `domain` missing/empty — dùng chuỗi rỗng trong message hay reject degenerate?
+- [ ] **Null/empty:** Opt-out request với phone/email malformed hoặc chỉ whitespace → normalization trả `None`; response phải rõ ràng (400 với lý do).
+- [ ] **Null/empty:** `VerifiedContact` có `phone=None` hoặc `email=None` (enrichment hoặc phone waterfall chỉ có 1 field) — HMAC phải tính được với partial input.
+- [ ] **Concurrent:** Double opt-out request cùng phone trong cùng workspace trong 2 request đồng thời → idempotent DNC upsert + no double refund.
+- [ ] **Concurrent:** Opt-out và unlock trên cùng contact đồng thời → tránh race gây unlock sau opt-out hoặc over-refund.
+- [ ] **Anonymized contact:** Opt-out lần 2 trên contact đã bị purge — trả `purged_contact_count=0` và `refunded_micros=0`, không gọi LLM, không trừ tiền.
+- [ ] **DNC-only opt-out:** Phone chưa có trong `verified_contacts` — vẫn tạo DNC record, vẫn cache invalidation, `purged_contact_count=0`.
+- [ ] **Global opt-out (superadmin):** Tìm + purge contacts xuyên workspace. Hiện `global_dnc_records` áp dụng tất cả workspace; purge global cần scan cross-workspace hay chỉ để DNC block tương lai? Chưa rõ.
+- [ ] **Blind lookup of encrypted columns:** `verified_contacts.phone` / `email` là Fernet ciphertext. Muốn find contacts để purge theo phone/email, **không thể** query plaintext hoặc so sánh với `value_hmac` composite mà không biết domain/email. Cần blind index (phone_hmac / email_hmac) hoặc phải decrypt toàn bộ workspace (privacy/perf fail).
+- [ ] **Refund target user:** Contact từng được unlock bởi user đã bị xóa hoặc `user_id` NULL → refund vào đâu? workspace owner, bỏ qua, hay ghi nhận unclaimed?
+- [ ] **No original BillingEvent:** `is_unlocked=True` nhưng không tìm thấy `BillingEvent` (dữ liệu cũ/trước story) → không refund, vẫn purge.
+
+### Q4 — Failure modes unspecified (Pattern 2, 4)
+
+- [ ] **`VerifiedContactEncryption.decrypt` fails** (ciphertext corrupted, key rotation, partial migration): opt-out purge vẫn có thể overwrite bằng `None` mà không cần decrypt; unlock endpoint phải trả 500, không leak PII.
+- [ ] **`BillingEventService.record_contact_unlock` lỗi sau khi đã set `is_unlocked=True`**: hiện tại code gọi billing rồi mới set `is_unlocked`, rollback sẽ giữ `is_unlocked=False`. Nếu refactor thứ tự, phải rollback transaction.
+- [ ] **Refund path chưa được thiết kế:** `wallet_credit.apply_debit` không có `apply_credit`. `WorkspaceCreditService.record_spend` reject non-positive. `WorkspaceCreditService.refund_credits` tăng `Workspace.credit_micros_balance`, không tăng `User.credit_micros_balance`. `BillingService.auto_refund_lead` tăng `User.credit_micros_balance` trực tiếp, viết negative `BillingEvent`. Story cần chốt: contact unlock debit từ user wallet (`User.credit_micros_balance`) → refund cũng vào user wallet + ghi negative `BillingEvent` + adjust member monthly spent.
+- [ ] **Redis down khi invalidate DNC cache:** `DncComplianceService` sẽ warn và tiếp tục; opt-out response vẫn 200 nhưng cache stale cho đến TTL. Cần test.
+- [ ] **Postgres deadlock khi concurrent DNC upsert + contact purge:** DNC table có unique `(workspace_id, record_type, value_hmac)`; contact purge update `verified_contacts` row khác; deadlock nếu cùng contact bị nhiều worker. Cần `SELECT FOR UPDATE` hoặc process per-contact serially.
+- [ ] **Migration backfill thất bại giữa chừng:** `value_hmac` NULL hàng triệu rows; migration batch + thiết lập NOT NULL phải idempotent.
+- [ ] **15% cap query fail:** `BillingEvent` table chưa có index `(workspace_id, event_type, created_at)`; counting unlocked per billing cycle trên lượng lớn row có thể chậm hoặc timeout.
+
+### Triage
+
+- **CRITICAL — Refund money path: RESOLVED.** Unlock debit từ `User.credit_micros_balance` (user wallet) và `WorkspaceMembership.monthly_spent_micros` (spend cap). Refund: credit user wallet + negative `BillingEvent` + decrement monthly spent; **không** tăng `Workspace.credit_micros_balance`. (Q4)
+- **CRITICAL — Blind index for encrypted PII lookup: RESOLVED.** Thêm `phone_hmac` / `email_hmac` columns tính bằng `hash_phone_hmac` trên normalized phone/email. (Q3 — security/privacy)
+- **Non-critical — Reuse existing mask/refund helpers:** Có thể sửa trong dev. (Q1/Q2)
+- **Non-critical — Edge cases concurrency/refund cap:** Cần thêm vào test skeleton trong `bmad-nowing-test-first-atdd`. (Q3)
+
+### Recommended pre-dev actions
+
+1. **(DONE in story update)** Add `phone_hmac` / `email_hmac` blind index columns và populate trong mọi writer.
+2. **(DONE in story update)** Implement refund via user wallet credit + negative `BillingEvent` + monthly spent decrement; không dùng `WorkspaceCreditService.refund_credits`.
+3. **Sau đó proceed** đến `bmad-nowing-test-first-atdd`.
diff --git a/_bmad-output/implementation-artifacts/sprint-status.yaml b/_bmad-output/implementation-artifacts/sprint-status.yaml
index 82ff047a7..94f3971a6 100644
--- a/_bmad-output/implementation-artifacts/sprint-status.yaml
+++ b/_bmad-output/implementation-artifacts/sprint-status.yaml
@@ -1,5 +1,5 @@
 # generated: 2026-08-08
-# last_updated: 2026-08-15  # 10-6, 10-7, 3-13 → done; followups reopened; Epic 21 opened for dev
+# last_updated: 2026-08-19  # 26-4 implementation complete, moved to review
 # project: Nowing
 # project_key: NOKEY
 # tracking_system: file-system
@@ -41,7 +41,7 @@
 # - Retrospective appends its action items to action_items; sprint-status surfaces open ones
 
 generated: "2026-08-08"
-last_updated: "2026-08-18"  # 26-3 story file created, validated, and fixed
+last_updated: "2026-08-19"  # 26-4 implementation complete, moved to review
 # ponytail: 2026-08-14 — reopened deferred/business-gated/dropped to backlog; 16-1 mutation gate reopened; 15-2 moved to review; tech-debt tracker reopened.
 # ponytail: 2026-08-08 SCP sprint-change-proposal-2026-08-08 — appended citation ACs to 3.15 (WEB_RESULT), 9.3 (async delivery), 2.10 (Exa MCP). 3 stories → review.
 # ponytail: 2026-08-08 sprint-planning — added Epic 1, 5 (DONE brownfield); added 9.1a, 9.1b, 4.8a-4.8h, 13.2a-13.2e; upgraded 12.1-12.5 to ready-for-dev (story files exist); 12.0 DONE (legal approved).
@@ -251,8 +251,8 @@ development_status:
 
   # === Epic 25: Superadmin & Platform Operations Control Plane ===
   # 2026-08-16: Multi-Tenant Hub, Scoped Impersonation, Manual Credit Desk, Affiliate Anti-Fraud Payouts, Telemetry & Dynamic Scraper Rules
-  epic-25: ready-for-dev
-  25-1: in-progress  # Multi-Tenant User & Workspace Hub + Scoped Impersonation
+  epic-25: in-progress
+  25-1: done  # Multi-Tenant User & Workspace Hub + Scoped Impersonation
   25-2: done  # Manual Credit Adjustment & Refund Desk with Dual-Audit Ledger
   25-3: ready-for-dev  # Affiliate Partner Payout Desk & Anti-Fraud Engine
   25-4: ready-for-dev  # Realtime LLM Token Cost, Proxy Health & Celery Queue Telemetry
@@ -265,8 +265,8 @@ development_status:
   epic-26: in-progress
   26-1: ready-for-dev  # FastMCP Ingest Gateway, Batch Ingestion & Stateless ChainLens Pipeline
   26-2: done  # dsh-worker Sidecar Container, Redis Streams & Task Resumption
-  26-3: in-progress  # Multi-Tier Hybrid LLM Router (Gemini Flash Free Tier + DeepSeek V4 + Qwen 3.8)
-  26-4: backlog  # PII Vault AES-256 Encryption, HMAC Deduplication & Decree 13 Opt-Out
+  26-3: pending-human-review  # Multi-Tier Hybrid LLM Router (Gemini Flash Free Tier + DeepSeek V4 + Qwen 3.8)
+  26-4: review  # PII Vault Fernet Encryption, HMAC Deduplication & Decree 13 Opt-Out
   26-5: backlog  # Split Canvas Glass Box Mission Control, Two-Tier Phone Unlock & Shimmer Influx
   26-6: backlog  # Telegram Interactive Checkpoint Bot & 1-Click Auto-Refund Dialog
   26-7: backlog  # Hermetic Quality Gates, Benchmark Suite & Anti-Zombie Chaos Testing
diff --git a/nowing_backend/app/db.py b/nowing_backend/app/db.py
index 4c565ae32..1244bdcc3 100644
--- a/nowing_backend/app/db.py
+++ b/nowing_backend/app/db.py
@@ -4670,7 +4670,7 @@ class Lead(Base, TimestampMixin):
     enriched = Column(Boolean, nullable=False, default=False, server_default="false")
     consent_status = Column(String(50), nullable=True)
     legal_basis = Column(String(50), nullable=True)
-    value_hmac = Column(String(64), nullable=True, index=True)
+    value_hmac = Column(String(64), nullable=False, index=True)
     tax_id = Column(String(50), nullable=True)
     legal_representative = Column(String(200), nullable=True)
     charter_capital_vnd = Column(BigInteger, nullable=True)
@@ -5230,7 +5230,9 @@ class VerifiedContact(Base, TimestampMixin):
     consent = Column(Boolean, nullable=False, default=False, server_default="false")
     consent_status = Column(String(50), nullable=True)
     legal_basis = Column(String(50), nullable=True)
-    value_hmac = Column(String(64), nullable=True, index=True)
+    value_hmac = Column(String(64), nullable=False, index=True)
+    phone_hmac = Column(String(64), nullable=True, index=True)
+    email_hmac = Column(String(64), nullable=True, index=True)
     is_valid = Column(Boolean, nullable=False, default=True, server_default="true")
     is_unlocked = Column(Boolean, nullable=False, default=False, server_default="false")
     pii_access_audit_logs = Column(
diff --git a/nowing_backend/app/lead_intelligence/dnc/normalizer.py b/nowing_backend/app/lead_intelligence/dnc/normalizer.py
index bc9992f22..c2357482c 100644
--- a/nowing_backend/app/lead_intelligence/dnc/normalizer.py
+++ b/nowing_backend/app/lead_intelligence/dnc/normalizer.py
@@ -137,3 +137,40 @@ def normalize_tax_id(tax_id: str | None) -> str | None:
 
     cleaned = re.sub(r"[^\w-]", "", tax_id.strip()).lower()
     return cleaned if cleaned else None
+
+
+def compute_phone_hmac(phone: str | None) -> str | None:
+    """Blind HMAC for a phone number (raw or E.164)."""
+    e164 = normalize_phone_e164(phone)
+    if not e164:
+        return None
+    return hash_phone_hmac(e164)
+
+
+def compute_email_hmac(email: str | None) -> str | None:
+    """Blind HMAC for an email address (raw or normalized)."""
+    norm = normalize_email(email)
+    if not norm:
+        return None
+    return hash_phone_hmac(norm)
+
+
+def compute_verified_contact_hmac(
+    phone: str | None,
+    email: str | None,
+    domain: str | None,
+) -> str:
+    """Canonical composite HMAC for verified contact deduplication (Story 26.4).
+
+    Canonical form: HMAC_SHA256(
+        "phone=<normalized_phone>|email=<normalized_email>|domain=<domain>",
+        config.SECRET_KEY
+    )
+    """
+    norm_phone = normalize_phone_e164(phone) or ""
+    norm_email = normalize_email(email) or ""
+    norm_domain = normalize_domain(domain) or ""
+    if not norm_phone and not norm_email and not norm_domain:
+        raise ValueError("degenerate contact: phone, email and domain are all empty")
+    canonical = f"phone={norm_phone}|email={norm_email}|domain={norm_domain}"
+    return hash_phone_hmac(canonical)
diff --git a/nowing_backend/app/lead_intelligence/enrichment/service.py b/nowing_backend/app/lead_intelligence/enrichment/service.py
index c5f77f34c..98e356bfc 100644
--- a/nowing_backend/app/lead_intelligence/enrichment/service.py
+++ b/nowing_backend/app/lead_intelligence/enrichment/service.py
@@ -27,6 +27,11 @@ from app.db import (
     VerifiedContact,
     Workspace,
 )
+from app.lead_intelligence.dnc.normalizer import (
+    compute_email_hmac,
+    compute_phone_hmac,
+    compute_verified_contact_hmac,
+)
 from app.lead_intelligence.enrichment import cache as enrichment_cache
 from app.lead_intelligence.enrichment.fallback import FallbackVerifier
 from app.lead_intelligence.enrichment.providers import run_waterfall
@@ -249,6 +254,11 @@ class EnrichmentService:
                 consent=consent_status == "explicit",
                 consent_status=consent_status,
                 legal_basis=legal_basis,
+                value_hmac=compute_verified_contact_hmac(
+                    item.get("phone"), item.get("email"), lead.domain
+                ),
+                phone_hmac=compute_phone_hmac(item.get("phone")),
+                email_hmac=compute_email_hmac(item.get("email")),
             )
             session.add(contact)
             await session.flush()
diff --git a/nowing_backend/app/lead_intelligence/schemas.py b/nowing_backend/app/lead_intelligence/schemas.py
index 7ef9dd2c2..ce5ff44be 100644
--- a/nowing_backend/app/lead_intelligence/schemas.py
+++ b/nowing_backend/app/lead_intelligence/schemas.py
@@ -71,6 +71,8 @@ class LeadRead(BaseModel):
     assigned_to_user_id: UUID | None = None
     version: int = 1
     intent: str | None = None
+    name: str | None = None
+    email: str | None = None
     phone: str | None = None
     price_estimate: str | None = None
     content_snippet: str | None = None
diff --git a/nowing_backend/app/routes/lead_batch_routes.py b/nowing_backend/app/routes/lead_batch_routes.py
index f1a4ca663..6151ca3e1 100644
--- a/nowing_backend/app/routes/lead_batch_routes.py
+++ b/nowing_backend/app/routes/lead_batch_routes.py
@@ -15,6 +15,8 @@ from app.db import Permission, VerifiedContact, Workspace, get_async_session
 from app.rate_limiter import limiter
 from app.services.billing_event_service import BillingEventService
 from app.services.lead_batch_service import LeadBatchService, LeadItemValidationError
+from app.services.pii.opt_out_service import OptOutService
+from app.services.pii.verified_contact_encryption import VerifiedContactEncryption
 from app.users import get_auth_context
 from app.utils.rbac import check_permission
 
@@ -114,12 +116,32 @@ async def batch_ingest_leads(
     return BatchLeadIngestResponse(**result)
 
 
+class PIIOptOutRequest(BaseModel):
+    """PII opt-out request body."""
+
+    record_type: str = Field(..., pattern="^(phone|email)$")
+    value: str = Field(..., min_length=1)
+    reason: str | None = "Right to be forgotten"
+
+
+class PIIOptOutResponse(BaseModel):
+    """PII opt-out response."""
+
+    purged_contact_count: int
+    refunded_micros: int
+    dnc_record_id: UUID
+
+
 class ContactUnlockResponse(BaseModel):
     """Contact unlock response."""
 
     contact_id: UUID
     is_unlocked: bool
     cost_micros: int
+    name: str | None = None
+    title: str | None = None
+    email: str | None = None
+    phone: str | None = None
 
 
 @router.post(
@@ -167,11 +189,23 @@ async def unlock_contact(
             detail="Contact not found",
         )
 
+    enc = VerifiedContactEncryption()
+
     if contact.is_unlocked:
         return ContactUnlockResponse(
             contact_id=contact.id,
             is_unlocked=True,
             cost_micros=0,
+            name=enc.decrypt(contact.name) if enc.is_encrypted(contact.name) else None,
+            title=enc.decrypt(contact.title)
+            if enc.is_encrypted(contact.title)
+            else None,
+            email=enc.decrypt(contact.email)
+            if enc.is_encrypted(contact.email)
+            else None,
+            phone=enc.decrypt(contact.phone)
+            if enc.is_encrypted(contact.phone)
+            else None,
         )
 
     try:
@@ -208,4 +242,68 @@ async def unlock_contact(
         contact_id=contact.id,
         is_unlocked=True,
         cost_micros=1_500,
+        name=enc.decrypt(contact.name) if enc.is_encrypted(contact.name) else None,
+        title=enc.decrypt(contact.title) if enc.is_encrypted(contact.title) else None,
+        email=enc.decrypt(contact.email) if enc.is_encrypted(contact.email) else None,
+        phone=enc.decrypt(contact.phone) if enc.is_encrypted(contact.phone) else None,
+    )
+
+
+@router.post(
+    "/workspaces/{workspace_id}/pii-opt-out",
+    response_model=PIIOptOutResponse,
+    status_code=status.HTTP_200_OK,
+)
+@limiter.limit("30/minute")
+async def pii_opt_out(
+    request: Request,
+    workspace_id: int,
+    body: PIIOptOutRequest = Body(...),
+    session: AsyncSession = Depends(get_async_session),
+    auth: AuthContext = Depends(get_auth_context),
+) -> PIIOptOutResponse:
+    """Process a PDPD Decree 13 opt-out request (Right to be Forgotten)."""
+    await check_permission(
+        session,
+        auth,
+        workspace_id,
+        Permission.LEADS_WRITE.value,
+        error_message="You don't have permission to opt-out PII in this workspace",
+    )
+
+    workspace = await session.get(Workspace, workspace_id)
+    if workspace is None:
+        raise HTTPException(
+            status_code=status.HTTP_404_NOT_FOUND,
+            detail="Workspace not found",
+        )
+
+    service = OptOutService(session)
+    try:
+        result = await service.process_opt_out(
+            workspace_id=workspace_id,
+            record_type=body.record_type,
+            value=body.value,
+            actor_user_id=auth.user.id,
+            ip_address=getattr(request, "client", None) and request.client.host,
+            global_scope=False,
+        )
+    except ValueError as exc:
+        detail = str(exc).lower()
+        if "phone" in detail or "email" in detail:
+            raise HTTPException(
+                status_code=status.HTTP_400_BAD_REQUEST,
+                detail=str(exc),
+            ) from exc
+        raise HTTPException(
+            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
+            detail=str(exc),
+        ) from exc
+
+    await session.flush()
+
+    return PIIOptOutResponse(
+        purged_contact_count=result.purged_contact_count,
+        refunded_micros=result.refunded_micros,
+        dnc_record_id=result.dnc_record_id,
     )
diff --git a/nowing_backend/app/routes/leads_routes.py b/nowing_backend/app/routes/leads_routes.py
index e0b84b4db..7c3074a25 100644
--- a/nowing_backend/app/routes/leads_routes.py
+++ b/nowing_backend/app/routes/leads_routes.py
@@ -68,22 +68,43 @@ def _map_lead_to_read(lead: Lead) -> LeadRead:
             for c in lead.verified_contacts
             if getattr(c, "phone", None) or getattr(c, "email", None)
         ]
+    first_contact = raw_contacts[0] if raw_contacts else None
     first_phone = (
-        raw_contacts[0].phone if raw_contacts else getattr(lead, "phone", None)
+        getattr(first_contact, "phone", None)
+        if first_contact
+        else getattr(lead, "phone", None)
     )
-    if first_phone:
-        from app.services.phone_waterfall_service import mask_phone
-        from app.services.pii.verified_contact_encryption import (
-            VerifiedContactEncryption,
-        )
+    first_email = getattr(first_contact, "email", None) if first_contact else None
+    first_name = getattr(first_contact, "name", None) if first_contact else None
+
+    from app.services.export_service import mask_email, mask_name, mask_phone
+    from app.services.pii.verified_contact_encryption import VerifiedContactEncryption
+
+    enc = VerifiedContactEncryption()
+    is_unlocked = bool(getattr(first_contact, "is_unlocked", False))
 
-        enc = VerifiedContactEncryption()
-        if enc.is_encrypted(first_phone):
+    def _render_field(value: str | None) -> str | None:
+        if not value:
+            return None
+        if enc.is_encrypted(value):
             try:
-                first_phone = enc.decrypt(first_phone)
+                value = enc.decrypt(value)
             except Exception:
-                first_phone = None
-        first_phone = mask_phone(first_phone) if first_phone else None
+                return None
+        return value
+
+    raw_phone = _render_field(first_phone)
+    raw_email = _render_field(first_email)
+    raw_name = _render_field(first_name)
+
+    if is_unlocked:
+        first_phone = raw_phone
+        first_email = raw_email
+        first_name = raw_name
+    else:
+        first_phone = mask_phone(raw_phone) if raw_phone else None
+        first_email = mask_email(raw_email) if raw_email else None
+        first_name = mask_name(raw_name) if raw_name else None
 
     # Derive intent and snippet from available metadata or source
     derived_intent = getattr(lead, "intent", None)
@@ -135,6 +156,8 @@ def _map_lead_to_read(lead: Lead) -> LeadRead:
         else None,
         status=lead.status or "new",
         intent=derived_intent,
+        name=first_name,
+        email=first_email,
         phone=first_phone,
         price_estimate=getattr(lead, "price_estimate", None),
         content_snippet=content_snippet,
diff --git a/nowing_backend/app/services/billing_event_service.py b/nowing_backend/app/services/billing_event_service.py
index e8df34151..1482a7bd5 100644
--- a/nowing_backend/app/services/billing_event_service.py
+++ b/nowing_backend/app/services/billing_event_service.py
@@ -88,6 +88,78 @@ class BillingEventService:
             return_existing=True,
         )
 
+    async def record_contact_unlock_refund(
+        self,
+        session: AsyncSession,
+        *,
+        verified_contact_id: UUID,
+        workspace_id: int,
+        client_id: str | None = None,
+        user_id: UUID,
+        cost_micros: int = 1_500,
+    ) -> BillingEvent:
+        """Record a contact-unlock refund and credit the payer wallet (Story 26.4).
+
+        Idempotent: returns an existing refund BillingEvent if one already exists.
+        """
+        # 1. Idempotency: existing refund row for this contact.
+        existing_refund = (
+            await session.execute(
+                select(BillingEvent).where(
+                    BillingEvent.event_entity_type == "verified_contact",
+                    BillingEvent.event_type == "contact_unlock_refund",
+                    BillingEvent.event_id == verified_contact_id,
+                    BillingEvent.workspace_id == workspace_id,
+                )
+            )
+        ).scalar_one_or_none()
+        if getattr(existing_refund, "event_type", None) == "contact_unlock_refund":
+            return existing_refund
+
+        # 2. Find the original unlock billing event to identify the payer.
+        original = (
+            await session.execute(
+                select(BillingEvent).where(
+                    BillingEvent.event_entity_type == "verified_contact",
+                    BillingEvent.event_type == "contact_unlock",
+                    BillingEvent.event_id == verified_contact_id,
+                    BillingEvent.workspace_id == workspace_id,
+                )
+            )
+        ).scalar_one_or_none()
+        if getattr(original, "event_type", None) != "contact_unlock":
+            raise ValueError(
+                f"no unlock billing event for contact {verified_contact_id}"
+            )
+
+        payer_id = original.user_id
+        if payer_id is None:
+            payer_id = user_id
+
+        # 3. Credit the payer wallet and decrement member monthly spent.
+        await wallet_credit.apply_credit(session, payer_id, cost_micros)
+        credit_svc = WorkspaceCreditService(session=session)
+        await credit_svc.refund_member_spend(
+            workspace_id=workspace_id,
+            user_id=payer_id,
+            amount_micros=cost_micros,
+        )
+
+        # 4. Persist the refund billing event (negative cost).
+        event = BillingEvent(
+            workspace_id=workspace_id,
+            client_id=client_id,
+            user_id=payer_id,
+            event_entity_type="verified_contact",
+            event_type="contact_unlock_refund",
+            event_id=verified_contact_id,
+            cost_micros=-cost_micros,
+            currency="USD",
+            cost_basis="actual",
+        )
+        session.add(event)
+        return event
+
     async def record_contact_enrichment(
         self,
         session: AsyncSession,
diff --git a/nowing_backend/app/services/export_service.py b/nowing_backend/app/services/export_service.py
index 5dd9f49b9..d17accf16 100644
--- a/nowing_backend/app/services/export_service.py
+++ b/nowing_backend/app/services/export_service.py
@@ -613,25 +613,37 @@ def mask_email(email: str | None) -> str:
     return f"{username[0]}***@{domain}"
 
 
+def mask_name(name: str | None) -> str:
+    """Mask a personal/company name for PII redaction."""
+    if not name:
+        return ""
+    clean = str(name).strip()
+    if len(clean) <= 3:
+        return clean
+    return f"{clean[0]}***{clean[-1]}"
+
+
 class ExportService:
     """Lead Export Service for CSV, Lark Base, and Google Sheets format conversion (Story 21.13)."""
 
     def generate_csv(self, leads: list[Any], mask_pii: bool = False) -> str:
         output = io.StringIO()
         writer = csv.writer(output)
-        writer.writerow([
-            "Company Name",
-            "Domain",
-            "Source",
-            "Industry",
-            "Location",
-            "Fit Score",
-            "Status",
-            "Contact Name",
-            "Contact Title",
-            "Email",
-            "Phone",
-        ])
+        writer.writerow(
+            [
+                "Company Name",
+                "Domain",
+                "Source",
+                "Industry",
+                "Location",
+                "Fit Score",
+                "Status",
+                "Contact Name",
+                "Contact Title",
+                "Email",
+                "Phone",
+            ]
+        )
 
         for lead in leads:
             contacts = getattr(lead, "verified_contacts", None) or []
@@ -645,19 +657,21 @@ class ExportService:
                 email = mask_email(email)
                 phone = mask_phone(phone)
 
-            writer.writerow([
-                getattr(lead, "company_name", "") or "",
-                getattr(lead, "domain", "") or "",
-                getattr(lead, "source", "") or "",
-                getattr(lead, "industry", "") or "",
-                getattr(lead, "location", "") or "",
-                getattr(lead, "fit_score", 0.0) or 0.0,
-                getattr(lead, "status", "") or "",
-                name,
-                title,
-                email,
-                phone,
-            ])
+            writer.writerow(
+                [
+                    getattr(lead, "company_name", "") or "",
+                    getattr(lead, "domain", "") or "",
+                    getattr(lead, "source", "") or "",
+                    getattr(lead, "industry", "") or "",
+                    getattr(lead, "location", "") or "",
+                    getattr(lead, "fit_score", 0.0) or 0.0,
+                    getattr(lead, "status", "") or "",
+                    name,
+                    title,
+                    email,
+                    phone,
+                ]
+            )
 
         return output.getvalue()
 
@@ -677,21 +691,23 @@ class ExportService:
                 email = mask_email(email)
                 phone = mask_phone(phone)
 
-            records.append({
-                "fields": {
-                    "Company Name": getattr(lead, "company_name", "") or "",
-                    "Domain": getattr(lead, "domain", "") or "",
-                    "Source": getattr(lead, "source", "") or "",
-                    "Industry": getattr(lead, "industry", "") or "",
-                    "Location": getattr(lead, "location", "") or "",
-                    "Fit Score": float(getattr(lead, "fit_score", 0.0) or 0.0),
-                    "Status": getattr(lead, "status", "") or "",
-                    "Contact Name": name,
-                    "Contact Title": title,
-                    "Email": email,
-                    "Phone": phone,
+            records.append(
+                {
+                    "fields": {
+                        "Company Name": getattr(lead, "company_name", "") or "",
+                        "Domain": getattr(lead, "domain", "") or "",
+                        "Source": getattr(lead, "source", "") or "",
+                        "Industry": getattr(lead, "industry", "") or "",
+                        "Location": getattr(lead, "location", "") or "",
+                        "Fit Score": float(getattr(lead, "fit_score", 0.0) or 0.0),
+                        "Status": getattr(lead, "status", "") or "",
+                        "Contact Name": name,
+                        "Contact Title": title,
+                        "Email": email,
+                        "Phone": phone,
+                    }
                 }
-            })
+            )
         return records
 
     def prepare_google_sheets_rows(
@@ -724,17 +740,19 @@ class ExportService:
                 email = mask_email(email)
                 phone = mask_phone(phone)
 
-            rows.append([
-                getattr(lead, "company_name", "") or "",
-                getattr(lead, "domain", "") or "",
-                getattr(lead, "source", "") or "",
-                getattr(lead, "industry", "") or "",
-                getattr(lead, "location", "") or "",
-                float(getattr(lead, "fit_score", 0.0) or 0.0),
-                getattr(lead, "status", "") or "",
-                name,
-                title,
-                email,
-                phone,
-            ])
+            rows.append(
+                [
+                    getattr(lead, "company_name", "") or "",
+                    getattr(lead, "domain", "") or "",
+                    getattr(lead, "source", "") or "",
+                    getattr(lead, "industry", "") or "",
+                    getattr(lead, "location", "") or "",
+                    float(getattr(lead, "fit_score", 0.0) or 0.0),
+                    getattr(lead, "status", "") or "",
+                    name,
+                    title,
+                    email,
+                    phone,
+                ]
+            )
         return rows
diff --git a/nowing_backend/app/services/lead_batch_service.py b/nowing_backend/app/services/lead_batch_service.py
index 97198eda2..aafa32ea3 100644
--- a/nowing_backend/app/services/lead_batch_service.py
+++ b/nowing_backend/app/services/lead_batch_service.py
@@ -20,7 +20,9 @@ from sqlalchemy.sql import func
 from app.config import config
 from app.db import Lead, VerifiedContact
 from app.lead_intelligence.dnc.normalizer import (
-    hash_phone_hmac,
+    compute_email_hmac,
+    compute_phone_hmac,
+    compute_verified_contact_hmac,
     normalize_domain,
     normalize_email,
     normalize_phone_e164,
@@ -104,8 +106,7 @@ def _build_batch_upsert_stmt(leads: list[dict[str, Any]]) -> Any:
     # ``verified_contacts``.
     lead_columns = set(Lead.__table__.columns.keys())
     lead_rows = [
-        {k: v for k, v in lead.items() if k in lead_columns}
-        for lead in sorted_leads
+        {k: v for k, v in lead.items() if k in lead_columns} for lead in sorted_leads
     ]
 
     stmt = pg_insert(Lead).values(lead_rows)
@@ -195,11 +196,9 @@ class LeadBatchService:
             if not any([lead.get("phone"), lead.get("email")]):
                 continue
 
-            norm_phone = normalize_phone_e164(lead.get("phone")) or ""
-            norm_email = normalize_email(lead.get("email")) or ""
-            contact_hmac = hash_phone_hmac(
-                f"{norm_phone}|{norm_email}",
-                secret_key=config.SECRET_KEY,
+            domain = lead.get("domain")
+            contact_hmac = compute_verified_contact_hmac(
+                lead.get("phone"), lead.get("email"), domain
             )
 
             contact = {
@@ -207,8 +206,10 @@ class LeadBatchService:
                 "workspace_id": workspace_id,
                 "client_id": lead.get("client_id"),
                 "lead_id": lead_id,
-                "name": self._cipher.encrypt(lead.get("company_name")),
-                "title": None,
+                "name": self._cipher.encrypt(
+                    lead.get("contact_name") or lead.get("company_name")
+                ),
+                "title": self._cipher.encrypt(lead.get("title")),
                 "email": self._cipher.encrypt(lead.get("email")),
                 "phone": self._cipher.encrypt(lead.get("phone")),
                 "verification_status": "verified",
@@ -221,6 +222,10 @@ class LeadBatchService:
                 "is_unlocked": False,
                 "pii_access_audit_logs": [],
                 "value_hmac": contact_hmac,
+                "phone_hmac": compute_phone_hmac(
+                    normalize_phone_e164(lead.get("phone"))
+                ),
+                "email_hmac": compute_email_hmac(normalize_email(lead.get("email"))),
             }
             contacts_to_insert.append(contact)
 
@@ -230,8 +235,11 @@ class LeadBatchService:
                 index_elements=["workspace_id", "value_hmac"],
                 set_={
                     "name": contact_stmt.excluded.name,
+                    "title": contact_stmt.excluded.title,
                     "email": contact_stmt.excluded.email,
                     "phone": contact_stmt.excluded.phone,
+                    "phone_hmac": contact_stmt.excluded.phone_hmac,
+                    "email_hmac": contact_stmt.excluded.email_hmac,
                 },
             )
             await session.execute(contact_upsert)
diff --git a/nowing_backend/app/services/phone_waterfall_service.py b/nowing_backend/app/services/phone_waterfall_service.py
index faaea17a0..24affb79e 100644
--- a/nowing_backend/app/services/phone_waterfall_service.py
+++ b/nowing_backend/app/services/phone_waterfall_service.py
@@ -32,6 +32,10 @@ from app.db import (
     PhoneWaterfallLog,
     VerifiedContact,
 )
+from app.lead_intelligence.dnc.normalizer import (
+    compute_phone_hmac,
+    compute_verified_contact_hmac,
+)
 from app.proprietary.platforms.batdongsan.fetch import fetch_detail_phone
 from app.proprietary.platforms.chotot.fetch import fetch_phone as chotot_fetch_phone
 from app.proprietary.platforms.xactions.phone_extractor import (
@@ -189,17 +193,7 @@ def mask_phone(phone: str | None) -> str:
 
 def hash_phone(phone: str | None) -> str | None:
     """Compute HMAC-SHA256 hex digest of canonical E.164 phone for DNC/cache alignment."""
-    if not phone:
-        return None
-    from app.lead_intelligence.dnc.normalizer import (
-        hash_phone_hmac,
-        normalize_phone_e164,
-    )
-
-    e164 = normalize_phone_e164(phone)
-    if not e164:
-        return None
-    return hash_phone_hmac(e164, config.SECRET_KEY)
+    return compute_phone_hmac(phone)
 
 
 @dataclass
@@ -863,8 +857,8 @@ class PhoneWaterfallService:
             client_id=client_id,
             lead_id=lead_id,
             enrichment_request_id=None,
-            name=lead.company_name,
-            title="Lead Contact",
+            name=self.encryption.encrypt(lead.company_name or "Doanh nghiep"),
+            title=self.encryption.encrypt("Lead Contact"),
             email=None,
             phone=encrypted_phone,  # Encrypted at rest in vault
             verification_status="verified",
@@ -874,6 +868,9 @@ class PhoneWaterfallService:
             consent_status="legitimate_interest",
             legal_basis="legitimate_interest",
             is_valid=True,
+            value_hmac=compute_verified_contact_hmac(norm_phone, None, lead.domain),
+            phone_hmac=compute_phone_hmac(norm_phone),
+            email_hmac=None,
         )
         self.session.add(contact)
         await self.session.flush()
@@ -929,9 +926,7 @@ class PhoneWaterfallService:
                     self.session, user_id, PHONE_RESOLUTION_COST_MICROS
                 )
             except wallet_credit.InsufficientCreditsError as ice:
-                logger.warning(
-                    "Wallet ran out of credits during final debit: %s", ice
-                )
+                logger.warning("Wallet ran out of credits during final debit: %s", ice)
                 return PhoneResolutionResult(
                     lead_id=lead_id,
                     phone=None,
diff --git a/nowing_backend/app/services/pii/opt_out_service.py b/nowing_backend/app/services/pii/opt_out_service.py
new file mode 100644
index 000000000..218efbea7
--- /dev/null
+++ b/nowing_backend/app/services/pii/opt_out_service.py
@@ -0,0 +1,360 @@
+"""PII opt-out / Right-to-be-Forgotten service (Story 26.4)."""
+
+from __future__ import annotations
+
+from dataclasses import dataclass
+from datetime import UTC, datetime
+from uuid import UUID, uuid4
+
+from sqlalchemy import select
+from sqlalchemy.ext.asyncio import AsyncSession
+
+from app.config import config
+from app.db import (
+    BillingEvent,
+    GlobalDncRecord,
+    VerifiedContact,
+    WorkspaceDncRecord,
+)
+from app.lead_intelligence.dnc.normalizer import (
+    compute_email_hmac,
+    compute_phone_hmac,
+    normalize_email,
+    normalize_phone_e164,
+)
+from app.lead_intelligence.dnc.service import DncComplianceService
+from app.services import wallet_credit
+from app.services.workspace_credit_service import WorkspaceCreditService
+
+_REFUND_AMOUNT_MICROS = 1_500
+
+
+@dataclass
+class OptOutResult:
+    """Result of a PII opt-out request."""
+
+    purged_contact_count: int
+    refunded_micros: int
+    dnc_record_id: UUID | None = None
+
+
+def _anonymize_contact(contact: VerifiedContact) -> None:
+    """Irreversibly purge PII fields and mark consent as withdrawn."""
+    contact.name = None
+    contact.title = None
+    contact.email = None
+    contact.phone = None
+    contact.phone_hmac = None
+    contact.email_hmac = None
+    contact.is_unlocked = False
+    contact.consent = False
+    contact.consent_status = "withdrawn"
+    contact.legal_basis = "opt_out"
+
+
+def _append_opt_out_audit_log(
+    contact: VerifiedContact,
+    *,
+    actor_id: UUID,
+    ip_address: str | None,
+    reason: str | None,
+) -> None:
+    if contact.pii_access_audit_logs is None:
+        contact.pii_access_audit_logs = []
+    contact.pii_access_audit_logs.append(
+        {
+            "access_type": "opt_out_purged",
+            "actor_id": str(actor_id),
+            "timestamp": datetime.now(UTC).isoformat(),
+            "ip_address": ip_address,
+            "reason": reason or "Right to be forgotten",
+        }
+    )
+
+
+async def _find_original_unlock_billing_event(
+    session: AsyncSession,
+    verified_contact_id: UUID,
+    workspace_id: int,
+) -> BillingEvent | None:
+    """Return the original contact_unlock BillingEvent for a contact."""
+    result = await session.execute(
+        select(BillingEvent).where(
+            BillingEvent.workspace_id == workspace_id,
+            BillingEvent.event_entity_type == "verified_contact",
+            BillingEvent.event_type == "contact_unlock",
+            BillingEvent.event_id == verified_contact_id,
+        )
+    )
+    event = result.scalar_one_or_none()
+    if getattr(event, "event_type", None) != "contact_unlock":
+        return None
+    return event
+
+
+async def _count_refundable_unlocks_this_cycle(
+    session: AsyncSession,
+    workspace_id: int,
+    cost_micros: int = _REFUND_AMOUNT_MICROS,
+) -> int:
+    """Remaining contact-unlock refund slots for this workspace in the current cycle.
+
+    Cap = 15% of total unlocked contacts. The cycle is monthly; for simplicity we
+    count refund events in the current calendar month.
+    """
+    if cost_micros <= 0:
+        return 0
+
+    total_unlocked = len(
+        [
+            c
+            for c in (
+                await session.execute(
+                    select(VerifiedContact).where(
+                        VerifiedContact.workspace_id == workspace_id,
+                        VerifiedContact.is_unlocked.is_(True),
+                    )
+                )
+            )
+            .scalars()
+            .all()
+            if getattr(c, "is_unlocked", False)
+        ]
+    )
+
+    allowed = max(1, int(total_unlocked * 0.15))
+
+    now = datetime.now(UTC)
+    already_refunded = len(
+        [
+            e
+            for e in (
+                await session.execute(
+                    select(BillingEvent).where(
+                        BillingEvent.workspace_id == workspace_id,
+                        BillingEvent.event_entity_type == "verified_contact",
+                        BillingEvent.event_type == "contact_unlock_refund",
+                        BillingEvent.created_at
+                        >= datetime(now.year, now.month, 1, tzinfo=UTC),
+                    )
+                )
+            )
+            .scalars()
+            .all()
+            if getattr(e, "event_type", None) == "contact_unlock_refund"
+        ]
+    )
+
+    return max(0, allowed - already_refunded)
+
+
+async def _credit_user_wallet(
+    session: AsyncSession,
+    user_id: UUID,
+    amount_micros: int,
+) -> None:
+    """Credit a user wallet for an opt-out refund."""
+    await wallet_credit.apply_credit(session, user_id, amount_micros)
+
+
+async def _decrement_member_monthly_spent(
+    session: AsyncSession,
+    *,
+    workspace_id: int,
+    user_id: UUID,
+    amount_micros: int,
+) -> None:
+    """Decrement the member's monthly spent counter without touching workspace balance."""
+    credit_svc = WorkspaceCreditService(session=session)
+    await credit_svc.refund_member_spend(
+        workspace_id=workspace_id,
+        user_id=user_id,
+        amount_micros=amount_micros,
+    )
+
+
+class OptOutService:
+    """Process PII opt-out requests per PDPD Decree 13/2023/ND-CP."""
+
+    def __init__(self, session: AsyncSession) -> None:
+        self.session = session
+
+    async def _refund_credit(
+        self,
+        contact: VerifiedContact,
+        original_event: BillingEvent,
+        workspace_id: int,
+    ) -> int:
+        """Refund one contact unlock and return refunded micros."""
+        payer_id = original_event.user_id
+        if payer_id is None:
+            # Fallback to the actor; should not happen for valid unlock events.
+            return 0
+
+        await _credit_user_wallet(self.session, payer_id, _REFUND_AMOUNT_MICROS)
+        await _decrement_member_monthly_spent(
+            self.session,
+            workspace_id=workspace_id,
+            user_id=payer_id,
+            amount_micros=_REFUND_AMOUNT_MICROS,
+        )
+
+        event = BillingEvent(
+            workspace_id=workspace_id,
+            user_id=payer_id,
+            event_entity_type="verified_contact",
+            event_type="contact_unlock_refund",
+            event_id=contact.id,
+            cost_micros=-_REFUND_AMOUNT_MICROS,
+            currency="USD",
+            cost_basis="actual",
+        )
+        self.session.add(event)
+        return _REFUND_AMOUNT_MICROS
+
+    async def _ensure_dnc_record(
+        self,
+        *,
+        workspace_id: int,
+        record_type: str,
+        value: str,
+        value_hmac: str,
+        reason: str | None,
+        global_scope: bool,
+    ) -> WorkspaceDncRecord | GlobalDncRecord:
+        if global_scope:
+            # Global opt-out requires superadmin scope; store globally.
+            record = GlobalDncRecord(
+                id=uuid4(),
+                record_type=record_type,
+                value=value,
+                value_hmac=value_hmac,
+                reason=reason or "Right to be forgotten",
+                source="opt_out",
+            )
+            self.session.add(record)
+            return record
+
+        existing = (
+            await self.session.execute(
+                select(WorkspaceDncRecord).where(
+                    WorkspaceDncRecord.workspace_id == workspace_id,
+                    WorkspaceDncRecord.record_type == record_type,
+                    WorkspaceDncRecord.value_hmac == value_hmac,
+                )
+            )
+        ).scalar_one_or_none()
+        if existing is not None:
+            existing.reason = reason or "Right to be forgotten"
+            existing.source = "opt_out"
+            return existing
+
+        record = WorkspaceDncRecord(
+            id=uuid4(),
+            workspace_id=workspace_id,
+            record_type=record_type,
+            value=value,
+            value_hmac=value_hmac,
+            reason=reason or "Right to be forgotten",
+            source="opt_out",
+        )
+        self.session.add(record)
+        return record
+
+    async def process_opt_out(
+        self,
+        *,
+        workspace_id: int,
+        record_type: str,
+        value: str,
+        actor_user_id: UUID,
+        ip_address: str | None = None,
+        global_scope: bool = False,
+    ) -> OptOutResult:
+        """Process a PII opt-out request.
+
+        1. Upsert a DNC record for the requested value.
+        2. Find all matching verified contacts via blind HMAC index.
+        3. Purge PII from each contact and append an audit log.
+        4. Refund 1,500 micros for each unlocked contact up to the 15% cap.
+        5. Invalidate DNC cache.
+        """
+        if record_type == "phone":
+            e164 = normalize_phone_e164(value)
+            if not e164:
+                raise ValueError(f"Invalid phone format: {value}")
+            value_hmac = compute_phone_hmac(e164)
+        elif record_type == "email":
+            norm_email = normalize_email(value)
+            if not norm_email:
+                raise ValueError(f"Invalid email format: {value}")
+            value_hmac = compute_email_hmac(norm_email)
+        else:
+            raise ValueError(f"Unsupported opt-out record type: {record_type}")
+
+        dnc_record = await self._ensure_dnc_record(
+            workspace_id=workspace_id,
+            record_type=record_type,
+            value=e164 if record_type == "phone" else norm_email,
+            value_hmac=value_hmac,
+            reason="Right to be forgotten",
+            global_scope=global_scope,
+        )
+
+        if record_type == "phone":
+            match_clause = VerifiedContact.phone_hmac == value_hmac
+        else:
+            match_clause = VerifiedContact.email_hmac == value_hmac
+
+        contacts = (
+            (
+                await self.session.execute(
+                    select(VerifiedContact).where(
+                        VerifiedContact.workspace_id == workspace_id,
+                        match_clause,
+                    )
+                )
+            )
+            .scalars()
+            .all()
+        )
+
+        refundable_slots = await _count_refundable_unlocks_this_cycle(
+            self.session, workspace_id
+        )
+
+        purged_count = 0
+        refunded_micros = 0
+        for contact in contacts:
+            was_unlocked = bool(contact.is_unlocked)
+
+            if was_unlocked and refundable_slots > 0:
+                original_event = await _find_original_unlock_billing_event(
+                    self.session, contact.id, workspace_id
+                )
+                if original_event is not None:
+                    await self._refund_credit(contact, original_event, workspace_id)
+                    refunded_micros += _REFUND_AMOUNT_MICROS
+                    refundable_slots -= 1
+
+            _anonymize_contact(contact)
+            _append_opt_out_audit_log(
+                contact,
+                actor_id=actor_user_id,
+                ip_address=ip_address,
+                reason="Right to be forgotten",
+            )
+            purged_count += 1
+
+        if not global_scope:
+            dnc_service = DncComplianceService(secret_key=config.SECRET_KEY)
+            await dnc_service.invalidate_workspace_cache(workspace_id)
+        else:
+            dnc_service = DncComplianceService(secret_key=config.SECRET_KEY)
+            await dnc_service.invalidate_global_cache()
+
+        return OptOutResult(
+            purged_contact_count=purged_count,
+            refunded_micros=refunded_micros,
+            dnc_record_id=dnc_record.id,
+        )
diff --git a/nowing_backend/app/services/wallet_credit.py b/nowing_backend/app/services/wallet_credit.py
index 880b23c68..87c0ed826 100644
--- a/nowing_backend/app/services/wallet_credit.py
+++ b/nowing_backend/app/services/wallet_credit.py
@@ -24,6 +24,7 @@ from app.services.etl_credit_service import InsufficientCreditsError
 
 __all__ = [
     "InsufficientCreditsError",
+    "apply_credit",
     "apply_debit",
     "check_balance",
     "spendable_micros",
@@ -120,3 +121,29 @@ async def apply_debit(
         pass
 
     return user.credit_micros_balance
+
+
+async def apply_credit(
+    session: AsyncSession, user_id: str | UUID, amount_micros: int
+) -> int | None:
+    """Credit ``amount_micros`` to the wallet and commit.
+
+    No-op for non-positive amounts; returns the new balance, or ``None``.
+    ponytail: SELECT FOR UPDATE keeps the read-modify-write atomic.
+    """
+    if amount_micros <= 0:
+        return None
+
+    from app.db import User
+
+    result = await session.execute(
+        select(User).where(User.id == user_id).with_for_update()
+    )
+    user = result.unique().scalar_one_or_none()
+    if not user:
+        raise ValueError(f"User with ID {user_id} not found")
+
+    user.credit_micros_balance += amount_micros
+    await session.commit()
+    await session.refresh(user)
+    return user.credit_micros_balance
diff --git a/nowing_backend/app/services/workspace_credit_service.py b/nowing_backend/app/services/workspace_credit_service.py
index a63485857..7aab545e0 100644
--- a/nowing_backend/app/services/workspace_credit_service.py
+++ b/nowing_backend/app/services/workspace_credit_service.py
@@ -488,6 +488,82 @@ class WorkspaceCreditService:
             "member_monthly_spent": member_monthly_spent,
         }
 
+    async def refund_member_spend(
+        self,
+        *,
+        workspace_id: int,
+        user_id: UUID,
+        amount_micros: int,
+    ) -> dict[str, Any]:
+        """Decrement a member's monthly spent counter without touching workspace balance."""
+        if amount_micros <= 0:
+            return {
+                "workspace_id": workspace_id,
+                "user_id": user_id,
+                "amount_micros": 0,
+                "member_monthly_spent": 0,
+                "member_monthly_spend_cap": None,
+            }
+
+        # In-memory fake-session path used by unit tests (FakeAsyncSession).
+        if hasattr(self.session, "workspaces") and hasattr(self.session, "memberships"):
+            membership = self.session.memberships.get((workspace_id, user_id))
+            if membership is None:
+                return {
+                    "workspace_id": workspace_id,
+                    "user_id": user_id,
+                    "amount_micros": amount_micros,
+                    "member_monthly_spent": 0,
+                    "member_monthly_spend_cap": None,
+                }
+            current_spent = membership.monthly_spent_micros or 0
+            membership.monthly_spent_micros = max(0, current_spent - amount_micros)
+            return {
+                "workspace_id": workspace_id,
+                "user_id": user_id,
+                "amount_micros": amount_micros,
+                "member_monthly_spent": membership.monthly_spent_micros,
+                "member_monthly_spend_cap": membership.monthly_spend_cap_micros,
+            }
+
+        from sqlalchemy import update
+
+        spend_result = await self.session.execute(
+            update(WorkspaceMembership)
+            .where(
+                WorkspaceMembership.workspace_id == workspace_id,
+                WorkspaceMembership.user_id == user_id,
+            )
+            .values(
+                monthly_spent_micros=func.greatest(
+                    0,
+                    func.coalesce(WorkspaceMembership.monthly_spent_micros, 0)
+                    - amount_micros,
+                ),
+            )
+            .returning(
+                WorkspaceMembership.monthly_spend_cap_micros,
+                WorkspaceMembership.monthly_spent_micros,
+            )
+        )
+        spend_row = spend_result.one_or_none()
+        if spend_row is None:
+            return {
+                "workspace_id": workspace_id,
+                "user_id": user_id,
+                "amount_micros": amount_micros,
+                "member_monthly_spent": 0,
+                "member_monthly_spend_cap": None,
+            }
+        returned_cap, returned_spent = spend_row
+        return {
+            "workspace_id": workspace_id,
+            "user_id": user_id,
+            "amount_micros": amount_micros,
+            "member_monthly_spent": returned_spent,
+            "member_monthly_spend_cap": returned_cap,
+        }
+
     async def set_member_spend_cap(
         self,
         *,
diff --git a/nowing_backend/tests/integration/lead_batch/test_contact_unlock_decryption.py b/nowing_backend/tests/integration/lead_batch/test_contact_unlock_decryption.py
new file mode 100644
index 000000000..66d6c39f2
--- /dev/null
+++ b/nowing_backend/tests/integration/lead_batch/test_contact_unlock_decryption.py
@@ -0,0 +1,163 @@
+"""Integration tests for contact unlock PII response and masking (Story 26.4)."""
+
+from __future__ import annotations
+
+import pytest
+from sqlalchemy import select
+
+from app.db import BillingEvent, Lead, VerifiedContact
+from app.services.pii.verified_contact_encryption import VerifiedContactEncryption
+
+pytestmark = [pytest.mark.integration]
+
+
+def _encrypt(value: str) -> str:
+    return VerifiedContactEncryption().encrypt(value)
+
+
+@pytest.mark.asyncio
+async def test_unlock_returns_decrypted_phone_and_email(
+    client, db_user, db_workspace, db_session
+):
+    """Pattern 1/6: unlock response contains decrypted PII only after billing."""
+    db_user.credit_micros_balance = 5_000
+    db_user.credit_micros_reserved = 0
+    await db_session.flush()
+
+    lead = Lead(
+        workspace_id=db_workspace.id,
+        company_name="Acme",
+        domain="acme.com",
+        value_hmac="lead-hmac",
+        source="test",
+    )
+    db_session.add(lead)
+    await db_session.flush()
+
+    phone = "+84908123456"
+    email = "alice@acme.com"
+    contact = VerifiedContact(
+        workspace_id=db_workspace.id,
+        lead_id=lead.id,
+        name=_encrypt("Alice"),
+        title=_encrypt("CEO"),
+        phone=_encrypt(phone),
+        email=_encrypt(email),
+        phone_hmac="phone-hash",
+        email_hmac="email-hash",
+        value_hmac="contact-hmac",
+        is_unlocked=False,
+        pii_access_audit_logs=[],
+    )
+    db_session.add(contact)
+    await db_session.flush()
+
+    resp = await client.post(
+        f"/api/v1/workspaces/{db_workspace.id}/leads/{lead.id}/contacts/{contact.id}/unlock"
+    )
+    assert resp.status_code == 200
+    body = resp.json()
+    assert body["is_unlocked"] is True
+    assert body["cost_micros"] == 1500
+    assert body["phone"] == phone
+    assert body["email"] == email
+
+    billing_event = (
+        await db_session.execute(
+            select(BillingEvent).where(
+                BillingEvent.workspace_id == db_workspace.id,
+                BillingEvent.event_type == "contact_unlock",
+            )
+        )
+    ).scalar_one_or_none()
+    assert billing_event is not None
+    assert billing_event.user_id == db_user.id
+
+
+@pytest.mark.asyncio
+async def test_unlock_does_not_leak_decrypted_pii_when_billing_fails(
+    client, db_user, db_workspace, db_session
+):
+    """Pattern 2/5: insufficient credits → 402 and no PII in response."""
+    db_user.credit_micros_balance = 0
+    db_user.credit_micros_reserved = 0
+    await db_session.flush()
+
+    lead = Lead(
+        workspace_id=db_workspace.id,
+        company_name="Acme",
+        domain="acme.com",
+        value_hmac="lead-hmac",
+        source="test",
+    )
+    db_session.add(lead)
+    await db_session.flush()
+
+    contact = VerifiedContact(
+        workspace_id=db_workspace.id,
+        lead_id=lead.id,
+        name=_encrypt("Alice"),
+        phone=_encrypt("+84908123456"),
+        email=_encrypt("alice@acme.com"),
+        phone_hmac="phone-hash",
+        email_hmac="email-hash",
+        value_hmac="contact-hmac",
+        is_unlocked=False,
+        pii_access_audit_logs=[],
+    )
+    db_session.add(contact)
+    await db_session.flush()
+
+    resp = await client.post(
+        f"/api/v1/workspaces/{db_workspace.id}/leads/{lead.id}/contacts/{contact.id}/unlock"
+    )
+    assert resp.status_code == 402
+    assert "phone" not in resp.json()
+    assert "email" not in resp.json()
+
+
+@pytest.mark.asyncio
+async def test_lead_list_masks_unlocked_false_contacts(
+    client, db_user, db_workspace, db_session
+):
+    """Pattern 1/6: lead list returns masked PII when contact is not unlocked."""
+    lead = Lead(
+        workspace_id=db_workspace.id,
+        company_name="Acme",
+        domain="acme.com",
+        value_hmac="lead-hmac",
+        source="test",
+    )
+    db_session.add(lead)
+    await db_session.flush()
+
+    contact = VerifiedContact(
+        workspace_id=db_workspace.id,
+        lead_id=lead.id,
+        name=_encrypt("Alice Nguyen"),
+        title=_encrypt("CEO"),
+        phone=_encrypt("+84908123456"),
+        email=_encrypt("alice@acme.com"),
+        phone_hmac="phone-hash",
+        email_hmac="email-hash",
+        value_hmac="contact-hmac",
+        is_unlocked=False,
+        pii_access_audit_logs=[],
+    )
+    db_session.add(contact)
+    await db_session.flush()
+
+    resp = await client.get(
+        f"/api/v1/workspaces/{db_workspace.id}/leads",
+    )
+    assert resp.status_code == 200
+    body = resp.json()
+    lead_item = next(
+        (item for item in body["items"] if item["id"] == str(lead.id)), None
+    )
+    assert lead_item is not None
+    # Masked phone and email; exact mask format depends on mask_phone/mask_email.
+    assert "***" in lead_item["phone"]
+    assert "***" in lead_item["email"]
+    # Name should not be the full plaintext.
+    assert lead_item["name"] != "Alice Nguyen"
diff --git a/nowing_backend/tests/integration/routes/conftest.py b/nowing_backend/tests/integration/routes/conftest.py
index e9c3c6578..6098e647d 100644
--- a/nowing_backend/tests/integration/routes/conftest.py
+++ b/nowing_backend/tests/integration/routes/conftest.py
@@ -127,3 +127,49 @@ async def pat_client(
     finally:
         app.dependency_overrides.clear()
         app.dependency_overrides.update(previous_overrides)
+
+
+@pytest_asyncio.fixture
+async def db_other_user(db_session: AsyncSession) -> User:
+    """A user who is not a member of the test workspace."""
+    user = User(
+        id=uuid4(),
+        email="other@nowing.net",
+        hashed_password="hashed",
+        is_active=True,
+        is_superuser=False,
+        is_verified=True,
+    )
+    db_session.add(user)
+    await db_session.flush()
+    return user
+
+
+@pytest_asyncio.fixture
+async def client_as_other(
+    db_session: AsyncSession,
+    db_other_user: User,
+) -> AsyncGenerator[httpx.AsyncClient, None]:
+    """Authenticated as a non-member user."""
+
+    async def override_session() -> AsyncGenerator[AsyncSession, None]:
+        yield db_session
+
+    async def override_auth() -> AuthContext:
+        return AuthContext.session(db_other_user)
+
+    previous_overrides = app.dependency_overrides.copy()
+    app.dependency_overrides[get_async_session] = override_session
+    app.dependency_overrides[get_auth_context] = override_auth
+
+    try:
+        async with httpx.AsyncClient(
+            transport=ASGITransport(app=app),
+            base_url="http://test",
+            timeout=30.0,
+            follow_redirects=False,
+        ) as test_client:
+            yield test_client
+    finally:
+        app.dependency_overrides.clear()
+        app.dependency_overrides.update(previous_overrides)
diff --git a/nowing_backend/tests/integration/routes/test_pii_opt_out.py b/nowing_backend/tests/integration/routes/test_pii_opt_out.py
new file mode 100644
index 000000000..3f65f083d
--- /dev/null
+++ b/nowing_backend/tests/integration/routes/test_pii_opt_out.py
@@ -0,0 +1,296 @@
+"""Integration tests for PII opt-out route (Story 26.4)."""
+
+from __future__ import annotations
+
+from datetime import UTC, datetime
+
+import pytest
+from sqlalchemy import select
+
+from app.db import (
+    BillingEvent,
+    Lead,
+    User,
+    VerifiedContact,
+    WorkspaceDncRecord,
+    WorkspaceMembership,
+)
+from app.lead_intelligence.dnc.normalizer import (
+    hash_phone_hmac,
+    normalize_email,
+    normalize_phone_e164,
+)
+from app.services.pii.verified_contact_encryption import VerifiedContactEncryption
+
+pytestmark = [pytest.mark.integration]
+
+
+def _encrypt(value: str) -> str:
+    return VerifiedContactEncryption().encrypt(value)
+
+
+def _phone_hash(phone: str) -> str:
+    e164 = normalize_phone_e164(phone)
+    assert e164
+    return hash_phone_hmac(e164)
+
+
+def _email_hash(email: str) -> str:
+    norm = normalize_email(email)
+    assert norm
+    return hash_phone_hmac(norm)
+
+
+@pytest.mark.asyncio
+async def test_opt_out_purges_and_refunds_unlocked_contact(
+    client_as_regular_user, db_user, db_workspace, db_session
+):
+    """Pattern 1/4/6: opt-out purges PII, refunds credit, writes DNC + BillingEvent."""
+    db_user.credit_micros_balance = 5_000
+    db_user.credit_micros_reserved = 0
+    await db_session.flush()
+
+    lead = Lead(
+        workspace_id=db_workspace.id,
+        company_name="Acme",
+        domain="acme.com",
+        value_hmac="lead-hmac",
+        source="test",
+    )
+    db_session.add(lead)
+    await db_session.flush()
+
+    phone = "+84908123456"
+    email = "alice@acme.com"
+    contact = VerifiedContact(
+        workspace_id=db_workspace.id,
+        lead_id=lead.id,
+        name=_encrypt("Alice"),
+        title=_encrypt("CEO"),
+        phone=_encrypt(phone),
+        email=_encrypt(email),
+        phone_hmac=_phone_hash(phone),
+        email_hmac=_email_hash(email),
+        value_hmac="contact-hmac",
+        is_unlocked=False,
+        consent=True,
+        consent_status="opted_in",
+        legal_basis="consent",
+        pii_access_audit_logs=[],
+    )
+    db_session.add(contact)
+    await db_session.flush()
+
+    # Unlock first so there is a BillingEvent to refund.
+    resp = await client_as_regular_user.post(
+        f"/api/v1/workspaces/{db_workspace.id}/leads/{lead.id}/contacts/{contact.id}/unlock"
+    )
+    assert resp.status_code == 200
+    body = resp.json()
+    assert body["cost_micros"] == 1500
+
+    user_before = await db_session.get(User, db_user.id)
+    assert user_before.credit_micros_balance == 3500
+
+    resp = await client_as_regular_user.post(
+        f"/api/v1/workspaces/{db_workspace.id}/pii-opt-out",
+        json={
+            "record_type": "phone",
+            "value": phone,
+            "reason": "Right to be forgotten",
+        },
+    )
+    assert resp.status_code == 200
+    body = resp.json()
+    assert body["purged_contact_count"] == 1
+    assert body["refunded_micros"] == 1500
+    assert body["dnc_record_id"]
+
+    # DB state
+    refreshed = (
+        await db_session.execute(
+            select(VerifiedContact).where(VerifiedContact.id == contact.id)
+        )
+    ).scalar_one()
+    assert refreshed.is_unlocked is False
+    assert refreshed.consent is False
+    assert refreshed.consent_status == "withdrawn"
+    assert refreshed.legal_basis == "opt_out"
+    assert refreshed.name is None
+    assert refreshed.title is None
+    assert refreshed.phone is None
+    assert refreshed.email is None
+    assert any(
+        log.get("access_type") == "opt_out_purged"
+        for log in refreshed.pii_access_audit_logs
+    )
+
+    user_after = await db_session.get(User, db_user.id)
+    assert user_after.credit_micros_balance == 5000
+
+    membership = (
+        await db_session.execute(
+            select(WorkspaceMembership).where(
+                WorkspaceMembership.workspace_id == db_workspace.id,
+                WorkspaceMembership.user_id == db_user.id,
+            )
+        )
+    ).scalar_one()
+    assert membership.monthly_spent_micros == 0
+
+    refund_event = (
+        await db_session.execute(
+            select(BillingEvent).where(
+                BillingEvent.workspace_id == db_workspace.id,
+                BillingEvent.event_type == "contact_unlock_refund",
+            )
+        )
+    ).scalar_one_or_none()
+    assert refund_event is not None
+    assert refund_event.cost_micros == -1500
+    assert refund_event.user_id == db_user.id
+
+    dnc_record = (
+        await db_session.execute(
+            select(WorkspaceDncRecord).where(
+                WorkspaceDncRecord.workspace_id == db_workspace.id,
+                WorkspaceDncRecord.record_type == "phone",
+                WorkspaceDncRecord.value_hmac == _phone_hash(phone),
+            )
+        )
+    ).scalar_one_or_none()
+    assert dnc_record is not None
+    assert dnc_record.source == "opt_out"
+
+
+@pytest.mark.asyncio
+async def test_opt_out_without_unlocked_contact_refunds_zero(
+    client_as_regular_user, db_user, db_workspace, db_session
+):
+    """Pattern 3/6: contact never unlocked → purge but no refund."""
+    lead = Lead(
+        workspace_id=db_workspace.id,
+        company_name="Acme",
+        domain="acme.com",
+        value_hmac="lead-hmac",
+        source="test",
+    )
+    db_session.add(lead)
+    await db_session.flush()
+
+    phone = "+84908123456"
+    contact = VerifiedContact(
+        workspace_id=db_workspace.id,
+        lead_id=lead.id,
+        name=_encrypt("Alice"),
+        phone=_encrypt(phone),
+        email=None,
+        phone_hmac=_phone_hash(phone),
+        email_hmac=None,
+        value_hmac="contact-hmac",
+        is_unlocked=False,
+        pii_access_audit_logs=[],
+    )
+    db_session.add(contact)
+    await db_session.flush()
+
+    resp = await client_as_regular_user.post(
+        f"/api/v1/workspaces/{db_workspace.id}/pii-opt-out",
+        json={
+            "record_type": "phone",
+            "value": phone,
+            "reason": "Right to be forgotten",
+        },
+    )
+    assert resp.status_code == 200
+    body = resp.json()
+    assert body["purged_contact_count"] == 1
+    assert body["refunded_micros"] == 0
+
+
+@pytest.mark.asyncio
+async def test_opt_out_respects_15_percent_refund_cap(
+    client_as_regular_user, db_user, db_workspace, db_session
+):
+    """Pattern 4: refund cap exhausted → only purge, no refund."""
+    db_user.credit_micros_balance = 100_000
+    db_user.credit_micros_reserved = 0
+    await db_session.flush()
+
+    lead = Lead(
+        workspace_id=db_workspace.id,
+        company_name="Acme",
+        domain="acme.com",
+        value_hmac="lead-hmac",
+        source="test",
+    )
+    db_session.add(lead)
+    await db_session.flush()
+
+    phone = "+84908123456"
+    contact = VerifiedContact(
+        workspace_id=db_workspace.id,
+        lead_id=lead.id,
+        name=_encrypt("Alice"),
+        phone=_encrypt(phone),
+        email=None,
+        phone_hmac=_phone_hash(phone),
+        email_hmac=None,
+        value_hmac="contact-hmac",
+        is_unlocked=True,
+        pii_access_audit_logs=[],
+    )
+    db_session.add(contact)
+    await db_session.flush()
+
+    # Seed one unlock BillingEvent; pretend 15% cap already reached via a refund event.
+    db_session.add(
+        BillingEvent(
+            workspace_id=db_workspace.id,
+            user_id=db_user.id,
+            event_entity_type="verified_contact",
+            event_type="contact_unlock_refund",
+            event_id=contact.id,
+            cost_micros=-1500,
+            currency="USD",
+            cost_basis="actual",
+            created_at=datetime.now(UTC),
+        )
+    )
+    await db_session.flush()
+
+    resp = await client_as_regular_user.post(
+        f"/api/v1/workspaces/{db_workspace.id}/pii-opt-out",
+        json={
+            "record_type": "phone",
+            "value": phone,
+            "reason": "Right to be forgotten",
+        },
+    )
+    assert resp.status_code == 200
+    body = resp.json()
+    assert body["purged_contact_count"] == 1
+    assert body["refunded_micros"] == 0
+
+
+@pytest.mark.asyncio
+async def test_opt_out_returns_400_for_invalid_phone(
+    client_as_regular_user, db_workspace
+):
+    """Pattern 5: malformed phone returns clear 400."""
+    resp = await client_as_regular_user.post(
+        f"/api/v1/workspaces/{db_workspace.id}/pii-opt-out",
+        json={"record_type": "phone", "value": "not-a-phone"},
+    )
+    assert resp.status_code == 400
+    assert "phone" in resp.json()["detail"].lower()
+
+
+@pytest.mark.asyncio
+async def test_non_member_cannot_opt_out(client_as_other, db_workspace):
+    """Pattern 3: non-member gets 403."""
+    resp = await client_as_other.post(
+        f"/api/v1/workspaces/{db_workspace.id}/pii-opt-out",
+        json={"record_type": "phone", "value": "+84908123456"},
+    )
+    assert resp.status_code == 403
diff --git a/nowing_backend/tests/integration/services/test_pii_opt_out_service.py b/nowing_backend/tests/integration/services/test_pii_opt_out_service.py
new file mode 100644
index 000000000..b92ad7b1c
--- /dev/null
+++ b/nowing_backend/tests/integration/services/test_pii_opt_out_service.py
@@ -0,0 +1,270 @@
+"""Service-level integration tests for PII opt-out (Story 26.4)."""
+
+from __future__ import annotations
+
+import pytest
+from sqlalchemy import select
+
+from app.db import BillingEvent, Lead, User, VerifiedContact, WorkspaceDncRecord
+from app.lead_intelligence.dnc.normalizer import (
+    hash_phone_hmac,
+    normalize_email,
+    normalize_phone_e164,
+)
+from app.services.pii.opt_out_service import OptOutService
+from app.services.pii.verified_contact_encryption import VerifiedContactEncryption
+
+pytestmark = [pytest.mark.integration]
+
+
+def _encrypt(value: str) -> str:
+    return VerifiedContactEncryption().encrypt(value)
+
+
+def _phone_hash(phone: str) -> str:
+    return hash_phone_hmac(normalize_phone_e164(phone))
+
+
+def _email_hash(email: str) -> str:
+    return hash_phone_hmac(normalize_email(email))
+
+
+@pytest.mark.asyncio
+async def test_opt_out_service_finds_contact_by_phone_hmac(
+    db_session, db_user, db_workspace
+):
+    """Pattern 6: blind index lookup works without decrypting entire table."""
+    db_user.credit_micros_balance = 10_000
+    await db_session.flush()
+
+    lead = Lead(
+        workspace_id=db_workspace.id,
+        company_name="Acme",
+        domain="acme.com",
+        value_hmac="lead-hmac",
+        source="test",
+    )
+    db_session.add(lead)
+    await db_session.flush()
+
+    phone = "+84908123456"
+    email = "alice@acme.com"
+    contact = VerifiedContact(
+        workspace_id=db_workspace.id,
+        lead_id=lead.id,
+        name=_encrypt("Alice"),
+        title=_encrypt("CEO"),
+        phone=_encrypt(phone),
+        email=_encrypt(email),
+        phone_hmac=_phone_hash(phone),
+        email_hmac=_email_hash(email),
+        value_hmac="contact-hmac",
+        is_unlocked=False,
+        pii_access_audit_logs=[],
+    )
+    db_session.add(contact)
+    await db_session.flush()
+
+    service = OptOutService(db_session)
+    result = await service.process_opt_out(
+        workspace_id=db_workspace.id,
+        record_type="phone",
+        value=phone,
+        actor_user_id=db_user.id,
+        ip_address="127.0.0.1",
+    )
+
+    assert result.purged_contact_count == 1
+    assert result.dnc_record_id is not None
+
+    dnc_record = (
+        await db_session.execute(
+            select(WorkspaceDncRecord).where(
+                WorkspaceDncRecord.workspace_id == db_workspace.id,
+                WorkspaceDncRecord.record_type == "phone",
+            )
+        )
+    ).scalar_one_or_none()
+    assert dnc_record is not None
+    assert dnc_record.value == normalize_phone_e164(phone)
+
+
+@pytest.mark.asyncio
+async def test_opt_out_service_finds_contact_by_email_hmac(
+    db_session, db_user, db_workspace
+):
+    """Pattern 6: email blind index also matches."""
+    lead = Lead(
+        workspace_id=db_workspace.id,
+        company_name="Acme",
+        domain="acme.com",
+        value_hmac="lead-hmac",
+        source="test",
+    )
+    db_session.add(lead)
+    await db_session.flush()
+
+    phone = "+84908123456"
+    email = "alice@acme.com"
+    contact = VerifiedContact(
+        workspace_id=db_workspace.id,
+        lead_id=lead.id,
+        phone=_encrypt(phone),
+        email=_encrypt(email),
+        phone_hmac=_phone_hash(phone),
+        email_hmac=_email_hash(email),
+        value_hmac="contact-hmac",
+        is_unlocked=False,
+        pii_access_audit_logs=[],
+    )
+    db_session.add(contact)
+    await db_session.flush()
+
+    service = OptOutService(db_session)
+    result = await service.process_opt_out(
+        workspace_id=db_workspace.id,
+        record_type="email",
+        value=email,
+        actor_user_id=db_user.id,
+    )
+
+    assert result.purged_contact_count == 1
+
+
+@pytest.mark.asyncio
+async def test_opt_out_service_refunds_exactly_1500_micros(
+    db_session, db_user, db_workspace
+):
+    """Pattern 4/6: refund amount and wallet math."""
+    db_user.credit_micros_balance = 10_000
+    await db_session.flush()
+
+    lead = Lead(
+        workspace_id=db_workspace.id,
+        company_name="Acme",
+        domain="acme.com",
+        value_hmac="lead-hmac",
+        source="test",
+    )
+    db_session.add(lead)
+    await db_session.flush()
+
+    phone = "+84908123456"
+    contact = VerifiedContact(
+        workspace_id=db_workspace.id,
+        lead_id=lead.id,
+        phone=_encrypt(phone),
+        email=None,
+        phone_hmac=_phone_hash(phone),
+        email_hmac=None,
+        value_hmac="contact-hmac",
+        is_unlocked=True,
+        pii_access_audit_logs=[],
+    )
+    db_session.add(contact)
+    await db_session.flush()
+
+    db_session.add(
+        BillingEvent(
+            workspace_id=db_workspace.id,
+            user_id=db_user.id,
+            event_entity_type="verified_contact",
+            event_type="contact_unlock",
+            event_id=contact.id,
+            cost_micros=1500,
+            currency="USD",
+            cost_basis="actual",
+        )
+    )
+    await db_session.flush()
+
+    service = OptOutService(db_session)
+    result = await service.process_opt_out(
+        workspace_id=db_workspace.id,
+        record_type="phone",
+        value=phone,
+        actor_user_id=db_user.id,
+    )
+
+    assert result.refunded_micros == 1500
+
+    user = await db_session.get(User, db_user.id)
+    assert user.credit_micros_balance == 11_500
+
+    refund_event = (
+        await db_session.execute(
+            select(BillingEvent).where(
+                BillingEvent.workspace_id == db_workspace.id,
+                BillingEvent.event_type == "contact_unlock_refund",
+            )
+        )
+    ).scalar_one_or_none()
+    assert refund_event is not None
+    assert refund_event.cost_micros == -1500
+
+
+@pytest.mark.asyncio
+async def test_opt_out_service_rollback_on_credit_failure(
+    db_session, db_user, db_workspace, monkeypatch
+):
+    """Pattern 2/6: partial work must not persist if credit refund fails."""
+    db_user.credit_micros_balance = 10_000
+    await db_session.flush()
+
+    lead = Lead(
+        workspace_id=db_workspace.id,
+        company_name="Acme",
+        domain="acme.com",
+        value_hmac="lead-hmac",
+        source="test",
+    )
+    db_session.add(lead)
+    await db_session.flush()
+
+    phone = "+84908123456"
+    contact = VerifiedContact(
+        workspace_id=db_workspace.id,
+        lead_id=lead.id,
+        phone=_encrypt(phone),
+        email=None,
+        phone_hmac=_phone_hash(phone),
+        email_hmac=None,
+        value_hmac="contact-hmac",
+        is_unlocked=True,
+        pii_access_audit_logs=[],
+    )
+    db_session.add(contact)
+    await db_session.flush()
+
+    db_session.add(
+        BillingEvent(
+            workspace_id=db_workspace.id,
+            user_id=db_user.id,
+            event_entity_type="verified_contact",
+            event_type="contact_unlock",
+            event_id=contact.id,
+            cost_micros=1500,
+            currency="USD",
+            cost_basis="actual",
+        )
+    )
+    await db_session.flush()
+
+    monkeypatch.setattr(
+        "app.services.pii.opt_out_service.OptOutService._refund_credit",
+        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("credit service down")),
+    )
+
+    service = OptOutService(db_session)
+    with pytest.raises(RuntimeError, match="credit service down"):
+        await service.process_opt_out(
+            workspace_id=db_workspace.id,
+            record_type="phone",
+            value=phone,
+            actor_user_id=db_user.id,
+        )
+
+    # Everything rolled back because db_session savepoint is rolled back automatically.
+    user = await db_session.get(User, db_user.id)
+    assert user.credit_micros_balance == 10_000
+    assert contact.is_unlocked is True
diff --git a/nowing_backend/tests/unit/services/test_contact_unlock_refund.py b/nowing_backend/tests/unit/services/test_contact_unlock_refund.py
new file mode 100644
index 000000000..dfebb7495
--- /dev/null
+++ b/nowing_backend/tests/unit/services/test_contact_unlock_refund.py
@@ -0,0 +1,254 @@
+"""Red-phase unit tests for contact-unlock refund (Story 26.4)."""
+
+from __future__ import annotations
+
+from types import SimpleNamespace
+from typing import Any
+from uuid import UUID, uuid4
+
+import pytest
+
+from app.config import config
+from app.services.billing_event_service import BillingEventService
+from app.services.workspace_credit_service import WorkspaceCreditService
+
+pytestmark = pytest.mark.unit
+
+
+class _FakeResult:
+    def __init__(self, value: Any = None, rows: list[Any] | None = None) -> None:
+        self._value = value
+        self._rows = rows or []
+
+    def scalar_one_or_none(self) -> Any:
+        return self._value
+
+    def scalar_one(self) -> Any:
+        if self._value is None:
+            raise ValueError("No row found")
+        return self._value
+
+    def scalars(self) -> Any:
+        return self
+
+    def all(self) -> list[Any]:
+        return self._rows
+
+
+class _FakeSession:
+    def __init__(self, event: Any | None = None) -> None:
+        self.added: list[Any] = []
+        self.committed = False
+        self.rolled_back = False
+        self.flushed = False
+        self._event = event
+
+    def add(self, obj: Any) -> None:
+        self.added.append(obj)
+
+    async def execute(self, _stmt: Any) -> _FakeResult:
+        return _FakeResult(self._event)
+
+    async def get(self, _model: type, _ident: Any) -> Any | None:
+        return None
+
+    async def commit(self) -> None:
+        self.committed = True
+
+    async def rollback(self) -> None:
+        self.rolled_back = True
+
+    async def flush(self) -> None:
+        self.flushed = True
+
+    async def refresh(self, _obj: Any) -> None:
+        pass
+
+
+def _make_unlock_billing_event(user_id: UUID) -> SimpleNamespace:
+    return SimpleNamespace(
+        id=uuid4(),
+        user_id=user_id,
+        cost_micros=1500,
+        event_type="contact_unlock",
+    )
+
+
+class TestRecordContactUnlockRefund:
+    """AC-3/AC-5: refund credit when a verified contact is opted out."""
+
+    @pytest.fixture(autouse=True)
+    def _fixed_secret(self, monkeypatch: pytest.MonkeyPatch) -> None:
+        monkeypatch.setattr(config, "SECRET_KEY", "test-secret")
+
+    @pytest.mark.asyncio
+    async def test_refund_credits_user_wallet_and_monthly_spent(
+        self, monkeypatch: pytest.MonkeyPatch
+    ) -> None:
+        payer_id = uuid4()
+        contact_id = uuid4()
+        original = _make_unlock_billing_event(payer_id)
+        session = _FakeSession(event=original)
+
+        calls: dict[str, Any] = {"wallet": [], "monthly_spent": []}
+
+        async def _apply_credit(_session: Any, user_id: Any, amount_micros: int) -> int:
+            calls["wallet"].append({"user_id": user_id, "amount_micros": amount_micros})
+            return 1500
+
+        async def _refund_member_spend(
+            self: WorkspaceCreditService,
+            *,
+            workspace_id: int,
+            user_id: UUID,
+            amount_micros: int,
+        ) -> dict[str, Any]:
+            calls["monthly_spent"].append(
+                {
+                    "workspace_id": workspace_id,
+                    "user_id": user_id,
+                    "amount_micros": amount_micros,
+                }
+            )
+            return {
+                "workspace_id": workspace_id,
+                "user_id": user_id,
+                "amount_micros": amount_micros,
+                "member_monthly_spent": 0,
+            }
+
+        monkeypatch.setattr(
+            "app.services.billing_event_service.wallet_credit.apply_credit",
+            _apply_credit,
+        )
+        monkeypatch.setattr(
+            WorkspaceCreditService,
+            "refund_member_spend",
+            _refund_member_spend,
+        )
+
+        result = await BillingEventService().record_contact_unlock_refund(
+            session,
+            verified_contact_id=contact_id,
+            workspace_id=1,
+            user_id=uuid4(),
+        )
+
+        assert result.cost_micros == -1500
+        assert result.event_type == "contact_unlock_refund"
+        assert result.event_entity_type == "verified_contact"
+        assert result.event_id == contact_id
+
+        assert len(calls["wallet"]) == 1
+        assert calls["wallet"][0]["amount_micros"] == 1500
+        assert calls["wallet"][0]["user_id"] == payer_id
+        assert len(calls["monthly_spent"]) == 1
+        assert calls["monthly_spent"][0]["amount_micros"] == 1500
+
+    @pytest.mark.asyncio
+    async def test_refund_is_idempotent(self, monkeypatch: pytest.MonkeyPatch) -> None:
+        payer_id = uuid4()
+        contact_id = uuid4()
+        existing_refund = SimpleNamespace(
+            id=uuid4(),
+            event_type="contact_unlock_refund",
+            cost_micros=-1500,
+        )
+        session = _FakeSession(event=existing_refund)
+
+        calls: dict[str, Any] = {"wallet": []}
+
+        async def _apply_credit(*args: Any, **kwargs: Any) -> None:
+            calls["wallet"].append({"args": args, "kwargs": kwargs})
+
+        monkeypatch.setattr(
+            "app.services.billing_event_service.wallet_credit.apply_credit",
+            _apply_credit,
+        )
+
+        result = await BillingEventService().record_contact_unlock_refund(
+            session,
+            verified_contact_id=contact_id,
+            workspace_id=1,
+            user_id=payer_id,
+        )
+
+        assert result is existing_refund
+        assert not calls["wallet"]
+        assert not session.added
+
+    @pytest.mark.asyncio
+    async def test_refund_fails_when_no_original_billing_event(self) -> None:
+        session = _FakeSession(event=None)
+
+        with pytest.raises(ValueError, match="no unlock billing event"):
+            await BillingEventService().record_contact_unlock_refund(
+                session,
+                verified_contact_id=uuid4(),
+                workspace_id=1,
+                user_id=uuid4(),
+            )
+
+    @pytest.mark.asyncio
+    async def test_refund_does_not_credit_workspace_pool(
+        self, monkeypatch: pytest.MonkeyPatch
+    ) -> None:
+        """WorkspaceCreditService.refund_credits touches workspace pool; refund must not."""
+        payer_id = uuid4()
+        contact_id = uuid4()
+        original = _make_unlock_billing_event(payer_id)
+        session = _FakeSession(event=original)
+
+        workspace_balance_calls: list[Any] = []
+
+        async def _refund_credits(
+            self: WorkspaceCreditService,
+            *,
+            workspace_id: int,
+            user_id: UUID,
+            amount_micros: int,
+            reason: str = "",
+        ) -> dict[str, Any]:
+            workspace_balance_calls.append({"amount_micros": amount_micros})
+            return {}
+
+        async def _refund_member_spend(
+            self: WorkspaceCreditService,
+            *,
+            workspace_id: int,
+            user_id: UUID,
+            amount_micros: int,
+        ) -> dict[str, Any]:
+            return {
+                "workspace_id": workspace_id,
+                "user_id": user_id,
+                "amount_micros": amount_micros,
+                "member_monthly_spent": 0,
+            }
+
+        async def _apply_credit(_session: Any, user_id: Any, amount_micros: int) -> int:
+            return amount_micros
+
+        monkeypatch.setattr(
+            WorkspaceCreditService,
+            "refund_credits",
+            _refund_credits,
+        )
+        monkeypatch.setattr(
+            WorkspaceCreditService,
+            "refund_member_spend",
+            _refund_member_spend,
+        )
+        monkeypatch.setattr(
+            "app.services.billing_event_service.wallet_credit.apply_credit",
+            _apply_credit,
+        )
+
+        await BillingEventService().record_contact_unlock_refund(
+            session,
+            verified_contact_id=contact_id,
+            workspace_id=1,
+            user_id=payer_id,
+        )
+
+        assert not workspace_balance_calls
diff --git a/nowing_backend/tests/unit/services/test_pii_helpers.py b/nowing_backend/tests/unit/services/test_pii_helpers.py
new file mode 100644
index 000000000..7dc352420
--- /dev/null
+++ b/nowing_backend/tests/unit/services/test_pii_helpers.py
@@ -0,0 +1,146 @@
+"""Red-phase unit tests for PII HMAC and masking helpers (Story 26.4)."""
+
+from __future__ import annotations
+
+import pytest
+
+from app.config import config
+from app.lead_intelligence.dnc.normalizer import (
+    compute_email_hmac,
+    compute_phone_hmac,
+    compute_verified_contact_hmac,
+    hash_phone_hmac,
+    normalize_domain,
+    normalize_email,
+    normalize_phone_e164,
+)
+from app.services.export_service import mask_email, mask_phone
+
+pytestmark = pytest.mark.unit
+
+SECRET = "test-secret-key-26-4"
+
+
+@pytest.fixture(autouse=True)
+def _fixed_secret(monkeypatch: pytest.MonkeyPatch) -> None:
+    monkeypatch.setattr(config, "SECRET_KEY", SECRET)
+
+
+class TestComputeVerifiedContactHmac:
+    """AC-2: canonical composite HMAC for deduplication."""
+
+    def test_canonical_form(self) -> None:
+        phone = normalize_phone_e164("+84 908 123 456")
+        email = normalize_email("Alice@Acme.COM")
+        domain = normalize_domain("https://acme.com/about")
+        assert phone == "+84908123456"
+        assert email == "alice@acme.com"
+        assert domain == "acme.com"
+
+        h = compute_verified_contact_hmac(phone, email, domain)
+        expected = hash_phone_hmac(
+            f"phone={phone}|email={email}|domain={domain}",
+            SECRET,
+        )
+        assert h == expected
+        assert len(h) == 64
+
+    def test_missing_phone_uses_empty_string(self) -> None:
+        h = compute_verified_contact_hmac(None, "alice@acme.com", "acme.com")
+        expected = hash_phone_hmac(
+            "phone=|email=alice@acme.com|domain=acme.com",
+            SECRET,
+        )
+        assert h == expected
+
+    def test_missing_email_uses_empty_string(self) -> None:
+        h = compute_verified_contact_hmac("+84908123456", None, "acme.com")
+        expected = hash_phone_hmac(
+            "phone=+84908123456|email=|domain=acme.com",
+            SECRET,
+        )
+        assert h == expected
+
+    def test_missing_domain_uses_empty_string(self) -> None:
+        h = compute_verified_contact_hmac("+84908123456", "alice@acme.com", None)
+        expected = hash_phone_hmac(
+            "phone=+84908123456|email=alice@acme.com|domain=",
+            SECRET,
+        )
+        assert h == expected
+
+    def test_degenerate_all_empty_raises(self) -> None:
+        with pytest.raises(ValueError, match="degenerate contact"):
+            compute_verified_contact_hmac(None, None, None)
+
+    def test_secret_not_configured_raises(
+        self, monkeypatch: pytest.MonkeyPatch
+    ) -> None:
+        monkeypatch.setattr(config, "SECRET_KEY", "")
+        with pytest.raises(ValueError, match="SECRET_KEY"):
+            compute_verified_contact_hmac("+84908123456", "a@b.com", "b.com")
+
+    def test_normalization_variants_produce_same_hmac(self) -> None:
+        """Boundary: +84 vs 0-prefix vs legacy 11-digit all normalize to same E.164."""
+        variants = ["+84908123456", "0908 123 456", "0908123456", "84908123456"]
+        hmacs = {
+            compute_verified_contact_hmac(v, "alice@acme.com", "acme.com")
+            for v in variants
+        }
+        assert len(hmacs) == 1
+
+
+class TestBlindIndexHmacs:
+    """AC-2: phone_hmac and email_hmac match DNC hash_phone_hmac."""
+
+    def test_compute_phone_hmac_matches_dnc(self) -> None:
+        phone = normalize_phone_e164("+84908123456")
+        assert compute_phone_hmac(phone) == hash_phone_hmac(phone, SECRET)
+
+    def test_compute_email_hmac_matches_dnc(self) -> None:
+        email = normalize_email("Alice@Acme.com")
+        assert compute_email_hmac(email) == hash_phone_hmac(email, SECRET)
+
+    def test_phone_hmac_is_64_hex(self) -> None:
+        h = compute_phone_hmac("+84908123456")
+        assert len(h) == 64
+        int(h, 16)  # valid hex
+
+    def test_email_hmac_is_64_hex(self) -> None:
+        h = compute_email_hmac("alice@acme.com")
+        assert len(h) == 64
+        int(h, 16)  # valid hex
+
+
+class TestMaskPhone:
+    """AC-7: phone masking for non-privileged display."""
+
+    @pytest.mark.parametrize(
+        "phone,expected",
+        [
+            ("+84908123456", "+84908***456"),
+            ("0908123456", "0908***456"),
+            ("090 123 45 67", "0901***567"),
+        ],
+    )
+    def test_masks_phone(self, phone: str, expected: str) -> None:
+        assert mask_phone(phone) == expected
+
+    def test_returns_empty_for_none(self) -> None:
+        assert mask_phone(None) == ""
+
+    def test_returns_original_for_short_phone(self) -> None:
+        assert mask_phone("12345") == "12345"
+
+
+class TestMaskEmail:
+    """AC-7: email masking for non-privileged display."""
+
+    def test_masks_email(self) -> None:
+        assert mask_email("alice@example.com") == "a***@example.com"
+
+    def test_returns_empty_for_none(self) -> None:
+        assert mask_email(None) == ""
+
+    def test_returns_original_for_no_at(self) -> None:
+        assert mask_email("notanemail") == "notanemail"
diff --git a/nowing_backend/tests/unit/services/test_pii_opt_out_service.py b/nowing_backend/tests/unit/services/test_pii_opt_out_service.py
new file mode 100644
index 000000000..828e64eec
--- /dev/null
+++ b/nowing_backend/tests/unit/services/test_pii_opt_out_service.py
@@ -0,0 +1,270 @@
+"""Red-phase unit tests for PII opt-out service (Story 26.4)."""
+
+from __future__ import annotations
+
+from types import SimpleNamespace
+from typing import Any
+from uuid import UUID, uuid4
+
+import pytest
+
+from app.config import config
+from app.services.pii.opt_out_service import OptOutService
+
+pytestmark = [pytest.mark.unit]
+
+
+class _FakeResult:
+    def __init__(self, value: Any = None, rows: list[Any] | None = None) -> None:
+        self._value = value
+        self._rows = rows or []
+
+    def scalar_one_or_none(self) -> Any:
+        return self._value
+
+    def scalar_one(self) -> Any:
+        if self._value is None:
+            raise ValueError("No row found")
+        return self._value
+
+    def scalars(self) -> Any:
+        return self
+
+    def all(self) -> list[Any]:
+        return self._rows
+
+
+class _FakeSession:
+    def __init__(self, contacts: list[Any] | None = None) -> None:
+        self.added: list[Any] = []
+        self.committed = False
+        self.flushed = False
+        self._contacts = contacts or []
+        self._dnc: Any | None = None
+
+    def add(self, obj: Any) -> None:
+        self.added.append(obj)
+
+    async def execute(self, _stmt: Any) -> _FakeResult:
+        return _FakeResult(rows=self._contacts)
+
+    async def get(self, _model: type, _ident: Any) -> Any | None:
+        return None
+
+    async def commit(self) -> None:
+        self.committed = True
+
+    async def flush(self) -> None:
+        self.flushed = True
+
+    async def refresh(self, _obj: Any) -> None:
+        pass
+
+
+class TestOptOutServiceProcess:
+    """AC-3: PII opt-out purges contacts and refunds credit."""
+
+    @pytest.fixture(autouse=True)
+    def _fixed_secret(self, monkeypatch: pytest.MonkeyPatch) -> None:
+        monkeypatch.setattr(config, "SECRET_KEY", "test-secret")
+
+    def _make_unlocked_contact(self) -> SimpleNamespace:
+        return SimpleNamespace(
+            id=uuid4(),
+            workspace_id=1,
+            lead_id=uuid4(),
+            phone="encrypted-phone",
+            email="encrypted-email",
+            name="Alice",
+            title="CEO",
+            phone_hmac="phone-hash",
+            email_hmac="email-hash",
+            value_hmac="contact-hmac",
+            is_unlocked=True,
+            consent=True,
+            consent_status="opted_in",
+            legal_basis="consent",
+            pii_access_audit_logs=[],
+        )
+
+    @pytest.mark.asyncio
+    async def test_opt_out_creates_dnc_record_and_purges(
+        self, monkeypatch: pytest.MonkeyPatch
+    ) -> None:
+        contact = self._make_unlocked_contact()
+        session = _FakeSession(contacts=[contact])
+
+        class FakeDncService:
+            def __init__(self, **kwargs: Any) -> None:
+                pass
+
+            async def invalidate_workspace_cache(
+                self, *args: Any, **kwargs: Any
+            ) -> None:
+                pass
+
+        monkeypatch.setattr(
+            "app.services.pii.opt_out_service.DncComplianceService",
+            FakeDncService,
+        )
+
+        service = OptOutService(session)
+        result = await service.process_opt_out(
+            workspace_id=1,
+            record_type="phone",
+            value="+84908123456",
+            actor_user_id=uuid4(),
+            ip_address="1.2.3.4",
+        )
+
+        assert result.purged_contact_count == 1
+        assert result.dnc_record_id is not None
+        assert contact.is_unlocked is False
+        assert contact.consent is False
+        assert contact.consent_status == "withdrawn"
+        assert contact.legal_basis == "opt_out"
+        assert contact.name is None
+        assert contact.title is None
+        assert contact.phone is None
+        assert contact.email is None
+
+        assert len(contact.pii_access_audit_logs) == 1
+        log = contact.pii_access_audit_logs[0]
+        assert log["access_type"] == "opt_out_purged"
+        assert log["ip_address"] == "1.2.3.4"
+
+    @pytest.mark.asyncio
+    async def test_opt_out_refunds_per_unlocked_contact(
+        self, monkeypatch: pytest.MonkeyPatch
+    ) -> None:
+        contact = self._make_unlocked_contact()
+        original_event = SimpleNamespace(
+            id=uuid4(),
+            user_id=uuid4(),
+            cost_micros=1500,
+        )
+
+        session = _FakeSession(contacts=[contact])
+
+        calls: dict[str, Any] = {"wallet": [], "monthly_spent": []}
+
+        async def _credit_wallet(
+            _s: Any, user_id: UUID | str, amount_micros: int
+        ) -> None:
+            calls["wallet"].append({"user_id": user_id, "amount_micros": amount_micros})
+
+        async def _decrement_monthly_spent(
+            _s: Any, *, workspace_id: int, user_id: UUID, amount_micros: int
+        ) -> None:
+            calls["monthly_spent"].append(
+                {
+                    "workspace_id": workspace_id,
+                    "user_id": user_id,
+                    "amount_micros": amount_micros,
+                }
+            )
+
+        monkeypatch.setattr(
+            "app.services.pii.opt_out_service._credit_user_wallet",
+            _credit_wallet,
+        )
+        monkeypatch.setattr(
+            "app.services.pii.opt_out_service._decrement_member_monthly_spent",
+            _decrement_monthly_spent,
+        )
+
+        async def _find_original_event(
+            _session: Any, _contact_id: UUID, _workspace_id: int
+        ) -> Any:
+            return original_event
+
+        monkeypatch.setattr(
+            "app.services.pii.opt_out_service._find_original_unlock_billing_event",
+            _find_original_event,
+        )
+
+        service = OptOutService(session)
+        result = await service.process_opt_out(
+            workspace_id=1,
+            record_type="phone",
+            value="+84908123456",
+            actor_user_id=uuid4(),
+        )
+
+        assert result.refunded_micros == 1500
+        assert len(calls["wallet"]) == 1
+        assert calls["wallet"][0]["amount_micros"] == 1500
+        assert calls["wallet"][0]["user_id"] == original_event.user_id
+        assert len(calls["monthly_spent"]) == 1
+        assert calls["monthly_spent"][0]["amount_micros"] == 1500
+
+        refund_event = next(
+            (
+                a
+                for a in session.added
+                if getattr(a, "event_type", None) == "contact_unlock_refund"
+            ),
+            None,
+        )
+        assert refund_event is not None
+        assert refund_event.cost_micros == -1500
+
+    @pytest.mark.asyncio
+    async def test_opt_out_idempotent(self, monkeypatch: pytest.MonkeyPatch) -> None:
+        contact = self._make_unlocked_contact()
+        contact.is_unlocked = False
+        session = _FakeSession(contacts=[contact])
+
+        service = OptOutService(session)
+        result = await service.process_opt_out(
+            workspace_id=1,
+            record_type="phone",
+            value="+84908123456",
+            actor_user_id=uuid4(),
+        )
+
+        assert result.purged_contact_count == 1
+        assert result.refunded_micros == 0
+
+    @pytest.mark.asyncio
+    async def test_opt_out_respects_15_percent_refund_cap(
+        self, monkeypatch: pytest.MonkeyPatch
+    ) -> None:
+        contact = self._make_unlocked_contact()
+        session = _FakeSession(contacts=[contact])
+
+        # Simulate cap exhausted: already refunded 15% this cycle.
+        async def _no_refunds(*a: Any, **k: Any) -> int:
+            return 0
+
+        monkeypatch.setattr(
+            "app.services.pii.opt_out_service._count_refundable_unlocks_this_cycle",
+            _no_refunds,
+        )
+
+        service = OptOutService(session)
+        result = await service.process_opt_out(
+            workspace_id=1,
+            record_type="phone",
+            value="+84908123456",
+            actor_user_id=uuid4(),
+        )
+
+        assert result.purged_contact_count == 1
+        assert result.refunded_micros == 0
+
+    @pytest.mark.asyncio
+    async def test_opt_out_no_matching_contact_still_creates_dnc(self) -> None:
+        session = _FakeSession(contacts=[])
+        service = OptOutService(session)
+
+        result = await service.process_opt_out(
+            workspace_id=1,
+            record_type="phone",
+            value="+84900000000",
+            actor_user_id=uuid4(),
+        )
+
+        assert result.purged_contact_count == 0
+        assert result.refunded_micros == 0
+        assert result.dnc_record_id is not None
