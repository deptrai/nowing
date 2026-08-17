# UX Contract — Tables Directory / Lead Lists Library

**Ngày:** 2026-08-11
**Phạm vi:** N3 — Tables directory / lead lists library
**Loại tài liệu:** *contract*
**Trace:** `ux-contract-epic21-addendum-2026-08-11.md` → `epic21-lead-intelligence-ux.md`

---

## Trạng thái UI bắt buộc

| # | Trạng thái | Bắt buộc |
|---|---|---|
| N3.1 | Màn `/tables` liệt kê tất cả lead lists | ✅ |
| N3.2 | Mỗi item hiển thị tên, last updated, source tag (X, Instagram, TikTok, Web), lead count | ✅ |
| N3.3 | Search theo tên | ✅ |
| N3.4 | Sort: Updated, Created, Name | ✅ |
| N3.5 | Create new lead list CTA | ✅ |
| N3.6 | Filter theo source tag | ✅ |

---

## Hành vi

- Click table item → mở trong data panel của chat hoặc màn table detail.
- Tables do agent tạo tự động có tag `auto`; user-created có tag `manual`.
- Hỗ trợ rename, duplicate, archive, delete từ actions menu.
- Empty state: “No lead lists yet. Start a research chat to generate one.”
- Search + sort + filter kết hợp với nhau.

---

## Table item metadata

| Field | Hiển thị |
|---|---|
| Name | Tên lead list |
| Source tag | X / Instagram / TikTok / Web / Multi |
| Lead count | Số lượng leads |
| Last updated | Relative time hoặc datetime |
| Type | Auto / Manual |
| Actions menu | Open / Duplicate / Archive / Delete |

---

## Architecture Enforcement Notes

- A “lead list” is a view over the existing `Lead` table, filtered by `source`/`client_id` (AD-31). No new `lead_list` storage entity should be introduced unless it adds metadata not already in `Lead` (e.g. saved filter criteria).
- Source tags come from `CapabilityRegistry` metadata (`emits_leads=true`) and `LeadSource.provider` (AD-39), not a hard-coded list.
- Create/duplicate/archive/delete operations must map to CRUD on `Lead` rows or soft-delete on a lightweight `LeadList` metadata row; reuse existing workspace-document lifecycle (FR-11) where possible.
- Search/sort/filter must use the same table query endpoints as the lead intelligence data panel.
