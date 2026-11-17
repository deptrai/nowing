# Credit Refund Policy — Compliance Purge (DRAFT v0.1)

**Ngày:** 2026-10-13 · **Tác giả:** John (PM) · **Trạng thái:** ✅ APPROVED — Phương án C (30-day window), duyệt 2026-10-13
**Story:** `_bmad-output/implementation-artifacts/spec-33-4-compliance-purge-credit-refund-30-day-window.md` (ready-for-dev)
**Nguồn:** `epic-33-retro-item-35` (deferred) — `_bmad-output/implementation-artifacts/epic-33-retro-2026-10-11.md`

---

## 1. Vấn đề

Khi `CompliancePurgeService` xóa `VerifiedContact`/`Lead` theo yêu cầu pháp lý (right-to-be-forgotten, Decree 13/GDPR), workspace đã trả credit để unlock contact đó **mất dữ liệu** mà:
- không được hoàn credit,
- không nhận thông báo giải thích (lead biến mất khỏi danh sách âm thầm),
- không có audit trail liên kết giữa purge event và credit transaction đã chi.

Purge là **bắt buộc pháp lý** — không phải lỗi hệ thống cũng không phải lỗi người dùng. Câu hỏi policy: có hoàn credit không, ở mức nào, trong điều kiện nào?

## 2. Ràng buộc đã biết

- Infrastructure refund **đã tồn tại** (Story 26.4): `BillingEventService.record_contact_unlock_refund` — idempotent qua BillingEvent, có serialize lock chống double-credit.
- Các guardrail sẵn có: **24h refund window** (`ContactUnlockRefundWindowExpired`), **15% auto-refund budget cap** (`AutoRefundBudgetCapExceeded`), 60s accidental-relock window.
- `CreditTransaction`/`BillingEvent` có `reference_id` → trace được workspace nào đã chi bao nhiêu cho contact nào.
- `purged_posts` (SocialPost) vẫn hardcoded `= 0` — purge chưa hoàn chỉnh (item khác, đã done theo tracker item-34 nhưng cần verify khi implement policy này).

## 3. Các lựa chọn đã xem xét

| Phương án | Mô tả | Ưu | Nhược |
|---|---|---|---|
| **A — Không hoàn** (hiện tại) | Credit mua quyền truy cập tại thời điểm unlock; purge tuân thủ nằm ngoài phạm vi bảo đảm. Dispute qua support. | Zero engineering; không bị abuse | UX tệ — lead biến mất âm thầm, cảm giác "mất tiền oan"; rủi ro tranh chấp thủ công; tệ với customer ở EU/VN khi họ thấy lead bay màu vì DNC |
| **B — Hoàn tự động 100%** | Mọi credit đã chi cho contact bị purge được hoàn về ví workspace. | Công bằng tuyệt đối | Trách nhiệm vô hạn — data đã khai thác (export, outreach) nhiều tháng vẫn được hoàn; khuyến khích "dùng xong xóa" |
| **C — Hoàn có cửa sổ (RECOMMENDED)** | Chỉ hoàn credit cho contact bị purge **trong vòng 30 ngày kể từ lần unlock gần nhất**; kèm thông báo in-app giải thích. Quá 30 ngày = giá trị đã tiêu thụ. | Cân bằng fairness vs liability; khớp tâm lý "mới mua mà mất"; tái dùng refund infra + budget cap | Cần 1 story nhỏ để nối purge → refund hook + notification |

## 4. Khuyến nghị (để PO duyệt)

**Chọn C — Refund có cửa sổ 30 ngày**, cụ thể:

1. **Cửa sổ hoàn:** contact bị compliance-purge trong vòng **30 ngày** kể từ unlock gần nhất → hoàn **100% credit đã chi** cho unlock đó về workspace wallet. Quá 30 ngày → không hoàn (value consumed), vẫn gửi thông báo.
2. **Áp dụng budget cap 15%** hiện hữu: nếu tổng refund trong kỳ vượt cap, phần vượt chuyển sang hàng đợi review thủ công (support ticket), **không** chặn purge — purge pháp lý luôn chạy.
3. **Thông báo in-app** cho workspace owner/admin: số lead/contact bị ảnh hưởng (chỉ count + tên lead đã redact, KHÔNG lộ PII đã purge), số credit hoàn (nếu có), lý do: "gỡ bỏ theo yêu cầu bảo vệ dữ liệu cá nhân".
4. **Audit:** ghi `credits_refunded` vào purge report payload + BillingEvent `contact_unlock_refund` với `reference_id` = purge event id (idempotent).
5. **Không retroactive:** chỉ áp dụng cho purge sau ngày policy hiệu lực; purge đã chạy trước đó xử lý qua support case-by-case.
6. **ToS update:** thêm điều khoản "compliance removal" — giải thích rõ cơ chế cửa sổ, tránh kỳ vọng hoàn vô hạn.

## 5. Edge cases cần spec rõ khi implement

- Contact unlock nhiều lần (unlock → relock → unlock lại): cửa sổ tính từ **lần unlock gần nhất có charge**.
- Nhiều workspace cùng unlock 1 contact: mỗi workspace hoàn độc lập theo ledger của mình.
- Contact purge nhưng Lead còn contact khác hợp lệ: chỉ hoàn phần credit của contact bị purge (per-contact unlock), không hoàn lead.
- Workspace đã về 0 credit / subscription hết hạn: vẫn ghi BillingEvent refund; balance vẫn credit vào ví (không hết hạn theo sub? — cần check `WalletCreditService` TTL).
- Self-host/DSh instance: policy này chỉ áp dụng cho SaaS billing; self-host không có credit system → skip refund, vẫn notify.

## 6. Việc tiếp theo sau khi duyệt

1. PO sign-off policy này (sửa con số 30 ngày nếu cần).
2. Tạo story nhỏ (BMAD build): hook `execute_purge` → `record_contact_unlock_refund` có cửa sổ + notification dispatch + `credits_refunded` trong purge report.
3. Update ToS/privacy docs + thông báo trong changelog.
4. Mark `epic-33-retro-item-35` → done trong sprint-status.
