---
baseline_revision: 0f03d28ef979c7a1fe4f7cdfa391f3b4841c3913
status: done
followup_review_recommended: true
---

# Story 33.4: Compliance-Purge Credit Refund (30-Day Window)

**Status:** done (implemented + reviewed 2026-10-14 — 15 medium + 6 low patched; follow-up review recommended)
**Nguồn:** `epic-33-retro-item-35` — policy đã duyệt: `_bmad-output/planning-artifacts/credit-refund-policy-compliance-purge-draft-2026-10-13.md` (Phương án C, approved 2026-10-13)

## Intent

As a Workspace Owner, I want credits refunded when a contact I unlocked is force-purged by a legal/compliance request within 30 days of unlock, so that I am not financially penalized for data removal I did not cause — and I get an in-app notification explaining what happened.

## Policy đã duyệt (Phương án C)

1. **Cửa sổ hoàn:** contact bị compliance-purge trong vòng **30 ngày** kể từ lần unlock gần nhất **có charge** → hoàn **100% credit đã chi** cho unlock đó về workspace wallet. Quá 30 ngày → không hoàn, vẫn notify.
2. **15% auto-refund budget cap** (existing guardrail): phần refund vượt cap chuyển sang support manual review. Purge pháp lý **không bao giờ bị chặn** bởi budget.
3. **In-app notification** cho workspace owner: count leads/contacts ảnh hưởng + credit hoàn + lý do chuẩn ("gỡ bỏ theo yêu cầu bảo vệ dữ liệu cá nhân"). **KHÔNG lộ PII đã purge** — chỉ count + tên lead đã redact.
4. **Audit:** `credits_refunded` trong purge report response + `BillingEvent(contact_unlock_refund)` + structured log. Contact-level `pii_access_audit_logs`/`refunded_at` **không áp dụng** (contact row đã bị xóa).
5. **Không retroactive:** chỉ áp dụng cho purge sau ngày story hiệu lực.
6. **Self-host/DSH:** không có credit system → skip refund, vẫn notify nếu có notification channel.

## Architecture — Two-Phase Post-Commit (F3)

`wallet_credit.apply_credit` (`app/services/wallet_credit.py:151`) gọi `session.commit()` hard-coded → refund **không thể** nằm trong purge transaction. Do đó chia 2 phase:

- **Phase 1 — Purge (trong `purge_individual`, giữ nguyên atomicity hiện tại):** collect `refund_candidates: list[{verified_contact_id, workspace_id}]` từ các `VerifiedContact` bị xóa (contact object vẫn còn id trong memory) → gắn vào return payload. Route `session.commit()` như hiện tại → deletes atomic.
- **Phase 2 — Refund + Notify (post-commit, best-effort):** sau `session.commit()` trong route (`app/routes/admin_dnc_routes.py:228`), loop `refund_candidates` → gọi refund + notification. Mỗi candidate fail → catch riêng, không fail response. `credits_refunded`/`refunds_skipped` merge vào response sau phase 2.

  Alternative được chấp nhận: phase 2 trong cùng `purge_individual` sau khi caller commit — nhưng route-level orchestration sạch hơn, giữ `purge_individual` thuần delete.

## Acceptance Criteria

- **AC-1:** `CompliancePurgeService.purge_individual` (`app/services/compliance_purge_service.py:51`) — trước `session.delete(contact)`, append `(contact.id, contact.workspace_id)` vào `refund_candidates`; return dict thêm key `"refund_candidates"`. Phase 2 (trong route `compliance_purge`): với mỗi candidate gọi `BillingEventService().record_contact_unlock_refund_24h(session, verified_contact_id=…, workspace_id=…, user_id=actor, cost_micros=<original.cost_micros>, refund_window_hours=720)`.
  - **Cost trap (bắt buộc):** `cost_micros` param default = 1500 → `refund_micros = min(1500, original_cost)` sẽ hoàn thiếu. Phải pass `cost_micros` = cost của `contact_unlock` BillingEvent gốc (query trước) hoặc ceiling đủ lớn; kiểm chứng bằng test case original_cost > 1500.
  - **Exception map (catch per-candidate, không re-raise):**
    - `RefundWindowExpiredError` → skip refund, vẫn notify (`refunds_skipped += 1`, reason=`window_expired`)
    - `NoOriginalUnlockEventError` → no-charge/self-host → skip, không notify-required (`refunds_skipped += 1`, reason=`no_unlock_charge`)
    - `RefundAlreadyProcessedError` → skip (`refunds_skipped += 1`, reason=`already_refunded`)
    - `RefundBudgetExhaustedError` → skip + `logger.warning("purge_refund_budget_exhausted", …)` (`refunds_skipped += 1`, reason=`budget_exhausted`) — support manual review ngoài phạm vi code.
- **AC-2:** Response `POST /admin/dnc/purge` trả `credits_refunded` (int, micros — tổng `abs(event.cost_micros)` của refund thành công) và `refunds_skipped` (int count) + `refund_details` (list `{contact_id, workspace_id, status, refunded_micros|skip_reason}`). Giữ nguyên shape spec 33.2.
- **AC-3:** Mỗi workspace có ≥1 refund thành công HOẶC ≥1 `window_expired` skip → `NotificationService.create_notification(session, user_id=workspace.user_id, notification_type="compliance_purge_refund", workspace_id=ws_id, …)` — `Workspace.user_id` = owner (`app/models/workspaces.py:158`). Body: số contact bị gỡ, credit hoàn (đổi ra credits), lý do chuẩn. Không embed phone/email/name đã purge. Notification trong phase 2, same session; lỗi notify → `logger.warning`, không fail.
- **AC-4:** Idempotent — purge re-run cùng record: contact đã xóa không match lại → `refund_candidates` rỗng; nếu gọi lại cùng contact_id thì `existing_refunds` check trong `record_contact_unlock_refund_24h` trả về event cũ → không double-credit. Test cả hai.
- **AC-5:** `RefundBudgetExhaustedError` → structured warning log + count vào `refunds_skipped(reason=budget_exhausted)` + purge vẫn hoàn tất. (Không có `BillingEvent.status` column — manual-review queue ngoài scope, log là bằng chứng.)
- **AC-6:** Self-host/no-credit → `NoOriginalUnlockEventError` path; không crash, notify optional. Unit test với session không có BillingEvent nào.

## Technical Notes

- Reuse `record_contact_unlock_refund_24h` (`app/services/billing_event_service.py:349`) — có sẵn idempotency (`existing_refunds`/`existing_relocks` + `_acquire_billing_lock`), window check, 15% cap across current+original billing cycles. Precedent: `app/services/dsh_telegram_checkpoint_service.py:795` (param `refund_window_hours`).
- **Không** dùng `record_contact_unlock_refund` (`:130`) — method đó cho opt-out flow, refund vô điều kiện, không window/cap.
- `_mark_contact_invalid_for_refund` (`:515`) sẽ no-op cho purged contact (`session.get` → None) — expected; audit nằm ở `BillingEvent` + log.
- New config optional: `COMPLIANCE_PURGE_REFUND_WINDOW_HOURS` default 720 trong `app/config/dsh.py` (gần `DSH_TELEGRAM_REFUND_WINDOW_HOURS`) — cho phép tune mà không deploy code.
- Multi-workspace cùng unlock 1 contact: mỗi `(contact_id, workspace_id)` refund độc lập — ledger per-workspace đã handle.
- Window tính từ `contact_unlock` BillingEvent `created_at` mới nhất — `_list_billing_events` lấy `original_rows[0]`; verify ordering trong test (unlock→relock→unlock lại case).

## Tests

- Unit: `tests/unit/services/test_compliance_purge_service.py` — refund trong cửa sổ (720h), ngoài cửa sổ (notify-only), `cost_micros > 1500` full refund, idempotent re-run, budget cap → skipped, `NoOriginalUnlockEventError` → self-host path, notify recipient = `workspace.user_id`.
- Integration: purge end-to-end với workspace wallet thật → `credit_micros_balance`/`available_balance` tăng đúng + `BillingEvent` refund row + `Notification` row tồn tại; `purged_counts` + `credits_refunded` đúng trong response.

## Definition of Done

- AC 1–6 pass unit + integration; ruff/format clean.
- ToS/privacy docs: thêm điều khoản "compliance removal" (tách task docs nếu legal cần review riêng).
- Mark `epic-33-retro-item-35` → done (đã done — policy stage).

## Review Triage Log

### 2026-10-14 — Review pass
- verdicts: 32 findings — high 0, medium 15, low 9, false 8, maybe-false 0
- findings:
  - `[medium]` `[patch]` BH1 `target_user_id` fallback `actor_user_id` (superadmin wallet bị credit) → `uuid.uuid4()` (crash "User not found") — patched: fallback `Workspace.user_id` qua `_workspace_owner_id`; không resolve được → skip `missing_user_id`, không fabricate uuid.
  - `[medium]` `[patch]` BH2 response contract sai AC-2 (fields lồng trong `refund_summary`, key khác spec) — patched: route emit top-level `credits_refunded`/`refunds_skipped`/`refund_details`.
  - `[false]` `[reject]` BH3 notification title/metadata "deviation khỏi AC-3" — reviewer bịa title + metadata schema mà spec không hề quy định; AC-3 chỉ yêu cầu counts + credits + reason chuẩn + no-PII (đã đủ).
  - `[medium]` `[patch]` BH4 notification recipient query `WorkspaceMembership.is_owner` + fallback `actor_user_id` (superadmin nhận notif) — patched: `Workspace.user_id` (workspaces.py:158) per spec AC-3, miss → warn+skip.
  - `[medium]` `[patch]` BH5 unhandled exception phase-2 → HTTP 500 sau khi phase-1 đã commit — patched: route wrap try/except → log + partial `refund_summary.error` + HTTP 200.
  - `[medium]` `[patch]` BH6 catch-all thiếu `session.rollback()` → transaction aborted, cascade fail các candidate sau — patched: `await session.rollback()` trong generic except.
  - `[low]` `[patch]` BH7 zero-cost unlock tăng `refunded_contacts` nhưng `refunded_micros_ws==0` → notify bị suppress + fallback `else 1500` ép cost — patched: notify condition theo `workspace_refunded_count` (count), pass `orig_cost` kể cả 0.
  - `[low]` `[patch]` BH8 `is_unlocked` flag bị bỏ qua khi collect candidates (tốn 2 billing query/contact chưa từng unlock) — patched: `was_unlocked` flag → skip sớm sau khi đếm `purged_count`; semantics xác nhận: `contact_unlock_service.py:164` set `is_unlocked=True` = "đã từng unlock".
  - `[low]` `[patch]` BH9 `str(exc)` lộ vào API response — patched: map `internal_error`, chi tiết giữ trong log.
  - `[low]` `[patch]` BH10 message/metadata lẫn purged vs refunded count — patched: thêm `refunded_contacts` vào message + metadata.
  - `[medium]` `[patch]` BH11 thiếu tests spec-mandated (AC-4 re-run, ordering unlock→relock→unlock, exception isolation, owner fallback) — patched: +5 unit cases, +AC-4 re-run block trong integration.
  - `[false]` `[reject]` ECH1 malformed `verified_contact_id`/`workspace_id` → ValueError abort loop — unreachable: candidates build từ ORM objects (`contact.id` UUID, `contact.workspace_id` int); đã có guard `if not c_id or ws_id is None: continue`.
  - `[medium]` `[patch]` ECH2 `user_id`+`actor_user_id` đều None → `uuid4` crash — cùng root cause BH1 → patched.
  - `[medium]` `[patch]` ECH3 thiếu rollback trong catch → transaction aborted — cùng root cause BH6 → patched.
  - `[medium]` `[patch]` ECH4 owner-lookup query trong notification section không exception-protected → 500 — cùng root cause BH5 (toàn phase-2 giờ bọc try/except ở route) → patched.
  - `[low]` `[patch]` ECH5 zero-cost unlock → không notify owner — cùng root cause BH7 → patched.
  - `[medium]` `[patch]` ECH6 phase-2 exception sau commit → 500 — cùng root cause BH5 → patched.
  - `[medium]` `[patch]` ECH7 response thiếu AC-2 top-level keys — cùng root cause BH2 → patched.
  - `[medium]` `[patch]` ECH8 notify recipient qua WorkspaceMembership → cùng root cause BH4 → patched.
  - `[false]` `[reject]` VG1 "wallet balance không được assert" — sai: integration test đã `await db_session.refresh(db_user)` + `assert db_user.credit_micros_balance == 1500`.
  - `[false]` `[reject]` VG2 "thiếu integration test cap = vi phạm AC-5" — spec §Tests chỉ mandate unit test cho cap path; `test_budget_exhausted_skips_with_structured_log` đã cover.
  - `[low]` `[reject]` VG3 thiếu multi-candidate/mixed-outcome test — `test_multiple_workspaces_send_isolated_notifications` đã cover 2 ws × 2 candidates; mixed-outcome không spec-mandated, ít khả năng gặp thực tế.
  - `[medium]` `[patch]` VG4 re-run idempotency (AC-4) chưa test — patched: integration re-run POST → purged 0, refund event count == 1.
  - `[medium]` `[patch]` VG5 owner fallback chain chưa test — patched: unit `test_workspace_owner_fallback_when_unlock_user_missing` + `test_missing_recipient_skips_with_missing_user_id`.
  - `[false]` `[reject]` VG6 malformed candidate input tests — cùng refutation ECH1 (unreachable).
  - `[medium]` `[patch]` VG7 exception isolation trong refund loop chưa test — patched: `test_exception_isolation_rolls_back_and_continues`.
  - `[low]` `[reject]` VG8 boundary 720h chưa test — spec không mandate; window logic nằm trong `record_contact_unlock_refund_24h` đã có tests riêng.
  - `[low]` `[reject]` VG9 message format chưa test — spec không mandate exact format.
  - `[low]` `[patch]` VG10 facade `payload` alias thừa + untested — patched: revert `facade.py` hoàn nguyên (param + call-arg xóa → không còn surface cần test).
  - `[false]` `[reject]` IA1 refund credit user wallet không phải "workspace wallet" — spec-consistent: reuse `record_contact_unlock_refund_24h` credit original payer User — đúng billing model hiện có, policy đã duyệt.
  - `[false]` `[reject]` IA2 refund logic coupled admin route — spec §Architecture Two-Phase Post-Commit chính nó chọn orchestration trong route `compliance_purge`.
  - `[false]` `[reject]` IA3 notification là DB row chứ không "in-app" — `Notification` DB row chính là in-app notification mechanism của platform.

## Auto Run Result

- **Summary:** Implement Story 33.4 — hoàn credit khi compliance-purge contact đã unlock trong cửa sổ 30 ngày (Phương án C). `purge_individual` collect `refund_candidates` (kèm `was_unlocked` flag); `process_post_purge_refunds` phase-2 post-commit: idempotency check → newest `contact_unlock` event → `record_contact_unlock_refund_24h(refund_window_hours=720, cost_micros=original.cost)` với exception map 4 loại + catch-all rollback → notify `Workspace.user_id` (không PII). Route emit AC-2 top-level fields; phase-2 failure → HTTP 200 + partial `refund_summary.error`.
- **Files changed:**
  - `nowing_backend/app/config/dsh.py` — `COMPLIANCE_PURGE_REFUND_WINDOW_HOURS` (default 720).
  - `nowing_backend/app/services/compliance_purge_service.py` — `refund_candidates` + `process_post_purge_refunds` (refund loop, exception map, owner resolution, notification, `details`).
  - `nowing_backend/app/routes/admin_dnc_routes.py` — wire 2-phase + AC-2 top-level fields + phase-2 failure isolation.
  - `nowing_backend/tests/unit/services/test_compliance_purge_service.py` — 11 unit cases cho phase-2.
  - `nowing_backend/tests/integration/routes/test_admin_dnc.py` — AC-2 asserts + AC-4 re-run + expired-window e2e.
  - `facade.py` — staged thay đổi (`payload` alias) đã revert hoàn nguyên theo review; không còn diff.
- **Review findings breakdown:** 32 findings (4 layers, model `claude-fable-5-1`). Patched: 15 medium (6 entries: recipient fallback, response contract, notify recipient, phase-2 500, rollback, test coverage) + 6 low (zero-cost notify, is_unlocked guard, str(exc) leak, refunded count, facade alias, missing_user_id). Rejected: 3 low (VG3 mixed-outcome, VG8 720h boundary, VG9 message format — không spec-mandated/đã cover). False: 8 (BH3 fabricated schema, ECH1+VG6 unreachable input, VG1 assert đã có, VG2 unit cap đã đủ, IA×3 spec-consistent). Deferred: 0. intent_gap/bad_spec: 0.
- **Follow-up review recommendation:** `true` — 6 medium entries patched trong 1 pass. Unverified risk: recipient-resolution mới (`session.get(Workspace)` owner path + `missing_user_id` skip) và exception-isolation flow (rollback + route-level catch) chưa qua review lần hai; khuyến nghị follow-up pass vào `compliance_purge_service.py` phase-2.
- **Verification performed:**
  - `uv run ruff format` + `uv run ruff check` trên 6 files đổi → clean (1 file reformatted).
  - `uv run pytest tests/unit/services/test_compliance_purge_service.py -q` → **18 passed** (incl. 5 case mới: newest-unlock ordering, exception isolation+rollback, owner fallback, missing_user_id, was_unlocked skip).
  - `uv run pytest tests/integration/routes/test_admin_dnc.py -q` → **6 passed** (Postgres/Redis host; AC-2 fields, AC-4 re-run idempotent + refund event count==1, expired window notify-only).
  - Jev test gate noul 0.98 → chạy đầy đủ.
  - Patched diff: `/tmp/story-33-4-verify-003.diff` (1280 lines).
- **Residual risks:**
  - `record_contact_unlock_refund_24h` với `cost_micros=0` (zero-cost unlock) ghi BillingEvent refund 0 — đếm refunded nhưng credit 0; chấp nhận được (đúng semantics "đã refund").
  - Phase-2 best-effort: refund skip `internal_error`/`budget_exhausted` không retry tự động — nằm ở `skipped` + structured log cho support xử lý (theo policy).
  - Follow-up review được recommend (xem trên).
