# Sprint Change Proposal: Frontend Navigation Performance & Layout Modernization

**Date:** 2026-09-17  
**Trigger:** Phản hồi từ người dùng về hiện tượng click điều hướng giữa các trang trong Dashboard (`Health`, `Usage`, `Automations`, `Artifacts`, `Playbooks`, `Connectors`, `Settings`...) bị giật lag, trễ 1–3 giây và UI bị đóng băng (Frozen Transition).  
**Scope Classification:** Moderate (Kiến trúc Frontend & Tối ưu Render Pipeline)  
**Target Epic:** **Epic 30: Technical Debt** (Append Story 30.10 — không tạo Epic mới)  

---

## 1. Issue Summary & Problem Statement

### 1.1 Vấn đề cốt lõi
Khi người dùng click vào các liên kết điều hướng trên Sidebar hoặc Icon Rail, giao diện web phản hồi rất chậm, thường xuyên xuất hiện các triệu chứng:
1. **Frozen UI (Màn hình đơ tạm thời):** Click vào nút nhưng màn hình cũ giữ nguyên 500ms – 2s không có phản hồi thị giác (visual feedback), tạo cảm giác "click không ăn".
2. **Layout Thrashing & Flicker:** Khi chuyển đổi giữa trang Chat (`new-chat`) và các trang quản trị/tiện ích (`Automations`, `Artifacts`, `Team`, `Chats`), toàn bộ container của trang bị unmount và mount lại từ đầu.
3. **Provider Overload & Uncached Network Waterfalls:** Root Layout gánh các thư viện nặng (`Fumadocs RootProvider`) và các blocking gates (`ZeroProvider` probe, `useSession` gọi API riêng rẽ).

### 1.2 Bằng chứng kỹ thuật thực tế (Codebase Evidence)
* `SidebarButton.tsx` và `IconRail.tsx` bọc các mục menu bằng `<Button onClick={() => router.push(url)}>`, triệt tiêu hoàn toàn tính năng prefetch tự động của Next.js App Router.
* 90% các thư mục route con trong `app/dashboard/[workspace_id]/` (`health`, `usage`, `connectors`, `automations`, `artifacts`, `playbooks`, `chats`, `crm`, `team`, `workspace-settings`, `user-settings`) **hoàn toàn thiếu file `loading.tsx`**, buộc Next.js phải chờ toàn bộ Server Component và JS chunk tải xong mới cho phép chuyển trang.
* `LayoutShell.tsx` (dòng 424–452) sử dụng câu lệnh điều kiện rẽ nhánh JSX:
  ```tsx
  {useWorkspacePanel ? (
      <WorkspacePanel>{children}</WorkspacePanel>
  ) : (
      <MainContentPanel>{children}</MainContentPanel>
  )}
  ```
  khiến React reconciliation phải phá hủy toàn bộ DOM layout cũ khi chuyển giữa Chat và Workspace views.
* `Fumadocs RootProvider` bọc ở `app/layout.tsx` và import CSS toàn cục trong `globals.css` làm phình vendor chunk của toàn bộ Dashboard.

---

## 2. Impact Analysis

### 2.1 Tác động lên Epics & Stories
* Không tạo Epic mới. Toàn bộ phạm vi được tích hợp trực tiếp vào **Epic 30: Technical Debt** dưới dạng **Story 30.10: Frontend Navigation Performance & Layout Modernization**.
* Tương thích hoàn toàn với các Epic hiện tại (Epic 4 TabBar, Epic 21 Lead Gen Canvas, Epic 24 Lead Clipper, Epic 26 Split Canvas, Epic 29 Health Analytics).

### 2.2 Tác động lên PRD & NFRs
* **Bổ sung NFR-PERF-UI:**
  * Thời gian phản hồi xúc giác/thị giác (Instant Feedback) khi click điều hướng nội bộ: **< 50ms** (hiển thị skeleton hoặc active tab ngay lập tức).
  * Thời gian hoàn tất chuyển trang (Page Transition Complete): **< 300ms** trong điều kiện mạng thông thường.
  * Zero Layout Shift (CLS < 0.05) đối với khung sườn ứng dụng (App Shell).

### 2.3 Tác động lên Kiến trúc (Architectural Decision)
* **Bổ sung AD-38: Semantic Client Navigation & Layout Boundary Invariants**:
  1. Mọi liên kết điều hướng nội bộ trong App Shell bắt buộc dùng `<Link href="..." prefetch={true}>`.
  2. Tất cả các sub-routes trong `app/dashboard/[workspace_id]/` bắt buộc phải có file `loading.tsx` tương ứng kế thừa `DashboardPageSkeleton`.
  3. Cấm rẽ nhánh ternary phá hủy Root Layout Container (`LayoutShell`); cấu trúc shell phải ổn định (persistent DOM tree).

---

## 3. Recommended Approach

Thay vì chia nhỏ thành 3–4 micro-stories gây phân mảnh tiến độ, toàn bộ công việc được gộp thành **01 Story duy nhất: Story 30.10** được tổ chức thành 3 phase thực thi tuần tự, rõ ràng:

* **Phase 1: Instant Navigation & Route Boundaries (P0 - Quick Wins)**
  * Chuyển đổi `SidebarButton` và `IconRail` sang semantic `<Link href="...">`.
  * Xây dựng `DashboardPageSkeleton` và triển khai `loading.tsx` cho toàn bộ 9 dashboard sub-routes.
  * Cấu hình `optimizePackageImports` trong `next.config.ts`.
* **Phase 2: Shell Architecture Unification (P1 - Core Refactor)**
  * Hợp nhất `MainContentPanel` và `WorkspacePanel` trong `LayoutShell` thành một container duy nhất ổn định (persistent container), triệt tiêu layout thrashing.
* **Phase 3: Provider Decoupling & Session Caching (P1/P2 - Hardening)**
  * Di dời `Fumadocs RootProvider` và CSS liên quan từ Root Layout sang `app/docs/layout.tsx`.
  * Chuẩn hóa `useSession` dùng React Query / Jotai atom để triệt tiêu request trùng lặp.

---

## 4. Detailed Story Proposal

### Story 30.10: Frontend Navigation Performance & Layout Modernization

**Epic:** Epic 30: Technical Debt  
**Type:** Technical Debt / Performance Optimization  
**Priority:** P0  
**Target Codebase:** `nowing_web`  

#### User Story
As a user navigating the Nowing dashboard,  
I want instantaneous feedback and zero UI-freezing when clicking between tools, chats, and workspace pages,  
So that my research and agent monitoring workflow feels desktop-grade, fluid, and responsive.

#### Acceptance Criteria
1. **AC-1 (Semantic Link Navigation & Prefetch):**
   * Toàn bộ các nút điều hướng trong `Sidebar.tsx`, `SidebarButton.tsx`, `IconRail.tsx`, và `AllChatsSidebar.tsx` chuyển sang sử dụng `<Link href="..." prefetch={true}>` của Next.js.
   * Hover chuột (`onMouseEnter`) kích hoạt prefetch RSC payload và query cache nếu có.
2. **AC-2 (Route Loading Boundaries):**
   * Xây dựng component dùng chung `DashboardPageSkeleton.tsx` với animation mượt mà (shimmer/pulse).
   * Cung cấp file `loading.tsx` chuẩn hóa cho tất cả các sub-routes: `health`, `usage`, `connectors`, `automations`, `artifacts`, `playbooks`, `chats`, `workspace-settings`, `user-settings`.
   * Khi click, UI chuyển ngay lập tức sang skeleton (< 50ms), loại bỏ hoàn toàn hiện tượng đóng băng màn hình cũ.
3. **AC-3 (Persistent Shell & Layout Stability):**
   * Tái cấu trúc `LayoutShell.tsx` để duy trì một container DOM duy nhất (`DesktopWorkspaceRegion`), không unmount/remount khi chuyển đổi giữa `isChatPage` và `useWorkspacePanel`.
   * Các style đặc thù (chiều rộng tối đa, padding) được áp dụng qua CSS class lên `children` container thay vì đổi thẻ cha.
4. **AC-4 (Provider Decoupling & Critical Bundle Optimization):**
   * Gỡ bỏ `RootProvider` của Fumadocs khỏi `app/layout.tsx`; chuyển định tuyến và CSS của Fumadocs vào `app/docs/layout.tsx`.
   * Thêm các thư viện nặng (`@radix-ui/*`, `recharts`) vào `experimental.optimizePackageImports` trong `next.config.ts`.
   * Dynamic import các chart nặng trong `usage-content.tsx` (`UsageChart`, `PerTurnUsageSection`).
5. **AC-5 (Verification & Performance Benchmark):**
   * E2E test kiểm tra chuyển trang giữa `new-chat` -> `health` -> `automations` -> `usage` không xảy ra console error và thời gian chuyển < 300ms trên local build.

---

## 5. Implementation Handoff & Next Steps

* **Phân loại phạm vi:** Moderate (Nội bộ frontend `nowing_web`, không ảnh hưởng backend API hay database).
* **Tiếp nhận thực thi:** Developer Agent (`bmad-agent-dev` hoặc workflow `bmad-build`).
* **Kế hoạch cập nhật artifacts:**
  1. Cập nhật `_bmad-output/planning-artifacts/epics.md`: Bổ sung Story 30.10 vào Epic 30.
  2. Cập nhật `_bmad-output/implementation-artifacts/sprint-status.yaml`: Thêm `30-10-frontend-navigation-performance-layout-modernization: ready-for-dev`.
