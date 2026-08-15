# Story 21.4: Lead Intelligence Panel & Company Graph

Status: in-progress

<!-- Note: Governed by UX Contract U3 & U4 in ux-contract-scrapers-expansion-and-lead-intelligence.md and Epic 21 Lead Intelligence Architecture -->

## Story

As a sales director, account executive, or prospecting agent,
I want an interactive Lead Intelligence Panel with Company Graph visualization, multi-domain lead cards, and 1-Click phone copy,
So that I can immediately qualify incoming multi-domain leads (BDS, Jobs, Tenders, E-commerce, Social, Telegram) and take frictionless outreach action.

## Acceptance Criteria

1. **AC-1: Multi-Domain Lead Card Visualization (Widget U3 & U4 Alignment)**
   - **Given** the Lead Intelligence Panel in Nowing Web,
   - **When** leads from any scraper domain (BDS, Jobs, Tenders, E-commerce, Telegram, Social, LinkedIn) are loaded for the active workspace,
   - **Then** each `LeadCard` renders:
     * **Fit Score Badge**: Numeric indicator ($0-100$) with polarized color coding: Green (`#22c55e` / High Fit $\ge 80$), Yellow (`#f59e0b` / Medium Fit $50-79$), Slate/Red (`#ef4444` / Low Fit $< 50$), with breakdown tooltip on hover.
     * **Intent Tag**: Structured chip with icon and distinct color: `[BÁN]`, `[MUA]`, `[TUYỂN DỤNG]`, `[ĐẤU THẦU]`, `[HỢP TÁC]`.
     * **Source Platform Icon & Metadata**: Badge showing platform origin (Facebook, X/Twitter, Telegram, Batdongsan, Muasamcong, LinkedIn, Shopee, etc.) with relative timestamp.
     * **Key Extracted Attributes**: Contact info, price/budget estimate, location/zoning summary, and company association.

2. **AC-2: 1-Click Phone Copy Pill with Toast & Accessibility**
   - **Given** an extracted phone number on a `LeadCard`,
   - **When** a user clicks the `PhoneCopyPill` button or triggers it via keyboard (`Enter` or `Space` on focus),
   - **Then**:
     * The normalized phone number (`09...` / E.164 without separators) is copied to `navigator.clipboard` (with graceful fallback to hidden `textarea` / `document.execCommand('copy')`).
     * The pill icon transitions smoothly from `Phone` / `Copy` icon to a green `Check` icon.
     * A toast notification is triggered with message `"Đã copy SĐT {phone}!"` lasting exactly $1.5$ seconds ($1500\text{ms}$).
     * ARIA accessibility attributes (`aria-label="Copy phone number {phone}"`, `role="button"`, `tabIndex={0}`) are properly provided.

3. **AC-3: Company Graph Drawer & Multi-Entity Linkage (Widget U4)**
   - **Given** a lead linked to an enterprise or company name,
   - **When** the user clicks "Xem Company Graph" / "Chi tiết doanh nghiệp",
   - **Then** the `CompanyGraphDrawer` slides out from the right displaying:
     * **Legal Entity Details**: Mã số thuế (MST), Legal Representative, Registered capital, Founding date, Address.
     * **Decision-Makers Directory (Story 21.9)**: List of executives / key personnel (CEO, Procurement Head, IT Director) with LinkedIn profile links and email/phone when available.
     * **Public Procurement & Tenders (Story 16.5)**: Active or recent tender packages (Số TBMT, Tender budget, Close date countdown).
     * **Hiring Velocity Signals (Story 12.10)**: Open positions from VN jobs scrapers (TopCV, ITviec, VietnamWorks), hot departments, and velocity trend percentage.

4. **AC-4: Realtime CRM Status Mutation & Optimistic Zero Sync**
   - **Given** a lead in status `new`, `contacted`, `qualified`, or `converted`,
   - **When** the user updates the status via pipeline dropdown or quick action,
   - **Then**:
     * The UI updates optimistically without UI flickering.
     * The change is dispatched to `PATCH /api/v1/workspaces/{workspace_id}/leads/{lead_id}/status`.
     * Zero Cache state is synchronized across all active workspace clients.

5. **AC-5: Backend Lead Aggregation & Query REST Contract**
   - **Given** an authenticated user with `leads:read` permission in workspace `{workspace_id}`,
   - **When** calling `GET /api/v1/workspaces/{workspace_id}/leads`,
   - **Then** the API returns paginated leads (`items`, `total`, `limit`, `offset`) filtered by `source`, `intent`, `min_score`, `search`, and multi-vertical `client_id` (AD-31).

## Tasks / Subtasks

- [x] Task 1: Backend Router & Schema Implementation (AC: 1, 4, 5)
  - [x] 1.1 Tạo schemas tại `app/lead_intelligence/schemas.py` hoặc mở rộng `app/lead_intelligence/scoring/schemas.py` với `LeadRead`, `LeadStatusUpdate`, `CompanyGraphRead`.
  - [x] 1.2 Tạo router `app/routes/leads_routes.py` với endpoints `GET /api/v1/workspaces/{workspace_id}/leads`, `PATCH /api/v1/workspaces/{workspace_id}/leads/{lead_id}/status`, `GET /api/v1/workspaces/{workspace_id}/companies/{company_name}/graph`.
  - [x] 1.3 Đăng ký router trong `app/routes/__init__.py`.
  - [x] 1.4 Viết backend unit tests tại `tests/unit/routes/test_leads_routes.py`.

- [x] Task 2: Frontend 1-Click Phone Copy Pill (AC: 2)
  - [x] 2.1 Xây dựng `nowing_web/components/leads/PhoneCopyPill.tsx` với standard Web Clipboard API + hidden textarea fallback.
  - [x] 2.2 Tích hợp Sonner toast thông báo 1.5s (`duration: 1500`) và animation checkmark xanh lá.
  - [x] 2.3 Viết component unit test `nowing_web/components/leads/__tests__/PhoneCopyPill.test.tsx`.

- [x] Task 3: Frontend Lead Card Component (AC: 1, 2)
  - [x] 3.1 Xây dựng `nowing_web/components/leads/LeadCard.tsx` hỗ trợ Fit Score badge, Intent Tag styling, Platform Icons, và PhoneCopyPill.
  - [x] 3.2 Viết component unit test `nowing_web/components/leads/__tests__/LeadCard.test.tsx`.

- [x] Task 4: Company Graph Drawer Component (AC: 3)
  - [x] 4.1 Xây dựng `nowing_web/components/leads/CompanyGraphDrawer.tsx` với sheet/drawer layout hiển thị Legal Entity, Decision Makers, Tenders, và Hiring signals.
  - [x] 4.2 Viết API hook `nowing_web/lib/apis/leads-api.service.ts` và hook Zero sync `nowing_web/lib/hooks/use-leads.ts`.

- [x] Task 5: Quality & Typecheck Verification (AC: 1-5)
  - [x] 5.1 Chạy Backend pytest `uv run pytest tests/unit/routes/test_leads_routes.py -q`.
  - [x] 5.2 Chạy Frontend typecheck `pnpm tsc --noEmit` và format `pnpm exec biome check`.

## Dev Notes

- **UX Contract Alignment:** Tuân thủ 100% Widget U3 & U4 trong `ux-contract-scrapers-expansion-and-lead-intelligence.md` và `ux-contract-lead-intelligence-panel.md`.
- **Zero Cache Invariant:** State mutations phải áp dụng Optimistic Update trước khi nhận phản hồi từ backend.
- **Frontend Architecture:** Vanilla CSS / Tailwind theo design system tokens của Nowing Web, không sử dụng thư viện UI ngoài lạ lẫm.
