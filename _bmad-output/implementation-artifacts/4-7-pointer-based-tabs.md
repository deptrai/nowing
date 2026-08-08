---
baseline_commit: 25ba542c2a3dec95b0a4020da8c129242ba748e2
baseline_branch: develop
story_key: 4-7-pointer-based-tabs
status: done
---

# Story 4.7: Pointer-Based Tabs with Live Title Resolution

**Status:** `done`
**Epic:** 4 — UI/UX: Productivity & Collaboration
**Priority:** HIGH
**Requirements:** FR-14
**Architecture:** AD-21 (client tab state pointer-only, local-first, v2 storage key)

## Story

As a user with many open tabs,
I want tabs to store only lightweight pointers (entity + workspace) and resolve titles, visibility, and metadata live,
So that tabs always reflect up-to-date content without stale snapshots, broken navigation, or redundant data.

## Context

### Upstream reference

SurfSense PR #1609 (`MODSetter/SurfSense#1609`, merged 2026-07-22) refactored tabs from full-snapshot storage to pointer-only storage with live react-query resolution. Key parts and files:

- **Pointer state shape** (`lib/atoms/tabs/tabs.atom.ts`, renamed to `pointer-tabs` storage)
  - Tabs store lightweight pointers only: `id`, `type` (`"chat" | "document"`), `entityId` (thread ID or document ID), `workspaceId`.
  - Stored under a **new v2 localStorage key**; the v1 snapshot shape is migrated/dropped, not merged — the refactor intentionally drops snapshot fields (`title`, `visibility`, `has-comments`, URL fragment) from tab sync.
  - Per-device (localStorage, not Zero-synced), same as before.

- **Live resolution hook** (`lib/hooks/use-resolved-tabs.ts` — `useResolvedTabs`)
  - Joins pointer tabs with react-query metadata: `getThreadFull` and `getDocument` REST endpoints.
  - Derives display `title` from live metadata; chat tabs use thread metadata, document tabs use document metadata.
  - Prunes a chat tab only on a **definitive 404** from the thread endpoint — transient/network errors keep the tab.

- **Cache write-through** (`lib/chat/thread-cache.ts`)
  - Rename, visibility, and delete mutations patch the same react-query caches (`setThreadMetadata`, `removeThread`, `setDocumentTitle`) so resolved tabs reflect changes immediately without a refetch.

- **Consumer rewiring**
  - `components/layout/ui/tabs/tab-bar.tsx`: renders from resolved tabs.
  - `components/layout/ui/shell/layout-shell.tsx`: layout shell splits tabbed/untabbed rendering behind a `show-tabs` flag; tab bar only renders when the flag is set; untabbed routes (e.g., new-chat) render the plain main panel.
  - Fallback navigation: for a pointer-only tab with no metadata yet, URLs are derived from `entityId` + `workspaceId` (e.g., `/dashboard/{workspaceId}/chat/{threadId}`).
  - `hooks/use-activate-thread.ts` and new-chat page effects dropped `title`, `visibility`, `hasComments` snapshot args from tab sync calls.

- **Out of scope for this story (already in Nowing or separately tracked)**
  - Per-user workspace creation limit (configurable) — **Story 8-12, already done** (`38b784fbacb1f7f0a05e2cd2259a0d7963b8c6ff`). Do not re-implement.
  - Rename/delete mutations themselves — already exist; only the cache patch points change.
  - UI polish items bundled in the upstream PR (threads loading skeleton, relative timestamps, playground sidebar collapsed cookie, chats-click handler, can-submit gating) are **not** part of this story unless epics explicitly require them.

### Nowing current state

- `nowing_web/atoms/tabs/tabs.atom.ts` — the Nowing `Tab` interface today stores a **full snapshot**: `id`, `type: "chat" | "document"`, `title`, `chatId?`, `chatUrl?`, `visibility?`, `hasComments?`, `documentId?`, `workspaceId?`. `TabsState { tabs, activeTabId }`; persisted via `atomWithStorage` key **`nowing:tabs`** (v1) with `migrateLegacyTabs` (`nowing_web/atoms/tabs/migrate-tabs.ts` + `migrate-tabs.test.ts`) mapping legacy `searchSpaceId` → `workspaceId`.
- `nowing_web/components/layout/ui/tabs/TabBar.tsx` — renders from `tabsAtom` + `activeTabIdAtom`, `closeTabAtom`, `switchTabAtom` (all in `tabs.atom.ts`).
- `nowing_web/components/layout/ui/shell/LayoutShell.tsx` — renders `TabBar` (~line 146); main panel uses `activeTabAtom`, `DocumentTabContent` (`layout/ui/tabs/DocumentTabContent.tsx`).
- **No `useResolvedTabs` anywhere** (confirmed by glob). No pointer shape, no v2 storage key.
- `nowing_web/lib/chat/thread-cache.ts` **exists** and keeps react-query patches fresh (used by rename/visibility/delete flows) — the write-through mechanism is already in place; the upstream PR's changes here are mostly pointer-driven consumers.
- Data layer: react-query + jotai-tanstack-query (`atomWithQuery`/`atomWithMutation`), **no Zero** in nowing_web. `getThreadFull`/`getDocument` REST endpoints exist behind `threadsApiService`/`documentsApiService` (verify exact method names while implementing; the resolver can use existing atomWithQuery conventions from `nowing_web/atoms/connectors/connector-query.atoms.ts`).

### Gaps to close for this story

1. `Tab` must shrink to pointer-only (`id`, `type`, `entityId`, `workspaceId`) with a new v2 storage key; v1 `nowing:tabs` snapshot data must be migrated (entityId = chatId/documentId) rather than lost.
2. `useResolvedTabs` does not exist — create it, joining thread/document metadata from react-query and deriving display titles; handle the loading state (show placeholder/derived title until metadata arrives).
3. Fallback navigation from pointer data (chatId/documentId + workspaceId) when metadata is still loading.
4. Chat tab pruning semantics: only on definitive 404, never on transient errors.
5. All tab consumers (`TabBar`, `LayoutShell` main panel, `DocumentTabContent`, tab-sync calls in `use-activate-thread` and new-chat page) must be rewired to the resolved shape.
6. Tab-bar visibility behind a `show-tabs` flag (untabbed routes render plain main panel) if the current shell does not already branch this way — verify `LayoutShell` behavior.

## Acceptance Criteria

1. **Pointer storage**
   - **Given** I open a chat and a document, **When** tabs are persisted, **Then** each tab stores only `id`, `type`, `entityId`, `workspaceId` under the new v2 storage key, and existing v1 snapshot tabs migrate to the pointer shape without losing the active tab.

2. **Live title resolution**
   - **Given** tabs are open and thread/document metadata is loaded, **When** I rename a thread or a document, **Then** the tab title updates from live metadata without reloading the page and without stale snapshot data.

3. **Fallback navigation**
   - **Given** a pointer tab whose metadata is still loading, **When** I click the tab, **Then** navigation falls back to a URL derived from `entityId` + `workspaceId` (e.g. `/dashboard/{workspaceId}/new-chat/{threadId}` for chat tabs — the actual Nowing route).

4. **Definitive-404 pruning**
   - **Given** a chat tab for a thread, **When** the thread endpoint returns a definitive 404, **Then** the tab is pruned; **Given** a transient network error, **Then** the tab remains.

5. **Consumer consistency**
   - **Given** the refactor, **When** I open the tab bar on a tabbed layout and navigate to a tabless route (new-chat), **Then** the tab bar renders only on tabbed layouts and the plain main panel renders on untabbed ones.

## Tasks / Subtasks

### State shape

- [x] Update `nowing_web/atoms/tabs/tabs.atom.ts`
  - [x] Redefine `Tab` as pointer-only: `{ id, type: "chat" | "document", entityId: string, workspaceId: string }`.
  - [x] Add new storage key (v2), e.g. `nowing:tabs:v2`; keep a migration from the v1 snapshot shape (map `chatId`/`documentId` → `entityId`; drop snapshot fields).
  - [x] Keep `TabsState { tabs, activeTabId }`, `tabsAtom`, `activeTabIdAtom`, `switchTabAtom`, `closeTabAtom` APIs stable so existing consumers compile.
- [x] Update `nowing_web/atoms/tabs/migrate-tabs.ts` + `migrate-tabs.test.ts` for the v1→v2 pointer migration.

### Resolution

- [x] Create `nowing_web/lib/hooks/use-resolved-tabs.ts` (`useResolvedTabs`)
  - [x] For each pointer tab, join metadata via react-query (thread metadata for `chat`, document metadata for `document`).
  - [x] Derive display title; fallback to placeholder or entity-derived label while loading.
  - [x] Prune chat tabs only on definitive 404 (HTTP status from the thread metadata query), never on transient errors.
  - [x] Expose resolved tabs (tab + live title + loading state) for the tab bar and shell.
- [x] Update `nowing_web/lib/chat/thread-cache.ts` — ensure rename/visibility/delete mutations patch the same query keys the resolver reads (verify against `getThreadFull`/`getDocument` keys).

### Consumers

- [x] Update `nowing_web/components/layout/ui/tabs/TabBar.tsx` — render from resolved tabs (`useResolvedTabs`), derive URLs for click/switch via fallback navigation.
- [x] Update `nowing_web/components/layout/ui/shell/LayoutShell.tsx`
  - [x] Branch tabbed vs untabbed behind a `show-tabs` flag (~line 146 `TabBar` render).
  - [x] Main panel resolves the active tab via `useResolvedTabs` instead of reading snapshot fields.
  - [x] `DocumentTabContent.tsx` — resolve document metadata from pointer `entityId`/`workspaceId`.
- [x] Update `nowing_web/hooks/use-activate-thread.ts` and new-chat page — drop `title`/`visibility`/`hasComments` snapshot args from tab-sync calls (entity/workspace pointers only).

### Tests

- [x] `nowing_web/atoms/tabs/__tests__/` (or alongside) — migration test (v1→v2), pointer-only serialization, active-tab preservation.
- [x] `nowing_web/lib/hooks/__tests__/use-resolved-tabs.test.tsx` — live title update on metadata change, fallback title while loading, prune-on-404 vs keep-on-transient-error (mock react-query).
- [x] Run existing test suite for `migrate-tabs.test.ts` and any tab-related component tests.

## Dev Notes

- **This story is the tabs half of upstream PR #1609.** The workspace-creation-limit half is Story 8-12 (done). Do not touch workspace limits, billing, or quota code here.
- **Keep the atom API stable** where cheap (tabsAtom, activeTabIdAtom, switchTabAtom, closeTabAtom) so `TabBar` and `LayoutShell` need only internal rewiring; prefer additive fields (`entityId`) over breaking renames unless the snapshot fields are the actual problem.
- **Migration must not lose the active tab or jump the user's position.** If v1 key exists and v2 doesn't, map `chatId ?? documentId` → `entityId`, `workspaceId`, preserve `activeTabId`, and write v2; consider keeping v1 until first successful write (or drop v1 after migration per upstream — upstream drops it; match upstream).
- **Derive URLs, don't guess.** Fallback URL builders must mirror the actual Nowing route patterns: chat tabs navigate to `/dashboard/{workspaceId}/new-chat/{threadId}` (see `router.push` call sites in `components/assistant-ui/user-message.tsx:104`, `components/public-chat/public-chat-footer.tsx:31`, `components/layout/ui/sidebar/NotificationsDropdown.tsx:199-216`); document tabs use the document route pattern under `/dashboard/{workspaceId}/` (grep existing push calls before writing). Today `chatUrl` is passed into `syncChatTabAtom` by callers (tabs.atom.ts:90) — in the pointer world the URL must be derived inside the consumer from `entityId`/`workspaceId`, not persisted.
- **404 vs transient:** use the react-query error shape (status code from the request), not "any error". Transient network failures must never prune a tab — this is the core UX regression the upstream fixed.
- **react-query conventions:** follow `nowing_web/atoms/connectors/connector-query.atoms.ts` (atomWithQuery + cacheKeys) for the resolver's queries; do not introduce Zero.
- **Do not re-introduce snapshot fields** in storage. `thread-cache.ts` patches are the single source of truth for live titles.

## Verification

- [x] Frontend typecheck and lint:
  ```bash
  cd nowing_web
  pnpm tsc --noEmit
  pnpm exec biome check --max-diagnostics=500 \
    atoms/tabs/tabs.atom.ts \
    atoms/tabs/migrate-tabs.ts \
    atoms/tabs/migrate-tabs.test.ts \
    lib/hooks/use-resolved-tabs.ts \
    lib/chat/thread-cache.ts \
    components/layout/ui/tabs/TabBar.tsx \
    components/layout/ui/shell/LayoutShell.tsx \
    components/layout/ui/tabs/DocumentTabContent.tsx
  ```
- [x] Tests (tab-related):
  ```bash
  cd nowing_web
  pnpm vitest run atoms/tabs lib/hooks/use-resolved-tabs 2>/dev/null || echo "check package.json test script"
  ```
  (Confirm the actual test runner from `package.json` — if none configured, run the nearest available script.)
- [x] Manual smoke: open a chat + a document tab, reload — tabs persist under v2 key with pointers only; rename a thread via UI — tab title updates without refresh; open the new-chat route — tab bar absent; visit a deleted thread — tab prunes on 404.
- [x] Confirm no regressions in `migrate-tabs.test.ts`.

## References

- Upstream PR: `MODSetter/SurfSense#1609` (tabs portion only; workspace-limit portion = Story 8-12)
- `nowing_web/atoms/tabs/tabs.atom.ts` — current snapshot-based `Tab` + storage key `nowing:tabs`
- `nowing_web/atoms/tabs/migrate-tabs.ts` / `migrate-tabs.test.ts`
- `nowing_web/components/layout/ui/tabs/TabBar.tsx`
- `nowing_web/components/layout/ui/shell/LayoutShell.tsx` (~line 146 `TabBar` render)
- `nowing_web/components/layout/ui/tabs/DocumentTabContent.tsx`
- `nowing_web/lib/chat/thread-cache.ts` — cache write-through for rename/visibility/delete
- `nowing_web/atoms/connectors/connector-query.atoms.ts` — atomWithQuery conventions
- `nowing_web/hooks/use-activate-thread.ts` — tab-sync call sites to rewire
- `_bmad-output/implementation-artifacts/8-12-workspace-limits.md` — the sibling half of PR #1609 (done; do not duplicate)

## Code Review Patches

- [x] [Review][Patch] **P1: Missing `use-resolved-tabs.test.tsx`** — Spec requires test file with 404 pruning, transient errors, and live title tests. Hook had zero test coverage. Fix: exported pure functions (`isValidEntityId`, `parseEntityId`, `isNotFoundError`, `getChatUrl`, `getFallbackTitle`, `resolveTab`) and wrote 18 tests covering all spec-required scenarios.
- [x] [Review][Patch] **P2: TabBar unsafe cast `as unknown as ResolvedTab`** — `closeTabAtom` returns `Tab` not `ResolvedTab`. Fix: construct a proper `ResolvedTab` with fallback title/URL/loading/isNotFound fields instead of casting.
