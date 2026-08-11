# Epic 21 UX Traceability Matrix (2026-08-11)

**Date:** 2026-08-11
**Scope:** N1–N8 UX patterns from Origami refresh
**Source:** `ux-research-origami-final-2026-08-11.md`, `ux-contract-epic21-addendum-2026-08-11.md`

---

## Requirements-to-UX-contract mapping

| ID | UX Pattern | FR | Story | Acceptance Criteria (UX) | Canonical Contract | Test Focus |
|---|---|---|---|---|---|---|
| N1 | Sidebar onboarding checklist | — | Story 21.4 | Checklist hiển thị 5 bước; hoàn thành mỗi bước update tiến độ; dismiss được | `ux-contract-sidebar-onboarding.md` | Visibility, completion events, dismiss state |
| N2 | Workspace mode switch | FR-66 | Story 21.4 | Tabs Outbound/Research/Content; chuyển mode đổi nav; persisted per user | `ux-contract-workspace-mode-switch.md` | Mode persistence, nav visibility, role gating |
| N3 | Tables directory | FR-63 | Story 21.1 | Liệt kê lead lists; search/sort/filter; metadata source/last updated | `ux-contract-tables-directory.md` | Search, sort, source tag, empty state |
| N4 | Inbox empty state + Email only; lead source from all scrapers | FR-66 | Story 21.4 | Empty state heading/CTA; outbound Email only; lead source from any connected scraper/connector | `ux-contract-lead-intelligence-panel.md` §8 | Empty state, lead-source gating, CTA routing |
| N5 | Positive-reply notifications (email/Telegram) | FR-66 | Story 21.4 | Trigger positive reply; channels email/Telegram; user toggles; Zalo disabled | `ux-contract-positive-reply-notifications.md` | Reply classification, channel delivery, toggle state |
| N6 | Per-lead projected cost | FR-69 | Story 21.7 | Cost hiển thị per lead/bulk; cập nhật theo filter/selection; estimated fallback | `ux-contract-lead-intelligence-panel.md` §7 | Cost calculation, filter updates, unknown cost |
| N7 | Source-specific table tabs | FR-63 | Story 21.1 | Tab Sources với All + sub-tabs động cho mọi scraper/connector đã tạo lead; badge counts; cross-reference | `ux-contract-lead-intelligence-panel.md` §2.1 | Tab switching, counts, multi-source dedup |
| N8 | “Connect a campaign” chip | FR-66 | Story 21.4 | Chip states Not connected/Active/Paused; dropdown chọn sequence; disabled send | `ux-contract-lead-intelligence-panel.md` §5 | Chip states, dropdown, sequence binding, disabled CTA |

---

## UI-state coverage

| Pattern | Empty | Loading | Error | Partial | Complete | Disabled |
|---|---|---|---|---|---|---|
| N1 | Checklist with 0/5 | — | — | 1–4/5 | 5/5 (auto-hide) | Dismissed |
| N2 | — | — | — | — | Tab selected | Tab hidden by role |
| N3 | No lists | Search loading | Fetch fail | Filtered lists | Sorted lists | — |
| N4 | Empty inbox | — | — | — | Has campaigns | LinkedIn/Zalo disabled; choose lead source |
| N5 | No alerts | Sending | Channel fail | Some channels | Delivered | Channel not connected |
| N6 | No leads | Calculating | — | Per-row estimate | Bulk total | Cannot compute |
| N7 | No leads | — | — | Single source | Multi-source | — |
| N8 | Not connected | Connecting | Sequence error | Active | Paused | Send disabled |

---

## Dependencies / blockers

| Pattern | Depends on | Blocker / Open question |
|---|---|---|
| N1 | User event tracking, sidebar component | None — can reuse existing events |
| N2 | User preferences, role/permission | Q6: Is Content mode a separate module? |
| N3 | Table storage, source metadata | None |
| N4 | Email sender setup, scraper/connector registry, sequence routing | Q1/Q2: lead-source selection in empty state vs Integrations |
| N5 | Notification service (Telegram existing), email reply parsing | Q3/Q4: Permissions + positive-reply classifier |
| N6 | Cost estimator service, FR-69 pricing | Q5: Credit/dollar display and exchange rate |
| N7 | Multi-source aggregation, dedup, capability registry | Q7: How are source tabs generated from scraper/connector registry? |
| N8 | Sequence service, campaign status | None |

---

## Files

- Research: `ux-design/ux-research-origami-final-2026-08-11.md`
- Addendum: `ux-designs/ux-Nowing-2026-07-22/ux-contract-epic21-addendum-2026-08-11.md`
- Canonical panel: `ux-designs/ux-Nowing-2026-07-22/ux-contract-lead-intelligence-panel.md`
- Wireframes: `ux-design/epic21-ux-wireframes-2026-08-11.md`
- Hand-off: `implementation-artifacts/epic21-ux-handoff-2026-08-11.md`
