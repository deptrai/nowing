# SurfSense Web - Component Inventory

**Ngày tạo:** 2026-07-21 16:59:34

## Tổng quan

Frontend Next.js sử dụng React 19, Tailwind CSS v4, Radix UI/shadcn, Plate editor, Jotai/Zustand cho state, Tanstack Query cho server state.

## Cấu trúc App Router

Các route chính:

- `app/(home)/[slug]/page.tsx`
- `app/(home)/announcements/layout.tsx`
- `app/(home)/announcements/page.tsx`
- `app/(home)/blog/[slug]/loading.tsx`
- `app/(home)/blog/[slug]/page.tsx`
- `app/(home)/blog/loading.tsx`
- `app/(home)/blog/page.tsx`
- `app/(home)/changelog/loading.tsx`
- `app/(home)/changelog/page.tsx`
- `app/(home)/connectors/page.tsx`
- `app/(home)/contact/page.tsx`
- `app/(home)/external-mcp-connectors/page.tsx`
- `app/(home)/free/[model_slug]/layout.tsx`
- `app/(home)/free/[model_slug]/loading.tsx`
- `app/(home)/free/[model_slug]/page.tsx`
- `app/(home)/free/layout.tsx`
- `app/(home)/free/loading.tsx`
- `app/(home)/free/page.tsx`
- `app/(home)/layout.tsx`
- `app/(home)/login/layout.tsx`
- `app/(home)/login/page.tsx`
- `app/(home)/mcp-server/page.tsx`
- `app/(home)/page.tsx`
- `app/(home)/pricing/page.tsx`
- `app/(home)/privacy/page.tsx`
- `app/(home)/register/layout.tsx`
- `app/(home)/register/page.tsx`
- `app/(home)/terms/page.tsx`
- `app/dashboard/[workspace_id]/artifacts/page.tsx`
- `app/dashboard/[workspace_id]/automations/[automation_id]/edit/page.tsx`
- `app/dashboard/[workspace_id]/automations/[automation_id]/page.tsx`
- `app/dashboard/[workspace_id]/automations/new/page.tsx`
- `app/dashboard/[workspace_id]/automations/page.tsx`
- `app/dashboard/[workspace_id]/buy-more/page.tsx`
- `app/dashboard/[workspace_id]/buy-pages/page.tsx`
- `app/dashboard/[workspace_id]/buy-tokens/page.tsx`
- `app/dashboard/[workspace_id]/chats/page.tsx`
- `app/dashboard/[workspace_id]/connectors/callback/route.ts`
- `app/dashboard/[workspace_id]/earn-credits/page.tsx`
- `app/dashboard/[workspace_id]/layout.tsx`
- `app/dashboard/[workspace_id]/logs/(manage)/page.tsx`
- `app/dashboard/[workspace_id]/logs/loading.tsx`
- `app/dashboard/[workspace_id]/more-pages/page.tsx`
- `app/dashboard/[workspace_id]/new-chat/[[...chat_id]]/page.tsx`
- `app/dashboard/[workspace_id]/new-chat/loading.tsx`
- `app/dashboard/[workspace_id]/onboard/page.tsx`
- `app/dashboard/[workspace_id]/page.tsx`
- `app/dashboard/[workspace_id]/playground/[platform]/[verb]/page.tsx`
- `app/dashboard/[workspace_id]/playground/api-keys/page.tsx`
- `app/dashboard/[workspace_id]/playground/layout.tsx`
- `app/dashboard/[workspace_id]/playground/page.tsx`
- `app/dashboard/[workspace_id]/playground/runs/page.tsx`
- `app/dashboard/[workspace_id]/purchase-cancel/page.tsx`
- `app/dashboard/[workspace_id]/purchase-success/page.tsx`
- `app/dashboard/[workspace_id]/team/page.tsx`
- `app/dashboard/[workspace_id]/user-settings/agent-permissions/page.tsx`
- `app/dashboard/[workspace_id]/user-settings/api-key/page.tsx`
- `app/dashboard/[workspace_id]/user-settings/appearance/page.tsx`
- `app/dashboard/[workspace_id]/user-settings/community-prompts/page.tsx`
- `app/dashboard/[workspace_id]/user-settings/desktop/page.tsx`
- `app/dashboard/[workspace_id]/user-settings/hotkeys/page.tsx`
- `app/dashboard/[workspace_id]/user-settings/layout.tsx`
- `app/dashboard/[workspace_id]/user-settings/messaging-channels/page.tsx`
- `app/dashboard/[workspace_id]/user-settings/page.tsx`
- `app/dashboard/[workspace_id]/user-settings/profile/page.tsx`
- `app/dashboard/[workspace_id]/user-settings/prompts/page.tsx`
- `app/dashboard/[workspace_id]/user-settings/purchases/page.tsx`
- `app/dashboard/[workspace_id]/workspace-settings/general/page.tsx`
- `app/dashboard/[workspace_id]/workspace-settings/layout.tsx`
- `app/dashboard/[workspace_id]/workspace-settings/models/page.tsx`
- `app/dashboard/[workspace_id]/workspace-settings/page.tsx`
- `app/dashboard/[workspace_id]/workspace-settings/prompts/page.tsx`
- `app/dashboard/[workspace_id]/workspace-settings/public-links/page.tsx`
- `app/dashboard/[workspace_id]/workspace-settings/team-roles/page.tsx`
- `app/dashboard/error.tsx`
- `app/dashboard/layout.tsx`
- `app/dashboard/loading.tsx`
- `app/dashboard/page.tsx`
- `app/desktop/login/layout.tsx`
- `app/desktop/login/page.tsx`
- `app/desktop/permissions/page.tsx`
- `app/invite/[invite_code]/page.tsx`
- `app/public/[token]/page.tsx`

## API routes

- `app/api/v1/[...path]/route.ts` – proxy mọi request tới backend.
- `app/api/zero/mutate/route.ts` và `app/api/zero/query/route.ts` – Zero sync endpoints.
- `app/api/contact/route.ts`, `app/api/search/route.ts` – liên hệ và search.
- `app/auth/[...path]/route.ts`, `app/verify-token/route.ts` – auth proxy.

## Thư mục components chính

- `ads/` — 3 file
- `connectors/` — 2 file
- `ui/` — 30 file
- `settings/` — 8 file
- `assistant-ui/` — 24 file
- `public-chat/` — 4 file
- `contact/` — 1 file
- `citation-panel/` — 1 file
- `homepage/` — 19 file
- `chat/` — 1 file
- `auth/` — 1 file
- `layout/` — 1 file
- `providers/` — 9 file
- `agent-action-log/` — 3 file
- `connectors-marketing/` — 5 file
- `announcements/` — 5 file
- `desktop/` — 2 file
- `mcp/` — 2 file
- `shared/` — 1 file
- `report-panel/` — 2 file
- `theme/` — 2 file
- `new-chat/` — 9 file
- `icons/` — 0 file
- `citations/` — 1 file
- `editor-panel/` — 2 file
- `sources/` — 3 file
- `public-chat-snapshots/` — 4 file
- `marketing/` — 1 file
- `tool-ui/` — 8 file
- `chat-comments/` — 0 file
- `documents/` — 9 file
- `seo/` — 2 file
- `free-chat/` — 9 file
- `prompt-kit/` — 2 file
- `pricing/` — 1 file
- `editor/` — 6 file

## State management

- **Jotai:** `atoms/` chứa global atoms.
- **Tanstack Query:** `hooks/` chứa query hooks.
- **Zustand:** một số store cục bộ.
- **React Context:** `contexts/` cho providers lớn.

## UI/Design system

- Tailwind CSS v4 với cấu hình `tailwind.config.js`.
- Radix UI primitives (`@radix-ui/react-*`).
- `class-variance-authority` + `tailwind-merge` + `cn()` utility.
- `lucide-react`, `@tabler/icons-react` cho icons.
- `geist` font.

---

_Tài liệu được tạo bởi BMAD Method `document-project` workflow_
