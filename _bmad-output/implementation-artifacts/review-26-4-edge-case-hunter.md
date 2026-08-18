# Story 26.4 Edge-Case / Production-Readiness Review

**Scope:** PII Vault, HMAC deduplication, Decree 13 Right-to-be-Forgotten opt-out, and hardened contact unlock.
**Reviewed:** `nowing_backend/app/routes/lead_batch_routes.py`, `nowing_backend/app/services/pii/opt_out_service.py`, `nowing_backend/app/services/lead_batch_service.py`, `nowing_backend/app/services/billing_event_service.py`, `nowing_backend/app/services/wallet_credit.py`, `nowing_backend/app/services/workspace_credit_service.py`, `nowing_backend/app/db.py`, `nowing_backend/app/lead_intelligence/dnc/normalizer.py`, `nowing_backend/app/services/phone_waterfall_service.py`, `nowing_backend/app/lead_intelligence/enrichment/service.py`, plus DNC/billing callers.
**Severity legend:**
- **P0** — data loss, money loss, PII leakage, or production outage; must block release.
- **P1** — correctness / compliance / race bug; fix before broad use.
- **P2** — test gap, performance, code hygiene, or minor UX.

---

## Executive Summary

The biggest cluster of risks is **transaction management in the new routes**: `pii_opt-out`, `unlock_contact`, and the existing `batch_ingest_leads` all leave the database session uncommitted. Because `get_async_session` is a simple `async_session_maker()` context and SQLAlchemy rolls back an uncommitted base transaction on `Session.close()`, the routes will appear to succeed while silently discarding PII purges, audit logs, `is_unlocked` flags, and DNC records. At the same time, `wallet_credit.apply_credit` / `apply_debit` commit early, so wallet money moves even when the rest of the work is lost. This combination is a P0 production blocker.

Other critical gaps: no Alembic migration for the new blind-index columns / `NOT NULL` / full unique constraints, legacy rows will have NULL `phone_hmac`/`email_hmac` so opt-out will miss them, and several race conditions exist around refunds and unlocks.

---

## P0 — Production blockers

### 1. `pii_opt_out`, `unlock_contact`, and `batch_ingest_leads` routes do not commit

- **Files / lines:**
  - `nowing_backend/app/routes/lead_batch_routes.py:105` (`batch_ingest_leads` returns without `session.commit()`)
  - `nowing_backend/app/routes/lead_batch_routes.py:239` (`unlock_contact` calls `await session.flush()` then returns)
  - `nowing_backend/app/routes/lead_batch_routes.py:303` (`pii_opt_out` calls `await session.flush()` then returns)
  - `nowing_backend/app/db.py:4107-4109` (`get_async_session` yields an `AsyncSession` and does not commit on exit)
  - SQLAlchemy `RootTransaction._close_impl` rolls back active base transactions when `Transaction.close()` is invoked from `Session.close()`.

- **Problem:** `get_async_session` is a plain `async with async_session_maker() as session: yield session`. When the route returns, `session.close()` runs. An uncommitted base transaction is rolled back. The routes only `flush()`, so all the DML they issue is visible in the current transaction but **never persisted**.

- **Impact:**
  - `pii_opt_out` can return a `dnc_record_id` and a `purged_contact_count` that are not actually in the database.
  - `unlock_contact` debits the wallet, returns decrypted PII, but `is_unlocked` and the audit log are rolled back → the contact can be charged again on the next call.
  - `batch_ingest_leads` appears to succeed but no leads or verified contacts are persisted.

- **Recommendation:** Add `await session.commit()` at the end of every write route in `lead_batch_routes.py`. Then verify that `BillingEventService` and `wallet_credit` commit semantics produce a single durable transaction (see P0 #2).

---

### 2. `wallet_credit.apply_credit` / `apply_debit` commit mid-work, splitting the transaction

- **Files / lines:**
  - `nowing_backend/app/services/wallet_credit.py:112` (`apply_debit` calls `await session.commit()`)
  - `nowing_backend/app/services/wallet_credit.py:147` (`apply_credit` calls `await session.commit()`)
  - `nowing_backend/app/services/billing_event_service.py:332` (`_record_business_event` calls `apply_debit` **before** `session.add(event)`)
  - `nowing_backend/app/services/pii/opt_out_service.py:194` (`_refund_credit` calls `apply_credit` **before** `session.add(event)`)

- **Problem:** Both helpers call `session.commit()`. After they return, a new transaction begins. Any `BillingEvent` or ORM mutations added afterwards sit in a separate, uncommitted transaction. The calling routes then fail to commit that second transaction (P0 #1), so the ledger row and the final state changes are lost even though the wallet was already debited/credited.

- **Impact:**
  - `unlock_contact`: user is charged, but the `BillingEvent` (`contact_unlock`), `is_unlocked=True`, and `pii_access_audit_logs` are not persisted.
  - `pii_opt_out`: wallet is credited, but some refund `BillingEvent`s and some contact purges may never be committed, depending on where the loop ends. The response overstates what was actually done.

- **Recommendation:** Remove the inner `session.commit()` from `wallet_credit.apply_credit` / `apply_debit` and let the top-level caller commit once. If that is too risky for other callers, wrap the opt-out / unlock flow in an explicit `async with session.begin():` and pass the same transaction to a non-committing wallet helper. At minimum, add `await session.commit()` to the routes and accept split transactions as a known limitation.

---

### 3. `OptOutService` reimplements refund without the existing idempotent helper

- **Files / lines:**
  - `nowing_backend/app/services/pii/opt_out_service.py:182-213` (`_refund_credit`)
  - `nowing_backend/app/services/billing_event_service.py:91-161` (`record_contact_unlock_refund` — unused)

- **Problem:** `BillingEventService.record_contact_unlock_refund` already exists, checks for an existing refund `BillingEvent`, falls back to `user_id` when the original payer is missing, and emits the negative-cost `BillingEvent`. `OptOutService._refund_credit` does none of this.

- **Impact:**
  - A second opt-out call on a contact whose `is_unlocked=False` change was not committed can refund again because `_refund_credit` does not look for an existing refund `BillingEvent`.
  - If `original_event.user_id` is `None`, the refund is silently skipped (design D2 requires a workspace-owner fallback).

- **Recommendation:** Replace `_refund_credit` with `BillingEventService.record_contact_unlock_refund`, or at least copy its idempotency check and `payer_id` fallback.

---

### 4. Concurrent opt-out / unlock flows have no row-level locking

- **Files / lines:**
  - `nowing_backend/app/services/pii/opt_out_service.py:108-148` (refund-cap count from a snapshot, not locked)
  - `nowing_backend/app/services/pii/opt_out_service.py:309-320` (matched contacts selected without `FOR UPDATE`)
  - `nowing_backend/app/services/billing_event_service.py:289-320` (duplicate billing check without `FOR UPDATE`)

- **Problem:**
  - `refundable_slots` is computed from a `SELECT` that is not locked. Two simultaneous `pii_opt_out` requests can each see the same remaining slots.
  - `process_opt_out` does not lock the matched `VerifiedContact` rows.
  - `record_contact_unlock` checks for an existing `BillingEvent` without `FOR UPDATE`.

- **Impact:**
  - Concurrent unlocks of the same contact can both pass the duplicate check and both debit the wallet.
  - Concurrent opt-outs can over-refund and over-purge the same contact.

- **Recommendation:**
  - Lock matched `VerifiedContact` rows with `select(...).with_for_update()`.
  - Lock the workspace refund cap (e.g., advisory lock, or a dedicated `workspace_billing_cycle_refund` row). Use `SELECT ... FOR UPDATE` in `BillingEventService` duplicate checks.

---

### 5. No Alembic migration for the new schema and no backfill plan

- **Files / lines:**
  - `nowing_backend/app/db.py:4673` (`Lead.value_hmac` is `nullable=False`)
  - `nowing_backend/app/db.py:5229-5241` (`VerifiedContact.value_hmac` `nullable=False`, plus new `phone_hmac`/`email_hmac`)
  - `nowing_backend/alembic/versions/` (no new migration found)
  - `nowing_backend/alembic/versions/ac475d54f6a2_story_26_1_chainlens_chunks_and_.py` (created `verified_contacts.value_hmac` as `nullable=True` with a **partial** unique index)
  - `nowing_backend/alembic/versions/224_*.py` (lead partial unique index)

- **Problem:** The ORM models declare non-nullable `value_hmac`, new `phone_hmac`/`email_hmac` columns, and full `UNIQUE(workspace_id, value_hmac)` constraints, but there is no migration to realize this in PostgreSQL. The existing partial unique indexes are also inconsistent with the model’s full unique constraints.

- **Impact:**
  - `alembic upgrade head` will not create the new columns/constraints.
  - Existing rows with `NULL` `value_hmac` or duplicate `(workspace_id, value_hmac)` will break when `NOT NULL` / full uniqueness is applied.
  - Existing rows lack `phone_hmac`/`email_hmac`, so `process_opt_out` will not find them.

- **Recommendation:**
  1. Add a new Alembic revision after the current head.
  2. Add `phone_hmac` / `email_hmac` as nullable.
  3. Backfill `verified_contacts.value_hmac`, `phone_hmac`, `email_hmac`, and `leads.value_hmac` for every row using the canonical helpers.
  4. Resolve duplicate HMACs (merge or rename) before applying `NOT NULL`.
  5. Drop the partial unique indexes and create full `UNIQUE(workspace_id, value_hmac)` constraints.
  6. Add composite indexes `(workspace_id, phone_hmac)` and `(workspace_id, email_hmac)`.

---

### 6. Opt-out blind-index matching will miss pre-existing contacts

- **Files / lines:**
  - `nowing_backend/app/services/pii/opt_out_service.py:304-320`
  - `nowing_backend/app/db.py:5233-5235` (`phone_hmac`/`email_hmac` added as `nullable=True`)

- **Problem:** `process_opt_out` only searches by `phone_hmac` or `email_hmac`. Any `VerifiedContact` created before these blind-index columns were populated will not be matched and will never be purged.

- **Impact:** Data-subject opt-outs are only partially honored; pre-existing PII remains in the database.

- **Recommendation:** Backfill all existing `VerifiedContact` rows (P0 #5) and/or add a fallback query by `value_hmac` or by a controlled decrypt-and-match scan.

---

## P1 — Correctness, compliance, and race bugs

### 7. `LeadBatchService` contact upsert can overwrite an opted-out / purged contact

- **Files / lines:**
  - `nowing_backend/app/services/lead_batch_service.py:232-245`

- **Problem:** The `ON CONFLICT DO UPDATE` on `(workspace_id, value_hmac)` updates `name`, `title`, `email`, `phone`, `phone_hmac`, and `email_hmac` but does **not** include `WHERE` guard to prevent overwriting a row whose `consent_status='withdrawn'` or `is_valid=False`. It also does not reset `is_unlocked=False` on conflict, so re-ingesting an already-unlocked contact keeps the new PII immediately visible.

- **Impact:**
  - If the DNC record for an opted-out contact is missing (e.g., because of P0 #1), re-ingest can resurrect PII.
  - Re-ingesting an unlocked contact with the same `value_hmac` (same phone/email/domain) overwrites encrypted PII while `is_unlocked=True`, exposing the new PII without a new billing event.

- **Recommendation:**
  - Add a `WHERE` clause to the upsert so it does not update rows with `consent_status='withdrawn'`.
  - Or, on conflict, re-lock the contact (`is_unlocked=False`) and require a new unlock.

---

### 8. `LeadBatchService` bulk contact insert can fail with `CardinalityViolation`

- **Files / lines:**
  - `nowing_backend/app/services/lead_batch_service.py:232-245`

- **Problem:** `contacts_to_insert` is built from the (deduplicated) `prepared` lead list, but there is no in-memory deduplication by `value_hmac` for verified contacts. Two leads with the same phone/email/domain in the same batch will produce two rows with the same `(workspace_id, value_hmac)` and the `INSERT ... ON CONFLICT DO UPDATE` will attempt to update the same row twice in one statement.

- **Impact:** PostgreSQL raises `CardinalityViolation` and the entire batch fails.

- **Recommendation:** Deduplicate `contacts_to_insert` by `(workspace_id, value_hmac)` before passing it to `pg_insert(...).values(...)`.

---

### 9. `unlock_contact` maps any `Exception` to HTTP 402

- **Files / lines:**
  - `nowing_backend/app/routes/lead_batch_routes.py:211-224`

- **Problem:** The `try/except Exception` around `record_contact_unlock` re-raises **any** failure as a `402 Payment Required`. This hides duplicate-billing `ValueError`s, `IntegrityError`s, `BillingEvent` serialization errors, etc.

- **Impact:** Misleading client errors and obscured production bugs; HTTP 402 may be returned for a DB outage.

- **Recommendation:** Catch specific exception types (`InsufficientCreditsError`, validation `ValueError`) and map to 402/422/500 accordingly.

---

### 10. `unlock_contact` does not check `consent_status` or `is_valid` before billing

- **Files / lines:**
  - `nowing_backend/app/routes/lead_batch_routes.py:194-209`

- **Problem:** The route returns decrypted PII if `contact.is_unlocked` is already `True`. It does not check whether `consent_status='withdrawn'` or `is_valid=False`. For an opted-out contact it would bill and return `None` for the PII fields.

- **Impact:** User is charged for an opted-out contact that has no PII.

- **Recommendation:** Reject unlock with `403` or `409` when `consent_status='withdrawn'` or `is_valid=False`.

---

### 11. `OptOutService._count_refundable_unlocks_this_cycle` over-refunds for small workspaces

- **Files / lines:**
  - `nowing_backend/app/services/pii/opt_out_service.py:108-148`

- **Problem:**
  - `allowed = max(1, int(total_unlocked * 0.15))` means for 1–6 unlocked contacts the refund cap is 1 contact, i.e. 100%–16.7% of unlocks, not 15%.
  - `total_unlocked` is the current `is_unlocked=True` snapshot, not the number of unlock events in the billing cycle.
  - It materializes all `VerifiedContact` rows into Python memory with `scalars().all()` instead of using `func.count`.

- **Impact:** Small workspaces can refund more than the 15% policy. Large workspaces may scan unnecessarily large result sets.

- **Recommendation:** Count `BillingEvent` with `event_type='contact_unlock'` in the current billing cycle, use `func.count`, and replace `max(1, ...)` with `max(0, ...)` or a documented minimum.

---

### 12. `pii_opt_out` ignores `body.reason` and hardcodes `global_scope=False`

- **Files / lines:**
  - `nowing_backend/app/routes/lead_batch_routes.py:281-289`
  - `nowing_backend/app/services/pii/opt_out_service.py:264-302`

- **Problem:**
  - `PIIOptOutRequest.reason` is never passed to `process_opt_out`; the service always uses `"Right to be forgotten"`.
  - `global_scope=False` is hardcoded and `process_opt_out` always filters by `workspace_id` even though `global_scope=True` exists in `_ensure_dnc_record`.

- **Impact:** The data subject’s reason is lost; superadmin/global opt-out is unreachable.

- **Recommendation:** Add `reason` to `process_opt_out` signature, propagate it, and implement a separate superadmin `/pii-opt-out?global=true` path that removes the workspace filter.

---

### 13. `BillingEventService.record_contact_unlock_refund` is dead code

- **Files / lines:**
  - `nowing_backend/app/services/billing_event_service.py:91-161`

- **Problem:** The method is unit-tested but never called by `OptOutService`. It has the same inner-commit issue as `record_contact_unlock`, and it duplicates logic.

- **Impact:** Two diverging refund implementations; maintenance risk.

- **Recommendation:** Either make `OptOutService` use it (after fixing P0 #2) or delete it.

---

### 14. `compute_verified_contact_hmac` can crash enrichment on degenerate contacts

- **Files / lines:**
  - `nowing_backend/app/lead_intelligence/dnc/normalizer.py:158-176`
  - `nowing_backend/app/lead_intelligence/enrichment/service.py:257-262`

- **Problem:** `compute_verified_contact_hmac` raises `ValueError` when phone, email, and domain are all empty. An enrichment provider returning a name-only contact with `lead.domain=None` will raise and abort the entire enrichment.

- **Impact:** Enrichment batch fails for a single degenerate contact.

- **Recommendation:** Skip contacts that cannot produce a valid `value_hmac` and log them, rather than letting the exception propagate.

---

### 15. `get_company_graph` and `ExportService` can leak encrypted tokens or ciphertext

- **Files / lines:**
  - `nowing_backend/app/routes/leads_routes.py:505-533` (`get_company_graph` uses `c.name` and `c.email` directly; only `c.phone` is decrypted/masked)
  - `nowing_backend/app/services/export_service.py:601-758` (`mask_email`/`mask_phone` are applied to encrypted tokens; `mask_name` is added but unused)

- **Problem:**
  - `get_company_graph` returns `c.name` and `c.email` as raw encrypted tokens (it builds the LinkedIn slug from ciphertext).
  - `ExportService` does not decrypt before masking. `mask_email` on a base64 token with no `@` returns the full token; `mask_name` is unused.

- **Impact:** Encrypted PII tokens are returned to clients / exported to third parties; not true redaction.

- **Recommendation:** Decrypt PII in display/export paths, then apply `mask_name`, `mask_email`, and `mask_phone` consistently. Do not render raw tokens.

---

## P2 — Test gaps, performance, and code hygiene

### 16. Unit and integration tests do not validate `session.commit()` or concurrency

- **Files / lines:**
  - `nowing_backend/tests/unit/services/test_pii_opt_out_service.py:37-270`
  - `nowing_backend/tests/integration/routes/test_pii_opt_out.py:1-300`
  - `nowing_backend/tests/unit/services/test_lead_batch_service.py:1-400`

- **Problem:** Tests use `_FakeSession` that records `added` but does not assert `commit()` was called. Integration tests share `db_session` with the route, so an uncommitted transaction is still visible to the same connection.

- **Impact:** The P0 missing-commit bug will not be caught by the current suite.

- **Recommendation:**
  - Assert `session.committed` in unit tests.
  - Add integration tests that open a **new** `AsyncSession` after the route to verify persistence.
  - Add concurrency tests (two simultaneous unlocks / opt-outs on the same contact).

---

### 17. `_count_refundable_unlocks_this_cycle` is O(n) in memory

- **Files / lines:**
  - `nowing_backend/app/services/pii/opt_out_service.py:108-123`

- **Problem:** It fetches all `VerifiedContact` rows where `is_unlocked=True` into a Python list and then filters again in a list comprehension.

- **Impact:** Slow for workspaces with many unlocked contacts; memory pressure.

- **Recommendation:** Use `select(func.count(VerifiedContact.id))` and a supporting index.

---

### 18. `pii_opt_out` route may record the proxy / last-hop IP

- **Files / lines:**
  - `nowing_backend/app/routes/lead_batch_routes.py:288`

- **Problem:** `ip_address = getattr(request, "client", None) and request.client.host` gives the immediate TCP peer, which behind a load balancer is the load balancer, not the data subject.

- **Impact:** Audit logs record the wrong IP.

- **Recommendation:** Use `X-Forwarded-For` / `CF-Connecting-IP` headers with a trusted-proxy allowlist.

---

### 19. `mask_name` leaves very short names unmasked

- **Files / lines:**
  - `nowing_backend/app/services/export_service.py:616-623`

- **Problem:** `if len(clean) <= 3: return clean` exposes short names such as "Anh", "Vy", or "Mai".

- **Impact:** Possible short-name PII leakage in masked views.

- **Recommendation:** Always mask at least the middle portion, e.g. `A**`, `V*`, or return a fixed redaction string.

---

### 20. Refund amount is hard-coded and not tied to the original `cost_micros`

- **Files / lines:**
  - `nowing_backend/app/services/pii/opt_out_service.py:29`
  - `nowing_backend/app/services/pii/opt_out_service.py:188-213`

- **Problem:** `_REFUND_AMOUNT_MICROS = 1_500` is used regardless of what the original unlock `BillingEvent.cost_micros` was.

- **Impact:** If pricing changes or a contact was unlocked at a different rate, the refund is wrong.

- **Recommendation:** Refund `min(_REFUND_AMOUNT_MICROS, original_event.cost_micros)` or store the exact unlock price and refund that.

---

### 21. `OptOutService` sets `refunded_at` indirectly and does not set `is_valid=False`

- **Files / lines:**
  - `nowing_backend/app/services/pii/opt_out_service.py:41-52` (`_anonymize_contact`)
  - `nowing_backend/app/db.py:5241`

- **Problem:** `VerifiedContact.refunded_at` is not updated on opt-out. `is_valid` remains `True`.

- **Impact:** Purged contacts still appear as valid leads; reports and filters may include them.

- **Recommendation:** Set `refunded_at=datetime.now(UTC)` for contacts that were actually refunded and set `is_valid=False` for all purged contacts.

---

## Summary of files edited / commands run

- **Files inspected (read/grep):**
  - `nowing_backend/app/routes/lead_batch_routes.py`
  - `nowing_backend/app/services/pii/opt_out_service.py`
  - `nowing_backend/app/services/lead_batch_service.py`
  - `nowing_backend/app/services/billing_event_service.py`
  - `nowing_backend/app/services/wallet_credit.py`
  - `nowing_backend/app/services/workspace_credit_service.py`
  - `nowing_backend/app/db.py`
  - `nowing_backend/app/lead_intelligence/dnc/normalizer.py`
  - `nowing_backend/app/lead_intelligence/dnc/service.py`
  - `nowing_backend/app/services/phone_waterfall_service.py`
  - `nowing_backend/app/lead_intelligence/enrichment/service.py`
  - `nowing_backend/app/routes/leads_routes.py`
  - `nowing_backend/app/services/export_service.py`
  - `nowing_backend/app/services/lead_intelligence/services/lead_stream_service.py`
  - `nowing_backend/tests/unit/services/test_pii_opt_out_service.py`
  - `nowing_backend/tests/integration/routes/test_pii_opt_out.py`
  - `nowing_backend/tests/unit/routes/test_lead_batch_ingest.py`
  - `nowing_backend/alembic/versions/ac475d54f6a2_story_26_1_chainlens_chunks_and_.py`
- **Files created:**
  - `nowing_backend/_bmad-output/implementation-artifacts/review-26-4-edge-case-hunter.md`
- **Commands run:**
  - `git status --short` (repo state)
  - `grep` and `read` searches across the above files
  - Python `inspect.getsource` on SQLAlchemy `RootTransaction` / `SessionTransaction` to confirm rollback-on-close behavior

---

## Recommended order of remediation

1. **P0 #1 & #2:** Add `await session.commit()` to `lead_batch_routes.py` routes and remove / centralize the inner `session.commit()` in `wallet_credit`/`BillingEventService`. Validate with a new integration test that opens a fresh session.
2. **P0 #3:** Make `OptOutService` reuse `BillingEventService.record_contact_unlock_refund` (or add its idempotency/payer-fallback logic).
3. **P0 #4:** Add `FOR UPDATE` locking in refund/unlock paths.
4. **P0 #5 & #6:** Create the Alembic migration, backfill `value_hmac` / `phone_hmac` / `email_hmac`, and apply `NOT NULL` / full unique constraints. Make `process_opt_out` match legacy rows if needed.
5. **P1 #7, #8, #9, #10, #11, #12, #14, #15:** Fix upsert guards, exception mapping, `consent_status` checks, refund-cap math, reason/global handling, enrichment degenerate contacts, and dead-code cleanup.
6. **P1 #15 & P2 #16+:** Add display/export decryption, `mask_name` usage, concurrency tests, commit assertions, and performance fixes.
