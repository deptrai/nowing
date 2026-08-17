# UX Contract — Lead Intelligence Data Panel

**Ngày:** 2026-08-10
**Phạm vi:** Epic 21 — Lead Intelligence 2-panel layout
**Bám vào:** FR-63..FR-69, Story 21.1-21.7, AD-36..AD-42
**Loại tài liệu:** *contract* — định nghĩa UI phải biểu diễn được những trạng thái nào.
**Ghi chú:** Merged N4/N6/N7/N8 từ `ux-contract-epic21-addendum-2026-08-11.md` (Origami refresh 2026-08-11). Zalo OA connection setup UI và outcome-pricing display screens còn pending validation sau khi legal/ToS và business verification đóng.

---

## 1. Layout: 2-Panel Mode

Chat panel (trái) + Data panel (phải), collapsible.

| Trạng thái | Nguồn event | Bắt buộc |
|---|---|---|
| **Split view** | Có leads/signals/sequences trong workspace | ✅ |
| **Full-width chat** | User collapse data panel | ✅ |
| **Panel restored** | User toggle panel hoặc có data mới | ✅ |
| **Mobile** | Viewport < 768px | Panel → bottom sheet |

### Toggle Behavior
- Toggle button ở chat header (phải)
- Icon: table (📊) khi đóng, X khi mở
- Keyboard shortcut: `Cmd/Ctrl + D`
- State persisted trong localStorage

---

## 2. Data Table Panel

### Table Tabs
| Tab | Nội dung | Nguồn |
|-----|----------|-------|
| Leads | Lead list với fit score, company, website | FR-64, FR-65 |
| Signals | Intent signals (funding, hiring, tech stack) | FR-63 |
| Sequences | Outreach sequences & progress | FR-66 |
| Sources | Lead list by source (tất cả scraper/connector đã dùng) | N7 / multi-source |

### Lead Source Tabs (N7)

Khi workspace có leads từ nhiều nguồn, tab **Sources** hiển thị sub-tabs. Các tab được sinh động từ registry các scraper/connector đã tạo lead cho workspace, không hard-code.

| Tab | Source | Badge | Ví dụ |
|---|---|---|---|
| All | Tất cả nguồn | tổng lead count | — |
| <source_id> | Nguồn cụ thể | count từ nguồn đó | X, Instagram, TikTok, Reddit, YouTube, Google Search, Google Maps, Amazon, web crawl, Exa, Indeed, Walmart, batdongsan, chotot, muaban, VietnamWorks, TopCV, ITviec, … |

- Sub-tab chỉ hiển thị khi nguồn đó có ít nhất 1 lead trong workspace.
- Tên/tab label lấy từ `provider` hoặc `source` metadata của lead.
- Chuyển tab không reset filter/sort.
- Cho phép cross-reference cùng một lead giữa các nguồn.

### Table Columns (Leads Tab)
| Column | Width | Sortable | Filterable |
|--------|-------|----------|------------|
| ⭐ | 40px | No | No |
| Fit Score | 80px | Yes | Yes |
| Company | 200px | Yes | Yes |
| Website | 150px | No | No |
| Industry | 120px | Yes | Yes |
| Signals | 100px | Yes | Yes |
| Contact | 150px | No | No |
| Actions | 120px | No | No |

### Fit Score Color Coding
| Range | Color | Meaning |
|-------|-------|---------|
| 80-100 | 🟢 Green | High fit |
| 50-79 | 🟡 Yellow | Medium fit |
| 0-49 | 🔴 Red | Low fit |

### Row Actions (hover to reveal)
- ⭐ Star: toggle favorite (persisted)
- 🔍 Enrich: trigger enrichment (cost indicator)
- 📧 Sequence: open sequence selector
- 🗑️ Remove: confirm dialog → remove from list

---

## 3. Suggested Actions

Xuất hiện sau agent response tạo leads/data.

| # | Action | Channel | Cost |
|---|--------|---------|------|
| 1 | Enrich 5 leads | FR-65 | 2.5 credits |
| 2 | Find similar companies | FR-6 | Free |
| 3 | Start outreach sequence | FR-66 | Variable |

### Behavior
- Fade-in animation (200ms) sau 500ms delay
- Max 3 actions visible
- Hover: scale 1.02 + shadow
- Click: execute + loading state

---

## 4. Filter Chips

Inline data refinement.

| Type | Options |
|------|---------|
| Location | Vietnam, US, EU, ... |
| Industry | SaaS, Fintech, E-commerce, ... |
| Company Size | 1-10, 11-50, 51-200, 200+ |
| Signal Type | Funding, Hiring, Tech Stack, News |
| Date Range | Last 7d, 30d, 90d, All |

### Behavior
- Add: click "+" → dropdown → select → chip appears
- Remove: click "×" on chip
- Clear all: "Clear" link
- Max 5 visible chips, overflow in dropdown

---

## 5. Campaigns/Sequences Section

| Trạng thái | Hiển thị |
|---|---|
| Not connected | "Not sending yet — connect a campaign" |
| Active | "Active: Sequence Name" + progress |
| Paused | "Paused: Sequence Name" |

### Campaign Chip Behavior (N8)

- Hiển thị ở cột **Campaign** của lead row hoặc trong **Sequences** tab.
- Trạng thái `Not connected` dùng màu xám/yellow subtle; `Active` màu xanh; `Paused` màu cam.
- Click chip `Not connected` → dropdown chọn sequence hoặc "Create new sequence".
- Click chip `Active`/`Paused` → mở sequence detail.
- Nút "Send & export" disabled hoặc warning nếu lead chưa gắn sequence.
- Gắn sequence → lead được thêm vào sequence steps, chip chuyển sang `Active`.

### Sequence Progress
```
Step 1: ✅ Sent    Step 2: ⏳ Waiting    Step 3: ○ Pending
```

---

## 6. Responsive Behavior

| Breakpoint | Layout |
|------------|--------|
| Desktop (>1200px) | Full 2-panel (sidebar + chat + data) |
| Tablet (768-1200px) | Data panel collapses to overlay |
| Mobile (<768px) | Single panel, data as bottom sheet |

---

## 7. Credits & Projected Cost Display

Hiển thị cost-per-action transparency.

| Context | Display |
|---------|---------|
| Enrich button (row) | "2.5 credits ($0.036) per lead" |
| Sequence start | "Est. 5-10 credits per sequence" |
| Header | Total credits remaining: "$5.03" |
| Pre-enrich row (N6) | "X credits ($Y) per lead" hoặc "estimated" nếu chưa xác định |
| Bulk action (N6) | "Projected cost: X credits ($Y) for Z leads" cập nhật theo filter/selection |
| Total projected (N6) | "Total projected: X credits ($Y)" trước khi enrich hoặc gửi |

### Projected Cost Behavior
- Tính toán dựa trên FR-69 / Story 21.7.
- Cập nhật real-time khi user thay đổi filter, sort, hoặc chọn leads.
- Nếu cost không xác định → hiển thị "estimated" với tooltip giải thích.

---

## 8. Inbox Empty State & Channel CTAs (N4)

Khi inbox/runs tab chưa có campaign nào, hiển thị empty state tập trung outbound.

| Element | Content | Bắt buộc |
|---|---|---|
| Heading | "Start your first outreach campaign" | ✅ |
| Subtext | "Build a lead list from any scraper, then connect an email sequence" | ✅ |
| Primary CTA | "Start a campaign" | ✅ |
| Outbound channel | **Email** | ✅ |
| Lead source prompt | "Choose a lead source" (hiển thị sau khi click Start) | ✅ |

### Channel CTA Behavior
- **Email** là outbound channel duy nhất cho MVP.
- **LinkedIn** và **Zalo** bị **tắt / ẩn**; không hiển thị trong empty state cho đến khi legal/ToS và sender setup được chốt (nếu có).
- Click "Start a campaign" → mở flow 2 bước:
  1. **Chọn lead source:** dropdown/list các scraper/connector đã kết nối trong workspace (ví dụ: X, Instagram, TikTok, Reddit, YouTube, Google Search, Google Maps, Amazon, web crawl, Exa, Indeed, Walmart, batdongsan, chotot, muaban, VietnamWorks, TopCV, ITviec). Có thể chọn nhiều nguồn.
  2. **Chọn email sender** và **tạo sequence**.
- Kênh Email chưa có sender/connection → disabled với tooltip "Connect an email sender first".
- Lead source chưa có kết nối → disabled với tooltip "Connect [source] connector first".

---

## 11. Architecture Enforcement Notes

To prevent rebuilding existing infrastructure, the UI must rely on these shared backend components:

| UI Surface | Shared backend / AD | Constraint |
|---|---|---|
| Lead source list | `LeadSource` cache (populated by `lead_extractor` from `CapabilityRegistry` metadata `emits_leads=true`) (AD-3, AD-39, AD-44, FR-6) | The source dropdown must be populated from the workspace-scoped `LeadSource` API, not a hard-coded list. `CapabilityRegistry` is the runtime verb registry; `LeadSource` is the derived cache.
| Source-specific tabs | `LeadSource` cache + `Lead` table (N7) | Tabs are rendered from the workspace's actual lead sources (workspace-scoped `LeadSource` cache), filtered by `client_id` (AD-31); no hard-coded source menu.
| Enrichment cost | `BillingEvent` (`usage_type = "contact_enrichment"`) + `User.credit_micros_balance` (AD-8, AD-10, AD-36, AD-42) | Cost indicator must read from wallet/`BillingEvent` endpoints; `TokenUsage` is only for LLM token steps. |
| Per-lead projected cost | `BillingEvent` + `credit_micros_balance` (AD-42) | Projected cost uses the existing cost estimator/usage dashboard; dashboard reuses Story 8.3. |
| Sequence creation | New `Sequence`/`SequenceStep` tables, reusing Epic 6 scheduler/Celery/notification (AD-39) | Sequence builder UI persists to first-class `Sequence` schema, not `Automation`/`AutomationRun`. `Sequence` has `client_id` and UUID `id` (AD-31). |
| Sequence triggers from signals | AD-33 `AlertRule` with `capability_id`, `notification_channels` from the allowed set (`in_app`, `telegram`, `email`), and `target_sequence_id` (AD-37, AD-39) | Signal-to-sequence triggers are configured as alert rules tied to a signal capability; no separate trigger UI. |
| Positive-reply / delivery / bounce notifications | Story 11.1 notification service extended with `email_reply`, `email_delivered`, `email_bounced` (AD-39) | Notification preferences UI extends existing notification settings; inbound email handler (SES webhook/IMAP idle) is a capability. |
| CRM connection | `Connection` / OAuth model (AD-3, AD-40) | CRM setup UI reuses the existing connector management flow. `CrmConnection`/`CrmSyncLog` include `client_id` (AD-31). |
| Outcome-pricing display | `BillingEvent` + usage/credit dashboard from Story 8.3 (AD-10, AD-42) | Outcome-pricing metrics reuse the same usage/credit UI; `TokenUsage` is not used for business outcomes. |
| PII in lead/contact display | `app/services/pii/redact.py` (AD-25) | UI never surfaces raw unredacted PII; redacted values come from the backend. `source_input` (raw recipe) is never shown in UI. |
| Multi-vertical client isolation | `client_id` on all Epic 21 tables (AD-31) | UI filters lead lists, sequences, and outcomes by the active `client_id`; cross-client leakage is a hard failure. |

_Trace: epic21-lead-intelligence-ux.md → AD-25, AD-33, AD-36..AD-42 → FR-63..FR-69_
