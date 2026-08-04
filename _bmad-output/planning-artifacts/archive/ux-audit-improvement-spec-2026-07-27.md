# UX Audit & Improvement Specification — Nowing

**Ngày:** 2026-07-27 · **Tác giả:** Sally (UX Designer, BMAD) · **Trạng thái:** Draft for review
**Thay thế/bổ sung:** `ux-design-specification.md` (2026-04-13) — spec cũ KHÔNG bị xóa; tài liệu này là bản đối chiếu với PRD mới nhất và spec cải tiến ưu tiên hóa.
**Phương pháp:** Audit trực tiếp trên app đang chạy (Playwright/Chromium, 13 screenshots, user `free@nowing.ai`) + chưng cất toàn văn PRD (2026-05-01), UX spec cũ, project-context, epics.md.

---

## 1. Kết luận điều hành

Khung xương của app (Split-Pane 3 cột: Sidebar → Chat → Context Pane) **đúng với Direction 3 đã chọn và vẫn đúng với PRD**. Vấn đề không nằm ở layout mà ở **4 tầng bị bỏ trống**:

1. **Tầng trạng thái (states):** app chết đứng bằng spinner vô tận khi bất kỳ dependency nào (sync, settings API) trục trặc — vi phạm trực tiếp NFR-R1 ("không White Screen of Death") và nguyên tắc "No blocking spinner" của chính spec cũ.
2. **Tầng friction đầu phiên:** chat bị khóa cho tới khi user tự chọn model; onboarding coachmark chặn click; greeting sai danh xưng. Mâu thuẫn với mục tiêu TTFT < 1.5s và "Delightfully Frictionless".
3. **Tầng niềm tin Local-first:** không có bất kỳ indicator Online/Syncing/Offline nào — trong khi PRD xác định đây là bản sắc sản phẩm và là rủi ro thị trường cần UI giải tỏa.
4. **Tầng "PRD mới":** toàn bộ Phase 2 UX Overhaul (9-UX-1..4: Live Research Lab, Report kiểu Messari, Interactive Analysis) **không có spec** — file thiết kế được tham chiếu (`.claude/plans/harmonic-cuddling-glacier.md`) không tồn tại trong repo. Epic 11 (FR41/FR45) và Story 3.5/5.6/5.7/10-4/10-5 cũng chưa có UX.

---

## 2. Bằng chứng audit trực tiếp (app đang chạy)

| # | Phát hiện | Bằng chứng | Vi phạm |
|---|---|---|---|
| F1 | **Silent failure / spinner vô tận.** Tạo space xong → spinner vĩnh viễn khi zero-cache chưa chạy (không lỗi, không timeout, không retry). Settings (`/dashboard/settings`) treo spinner **kể cả khi zero-cache đã chạy**. | `ux-06`, `ux-08`, `ux2-05` | NFR-R1, spec "No blocking spinner → Skeleton" |
| F2 | **Chat khóa chờ chọn model.** Composer disabled + cảnh báo cam "Select a model"; user mới không thể gõ gì cho tới khi tự tìm ra dropdown ở header. | `ux2-01` | TTFT < 1.5s (NFR-P1), "Frictionless"; Story 3.5 chưa có UX |
| F3 | **First-run dashboard trống rỗng.** `/dashboard` chỉ có 1 icon + 1 nút; không header, không user menu, không lối tới settings/billing/docs/logout. Sau khi vào space thì shell đầy đủ — nghịch lý: màn đầu tiên user gặp lại là màn nghèo nhất. | `ux-03` | Emotional goal "Empowered & In Control" |
| F4 | **Semantics & a11y mỏng.** Inventory `nav`/`aside`/`[role=tablist]` trả về rỗng ở mọi màn; coachmark onboarding chặn pointer toàn trang; không thấy focus ring nhất quán. | walk log | WCAG AA (spec Design System Foundation) |
| F5 | **Copy & danh xưng.** "Fresh start today, Free!" — gọi user bằng plan/email prefix vì `display_name` null không có fallback tử tế. Ngôn ngữ trộn EN toàn bộ (PRD user chính là người Việt — cần quyết định i18n có thuộc scope không). | `ux2-01` | Micro-emotion "Confidence > Confusion" |
| F6 | **Không có sync/offline indicator.** Không tìm thấy bất kỳ trạng thái Online/Syncing/Offline nào trong shell — kể cả khi zero-cache chạy. | `ux2-01` | PRD Risk Mitigation: "UI state router Offline/Syncing/Online"; FR10-11 |
| F7 | **Zero-cache là single point of failure phía FE** nhưng UI không nói gì khi nó vắng mặt (WebSocket 4848 fail lặp vô hạn trong console, UI im lặng). | console log | FR41 pattern (banner + retry) chưa tồn tại |

**Điểm tốt cần giữ:** landing page chỉn chu (hero serif "NotebookLM for Teams", carousel tính năng); shell 3-pane trong space đúng direction; modal tạo space sạch; sidebar usage meter (0/10 pages, 0/1.0M tokens) + upsell rõ ràng; composer có `/` prompts và `@` mention docs — đúng tinh thần "Query-to-Widget".

---

## 3. Gap analysis so với PRD mới nhất (tổng hợp từ chưng cất tài liệu)

### 3.1 PRD yêu cầu nhưng spec cũ không cover (mức CAO)
- **C1.1 — Hai mô hình thời gian chờ mâu thuẫn:** spec cũ xây toàn bộ perceived-progress quanh P95 < 90s (Orchestra); story 9-UX-1 định nghĩa "**2-14 minute** research process" với narration first-person. Đây là 2 tâm lý chờ hoàn toàn khác nhau, cần 2 hệ UI riêng.
- **C1.2 — Phase 2 UX Overhaul (9-UX-1..4) không có spec trong repo:** Live Research Lab, Crypto-Native Report Layout (Token Hero, sticky TOC, slide-in source detail), Interactive Analysis (bull/bear, token compare), Data Sources mới (Nansen/CertiK/Dune/TokenInsight).
- **C1.3 — Epic 11 không có UX:** FR41 banner "Connection lost — click to retry" sau 5 lần SSE fail; FR45 `useSubscriptionGate()` — blur + upgrade CTA khi subscription hết hạn, hoạt động offline, auto-unlock khi sync về.
- **C1.4 — Report layout cho deep research chưa được thiết kế** (hiện chỉ có text streaming + citation badge).

### 3.2 Spec cũ đã lỗi thời / tự mâu thuẫn
- **C2.1** Định danh Epic lệch sau đợt rename 2026-05-06 (Epic 10 cũ → 9-DF; Epic 10 mới = Institutional Terminal).
- **C2.2** Spec tự đánh dấu có block trùng lặp "should be deduped" (2 bản UX Consistency Patterns).
- **C2.3** Direction 3 tuyên bố "KHÔNG phải Dashboard" nhưng Phụ lục B (Epic 10) yêu cầu grid kiểu Bloomberg với "AI as Sidebar" — direction gốc bị đảo ở Institutional.
- **C2.4** "Data Freshness 🟢 Live (Kafka/WebSocket)" sai kiến trúc — FR40 nói rõ dữ liệu là **historical snapshots** qua cache middleware.
- **C2.5** Số agent không chốt (4→10 vs 11).

### 3.3 Story UI chưa có UX spec
9-FE-1 (Orchestra Strip + Citation Stacking — spec cũ tự nhận "NEW STORY còn thiếu"), 11.1/11.5/11.6, 3.5 (model picker theo quota), 5.6 (Admin Model Config), 5.7 (Token PAYG), 6.8/6.9 (Admin Gift Requests), 10-4/10-5 (Enterprise Risk, Liquidity Routing).

---

## 4. Định hướng thiết kế cập nhật (reconciliation)

### 4.1 Mode System — giải quyết mâu thuẫn C2.3 một lần dứt điểm
Không chọn lại direction. Chính thức hóa **một chassis, hai mode**:
- **Copilot Mode (mặc định, mọi journey MVP):** Direction 3 hiện tại — chat trung tâm, Context Pane phải.
- **Terminal Mode (Epic 10, opt-in per space):** grid workspace kéo-thả (react-resizable-panels đã có sẵn), AI thu thành rail phải (Copilot rail). Chuyển mode bằng toggle trong header space, trạng thái lưu per-space.
Nguyên tắc: **widget nào cũng phải sống được ở cả 2 mode** (Context Pane card ↔ grid tile là cùng một component với 2 container).

### 4.2 Dual-Clock Progress — giải quyết C1.1 + C1.7
- **Clock A — Orchestra (≤90s):** giữ `OrchestraStrip` + `AgentRow` như spec cũ; bổ sung **tier indicator** cho degradation ladder NFR-Q3: tier 2/3 (sequential/paced, ~42-50s) hiển thị "Đang chạy tuần tự để đảm bảo chất lượng — lâu hơn bình thường một chút" thay vì để user tưởng treo.
- **Clock B — Live Research Lab (2-14 phút, 9-UX-1):** component mới `ResearchTimeline` — narration first-person theo dòng thời gian (mỗi bước là một entry: "Đang đọc 14 nguồn về tokenomics…"), có thể thu nhỏ thành pill nổi để user làm việc khác, notification khi xong. Điểm neo tâm lý: **checkpoint mỗi ≤30s** phải có nội dung mới (không im lặng quá 30s — kế thừa "soft attention break").

### 4.3 Trust Layer — Local-first phải nhìn thấy được
- `SyncStatusChip` cố định ở header: ● Online (emerald glow) / ◐ Syncing (amber pulse) / ○ Offline (muted) — đúng ngôn ngữ glow/viền của design system cũ.
- Offline: nút AI disable mềm + tooltip "Cần kết nối để gọi AI — tài liệu vẫn đọc được", KHÔNG popup lỗi (Journey 2).
- Data freshness đổi thành "**Snapshot • cập nhật X phút trước**" (đúng FR40), bỏ ngôn ngữ Live/Kafka.
- Logout: dialog cảnh báo purge IndexedDB (NFR-S2) — "Dữ liệu offline trên máy này sẽ bị xóa".

---

## 5. Spec cải tiến ưu tiên hóa

### P0 — Sửa nền móng (tuần 1-2; chặn mọi thứ khác về mặt trải nghiệm)

**P0-1 · Hệ trạng thái async chuẩn cho MỌI surface** *(sửa F1, F7; nền cho FR41)*
- Quy tắc: mọi vùng dữ liệu có đúng 4 trạng thái: `skeleton` (theo hình dạng nội dung, ≤10s) → `content` / `empty` (icon + 1 câu + 1 CTA) / `error` (câu ngắn + nút Thử lại + chi tiết collapse).
- Spinner toàn màn bị CẤM ngoài auth transition. Timeout mặc định 10s → chuyển error.
- Zero-cache mất kết nối: banner mỏng đầu viewport "Mất kết nối đồng bộ — Thử lại" (chính là pattern FR41, dùng chung cho SSE).
- Shadcn: `Skeleton`, `Alert`, `Button variant=ghost`; state machine chung `useAsyncSurface()`.

**P0-2 · Xóa friction model** *(sửa F2; thực thi Story 3.5)*
- Auto-select model mặc định theo plan ngay khi vào space (free → model rẻ nhất được phép theo quota).
- Composer KHÔNG BAO GIỜ disabled vì thiếu model; nếu thiếu → gõ bình thường, khi submit hiện inline picker "Chọn model để gửi" (1 click).
- Model picker hiển thị quota context: tên + badge chi phí ước tính ("~2K tokens/câu") + phần quota còn lại.

**P0-3 · SyncStatusChip + logout purge messaging** *(sửa F6; PRD Risk, NFR-S2)* — như 4.3.

**P0-4 · Sửa Settings + hoàn thiện shell** *(sửa F1-settings, F3)*
- Điều tra & sửa nguyên nhân treo `/dashboard/settings` (bug thật, không phải thiếu service).
- Dashboard (chưa có space): thêm header tối thiểu (logo, user menu: Settings/Billing/Docs/Logout) + empty state kể chuyện: 3 bước minh họa (Tạo space → Kết nối nguồn → Hỏi AI).
- Greeting: `display_name || email_local_part` nhưng KHÔNG bao giờ dùng plan name; nếu trùng tên plan → "Chào buổi sáng 👋".

**P0-5 · Onboarding không chặn** *(sửa F4 một phần)*
- Coachmark chuyển sang anchored popover không modal (không dim toàn trang, không chặn pointer bên ngoài), có "Bỏ qua tất cả", resumable từ menu Trợ giúp.

### P1 — Đuổi kịp PRD (tuần 3-6)

**P1-1 · Crypto-Native Report Layout** *(9-UX-2, C1.4)*
- `ReportShell`: Token Hero card (logo, giá snapshot + freshness, các chỉ số chính), sticky TOC trái (scroll-spy), thân report với số liệu có `MultiCitationBadge` (giữ nguyên hệ single/stacked/cluster/conflict của spec cũ), charts nhúng lazy, click nguồn → `SourceDetailSheet` slide-in phải (shadcn `Sheet`).
- Chế độ đọc: max-width 800px giữ nguyên; nút "Export/Share" ở header report.

**P1-2 · ResearchTimeline (Live Research Lab)** *(9-UX-1, C1.1)* — như 4.2 Clock B; kèm event log tái sử dụng cho retrospective ("Xem lại AI đã làm gì").

**P1-3 · useSubscriptionGate UX** *(FR45, C1.3)*
- Content gated: blur 8px + overlay khóa 🔒 "Nội dung Deep Research — gói của bạn đã hết hạn" + CTA "Gia hạn Pro"; hoạt động offline (đọc từ Zero cache); khi sync phát hiện renewal → unblur với transition 300ms (một micro-delight đúng lúc).
- KHÔNG che metadata/tiêu đề — user phải thấy mình đang bỏ lỡ gì.

**P1-4 · Orchestra tier UI + chốt số agent** *(C1.7, C2.5)* — OrchestraStrip hiện "N agents" động từ config (không hardcode 6/11); tier notice như 4.2.

**P1-5 · Admin console pattern tối thiểu** *(C1.5; 5.5/5.6/6.8/6.9)*
- Một layout admin chung: bảng dữ liệu (shadcn `DataTable`) + hàng hành động Approve/Reject + confirm dialog + toast kết quả + audit note. Áp cho Gift Requests trước (6.9), Model Config sau (5.6).

### P2 — Tầm nhìn (sau P1)
- Terminal Mode grid đầy đủ (Epic 10) + 10-4/10-5 (stress-test, liquidity routing widgets).
- Gift flow polish (Phụ lục D đã có nền): trang `/gift/buy`, `/redeem`, visualize công thức stacking expiry.
- Desktop (Epic 8): provider badge mỗi response ("GPT-4o" / "Llama 3.1 8B local") + banner "Switched to local LLM" — pattern dùng chung với web khi fallback model.
- Storage guard: cảnh báo dung lượng IndexedDB + Partial Sync theo tag/filter (chọn gì để sync).
- i18n quyết định chính thức (khuyến nghị: vi/en toggle, mặc định theo browser).

---

## 6. Design tokens & nhất quán (giữ và siết)

- **Giữ:** zinc/slate + dark primary `#09090b`, accent Indigo (CTA) / Teal (citation), status bằng glow viền mỏng, Inter/Geist + JetBrains Mono, grid 8px, animation <150ms, không framer-motion spring, WCAG AA, `ring-2 ring-indigo-500`.
- **Siết thêm:**
  - Serif display CHỈ dùng cho marketing/landing + hero greeting; cấm trong data UI, report body, admin.
  - Landmark semantics bắt buộc: `<nav>`, `<aside>`, `<main>`, `role="tablist"` — sửa tình trạng inventory rỗng (F4).
  - Mọi trạng thái màu phải kèm icon/text (color-blind safe — đã có trong spec cũ, thực thi nghiêm).
  - Dev overlay/Issues badge không được xuất hiện ở production build.

## 7. Việc dọn nhà tài liệu (doc hygiene)
1. Dedup 2 bản "UX Consistency Patterns" trong spec cũ (spec tự đánh dấu — C2.2).
2. Sửa toàn bộ tham chiếu Epic theo bảng rename 2026-05-06 (C2.1).
3. Tạo story `9-FE-1: Orchestra Conductor Strip + Citation Stacking` (spec cũ tự nhận thiếu FE AC).
4. Khôi phục hoặc viết lại spec Phase 2 (`harmonic-cuddling-glacier.md` không có trong repo) — tài liệu này (mục 4-5) là bản thay thế đề xuất.
5. Cập nhật Data Freshness copy trong Phụ lục B theo FR40 (C2.4).

---

## Phụ lục: Điều kiện tái lập audit
Stack chạy trong sandbox: Docker (pgvector, redis, electric, **rocicorp/zero:0.26.2** — thiếu searxng), backend uvicorn :8000, Next dev :4998, user seed `free@nowing.ai`. Screenshots: `ux-01..08`, `ux2-01..05`. Lưu ý môi trường: settings treo cả khi zero-cache chạy; post-create spinner chỉ xảy ra khi zero-cache vắng — hai hiện tượng khác nhau, cùng một bài học UX (P0-1).
