# UX Contract — Workspace Mode Switch

**Ngày:** 2026-08-11
**Phạm vi:** N2 — Workspace mode switch (Outbound / Research / Content)
**Loại tài liệu:** *contract*
**Trace:** `ux-contract-epic21-addendum-2026-08-11.md` → `epic21-lead-intelligence-ux.md`

---

## Trạng thái UI bắt buộc

| # | Trạng thái | Bắt buộc |
|---|---|---|
| N2.1 | Tab/switch ở đỉnh sidebar: **Outbound** / **Research** / **Content** | ✅ |
| N2.2 | Outbound mode: hiển thị nav Inbox, Campaigns, Senders, Tables | ✅ |
| N2.3 | Research mode: hiển thị nav New chat, Automations, Artifacts, Playground | ✅ |
| N2.4 | Content mode: hiển thị nav Deliverables, Playbooks, Reports | ✅ |
| N2.5 | Mode hiện tại được highlight rõ ràng | ✅ |

---

## Hành vi

- Mode persisted per user (localStorage / user preferences).
- Chuyển mode không reset chat/data panel; chỉ thay đổi nav và default view.
- Sales user default = **Outbound**.
- Researcher/default user default = **Research**.
- Content/Marketing user có thể chọn **Content**.
- Nếu user không có quyền outbound, tab Outbound bị ẩn hoặc disabled.

---

## Nav items theo mode

| Mode | Nav items |
|---|---|
| Outbound | Inbox, Campaigns, Senders, Tables, Leads, Settings |
| Research | New chat, Chats, Automations, Artifacts, Playground, Settings |
| Content | Deliverables, Playbooks, Reports, Assets, Settings |

---

## Architecture Enforcement Notes

- Workspace mode is a **UI-only state** (sidebar nav filter). It must not introduce a new workspace entity or routing model.
- Outbound mode surfaces data from existing `Lead`, `Sequence` (Campaigns), `Connection` (Senders), and `LeadSource`/`CapabilityRegistry` (Tables/Leads), all filtered by the active `client_id` (AD-31).
- Research mode reuses existing chat, automations, artifacts, playground surfaces.
- Content mode reuses existing deliverables, playbooks, reports, assets.
- No new backend endpoints should be created solely for mode switching.
