# UX Contract — Sidebar Onboarding Checklist

**Ngày:** 2026-08-11
**Phạm vi:** N1 — Sidebar onboarding checklist cho lead-gen workspace
**Loại tài liệu:** *contract*
**Trace:** `ux-contract-epic21-addendum-2026-08-11.md` → `epic21-lead-intelligence-ux.md`

---

## Trạng thái UI bắt buộc

| # | Trạng thái | Bắt buộc |
|---|---|---|
| N1.1 | Sidebar hiển thị checklist “Lead-gen setup: X/5 done” khi workspace chưa hoàn tất | ✅ |
| N1.2 | 5 bước: tạo ICP, chạy first search, enrich lead, connect campaign, gửi first message | ✅ |
| N1.3 | Các bước done có dấu ✅; bước tiếp theo highlight | ✅ |
| N1.4 | Checklist có thể collapse, hide, hoặc dismiss | ✅ |
| N1.5 | Checklist tự động ẩn khi tất cả bước done | ✅ |

---

## Hành vi

- Checklist xuất hiện ở sidebar khi user mở workspace lần đầu hoặc chưa hoàn thành đủ 5 bước.
- Click bước chưa done → mở chat với prompt gợi ý hoặc điều hướng đến màn hình tương ứng.
- Dismissed checklist vẫn có thể khôi phục qua Settings hoặc “Show onboarding”.
- Tiến độ được tính dựa trên events: ICP saved, first search completed, lead enriched, campaign connected, first message sent.

---

## Các bước chi tiết

| Bước | Tên | Completion criteria |
|---|---|---|
| 1 | Define your ICP | User lưu ICP profile cho workspace |
| 2 | Run your first search | Agent trả về ít nhất 1 lead list |
| 3 | Enrich a lead | User trigger enrichment trên 1 lead |
| 4 | Connect a campaign | Lead được gắn sequence/campaign |
| 5 | Send your first message | First message trong sequence được gửi |

---

## Architecture Enforcement Notes

- Onboarding checklist completion **must** be derived from existing workspace data: `Workspace` (ICP), `Lead`/`LeadSource` (first search), `EnrichmentRequest` (lead enriched), `Sequence` (campaign connected), `SequenceEvent` (first message sent). Do not create a dedicated `onboarding_progress` table.
- Clicking a step **must** reuse existing navigation/chat flows (FR-14, FR-15). No new onboarding-specific screens except this checklist widget.
- The checklist widget itself is a new UI component, but its state is computed, not persisted as a separate entity.
