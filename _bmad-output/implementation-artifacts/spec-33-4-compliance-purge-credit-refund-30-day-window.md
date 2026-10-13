# Story 33.4: Compliance-Purge Credit Refund (30-Day Window)

**Status:** ready-for-dev (spec patched 2026-10-13 sau dev review — 5 fixes F1–F5)
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
