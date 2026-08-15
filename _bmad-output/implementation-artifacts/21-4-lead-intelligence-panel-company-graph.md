# Story 21.4: Lead Intelligence Panel & Company Graph

Status: ready-for-dev

<!-- Note: Governed by UX Contract U3 & U4 and Epic 21 Lead Gen Architecture -->

## Story

As a sales director or account executive,
I want an interactive Lead Intelligence Panel with Company Graph visualization and 1-Click phone copy,
So that I can quickly qualify incoming multi-domain leads and take immediate sales action.

## Acceptance Criteria

1. **Given** the Lead Management view in Nowing Web, **When** leads from any scraper domain (BDS, Jobs, Tenders, E-commerce, Telegram, Social) are displayed, **Then** each Lead Card renders a Fit Score Badge ($0-100$), Intent Tag (`[BÁN]`, `[MUA]`, `[TUYỂN DỤNG]`, `[ĐẤU THẦU]`), Source Platform icon, and timestamp.
2. **Given** an extracted phone number on a Lead Card, **When** a user clicks the "Copy Phone" Pill button, **Then** the normalized number (`09...`) is copied to the system clipboard, the icon transitions to a green checkmark, and a subtle toast appears for $1.5$ seconds with keyboard accessibility (`Space`/`Enter`).
3. **Given** a lead linked to an enterprise/company, **When** opening the Company Graph drawer, **Then** the panel displays associated decision-makers, open job positions (from Story 12.10), active tenders (from Story 16.5), and legal entity details in an interactive relationship graph.
4. **Given** a change in Lead status (`new` -> `contacted` -> `qualified` -> `converted`), **When** updated by the user, **Then** the state is synchronized in realtime via Zero Cache with optimistic UI updates.

## Tasks / Subtasks

- [ ] Task 1: Backend Lead Aggregation & Enrichment API (AC: 1, 3, 4)
  - [ ] 1.1 Xây dựng router `app/routes/leads_routes.py` với endpoint `GET /api/v1/workspaces/{workspace_id}/leads`.
  - [ ] 1.2 Viết query tổng hợp Lead từ các bảng `social_posts`, `telegram_messages`, `procurement_tenders`, `company_decision_makers`.
  - [ ] 1.3 Endpoint `PATCH /api/v1/workspaces/{workspace_id}/leads/{lead_id}/status` hỗ trợ cập nhật trạng thái CRM.
- [ ] Task 2: Frontend Lead Card & 1-Click Phone Copy Pill (AC: 1, 2)
  - [ ] 2.1 Xây dựng `LeadCard.tsx` tại `nowing_web/components/leads/LeadCard.tsx` theo chuẩn Vanilla CSS / CSS Modules.
  - [ ] 2.2 Xây dựng `PhoneCopyPill.tsx` hỗ trợ Clipboard API, fallback `textarea` ẩn, toast feedback 1.5s và keyboard accessibility.
  - [ ] 2.3 Hiển thị Fit Score Badge với màu phân cực (Xanh lá $\ge 80$, Vàng $50-79$, Xám $<50$).
- [ ] Task 3: Company Graph Drawer & Entity Linkage (AC: 3)
  - [ ] 3.1 Xây dựng `CompanyGraphDrawer.tsx` tại `nowing_web/components/leads/CompanyGraphDrawer.tsx`.
  - [ ] 3.2 Hiển thị danh sách Lãnh đạo (Story 21.9), Gói thầu công (Story 16.5), và Tín hiệu tuyển dụng (Story 12.10).
- [ ] Task 4: Zero Cache State Synchronization (AC: 4)
  - [ ] 4.1 Cấu hình schema Zero Cache cho bảng `leads_crm` / `social_posts`.
  - [ ] 4.2 Viết hook `useLeadMutations` với Optimistic UI update khi kéo thả Pipeline.
- [ ] Task 5: Component & E2E Tests (AC: 1-4)
  - [ ] 5.1 Viết unit test cho `PhoneCopyPill.test.tsx` (kiểm tra click, copy event, keyboard navigation).
  - [ ] 5.2 Viết Playwright E2E test cho luồng lọc Lead và mở Company Graph.

## Dev Notes

- **UX Contract Alignment:** Tuân thủ 100% Widget U3 & U4 trong `ux-contract-scrapers-expansion-and-lead-intelligence.md`.
- **Zero Cache Invariant:** State mutations phải áp dụng Optimistic Update trước khi nhận phản hồi từ backend.
- **Frontend Architecture:** Vanilla CSS / Tailwind theo design system tokens của Nowing Web, không sử dụng thư viện UI bên ngoài nặng nề.

### References
- [UX Contract: ux-contract-scrapers-expansion-and-lead-intelligence.md#U3]
- [Architecture Spine: architecture-xactions-social-integration-2026-08-15/ARCHITECTURE-SPINE.md]
