# Blind Hunter Review — review-26-4-diff

Review performed with no project context, no spec, and no extra files; findings are derived solely from the provided diff.

- **P0 — `wallet_credit.apply_credit()` calls `session.commit()` inside the helper, breaking opt-out transaction atomicity**
  - Evidence: `nowing_backend/app/services/wallet_credit.py` lines 1546–1569 (especially `await session.commit()` at line 1567); called from `nowing_backend/app/services/pii/opt_out_service.py` `_refund_credit` lines 1356–1380 and `nowing_backend/app/services/billing_event_service.py` `record_contact_unlock_refund` line 833.
  - Explanation: The helper commits the caller’s session before the opt-out route or caller can finish. `OptOutService.process_opt_out` calls it once per unlocked contact inside a loop, so the database is committed incrementally. If a later contact fails, the wallet credit for earlier contacts is already persisted while their purge / audit log / refund BillingEvent may not be. This also makes the integration test assertion at `nowing_backend/tests/integration/services/test_pii_opt_out_service.py` line 2454 (“Everything rolled back…”) misleading because real `apply_credit` commits first.

- **P0 — `Lead.value_hmac` and `VerifiedContact.value_hmac` are changed to `nullable=False` with no Alembic migration, backfill, or unique constraints**
  - Evidence: `nowing_backend/app/db.py` lines 467–479; the story doc itself lists required migration tasks at lines 168–177 and AC-6 at lines 139–148, but no `alembic/versions/*` file appears in the diff.
  - Explanation: Existing rows with `NULL` will fail `NOT NULL` checks. `lead_batch_service.py` `ON CONFLICT index_elements=["workspace_id", "value_hmac"]` (lines 1084–1094) and opt-out deduplication depend on a `(workspace_id, value_hmac)` unique index/constraint that is not defined in the model or in any visible migration. Without it, the batch upsert will raise `UndefinedObject` and duplicates can be inserted.

- **P0 — No visible code populates `Lead.value_hmac` after making it `NOT NULL`**
  - Evidence: `nowing_backend/app/db.py` line 468; `nowing_backend/app/services/lead_batch_service.py` lines 1036–1044 build `lead_rows` from the incoming `leads` list and line 1044 does `pg_insert(Lead).values(lead_rows)`. The diff only shows `value_hmac` being set for `VerifiedContact` (e.g., line 1076), never for the lead row.
  - Explanation: `Lead.value_hmac` is now a required column, yet the only writers changed in the diff do not show setting it. Unless unchanged code already populates it, every `Lead` insert will raise an `IntegrityError`.

- **P1 — Opt-out refund path is not idempotent and is racy**
  - Evidence: `nowing_backend/app/services/pii/opt_out_service.py` `_refund_credit` lines 1349–1380, `_find_original_unlock_billing_event` lines 1242–1259, and `process_opt_out` loop lines 1493–1514.
  - Explanation: `_refund_credit` never checks whether a `contact_unlock_refund` `BillingEvent` already exists for this contact, and the original `contact_unlock` event is read without `SELECT FOR UPDATE`. Two concurrent opt-outs for the same phone can both see the same original event and credit the payer twice. The separately added `BillingEventService.record_contact_unlock_refund` (lines 784–854) contains an idempotency check but is not called by the opt-out flow, leaving two diverging refund implementations.

- **P1 — 15% refund cap is calculated against the wrong denominator and time window**
  - Evidence: `nowing_backend/app/services/pii/opt_out_service.py` `_count_refundable_unlocks_this_cycle` lines 1262–1315.
  - Explanation: `total_unlocked` counts all `VerifiedContact.is_unlocked=True` (a current flag, not per-cycle unlocked events), and `already_refunded` uses the calendar month (`created_at >= datetime(now.year, now.month, 1, …)`), not the workspace’s billing cycle. `allowed = max(1, int(total_unlocked * 0.15))` means a workspace with 0 unlocked contacts still gets 1 refund slot and with 1 unlocked contact can refund 100% of it. The count is also read without locking, so concurrent requests can exceed the cap.

- **P1 — Refund-cap query loads all unlocked contacts and refund events into Python memory**
  - Evidence: `nowing_backend/app/services/pii/opt_out_service.py` lines 1275–1290 and 1295–1313.
  - Explanation: It executes `scalars().all()` on `VerifiedContact` and `BillingEvent` and then runs `len([...])` in Python. For a large workspace this is a memory/time bomb and, as the story doc notes at line 403, there is no index on `(workspace_id, event_type, created_at)`, so it can table-scan.

- **P1 — `pii_opt_out` request `reason` is collected by the schema but never used**
  - Evidence: `nowing_backend/app/routes/lead_batch_routes.py` `PIIOptOutRequest` line 591 (includes `reason`) and `pii_opt_out` route lines 681–688 (does not pass `body.reason` to `process_opt_out`); `nowing_backend/app/services/pii/opt_out_service.py` `process_opt_out` signature lines 1431–1440 (has no `reason` parameter) and hardcodes `reason="Right to be forgotten"` at lines 1467 and 1512.
  - Explanation: The DNC record and audit log always use the default reason, regardless of the caller-supplied value. This makes the field a no-op and can produce incorrect compliance records.

- **P1 — `leads_routes.py` `_map_lead_to_read` decrypts PII for every lead list request, even for unprivileged/masked views**
  - Evidence: `nowing_backend/app/routes/leads_routes.py` lines 712–763, especially `_render_field` at lines 739–750 and the unconditional `enc.decrypt` calls.
  - Explanation: The handler decrypts `phone`, `email`, and `name` and then re-masks them when `is_unlocked=False`. This is unnecessary CPU work, widens the attack surface, and means any decryption failure or exception path could leak PII. It also returns `None` on decryption failure, which can hide data-integrity problems.

- **P1 — Opt-out refund may crash or leave partial state if the original payer no longer exists**
  - Evidence: `nowing_backend/app/services/pii/opt_out_service.py` `_refund_credit` lines 1356–1380; `nowing_backend/app/services/wallet_credit.py` `apply_credit` lines 1563–1564.
  - Explanation: If the original `BillingEvent.user_id` is missing or the user was deleted, `wallet_credit.apply_credit` raises `ValueError("User with ID {user_id} not found")`. Because `apply_credit` already committed earlier contacts in the loop, the exception leaves the database partially purged and partially refunded. The story doc flags this exact edge case at line 392, but the code does not handle it gracefully.

- **P1 — `pii_opt_out` route error handling is fragile and can leak internal IDs**
  - Evidence: `nowing_backend/app/routes/lead_batch_routes.py` lines 689–699.
  - Explanation: It maps `ValueError` to 400 only when the detail contains the words “phone” or “email”. A `ValueError` from `wallet_credit.apply_credit` (`"User with ID {user_id} not found"`) falls through to 422 and echoes the user UUID in the response. There is no typed exception handling for validation vs. refund errors.

- **P1 — `OptOutService` does not tolerate DNC cache invalidation failures**
  - Evidence: `nowing_backend/app/services/pii/opt_out_service.py` lines 1516–1521.
  - Explanation: It calls `DncComplianceService.invalidate_workspace_cache` / `invalidate_global_cache` unguarded. If Redis is down, the exception propagates and the route fails. The story doc Q4 at line 400 explicitly says the service should warn and continue, but the implementation does not.

- **P1 — `WorkspaceCreditService.refund_member_spend` silently does nothing when the membership row is missing**
  - Evidence: `nowing_backend/app/services/workspace_credit_service.py` lines 1599–1605 and 1637–1644.
  - Explanation: If the `WorkspaceMembership` does not exist, the method returns a dict that still reports `amount_micros` as refunded, but it does not decrement `monthly_spent_micros`. This can leave a member over their spend cap and creates an inaccurate refund record.

- **P1 — `BillingEventService.record_contact_unlock_refund` is added but not used by the opt-out flow**
  - Evidence: `nowing_backend/app/services/billing_event_service.py` lines 784–854; `nowing_backend/app/services/pii/opt_out_service.py` `_refund_credit` lines 1349–1380.
  - Explanation: The service reimplements refund logic and writes its own `BillingEvent`, bypassing the helper. This creates two paths that can drift; the helper’s idempotency and validation logic are ignored.

- **P1 — `WorkspaceCreditService.refund_member_spend` contains test-only fake-session branching and possible missing `func` import**
  - Evidence: `nowing_backend/app/services/workspace_credit_service.py` lines 1596–1614 and 1618–1636.
  - Explanation: It branches on `hasattr(self.session, "workspaces")` to detect a fake unit-test session, which is a code smell. The real `UPDATE` path does not use `SELECT FOR UPDATE` or an atomic decrement expression, so concurrent refunds can lose updates. It also uses `func.greatest` / `func.coalesce` (lines 1625–1628) without a visible `from sqlalchemy import func`; if `func` is not already imported at the top of the file, this is a `NameError`.

- **P2 — `compute_verified_contact_hmac` / `compute_phone_hmac` rely on `hash_phone_hmac` default secret**
  - Evidence: `nowing_backend/app/lead_intelligence/dnc/normalizer.py` lines 493–527.
  - Explanation: `hash_phone_hmac(e164)` and `hash_phone_hmac(canonical)` are called without passing `config.SECRET_KEY`. If the default ever changes or the helper is called with a different default, the canonical HMAC and the blind-index/DNC HMACs will diverge and opt-out lookup will fail. The diff already changed `phone_waterfall_service.py` `hash_phone` from explicit `hash_phone_hmac(e164, config.SECRET_KEY)` to `compute_phone_hmac(phone)` (lines 1113–1126), amplifying the risk.

- **P2 — `mask_name` and `mask_email` leak short PII**
  - Evidence: `nowing_backend/app/services/export_service.py` lines 863–875; unit tests at lines 2855–2869.
  - Explanation: `mask_name` returns the original string unchanged when `len(clean) <= 3`. `mask_email` returns `a***@example.com`, which is essentially the full email for a one-character local part (e.g., `a@example.com`). These redactions are weaker than the spec examples and can disclose data.

- **P2 — `lead_batch_service.py` may pass `None` to the encryption cipher for `title`**
  - Evidence: `nowing_backend/app/services/lead_batch_service.py` lines 1066–1069.
  - Explanation: `"title": self._cipher.encrypt(lead.get("title"))` will call `encrypt` with `None` when the lead has no title. The original code stored `title` as `None` without encryption. If `VerifiedContactEncryption.encrypt` does not accept `None`, batch ingestion will crash for leads without a title.

- **P2 — `phone_waterfall_service.py` stores a hardcoded Vietnamese fallback name and generic title**
  - Evidence: `nowing_backend/app/services/phone_waterfall_service.py` lines 1136–1137.
  - Explanation: `name=self.encryption.encrypt(lead.company_name or "Doanh nghiep")` and `title=self.encryption.encrypt("Lead Contact")` use a hardcoded non-English default and a generic title. This is unfriendly to non-Vietnamese users and may cause masking/unlock display issues when `company_name` is missing.

- **P2 — `LeadRead` schema expanded with `name` and `email`, widening PII exposure surface**
  - Evidence: `nowing_backend/app/lead_intelligence/schemas.py` lines 564–565; `nowing_backend/app/routes/leads_routes.py` lines 712–773.
  - Explanation: The schema now carries two extra PII fields. While `_map_lead_to_read` masks them, any other endpoint or direct use of `LeadRead` that does not go through this mapper can leak encrypted or unmasked PII, and the masking logic is centralized in one mapper that is easy to bypass.

- **P2 — `pii_opt_out` route hardcodes `global_scope=False`, making global opt-out unreachable**
  - Evidence: `nowing_backend/app/routes/lead_batch_routes.py` lines 686–687.
  - Explanation: `OptOutService.process_opt_out` supports `global_scope`, but the route always passes `False`. A data-subject global Right-to-be-Forgotten flow cannot be exercised, and the permission check does not distinguish superadmin scope.

- **P2 — `zero_publication.py` is not updated for the new PII-derived HMAC columns**
  - Evidence: `nowing_backend/app/db.py` lines 476–479 add `value_hmac`, `phone_hmac`, `email_hmac` to `VerifiedContact` and `Lead`. The story doc explicitly warns at line 239 to “verify `app/zero_publication.py`”. No change to `app/zero_publication.py` appears in the diff.
  - Explanation: CDC publication may include the new HMAC columns for `leads` or `verified_contacts`, leaking PII-derived data into the cache stream. `verified_contacts` itself must not be published at all.

- **P2 — `VerifiedContact` blind-index columns use single-column indexes instead of required composite indexes**
  - Evidence: `nowing_backend/app/db.py` lines 478–479 set `phone_hmac = Column(..., index=True)` and `email_hmac = Column(..., index=True)`. The story doc lines 146–147 require indexes on `(workspace_id, phone_hmac)` and `(workspace_id, email_hmac)`.
  - Explanation: `OptOutService` filters by `workspace_id` and `phone_hmac`/`email_hmac`. A single-column index on `phone_hmac` is not selective and may not be used for that query shape; a composite index is required by the AC.

- **P2 — DNC record creation is racy and not protected by `SELECT FOR UPDATE`**
  - Evidence: `nowing_backend/app/services/pii/opt_out_service.py` `_ensure_dnc_record` lines 1382–1429.
  - Explanation: It queries for an existing `WorkspaceDncRecord` and inserts if none. Two concurrent opt-outs for the same value can both see `existing is None` and insert duplicates. If the unique constraint on `(workspace_id, record_type, value_hmac)` does not exist, duplicates will be persisted; if it does, one will get an `IntegrityError`. The story doc Q4 at line 401 explicitly calls this out.

- **P2 — `ContactUnlockResponse` returns extra decrypted PII fields and may crash on purged contacts**
  - Evidence: `nowing_backend/app/routes/lead_batch_routes.py` lines 608–611 and 626–636 and 643–647.
  - Explanation: AC-5 only requires `phone` and `email` in the unlock response, but the response now decrypts and returns `name` and `title` too. It also calls `enc.is_encrypted()` and `enc.decrypt()` on fields that may be `None` after an opt-out purge; if `is_encrypted` does not accept `None`, an idempotent re-unlock of a purged contact will 500.

- **P2 — `record_contact_unlock_refund` credits the wallet before adding the refund `BillingEvent`**
  - Evidence: `nowing_backend/app/services/billing_event_service.py` lines 833–853; same pattern in `nowing_backend/app/services/pii/opt_out_service.py` `_refund_credit` lines 1361–1379.
  - Explanation: `wallet_credit.apply_credit()` commits first (because it calls `session.commit()`), then the refund `BillingEvent` is added. If the caller aborts before its next flush, the wallet is credited but no refund `BillingEvent` is written, breaking the financial ledger.
