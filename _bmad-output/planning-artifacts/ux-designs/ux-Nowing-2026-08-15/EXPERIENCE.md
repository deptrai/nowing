---
name: Nowing
status: final
sources:
  - {planning_artifacts}/prds/prd-Nowing-2026-07-22/prd.md
  - {planning_artifacts}/ux-design/ux-research-origami-final-2026-08-11.md
  - {planning_artifacts}/ux-designs/ux-Nowing-2026-07-22/ux-contract-lead-intelligence-panel.md
  - {planning_artifacts}/ux-designs/ux-Nowing-2026-07-22/ux-contract-epic21-addendum-2026-08-11.md
updated: 2026-08-15
---

# Nowing — Experience Spine (`EXPERIENCE.md`)

> **Spec Compliance:** Defines the complete behavioral and interaction model for Nowing's redesigned AI Lead & Knowledge Platform. Paired with `DESIGN.md`.

---

## 1. Foundation

- **Platform Target:** Desktop-first responsive web application (Optimized for 1280px+ viewports, with fully functional 1024px and mobile responsive fallback).
- **Core Technology Stack:** Next.js 16 (App Router), Tailwind CSS / Vanilla CSS tokens, Zero-cache real-time synchronization (`zero.nowing.net`), FastAPI backend, Celery scraper workers.
- **Design System Relationship:** Uses custom tokenized components inheriting Radix UI headless interaction primitives with Nowing's Light-Green & Crisp-White visual tokens defined in `DESIGN.md`.

---

## 2. Information Architecture & Sitemap

### 2.1 Navigation Structure

```
[Nowing Root Shell]
├── Left Rail (64px / 240px)
│   ├── Workspace Switcher (Personal / Team)
│   ├── Mode Switcher [ 🎯 Leads | 🧠 Research | ⚡ Scrapers ]
│   ├── Main Nav Items:
│   │   ├── 💬 Chat / Co-pilot (`/dashboard/[id]/chat`)
│   │   ├── 📥 Outreach Inbox (`/dashboard/[id]/inbox`)
│   │   ├── 📢 Campaigns & Sequences (`/dashboard/[id]/campaigns`)
│   │   ├── 📋 Tables & Lead Lists (`/dashboard/[id]/tables`)
│   │   └── ⚡ Scraper Hub (`/dashboard/[id]/scrapers`)
│   ├── Active Threads List (Collapsible)
│   ├── Onboarding Checklist Card (0/5 steps progress)
│   └── User Footer (Settings, Credits Balance, Profile)
│
├── Main Viewport Canvas:
│   ├── Mode 1: Lead Intelligence (Split 2-Panel View)
│   │   ├── Left Pane (420px): Conversational Agent + Suggested Actions
│   │   └── Right Pane (Flex): Multi-source Table Matrix + Filter Chips + Campaign Status
│   │
│   ├── Mode 2: Deep Research & Knowledge Canvas
│   │   ├── Left Pane: Query Builder & Step-by-Step Reasoner
│   │   └── Right Pane: Synthesized Intelligence Document + Provenance Graph + Citations
│   │
│   ├── Mode 3: Scraper Automation Hub
│   │   ├── Platform Connectors (Batdongsan, Muaban BDS, Chotot, Telegram)
│   │   └── Task Queue & Live Ingestion Logs
│   │
│   └── Settings & Admin Console
│       ├── Global Model Connections & AI Routing
│       ├── Scraper Platform Accounts (Proxy/Session pool)
│       └── Workspace Limits & Billing
```

---

## 3. Voice and Tone (Microcopy)

| Context | Do (Nowing Voice) | Don't (Avoid) |
|---|---|---|
| **First-time Greeting** | "Chào anh Hùng, hôm nay anh muốn tìm kiếm nguồn khách hàng hay phân tích thị trường nào?" | "Chào mừng bạn đến với hệ thống AI siêu cấp VIP! 🚀" |
| **Suggested Action** | "Lọc 12 tin BĐS chính chủ giá dưới 5 tỷ và trích xuất số điện thoại" | "Bấm vào đây để làm thêm trò hay ho nhé" |
| **Lead Fit Explanation** | "Khớp 98%: Doanh nghiệp vừa đăng tuyển 5 nhân sự IT và có nhu cầu mua thiết bị văn phòng." | "AI tính toán thấy hợp lý nên đề xuất." |
| **Credit Transparency** | "Dự kiến tiêu tốn 1.5 credits (~350 VNĐ) cho mỗi số điện thoại được giải mã." | "Thực hiện tìm kiếm (có thể mất phí)." |
| **Campaign Connection Alert** | "Chưa kết nối chiến dịch gửi — Kết nối Zalo OA hoặc Email để gửi tin nhắn hàng loạt." | "Lỗi: Bạn chưa tạo campaign." |

---

## 4. Component Patterns & Behaviors

### 4.1 Split 2-Panel Workspace (`/chat?table=...`)
- **Resizable Divider:** Allows users to drag the center border to expand the chat panel (for deep dialogue) or expand the data table (for bulk scanning).
- **Contextual Synchronization:** Clicking on any row in the Right Table immediately updates the Chat context on the Left with that lead's metadata, enabling prompts like *"Tạo kịch bản tiếp cận qua Zalo cho khách hàng này"*.
- **Suggested Next Actions:** Renders max 3 dynamic pills below the assistant message. Clicking an action automatically dispatches the prompt without retyping.

### 4.2 Multi-Table Tabs & Filter Bar
- Supports switching between multiple active lead tables (`Doanh nghiệp BĐS`, `Ứng viên IT`, `Tin bán nhà Quận 7`).
- Filter chips (e.g., `Khu vực: TP.HCM`, `Fit Score > 80%`, `Có số điện thoại`) allow instant client-side filtering without reloading data.

### 4.3 Lead Detail Flyout Drawer
- Clicking any lead opens a smooth slide-out drawer from the right.
- Displays: Full contact enrichment history, AI Fit Score breakdown, Scraped raw post snapshot, Timeline of past outreaches, and 1-click Zalo / Phone dial action.

---

## 5. State Patterns

| State | Chat Pane Treatment | Table / Canvas Treatment |
|---|---|---|
| **Initial Empty State** | Shows warm greeting + 3 quick starter prompts (e.g. *Tìm chủ nhà bán gấp Quận 2*, *Quét nhóm Telegram mua sỉ*) | Clean illustration + "Bắt đầu cuộc trò chuyện để tạo danh sách leads đầu tiên" |
| **AI Generating / Scraping** | Animated Origami Wing icon + step-by-step progress trace (e.g. `Đang quét Batdongsan... Đang lọc tin chính chủ...`) | Shimmer skeleton on table rows with live row insertion via Zero-cache |
| **Enrichment in Progress** | Small progress spinner inside the credit counter | Table cell displays a pulsing mint badge: `Đang giải mã SĐT...` |
| **Offline / Network Interrupted** | Top status bar toast: `Mất kết nối — Dữ liệu sẽ tự động đồng bộ khi có mạng lại` | Read-only cached view remains interactive via local Zero-cache store |
| **Credit Exhausted** | Modal dialog: `Hết Credits — Nâng cấp gói hoặc thêm API Key riêng để tiếp tục` | Table remains browseable and exportable |

---

## 6. Interaction Primitives & Keyboard Shortcuts

- `⌘K` / `Ctrl+K`: Global Command Palette (Jump to any chat, table, or scraper task).
- `N`: Quick New Chat.
- `E`: Enrich selected rows with Phone/Email.
- `S`: Send selected leads to Outreach Campaign / Zalo sequence.
- `Space`: Preview selected lead in quick flyout.
- `Esc`: Close any drawer or modal.

---

## 7. Accessibility Floor

- **Contrast:** All text tokens adhere to **WCAG 2.1 Level AA** (minimum 4.5:1 for normal text, 3:1 for large display titles and badge backgrounds).
- **Focus Rings:** High-visibility `#10B981` 2px focus rings on all interactive elements during keyboard navigation (`Tab` / `Shift+Tab`).
- **Screen Reader Support:** Table cells include proper `aria-colindex` and `aria-rowindex`. Fit scores announce as *"Điểm phù hợp: 98 trên 100"*.

---

## 8. Key Flows & Named-Protagonist Journeys

### Flow 1: Săn BĐS Chính Chủ Giá Tốt (Anh Hùng — Môi Giới BĐS TP.HCM, 9:15 AM)
1. **Intake:** Anh Hùng mở Nowing, chọn mode `🎯 Leads`.
2. **Prompting:** Anh gõ vào ô chat: *"Quét toàn bộ tin bán nhà phố Quận Tân Bình dưới 6 tỷ đăng trong 24h qua trên Batdongsan và Chotot, loại bỏ tin môi giới trùng lặp."*
3. **Execution:** Nowing kích hoạt Scraper Runner. Trên bảng bên phải, các hàng dữ liệu bắt đầu nhảy ra theo thời gian thực nhờ Zero-cache kèm Fit Score (95%, 90%, 82%).
4. **Suggested Action:** AI phản hồi kèm 3 nút gợi ý. Anh Hùng bấm vào nút `[ 📱 Giải mã số điện thoại 8 tin chính chủ điểm cao nhất ]`.
5. **Climax:** Hệ thống trừ 12 credits, số điện thoại thật hiện ra ngay trên bảng kèm nhãn `Chính chủ xác minh`. Anh Hùng bấm nút `[ 💬 Mở Zalo chào giá ]` để bắt đầu gửi tin nhắn tiếp cận đầu tiên trong vòng chưa đầy 2 phút kể từ khi mở app.

### Flow 2: Tuyển Dụng Headhunter IT Nhanh (Chị Linh — HR Lead, 2:30 PM)
1. **Intake:** Chị Linh cần tuyển gấp 3 Senior Next.js Developer cho dự án FinTech.
2. **Prompting:** Chị nhập yêu cầu vào Nowing Chat.
3. **Data Matrix:** Bảng `Candidates Matrix` tự động gom dữ liệu từ LinkedIn, GitHub và Telegram Dev Groups.
4. **Filter:** Chị Linh dùng thanh Filter Chip chọn `Kinh nghiệm > 4 năm` và `Trạng thái: Đang tìm việc`.
5. **Climax:** Chị Linh chọn 15 ứng viên hàng đầu và bấm `[ 🚀 Tạo chiến dịch Outbound ]`. Nowing tạo sẵn 3 mẫu email/Zalo được cá nhân hóa theo từng portfolio của ứng viên, sẵn sàng để kích hoạt chiến dịch gửi tự động.

---

## 9. Inspiration & Anti-patterns

- **Inspiration from Origami (`origami.chat`):**
  - The clean 2-panel layout combining conversational intent with tabular output.
  - The suggested next action pills directly following assistant turns.
  - Transparent per-lead cost projections (`1.5 credits / lead`).
- **Nowing Differentiators:**
  - Light-first green theme (`#10B981`, `#ECFDF5`) instead of Origami's pink/fuchsia theme.
  - Native integration with Vietnamese platforms (Batdongsan, Muaban BDS, Chotot, Zalo OA, Telegram).
  - Durable provenance citations and deep research canvas mode.
- **Anti-patterns Banned:**
  - No bloated, multi-nested modals.
  - No decorative gradients that obscure text legibility.
  - No hidden credit deductions without upfront estimations.

---

## 10. Readiness Gap Contracts

Các UX contract sau bổ sung cho các requirement chưa có đủ UX chi tiết trong tài liệu này:

- `ux-contract-first-run-onboarding.md` — first-run memory seeding (FR-40, E3.13)
- `ux-contract-readiness-gaps.md` — Agent Registry, vertical client tenancy, chat benchmark, outcome-based pricing, CRM sync, bounded memory injection

Chúng được đưa vào canonical UX 2026-08-15 sau Implementation Readiness Assessment 2026-08-20.
