# Story 33.4: Compliance-Purge Credit Refund (30-Day Window)

**Status:** ready-for-dev
**Nguồn:** `epic-33-retro-item-35` — policy đã duyệt: `_bmad-output/planning-artifacts/credit-refund-policy-compliance-purge-draft-2026-10-13.md` (Phương án C, approved 2026-10-13)

## Intent

As a Workspace Owner, I want credits refunded when a contact I unlocked is force-purged by a legal/compliance request within 30 days of unlock, so that I am not financially penalized for data removal I did not cause — and I get an in-app notification explaining what happened.

## Policy đã duyệt (Phương án C)

1. **Cửa sổ hoàn:** contact bị compliance-purge trong vòng **30 ngày** kể từ lần unlock gần nhất **có charge** → hoàn **100% credit đã chi** cho unlock đó về workspace wallet. Quá 30 ngày → không hoàn, vẫn notify.
2. **15% auto-refund budget cap** (existing guardrail): phần refund vượt cap chuyển sang support manual review. Purge pháp lý **không bao giờ bị chặn** bởi budget.
3. **In-app notification** cho workspace owner/admin: count leads/contacts ảnh hưởng + credit hoàn + lý do chuẩn ("gỡ bỏ theo yêu cầu bảo vệ dữ liệu cá nhân"). **KHÔNG lộ PII đã purge** — chỉ count + tên lead đã redact.
4. **Audit:** `credits_refunded` trong purge report response + `BillingEvent(contact_unlock_refund)` với `reference_id` = purge event id (idempotent).
5. **Không retroactive:** chỉ áp dụng cho purge sau ngày story hiệu lực.
6. **Self-host/DSH:** không có credit system → skip refund, vẫn notify nếu có notification channel.

## Acceptance Criteria

- **AC-1:** `CompliancePurgeService.execute_purge` — sau khi xóa `VerifiedContact`, query `CreditTransaction`/`BillingEvent` để tìm unlock charge còn trong cửa sổ 30 ngày cho từng (contact, workspace); với mỗi record đủ điều kiện gọi `BillingEventService.record_contact_unlock_refund` (đã idempotent + serialize-locked sẵn — tái dùng, không viết lại).
- **AC-2:** Response `POST /admin/dnc/purge` trả `credits_refunded` (tổng credit đã hoàn) và `refunds_skipped` (count unlock ngoài cửa sổ / vượt budget cap) — giữ nguyên shape spec 33.2.
- **AC-3:** Mỗi workspace ảnh hưởng nhận `NotificationService.create_notification` (type `compliance_purge_refund`): nội dung gồm số contact bị gỡ, số credit hoàn, lý do chuẩn. Không embed phone/email/name đã purge vào body.
- **AC-4:** Idempotent — chạy lại purge cùng record không tạo refund đúp (tận dụng unique constraint/`FOR UPDATE` trong `record_contact_unlock_refund`).
- **AC-5:** Budget cap vượt → refund phần đó ghi `BillingEvent` status `manual_review` (hoặc tương đương) + structured log; purge vẫn hoàn tất.
- **AC-6:** Self-host (không có `WalletCreditService`/credits) → skip refund branch, không crash.

## Technical Notes

- Reuse `app/services/billing_event_service.py::record_contact_unlock_refund` (Story 26.4) — đã có idempotency lock, window/budget exceptions. Mở rộng window từ 24h hiện hữu thành tham số `window_days` (default 1 → policy compliance dùng 30) hoặc thêm variant method.
- Window tính từ **lần unlock gần nhất có charge** (`BillingEvent`/`CreditTransaction` type `contact_unlock` / `CONTACT_UNLOCK` mới nhất với `credits_spent > 0`).
- Multi-workspace cùng unlock 1 contact: hoàn độc lập theo ledger từng workspace.
- Contact purge nhưng `Lead` còn contact khác hợp lệ: chỉ hoàn per-contact unlock, không đụng lead-level charges.
- Thông báo lỗi → log warning, không fail purge transaction (nhưng refund phải trong cùng transaction DB để đảm bảo atomic với audit).

## Tests

- Unit: `tests/unit/services/test_compliance_purge_service.py` — thêm cases: refund trong cửa sổ, ngoài cửa sổ (notify-only), idempotent re-run, budget cap → manual_review, self-host no-credit path.
- Integration: purge end-to-end với workspace wallet thật → verify `available_balance` tăng đúng + BillingEvent + notification row tồn tại.

## Definition of Done

- AC 1–6 pass unit + integration; ruff/format clean.
- ToS/privacy docs: thêm điều khoản "compliance removal" (tách task docs nếu legal cần review riêng).
- Mark `epic-33-retro-item-35` → done.
