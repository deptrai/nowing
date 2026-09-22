---
story_key: 30-10-frontend-navigation-performance-layout-modernization
status: done
epic: 30
priority: P0
target_codebase: nowing_web
baseline_commit: b492c11bce39e34abb5ff342294037f974898e69
---

# Story 30.10: Frontend Navigation Performance & Layout Modernization

**Status:** `done`  
**Epic:** Epic 30: Technical Debt  
**Priority:** P0  
**Target Codebase:** `nowing_web`  
**Architectural Approval:** Winston (Lead Architect), Sally (UX), Amelia (Dev), Murat (QA), Mary (BA)

## Story

As a user navigating the Nowing dashboard,  
I want instantaneous feedback and zero UI-freezing when clicking between tools, chats, and workspace pages,  
So that my research and agent monitoring workflow feels desktop-grade, fluid, and responsive.

## Problem Statement

Hiện tượng click điều hướng giữa các trang trong Dashboard (`Health`, `Usage`, `Automations`, `Artifacts`, `Playbooks`, `Connectors`, `Settings`, `CRM`...) bị giật lag, trễ 1–3 giây và UI bị đóng băng (Frozen Transition).
Nguyên nhân gốc rễ kỹ thuật:
1. `SidebarButton.tsx` và `IconRail.tsx` bọc các mục menu bằng `<Button onClick={() => router.push(url)}>`, triệt tiêu hoàn toàn tính năng prefetch tự động của Next.js App Router.
2. 90% các thư mục route con trong `app/dashboard/[workspace_id]/` thiếu file `loading.tsx`, buộc Next.js phải chờ toàn bộ Server Component và JS chunk tải xong mới cho phép chuyển trang.
3. `LayoutShell.tsx` sử dụng rẽ nhánh ternary `{useWorkspacePanel ? <WorkspacePanel> : <MainContentPanel>}` khiến React reconciliation unmount/remount toàn bộ cây DOM layout khi chuyển giữa Chat và Workspace views.
4. `Fumadocs RootProvider` bọc ở `app/layout.tsx` làm phình vendor chunk của toàn bộ Dashboard.

## Acceptance Criteria

### AC-1: Semantic Link Navigation & RSC Prefetching (P0)
- **AC-1.1:** `SidebarButton.tsx` được nâng cấp thành polymorphic component, chấp nhận prop `href?: string` và `prefetch?: boolean` (mặc định `true`). Khi có `href`, render `<Link href={href} prefetch={prefetch} ...>`; khi không có `href`, fallback về `<button type="button" onClick={onClick} ...>`.
- **AC-1.2:** Toàn bộ các liên kết điều hướng trong `Sidebar.tsx`, `NavSection.tsx`, `IconRail.tsx`, và danh sách chat trong `AllChatsSidebar.tsx` chuyển sang truyền prop `href`. Tuyệt đối không dùng imperative `router.push()` cho việc chuyển đổi menu tĩnh.
- **AC-1.3:** Khi người dùng hover (`onMouseEnter`) vào bất kỳ liên kết điều hướng nào, Next.js tự động prefetch RSC payload và client chunk tương ứng.
- **AC-1.4:** Phản hồi xúc giác/thị giác (active indicator hoặc visual state) diễn ra tức thì (< 50ms) bằng CSS `:active` (`active:scale-[0.98] active:bg-accent/80`), độc lập hoàn toàn với thời gian tải dữ liệu từ API.

### AC-2: Comprehensive Loading Boundaries & Skeletons (P0)
- **AC-2.1 (Universal Root Fallback):** Tạo file `nowing_web/app/dashboard/[workspace_id]/loading.tsx` sử dụng component chuẩn `DashboardPageSkeleton.tsx` làm fallback mặc định bao bọc toàn bộ không gian làm việc.
- **AC-2.2 (Dedicated Leaf Routes):** Tạo file `loading.tsx` chuẩn hóa cho tất cả các sub-routes trong `app/dashboard/[workspace_id]/`:
  `health`, `usage`, `connectors`, `automations`, `artifacts`, `playbooks`, `chats`, `workspace-settings`, `user-settings`, `crm`, `leads`, `research`, `team`, `governance`.
- **AC-2.3 (Zero CLS Skeleton):** Tạo `DashboardPageSkeleton.tsx` tại `nowing_web/components/layout/ui/skeletons/DashboardPageSkeleton.tsx`. Component là pure Server Component, có layout container, header anchor (72px) và grid cards khớp với wireframe thật để triệt tiêu layout shift (CLS < 0.05).

### AC-3: Persistent Layout Shell Invariant (AD-38) (P1)
- **AC-3.1:** Tái cấu trúc `LayoutShell.tsx` nhằm loại bỏ khối rẽ nhánh ternary `{useWorkspacePanel ? <WorkspacePanel> : <MainContentPanel>}`.
- **AC-3.2:** Vùng làm việc chính (`DesktopWorkspaceRegion`) duy trì một thẻ `<main id="main-workspace-root">` bất biến duy nhất xuyên suốt mọi chu trình chuyển đổi route giữa Chat (`/new-chat`, `/c/[chat_id]`) và Workspace views (`/automations`, `/health`, `/usage`, v.v.).
- **AC-3.3:** Khác biệt hiển thị (full-width vs centered max-width) được xử lý thuần túy qua CSS utility classes trên container con, không unmount hay recreate node cha.
- **AC-3.4:** `RightPanel` được giữ ổn định trong cây DOM desktop và chỉ ẩn/hiện thông qua prop `disabled={useWorkspacePanel}`, bảo toàn trạng thái animations và subscriptions.

### AC-4: Bundle Optimization & Vendor Decoupling (P1/P2)
- **AC-4.1:** Di dời component `<RootProvider>` của Fumadocs khỏi `nowing_web/app/layout.tsx`, tái định vị độc quyền bên trong `nowing_web/app/docs/layout.tsx`.
- **AC-4.2:** Cấu hình `nowing_web/next.config.ts` bổ sung `recharts` và danh sách tường minh toàn bộ 22 thư viện `@radix-ui/react-*` vào mục `experimental.optimizePackageImports` (tuyệt đối không dùng ký tự đại diện `*`).
- **AC-4.3:** Component `UsageChart` và `PerTurnUsageSection` trong `nowing_web/components/usage/usage-content.tsx` được chuyển sang tải động qua `next/dynamic` với placeholder skeleton, loại bỏ `recharts` khỏi critical initial bundle.
- **AC-4.4:** Hook `nowing_web/hooks/use-session.ts` áp dụng cơ chế caching và deduplication qua React Query (`queryKey: ["auth-session"]`) với staleTime hợp lý.

### AC-5: Performance SLA & Automated Quality Gates (P0)
- **AC-5.1 (SLA Định Lượng trên Production Build):**
  - Instant visual feedback time: **< 50ms**.
  - Complete transition settle time: **< 300ms**.
  - App Shell Cumulative Layout Shift (CLS): **< 0.05**.
- **AC-5.2 (Zero Regression):** Không phát sinh lỗi console, lỗi hydration mismatch; Biome linter pass 100% (`pnpm biome check`).

## Non-Goals
1. Không can thiệp backend API, FastAPI endpoints, Celery workers, database schemas.
2. Không thay đổi thiết kế visual, typography, màu sắc, bố cục hiển thị.
3. Không tái cấu trúc logic nghiệp vụ bên trong các trang con (`crm`, `leads`, chat streaming).
4. Không thay đổi thư viện state management (Jotai, React Query).
5. Không thay đổi cấu trúc navigation mobile ngoài việc cập nhật `SidebarButton`.

## Implementation Directives for Dev

1. **Polymorphic `SidebarButton`:**
   Hỗ trợ cả `href` (dùng Next `<Link>`) và `onClick` (dùng `<Button>`), tránh lồng thẻ `<a>` trong `<button>` hoặc truyền `type="button"` vào `<a>`.
2. **Persistent Root Container trong `LayoutShell.tsx`:**
   Giữ nguyên một thẻ `<main id="main-workspace-root">` cố định trong `DesktopWorkspaceRegion`.
3. **Cấu hình tường minh `next.config.ts`:**
   Liệt kê đầy đủ 22 thư viện `@radix-ui/react-*`, `recharts`, `lucide-react`, `@tabler/icons-react`, `motion` trong `optimizePackageImports`.
4. **Fumadocs Isolation:**
   Gỡ `<RootProvider>` tại `app/layout.tsx`, bọc vào `app/docs/layout.tsx` với `<RootProvider theme={{ enabled: false }}>`.
5. **Pure Server Component Skeletons:**
   `DashboardPageSkeleton.tsx` và toàn bộ các file `loading.tsx` phải là Server Component thuần túy (không `"use client"`).

## Tasks & Acceptance

- [x] **Task 1: Semantic Navigation & Polymorphic Link (AC-1)**
  - Nâng cấp `SidebarButton.tsx` hỗ trợ polymorphic `href?: string` render Next.js `<Link prefetch={true}>`.
  - Cập nhật `Sidebar.tsx`, `IconRail.tsx`, `NavSection.tsx`, `AllChatsSidebar.tsx` chuyển sang truyền `href`.
- [x] **Task 2: Comprehensive Loading Boundaries & Skeletons (AC-2)**
  - Tạo Server Component `DashboardPageSkeleton.tsx` tại `components/layout/ui/skeletons/`.
  - Tạo universal fallback `app/dashboard/[workspace_id]/loading.tsx`.
  - Tạo `loading.tsx` cho tất cả các sub-routes (`health`, `usage`, `connectors`, `automations`, `artifacts`, `playbooks`, `chats`, `workspace-settings`, `user-settings`, `crm`, `leads`, `research`, `team`, `governance`).
- [x] **Task 3: Persistent Layout Shell Invariant AD-38 (AC-3)**
  - Hợp nhất rẽ nhánh trong `LayoutShell.tsx` thành `<main id="main-workspace-root">` duy nhất.
  - Điều chỉnh styling full-width vs centered max-width bằng CSS classes trên container con.
  - Giữ `RightPanel` ổn định với `disabled={useWorkspacePanel}`.
- [x] **Task 4: Bundle Optimization & Vendor Decoupling (AC-4)**
  - Di dời Fumadocs `RootProvider` từ `app/layout.tsx` sang `app/docs/layout.tsx`.
  - Cập nhật `next.config.ts` với `optimizePackageImports` (22 Radix UI packages, recharts, lucide-react, motion).
  - Dynamic import `UsageChart` trong `usage-content.tsx`.
  - Kiểm tra `useSession` cache key trong React Query.
- [x] **Task 5: Verification & Quality Gate (AC-5)**
  - Chạy `pnpm biome check` và fix linter issues.
  - Chạy test / build để xác nhận không có hydration mismatch hay compilation error.


## Suggested Review Order

**Semantic Navigation & Prefetching (AC-1)**

- Polymorphic link component with prefetching and tactile active feedback
  [`SidebarButton.tsx:130`](../../../nowing_web/components/layout/ui/sidebar/SidebarButton.tsx#L130)

- WorkspaceAvatar Link navigation with primary-click pointer down guard
  [`WorkspaceAvatar.tsx:160`](../../../nowing_web/components/layout/ui/icon-rail/WorkspaceAvatar.tsx#L160)

- Sidebar link routing wiring and prefetch configuration
  [`Sidebar.tsx:210`](../../../nowing_web/components/layout/ui/sidebar/Sidebar.tsx#L210)

- Chat thread Link navigation with mobile long-press guard
  [`AllChatsSidebar.tsx:338`](../../../nowing_web/components/layout/ui/sidebar/AllChatsSidebar.tsx#L338)

- Chat list item Link conversion with prefetch on hover
  [`ChatListItem.tsx:75`](../../../nowing_web/components/layout/ui/sidebar/ChatListItem.tsx#L75)

- Navigation provider routing coordination without redundant router.push
  [`LayoutDataProvider.tsx:502`](../../../nowing_web/components/layout/providers/LayoutDataProvider.tsx#L502)

**Persistent Layout Shell Invariant AD-38 (AC-3)**

- Unified main-workspace-root container eliminating ternary layout branch
  [`LayoutShell.tsx:130`](../../../nowing_web/components/layout/ui/shell/LayoutShell.tsx#L130)

- Persistent RightPanel mounting with disabled state toggle
  [`RightPanel.tsx:533`](../../../nowing_web/components/layout/ui/right-panel/RightPanel.tsx#L533)

**Comprehensive Loading Boundaries (AC-2)**

- Reusable pure Server Component page skeleton with fixed 72px header anchor
  [`DashboardPageSkeleton.tsx:13`](../../../nowing_web/components/layout/ui/skeletons/DashboardPageSkeleton.tsx#L13)

- Universal root loading boundary for dashboard workspace routes
  [`app/dashboard/[workspace_id]/loading.tsx:1`](../../../nowing_web/app/dashboard/[workspace_id]/loading.tsx#L1)

**Bundle Optimization & Vendor Decoupling (AC-4)**

- Isolation of Fumadocs RootProvider to docs subtree
  [`app/docs/layout.tsx:18`](../../../nowing_web/app/docs/layout.tsx#L18)

- Root layout clean-up with ReactQueryClientProvider elevation
  [`app/layout.tsx:241`](../../../nowing_web/app/layout.tsx#L241)

- Optimization of package imports for Radix UI, Recharts, Lucide, Motion
  [`next.config.ts:70`](../../../nowing_web/next.config.ts#L70)

- Dynamic import of heavy Recharts usage charts
  [`usage-content.tsx:1197`](../../../nowing_web/components/usage/usage-content.tsx#L1197)

- Deduplicated session caching via React Query with SSR hydration safety
  [`use-session.ts:90`](../../../nowing_web/hooks/use-session.ts#L90)
