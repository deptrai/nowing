# Kiến Trúc Web Frontend

## Tổng Quan
Ứng dụng Web Nowing được xây dựng trên **Next.js 16**, tận dụng các tính năng mới nhất như **React Server Components (RSC)** và **Server Actions**. Nó mang lại trải nghiệm người dùng (UX) hiện đại, nhanh chóng và tương tác cao, đóng vai trò là giao diện chính để người dùng quản lý kiến thức và tương tác với AI Agents.

## Stack Công Nghệ (Tech Stack)

| Hạng Mục | Công Nghệ | Ghi Chú |
|----------|-----------|---------|
| **Core** | Next.js 16 (Turbopack) | App Router, Server Actions |
| **Language** | TypeScript | Type safety toàn diện |
| **UI Library** | React 19 | Hooks mới (useOptimistic, useFormStatus) |
| **Styling** | Tailwind CSS v4 | Utility-first CSS |
| **Real-time Sync** | @rocicorp/zero ^0.26.2 | Multiplayer sync qua zero-cache → Postgres logical replication |
| **Local-First DB** | @electric-sql/pglite + Drizzle ORM | PGlite cho offline/client-side queries |
| **Client State** | Jotai ^2.15.1 + jotai-tanstack-query | Atomic state management, 25+ atom modules |
| **Components** | Shadcn UI + Assistant UI | Reusable components & AI Chat UI |

## Mô Hình Kiến Trúc (Architecture Patterns)

### 1. App Router & Server Components
- **Mặc định là Server Component**: Hầu hết các components (Layout, Page) được render trên server để tối ưu SEO và tải trang ban đầu.
- **Client Components**: Chỉ sử dụng (`"use client"`) cho các phần tương tác (interactive) như form, button, hoặc real-time chat.
- **Data Fetching**: Fetch dữ liệu trực tiếp trong Server Components (không cần useEffect cho initial data).

### 2. Server Actions cho Mutations
- Thay vì tạo API routes riêng biệt cho mọi hành động (submit form, like bài viết), Nowing sử dụng **Server Actions**.
- Gọi hàm backend trực tiếp từ frontend code.
- Xử lý xác thực và validation ngay trong action.

### 3. Dual Real-time Sync Stack

Nowing sử dụng **hai** hệ thống sync song song, mỗi hệ thống phục vụ mục đích riêng:

#### 3a. Rocicorp/Zero — Primary Real-time Multiplayer Sync
- **Vai trò**: Đồng bộ real-time giữa nhiều users trên cùng search space.
- **Cơ chế**: `zero-cache` (Docker service, port 4848) đọc Postgres WAL qua logical replication → push changes tới clients qua WebSocket.
- **Provider**: `ZeroProvider.tsx` wrap toàn bộ dashboard, cung cấp `useZero()` hook.
- **Auth**: Zero tự động refresh JWT khi `connectionState === "needs-auth"` thông qua `ZeroAuthSync` component.
- **Schema**: Định nghĩa tại `zero/schema/`, queries tại `zero/queries/`.
- **Hooks sử dụng Zero**:
  - `use-messages-sync.ts` — chat messages real-time
  - `use-comments-sync.ts` — chat comments real-time
  - `use-connectors-sync.ts` — connector status sync
  - `use-folder-sync.ts` — folder/document tree sync
  - `use-zero-document-type-counts.ts` — document count badges

#### 3b. ElectricSQL/PGlite — Client-side Offline Database
- **Vai trò**: Local-first database trong browser cho instant queries mà không cần network round-trip.
- **Cơ chế**: `@electric-sql/pglite` chạy Postgres trong WASM, `pglite-sync` đồng bộ từ server.
- **ORM**: Drizzle ORM (`drizzle.config.ts`, `app/db/schema.ts`) cung cấp type-safe queries trên PGlite.
- **Use case**: Optimistic UI updates, offline search, client-side aggregation.

### 4. Client State Management (Jotai)

Nowing sử dụng **Jotai** (atomic state) thay vì Redux/Zustand, tổ chức theo domain modules:

```
atoms/
├── auth/              — user session, tokens
├── chat/              — active thread, messages, orchestra events
├── chat-comments/     — comment threads on messages
├── connectors/        — connector list, sync status
├── documents/         — document tree, selection state
├── editor/            — Plate editor state
├── inbox/             — notification inbox
├── layout/            — sidebar collapse, panel visibility
├── settings/          — user preferences
├── ui/                — modals, toasts, loading states
├── agent-tools/       — tool call UI state
├── image-gen-config/  — image generation settings
├── new-llm-config/    — LLM model selector state
├── vision-llm-config/ — vision model config
├── tabs/              — multi-tab navigation
├── members/           — team member list
├── roles/             — RBAC roles
├── permissions/       — permission state
├── search-spaces/     — workspace selector
├── prompts/           — saved prompt templates
├── logs/              — activity logs
├── invites/           — team invitations
├── connector-dialog/  — connector setup wizard
└── public-chat-snapshots/ — shared chat snapshots
```

`jotai-tanstack-query` được dùng cho server-state atoms (API data caching + revalidation).

### 5. Kiến Trúc AI Chat

- **Streaming**: Backend LangGraph stream qua SSE → frontend `AssistantRuntime` (from `@assistant-ui/react`) consume và render progressively.
- **Generative UI**: Render các components React ngay trong luồng chat:
  - `CryptoReportLayout` — full crypto analysis report với TOC, citation chips, charts
  - `EmbeddedChartWrapper` — inline charts từ `chart:` code blocks
  - `CryptoCitationInline` — clickable data citations với source detail panel
  - `InlineCitation` / `UrlCitation` — KB chunk và web search citations
- **Markdown Pipeline**: `markdown-text.tsx` xử lý:
  1. `preprocessMarkdown()`: strip HTML comments, normalize LaTeX, transform `[[cite:id]]value[[/cite]]` → `[cryptocite:id:value]`
  2. remark-gfm + remark-math → rehype-katex
  3. Custom components: tables, images, code blocks, heading slugs (for TOC linking)
- **Tool Call Handling**: Client hiển thị trạng thái "đang xử lý" khi Agent gọi tool, với orchestra narration events cho crypto sub-agents.
- **Scenario Simulator**: Interactive panel cho "what-if" crypto analysis, responsive stacking (`2xl` breakpoint = 1536px).

## Cấu Trúc Thư Mục Chính (`nowing_web/app`)

### Public Routes
- `(home)/` — Landing page, Marketing sites
- `auth/` — Login, Register, Password reset
- `docs/` — Public documentation
- `invite/` — Team invitation acceptance
- `public/` — Public shared chat views
- `redeem/` — Gift code redemption
- `verify-token/` — Email verification

### Protected Routes (Dashboard)
- `dashboard/[search_space_id]/` — Workspace-scoped routes:
  - `new-chat/[[...chat_id]]/` — AI Chat interface (main feature)
  - `crypto/` — Crypto-specific views
  - `crypto-tools-demo/` — Crypto tools playground
  - `connectors/` — Manage external connectors
  - `connectors/callback/` — OAuth callback handlers
  - `team/` — Team management
  - `user-settings/` — User preferences
  - `logs/` — Activity & usage logs
  - `buy-tokens/` — Token purchase
  - `gift/` — Gift subscription management
  - `onboard/` — Onboarding wizard
  - `more-pages/` — Additional pages

### Internal Routes
- `api/` — Route Handlers (webhooks, zero query proxy)
- `db/` — Database schema & client setup (Drizzle + PGlite)
- `desktop/` — Electron-specific routes

## Key Components (`nowing_web/components`)

### AI Chat Components (`assistant-ui/`)
- `markdown-text.tsx` — Markdown renderer với citation parsing, LaTeX, charts
- `markdown-code-block.tsx` — Syntax-highlighted code blocks
- `inline-citation.tsx` — KB chunk citation chips
- `thinking-steps.tsx` — AI reasoning step display
- `connector-popup.tsx` — In-chat connector attachment
- `thread-list.tsx` — Chat thread sidebar

### Crypto Report (`new-chat/report/`)
- `crypto-report-layout.tsx` — Full report layout với TOC sidebar + scenario simulator
- `crypto-citation-inline.tsx` — Crypto-specific citation chips (CoinGecko, DeFiLlama, etc.)
- `embedded-charts/` — Chart rendering trong markdown
- `report-toc.tsx` — Sticky table of contents
- `source-detail-panel.tsx` — Citation source detail slide-in sheet

### Providers
- `ZeroProvider.tsx` — Rocicorp/Zero real-time sync
- `QueryProvider.tsx` — TanStack Query
- `AuthProvider.tsx` — Authentication context
