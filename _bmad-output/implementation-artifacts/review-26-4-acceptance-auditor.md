# Acceptance-Auditor Findings — Story 26.4 PII Vault / HMAC / Opt-Out

Reviewed `review-26-4-diff.md` (commit `74d876fc4`) against the spec `26-4-pii-vault-hmac-deduplication-decree-13-opt-out.md` and the referenced architecture spine `ARCHITECTURE-SPINE.md` (AD-105, AD-109, AD-110, AD-104). All findings are violations, deviations, or contradictions. Tests run: `ruff check`/`ruff format` passed, targeted unit + integration tests passed; however the test suite does not cover the missing/unsafe paths below.

---

## Findings

- **Missing Alembic migration and backfill for schema changes**
  - **Violates**: AC-6 (schema migration/backfill) and AD-109 Rule 3 (`value_hmac NOT NULL` + unique constraints).
  - **Evidence**: `git diff --name-only HEAD~1 -- nowing_backend/alembic/versions/` returns nothing; the diff changes `app/db.py` (`Lead.value_hmac` at line 4673, `VerifiedContact` columns at 5233-5235) but adds no migration. The existing migrations `nowing_backend/alembic/versions/ac475d54f6a2_...` (lines 89-103 partial unique on `verified_contacts`) and `nowing_backend/alembic/versions/224_add_unique_constraint_leads_value_hmac.py` (lines 18-26 partial unique on `leads`) are still partial and do not add `phone_hmac`/`email_hmac`. Existing databases cannot upgrade; old rows will not have the required HMACs.

- **`phone_hmac` / `email_hmac` indexes are single-column, not composite with `workspace_id`**
  - **Violates**: AC-6 #7 (composite indexes for opt-out/DNC lookups).
  - **Evidence**: `app/db.py:5234-5235` declares `phone_hmac = Column(..., index=True)` and `email_hmac = Column(..., index=True)`. The spec requires `(workspace_id, phone_hmac)` and `(workspace_id, email_hmac)` indexes.

- **Partial unique indexes on `leads`/`verified_contacts` not replaced with full unique constraints**
  - **Violates**: AC-6 #5/#6 (full `UNIQUE(workspace_id, value_hmac)`) and AD-109 Rule 3.
  - **Evidence**: The model declares full unique constraints (`app/db.py:4641-4644` for `Lead`, `app/db.py:5181-5185` for `VerifiedContact`), but the existing Alembic migrations still create partial indexes with `WHERE value_hmac IS NOT NULL` (`ac475...:97-103` and `224...:20-26`). No new migration recreates them, causing schema drift for existing deployments.

- **PII opt-out refund bypasses `BillingEventService` and calls `wallet_credit.apply_credit` directly**
  - **Violates**: AC-3 step 5 / "Important Do-Nots" in the spec ("Route through BillingEventService so spend caps and idempotency are enforced").
  - **Evidence**: `app/services/pii/opt_out_service.py:194-202` calls `wallet_credit.apply_credit`. `app/services/billing_event_service.py:91-161` defines `record_contact_unlock_refund`, but a `grep` for that symbol returns only its own definition and `tests/unit/services/test_contact_unlock_refund.py`; no production caller uses it. This is dead code and the refund is not idempotent through the billing service.

- **Opt-out refund does not fall back to the workspace owner when payer is missing**
  - **Violates**: Spec Design Decision D2 ("credit User.credit_micros_balance của payer từ BillingEvent hoặc workspace owner nếu payer missing").
  - **Evidence**: `app/services/pii/opt_out_service.py:189-192` returns `0` when `original_event.user_id` is `None` and does not attempt to locate the workspace owner. (The unused `BillingEventService.record_contact_unlock_refund:135-137` falls back to the actor, not the owner.)

- **Refund cap uses current `is_unlocked` count instead of billing-cycle unlocks**
  - **Violates**: AC-3 step 5 and AD-110 Rule 4 ("15% of total unlocked leads per billing cycle").
  - **Evidence**: `app/services/pii/opt_out_service.py:108-125` counts `VerifiedContact.is_unlocked.is_(True)` (a snapshot of current state, not billing-cycle unlocks). The `already_refunded` count is the only value filtered by the billing cycle (`:128-145`). Also `allowed = max(1, int(total_unlocked * 0.15))` makes the cap at least one even when no unlocks exist.

- **PII opt-out route ignores the request `reason` and hardcodes it**
  - **Violates**: AC-3 steps 2/4 (`reason` is user-supplied for the DNC record and audit) and Task 6 (standard audit log shape).
  - **Evidence**: `app/routes/lead_batch_routes.py:586-592` defines `PIIOptOutRequest.reason`, but the route at `app/routes/lead_batch_routes.py:287-289` passes only `record_type` and `value`. `OptOutService.process_opt_out` (`app/services/pii/opt_out_service.py:274-360`) has no `reason` parameter; `_ensure_dnc_record` (`app/services/pii/opt_out_service.py:295-300`) and `_append_opt_out_audit_log` (`app/services/pii/opt_out_service.py:62-71`) both hardcode `"Right to be forgotten"`.

- **Global / superadmin PII opt-out is not implemented**
  - **Violates**: AC-3 steps 2/3 (global DNC records for superadmins, cross-workspace purge).
  - **Evidence**: `app/routes/lead_batch_routes.py:289` hardcodes `global_scope=False` and the schema has no `global` flag. Even if `global_scope=True` were passed, `app/services/pii/opt_out_service.py:309-314` always filters `VerifiedContact.workspace_id == workspace_id`, so global purge would not happen.

- **Contact-unlock audit log is missing `ip_address` and `reason`**
  - **Violates**: AC-5 (unlock audit log), AC-6 / Task 6 (standard JSON shape), and AD-105 Rule 5.
  - **Evidence**: `app/routes/lead_batch_routes.py:226-238` appends only `user_id`, `workspace_id`, `lead_id`, `contact_id`, `timestamp`, and `access_type`. The route extracts `ip_address` at `app/routes/lead_batch_routes.py:282` but never stores it in the audit log.

- **Opt-out audit log is missing `workspace_id`, `lead_id`, `contact_id`, and uses `actor_id` instead of `user_id`**
  - **Violates**: AC-3 / AC-6 (standard `pii_access_audit_logs` shape).
  - **Evidence**: `app/services/pii/opt_out_service.py:62-71` writes `{"access_type", "actor_id", "timestamp", "ip_address", "reason"}`. The spec requires `{"user_id", "workspace_id", "lead_id", "contact_id", "access_type", "timestamp", "ip_address", "reason"}`. The contact/lead IDs are available in the `VerifiedContact` object being purged.

- **Wallet is debited before PII is decrypted, and `wallet_credit` helpers commit inside the helper, breaking the single-transaction requirement**
  - **Violates**: AC-5 (unlock failure handling) and AD-105 Rule 4 ("decrypt phone/email, set is_unlocked, call wallet_credit.apply_debit, and write BillingEvent in a single transaction; if decryption fails, the wallet is not debited").
  - **Evidence**: `app/routes/lead_batch_routes.py:211-239` calls `BillingEventService.record_contact_unlock` (which calls `wallet_credit.apply_debit` at `app/services/wallet_credit.py:112` and commits inside the helper) before it sets `is_unlocked=True` and before it constructs `ContactUnlockResponse` with decryption. If `ContactUnlockResponse` decryption fails, the wallet debit is already committed while the `is_unlocked`/`BillingEvent` updates will roll back. The same `commit` pattern is in `wallet_credit.apply_credit` (`app/services/wallet_credit.py:147`), making the opt-out refund non-atomic.

- **Lead list endpoint returns decrypted PII when `is_unlocked=True`**
  - **Violates**: "Important Do-Nots" in the spec ("Do NOT expose decrypted PII in masked/default lead list responses. Only unlock response returns decrypted phone/email, and only after billing.") and AC-7.
  - **Evidence**: `app/routes/leads_routes.py:96-107` decrypts `phone`, `email`, `name`, and `title` and returns them in `LeadRead` when `first_contact.is_unlocked` is true.

- **`ExportService` does not mask contact `name` or `title` when `mask_pii=True`**
  - **Violates**: AC-7 / Task 5 (mask `name` with `mask_name`).
  - **Evidence**: `app/services/export_service.py:656-674` (CSV), `690-709` (Lark), and `739-756` (Sheets) only apply `mask_email` and `mask_phone`; `name` and `title` are emitted unmasked (or as raw encrypted tokens). The new `mask_name` helper exists at `app/services/export_service.py:616-623` but is never called in the export paths.

- **`EnrichmentService` / `enrichment_routes` do not fail-closed on DNC before creating `VerifiedContact`**
  - **Violates**: AC-4 ("Future scrapers, batch ingest, phone waterfall, or enrichment processes ... DncComplianceService fail-closed blocks the record, no new VerifiedContact is created, and no credit is charged for it.")
  - **Evidence**: `app/lead_intelligence/enrichment/service.py:234-265` and `app/routes/enrichment_routes.py:74-110` create `VerifiedContact` without calling `DncComplianceService`. By contrast, `app/services/phone_waterfall_service.py:799-808` and `app/services/lead_batch_service.py:159-178` do call DNC.

- **`BillingEvent` model has no `reason` column, so the architecture-required `reason='contact_unlock'` cannot be stored**
  - **Violates**: AD-105 Rule 4 (`BillingEvent` written with `reason='contact_unlock'`) and AC-5 (`BillingEvent` for contact unlock).
  - **Evidence**: `app/db.py:4606-4627` defines `BillingEvent` with `id`, `workspace_id`, `user_id`, `event_type`, `event_entity_type`, `event_id`, `cost_micros`, `cost_basis`, `created_at`, `client_id` — no `reason` column. `app/services/billing_event_service.py:78-89` does not set `reason` because the column does not exist.

- **Contact-unlock route does not consult the DNC table and can bill to unlock an already-opt-out/anonymized contact**
  - **Violates**: AD-110 Rule 2 ("Crawlers, batch ingest, and contact unlocks MUST bypass HMACs present in the active DNC/blacklist table.") and AC-5.
  - **Evidence**: `app/routes/lead_batch_routes.py:153-239` finds the contact by UUID, checks only `is_unlocked`, and proceeds to debit. After opt-out, a contact has PII set to `None` and `is_unlocked=False`; the route will still debit and return `None` values. No DNC lookup is performed.

- **Missing required DNC fail-closed and concurrency tests**
  - **Violates**: AC-8.2 and AC-8.3.
  - **Evidence**: `git show --name-status HEAD` adds `tests/integration/routes/test_pii_opt_out.py`, `tests/integration/services/test_pii_opt_out_service.py`, and unit tests, but does not add `tests/integration/services/test_pii_opt_out_concurrency.py` or any integration test verifying that a DNC-listed phone/email is blocked by batch, phone waterfall, or enrichment. The implemented tests all passed, but they do not cover the specified acceptance scenarios.

- **`mask_name` leaves very short names unmasked**
  - **Violates**: AC-7 ("names are masked as `Nguyễn ***`" with no exception).
  - **Evidence**: `app/services/export_service.py:621-623` returns the cleaned name as-is when `len(clean) <= 3`. `mask_phone`/`mask_email` have similar short-value fallbacks. This leaks short names in masked display.

- **`verified_contacts` bulk upsert is not sorted/deduplicated by `value_hmac`**
  - **Violates**: AD-109 Rule 4 ("All SQL bulk upserts on `leads` and `verified_contacts` MUST deterministically sort records by `value_hmac ASC` before executing `INSERT ... ON CONFLICT DO UPDATE`.") and AC-6 (HMAC uniqueness/determinism).
  - **Evidence**: `app/services/lead_batch_service.py:189-245` builds `contacts_to_insert` in input order and calls `pg_insert(VerifiedContact).on_conflict_do_update(index_elements=["workspace_id", "value_hmac"])` without sorting. If a batch contains two items that map to the same `(workspace_id, value_hmac)`, Postgres `ON CONFLICT DO UPDATE` with duplicate source rows will raise a cardinality violation.

- **Opt-out refund is not concurrency-safe or idempotent per contact**
  - **Violates**: AC-3 step 5 (idempotent refund) and AC-8.3 (concurrent opt-out).
  - **Evidence**: `app/services/pii/opt_out_service.py:182-213` does not check whether a `contact_unlock_refund` `BillingEvent` already exists for the contact; it relies only on `refundable_slots`. A concurrent phone and email opt-out on a single contact with both values could both see an unlocked contact and refund twice. The unused `BillingEventService.record_contact_unlock_refund:105-117` does check for an existing refund, but the opt-out service does not call it.

- **Contact-unlock route maps all `record_contact_unlock` exceptions to `402`, masking 500/decode errors**
  - **Violates**: AC-5 failure-mode contract ("On failure (insufficient credits, billing error, decryption error): return 402 Payment Required or 500").
  - **Evidence**: `app/routes/lead_batch_routes.py:211-239` wraps the entire unlock flow in `except Exception: raise HTTPException(status_code=402, ...)`. A genuine decryption or server error is reported as a payment failure instead of 500.

- **No `BillingEvent` index on `(workspace_id, event_type, created_at)` for the 15% cap query**
  - **Violates**: Dev Notes Q4 performance/integrity warning (not an AC, but a stated risk).
  - **Evidence**: `app/services/pii/opt_out_service.py:128-145` queries `BillingEvent` by `workspace_id`, `event_type`, and `created_at`, but `app/db.py:4606-4627` does not define such an index. As the `BillingEvent` table grows, the refund-cap count becomes an O(n) scan per contact.

---

## Test / lint verification notes

- `ruff check` and `ruff format --check` pass for the changed files.
- Targeted unit tests (`tests/unit/services/test_pii_*.py`, `tests/unit/services/test_contact_unlock_refund.py`) pass.
- Targeted integration tests (`tests/integration/routes/test_pii_opt_out.py`, `tests/integration/services/test_pii_opt_out_service.py`, `tests/integration/lead_batch/test_contact_unlock_decryption.py`) pass on a fresh `nowing_test` DB created via `Base.metadata.create_all`.
- However, because no Alembic migration was added, these tests do **not** exercise an upgrade from an existing 26.1/26.2/26.3 database. Existing deployments will fail to run the new code.
