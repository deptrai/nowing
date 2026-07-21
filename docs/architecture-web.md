# Kiến trúc - SurfSense Web

**Ngày tạo:** 2026-07-21 16:59:34

## Tóm tắt

Frontend chính của SurfSense, xây dựng bằng Next.js 16 App Router. Cung cấp landing page, dashboard, chat, connectors, settings, docs site, và desktop-specific pages.

## Tech Stack

| Thành phần | Công nghệ |
|---|---|
| Framework | Next.js 16, React 19, TypeScript |
| Styling | Tailwind CSS v4, Radix UI, shadcn/ui patterns |
| State | Jotai (`atoms/`), Zustand, Tanstack Query (`hooks/`) |
| Editor | Plate.js, Monaco editor |
| Animation | motion (Framer Motion), lenis |
| Docs | Fumadocs (`content/docs/`, `app/docs/`) |
| Database ORM | Drizzle ORM, Drizzle Kit, PostgreSQL (`pg`/`postgres`) |
| E2E Tests | Playwright |
| Linter/Format | Biome, ESLint |

## Kiến trúc ứng dụng

- **App Router:** `app/(home)/` cho marketing, `app/dashboard/[workspace_id]/` cho ứng dụng chính, `app/desktop/` cho desktop auth/permissions.
- **Server proxy:** mọi API call đi qua `app/api/v1/[...path]/route.ts` để forward tới backend.
- **Real-time sync:** `app/api/zero/mutate` & `app/api/zero/query` dùng Rocicorp Zero.
- **Auth:** `app/auth/[...path]/route.ts` và `app/verify-token/route.ts`.

## Cấu trúc thư mục chính

| Thư mục | Mục đích |
|---|---|
| `app/(home)/` | Landing, blog, changelog, pricing, connectors, login/register |
| `app/dashboard/` | Workspace dashboard, chats, automations, settings, playground |
| `app/api/` | API proxy routes |
| `components/` | UI components (shadcn/radix, editor, layout) |
| `lib/` | Utilities, API clients, helpers |
| `hooks/` | React Query hooks và custom hooks |
| `atoms/` | Jotai global state |
| `contexts/` | React Context providers |
| `features/` | Feature-specific modules |
| `zero/` | Zero sync configuration |
| `content/docs/` | Fumadocs content |
| `public/` | Static assets |

## Component inventory

Xem [component-inventory-web.md](./component-inventory-web.md).

## Tích hợp

Xem [integration-architecture.md](./integration-architecture.md).

---

_Tài liệu được tạo bởi BMAD Method `document-project` workflow_
