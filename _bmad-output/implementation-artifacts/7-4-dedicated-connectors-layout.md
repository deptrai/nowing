---
baseline_commit: 25ba542c2a3dec95b0a4020da8c129242ba748e2
baseline_branch: develop
story_key: 7-4-dedicated-connectors-layout
status: review
---

# Story 7.4: Dedicated Connectors Layout (replace connector modal with a full-page dashboard)

**Status:** review
**Epic:** 7 — Integrations: Native + MCP
**Priority:** HIGH
**Requirements:** FR-25, FR-7, FR-8
**Architecture:** AD-19

## Story

As a user managing many connectors,
I want a dedicated connectors dashboard page (master-detail: rail of connected connectors + shared detail pane),
So that I can see live health (syncing/failed), manage accounts, and connect new integrations in one place instead of a modal.

## Context

### Upstream reference

SurfSense PR #1624 (`MODSetter/SurfSense#1624`, merged 2026-07-23) replaced the connector modal with a dedicated connectors layout. Key parts and files:

- **Dedicated route** (`surfsense_web/app/(workspace)/[workspace_id]/connectors/`)
  - `page.tsx`: the `/connectors` dashboard page inside the workspace panel.
  - OAuth callback route alongside it (the Nowing equivalent `app/dashboard/[workspace_id]/connectors/callback/` already exists).

- **Master-detail layout** (`surfsense_web/components/connectors/`)
  - Sub-rail listing connected connectors with **live health**: syncing spinner, failed `TriangleAlert`, and account count.
  - Shared detail pane that reuses the existing connect / edit / indexing / accounts / YouTube-flow views (extracted from the old modal into pane-level components).
  - Overview detail pane (default selection): full-width search bar + flat catalog of connector cards.

- **Catalog flattening**
  - Removed the connector category taxonomy (Knowledge Base / Tools & Live) in favor of a **single flat catalog** of connector cards.
  - Renamed the concept to **"Integrations"** in docs/UX copy.

- **Grouping helper** (`lib/connectors/group-connectors-by-type.ts`)
  - `groupConnectorsByType()` shared by both the rail and the composer "+" add-menu (labeled "Your connectors").

- **Composer add-menu rework**
  - Desktop: "+" opens an "MCP Connectors" submenu (flat root list; submenus replace in place).
  - Mobile: single drill-in vaul drawer (flat root list, submenus replace in place with a back button).

- **Deep-link / manage view**
  - Tapping a connected connector deep-links into the manage view via `importConnectorRequestAtom` (routes by account count: none → OAuth connect, one → edit, many → accounts list) — the existing atom in Nowing.
  - `LiveConnectorConnectedCard` fallback manage view for live non-MCP connectors (native/Composio Gmail & Calendar).

- **Sidebar cleanup**
  - Google Drive / OneDrive / Dropbox moved out of the Documents sidebar "Import" menu into the connector catalog.

- **Deprecations** (flagged, hidden unless connected): legacy connectors — Discord, Teams, Luma, Tavily/SearXNG/Linkup/Baidu search APIs, YouTube/web/Elasticsearch crawlers.

### Nowing current state

- **No `/connectors` route yet.** `nowing_web/app/dashboard/[workspace_id]/connectors/` contains only `callback/` (OAuth callback). The dashboard shell (`app/dashboard/[workspace_id]/layout.tsx` / shell layout) has no connectors page entry.
- **Connector UI is modal-based today:**
  - `nowing_web/components/assistant-ui/connector-popup.tsx` + `connector-popup/hooks/use-connector-dialog.ts` — the modal; driven by `connectorDialogOpenAtom` and `importConnectorRequestAtom` (`nowing_web/atoms/connector-dialog/connector-dialog.atoms.ts`).
  - `connectorDialogOpenAtom` set from `components/assistant-ui/thread.tsx` (lines 291, 1100) and `connector-popup.tsx` (line 108).
  - `importConnectorRequestAtom` consumed by `useConnectorDialog` and set by `components/layout/ui/sidebar/DocumentsSidebar.tsx` (lines 22, 256) — the "Import" menu (Google Drive / Composio Drive / OneDrive / Dropbox) is here today, matching upstream's pre-PR state.
  - `connector-popup/hooks/` already has the connect/edit/indexing/accounts view logic to extract into pane-level components.
- **Connector data query exists:** `nowing_web/atoms/connectors/connector-query.atoms.ts` — `connectorsAtom` via `atomWithQuery` + `connectorsApiService.getConnectors(workspaceId)`, `cacheKeys.connectors.all(workspaceId)`, 5-min staleTime.
- **Settings panel exists:** `nowing_web/components/settings/model-connections/model-provider-connections-panel.tsx`, rendered by `components/settings/model-connections-settings.tsx` (line 150) and `app/dashboard/[workspace_id]/onboard/page.tsx` — the upstream PR's detail pane reuses this family of views; verify which views it holds (connect/edit/accounts) and extract what the pane needs.
- **Icons:** `nowing_web/components/icons/providers/*.svg` (e.g. `gemini.svg`); the epics notes the MCP icon uses `mask: currentColor` — verify the existing MCP icon (likely in `components/icons/providers/` or a lucide-style custom) before adding a new one.
- **No** `groupConnectorsByType`, `ConnectorTypeRow`, `useConnectorRows`, `LiveConnectorConnectedCard`, or flat catalog components yet (confirmed by glob).

### Gaps to close for this story

1. Dedicated `/connectors` route + shell entry (nav link in the workspace dashboard sidebar) — does not exist.
2. Master-detail layout with health rail (syncing spinner / failed TriangleAlert / account count) and shared detail pane; reuse the existing connector-popup view logic rather than duplicating it.
3. Flat catalog (no category taxonomy) + full-width search bar; "Integrations" naming.
4. `groupConnectorsByType` shared helper; composer "+" add-menu rework (desktop MCP submenu, mobile drill-in vaul drawer) — verify Nowing's composer add-menu current structure.
5. Deep-link manage view via `importConnectorRequestAtom`; `LiveConnectorConnectedCard` fallback for live non-MCP connectors.
6. DocumentsSidebar "Import" menu entries (Drive/OneDrive/Dropbox) moved into the catalog.
7. MCP icon `mask: currentColor` (per epics AC) — verify against the existing icon set.

## Acceptance Criteria

1. **Dedicated page**
   - **Given** I navigate to `/dashboard/{workspace_id}/connectors`, **Then** a full-page connectors dashboard renders inside the workspace shell with a sub-rail of connected connectors and a default Overview detail pane.

2. **Live health**
   - **Given** a connector is syncing or failed, **When** I open the connectors page, **Then** the rail shows a syncing spinner or failed `TriangleAlert` respectively, plus the account count, and these reflect live state without a manual refresh.

3. **Flat catalog**
   - **Given** I open the Overview pane, **Then** I see a full-width search bar and a single flat catalog of connector cards (no Knowledge Base / Tools category split), with connectors grouped by type only for display ordering.

4. **Manage via deep-link**
   - **Given** I tap a connected connector in the rail, **When** it has no accounts, **Then** it opens OAuth connect; **Given** one account, **Then** the edit view; **Given** many, **Then** the accounts list — routed by account count through `importConnectorRequestAtom` mode `auto`.

5. **Composer add-menu**
   - **Given** the composer "+" menu, **When** on desktop, **Then** it shows an "MCP Connectors" submenu; **When** on mobile, **Then** a single drill-in vaul drawer with submenus replacing in place and a back button.

6. **Legacy cleanup**
   - **Given** the new layout, **Then** legacy connectors (Discord, Teams, Luma, search API connectors, YouTube/web/Elasticsearch crawlers) are hidden unless connected, and Drive/OneDrive/Dropbox entries are removed from the Documents sidebar Import menu and surfaced in the connector catalog instead.

## Tasks / Subtasks

### Route + shell

- [ ] Create `nowing_web/app/dashboard/[workspace_id]/connectors/page.tsx` — server/page entry rendering the connectors dashboard inside the workspace layout.
- [ ] Add a nav entry (e.g. "Connectors"/"Integrations") to the workspace sidebar (`nowing_web/components/layout/ui/sidebar/` — verify the dashboard navigation structure) pointing at `/dashboard/{workspace_id}/connectors`.

### Layout + components

- [ ] Create `nowing_web/components/connectors/`
  - [ ] `connectors-page.tsx` — master-detail layout container; selected connector id state.
  - [ ] `connector-rail.tsx` — sub-rail: connected connectors with live health (syncing spinner, failed `TriangleAlert`, account count), sourced from `connectorsAtom`; selection highlight.
  - [ ] `connector-detail-pane.tsx` — shared detail pane that renders the pane-level view for the selected connector (connect/edit/indexing/accounts/YouTube flow); reuses the view logic extracted from `connector-popup/hooks/`.
  - [ ] `overview-pane.tsx` — default pane: full-width search bar + flat connector card catalog.
  - [ ] `connector-card.tsx` — flat catalog card (icon, name, description, connect/manage action, hidden-if-deprecated).
- [ ] Extract the connect/edit/indexing/accounts view logic from `nowing_web/components/assistant-ui/connector-popup/` into pane-level components the detail pane reuses (keep the popup working if still reachable elsewhere, or rewire its consumers to the page).

### Grouping + catalog

- [ ] Create `nowing_web/lib/connectors/group-connectors-by-type.ts` — `groupConnectorsByType(connectors)` shared by rail and composer add-menu.
- [ ] Build the flat catalog model from `connectorsAtom` data (verify `connectorsApiService.getConnectors` payload shape: connector type, display name, icon, accounts, health/status fields).

### Composer add-menu

- [ ] Rework the composer "+" add-menu (`nowing_web/components/assistant-ui/` — find the composer trigger):
  - [ ] Desktop: "MCP Connectors" submenu (flat root list; submenus replace in place).
  - [ ] Mobile: single drill-in vaul drawer (flat root list; submenus replace in place with back button).

### Deep-link / manage

- [ ] Wire rail taps to `importConnectorRequestAtom` (mode `auto`) so the detail pane routes by account count (none → OAuth, one → edit, many → accounts).
- [ ] Add `LiveConnectorConnectedCard`-equivalent fallback manage view for live non-MCP connectors (native/Composio Gmail & Calendar) in the detail pane.

### Cleanup + icons

- [ ] Remove Google Drive / OneDrive / Dropbox entries from `DocumentsSidebar.tsx` "Import" menu (lines ~22, ~256); they are surfaced via the connector catalog instead.
- [ ] Verify/adjust MCP icon so it uses `mask: currentColor` (check `nowing_web/components/icons/providers/`); add any missing connector icons.
- [ ] Update UX copy to "Integrations" where the connector concept is labeled (docs/UI strings; verify `messages/en.json` keys if copy lives there).

### Tests

- [ ] Unit test `groupConnectorsByType` (grouping, empty list, deprecated-hidden-if-not-connected).
- [ ] Component/integration test for the rail health states (syncing vs failed vs connected) using mocked `connectorsAtom` data.
- [ ] Navigation test: `/dashboard/{workspace_id}/connectors` renders page + rail + overview; tapping a connector switches detail pane by account-count routing.

## Dev Notes

- **The page is inside the workspace shell** — it must reuse the existing dashboard layout/nav, not create a separate top-level route.
- **Reuse, don't rewrite.** The connector-popup hooks (`useConnectorDialog`, connect/edit/accounts logic) and `connectorsAtom` are the data source; extract pane-level components rather than re-implementing connect flows. If the popup is fully replaced, remove its consumers from `thread.tsx` (lines 291, 1100) and rewire to the page; keep `importConnectorRequestAtom` semantics (it is the deep-link contract).
- **Health state** comes from the connector list payload — verify what `getConnectors` returns (status field: syncing/failed/connected) and surface it in the rail; 5-min staleTime means health is near-live, matching upstream behavior.
- **Flat catalog, no taxonomy.** No Knowledge Base / Tools & Live split — the epics requires a single flat catalog; grouping is only for rail/display ordering via `groupConnectorsByType`.
- **Vaul drawer is the mobile pattern — already in the codebase.** `nowing_web/components/ui/drawer.tsx` is the existing vaul-based drawer primitive (already used by `assistant-ui/thread.tsx` and others). Build the mobile drill-in drawer on it; do not add a new dependency.
- **Deprecated connectors** are hidden unless connected — flag them in the catalog model with the connect state, don't delete their code paths yet (accounted legacy connectors must still render manage views).
- **MCP icon mask:** the epics AC says the MCP icon uses `mask: currentColor` — verify the existing `components/icons/providers/` set and align the icon style (mask vs colored) so the rail and catalog render consistently.

## Verification

- [ ] Frontend typecheck and lint:
  ```bash
  cd nowing_web
  pnpm tsc --noEmit
  pnpm exec biome check --max-diagnostics=500 \
    app/dashboard/[workspace_id]/connectors/page.tsx \
    components/connectors \
    lib/connectors/group-connectors-by-type.ts \
    components/assistant-ui/thread.tsx \
    components/layout/ui/sidebar/DocumentsSidebar.tsx
  ```
- [ ] Tests (as available):
  ```bash
  cd nowing_web
  # run the test runner configured in package.json (vitest/playwright) for the new tests
  ```
- [ ] Manual smoke:
  - `/dashboard/{workspace_id}/connectors` renders rail + Overview pane with search bar.
  - Connected connector tap → manage view routed by account count (0/1/many).
  - Syncing/failed connector shows spinner/alert in rail.
  - Composer "+" → MCP Connectors submenu (desktop) / drill-in drawer (mobile).
  - Documents sidebar Import menu no longer lists Drive/OneDrive/Dropbox.
- [ ] Playwright (if `test:e2e` configured): visit connectors page as logged-in user, assert no console `TransformFailed 401` and page renders.

## Implementation Notes (2026-08-05)

MVP delivered in this pass:
- Dedicated `/dashboard/{workspace_id}/connectors` route, master-detail page, rail, overview catalog, and placeholder detail pane.
- `groupConnectorsByType` helper with `tsx` tests.
- Sidebar "Integrations" nav link.
- Connector modal hidden on the connectors route so the page owns `importConnectorRequestAtom` selection without a conflicting popup.

## Implementation Notes (2026-08-08 — Pass 2)

Completed deferred TODOs:
- **Deep-link manage view routing**: `ConnectorDetailPane` now reuses `useConnectorDialog` hook to render connect/edit/accounts views inline (no dialog). Page uses local `selectedType` state independent of `importConnectorRequestAtom` so the pane stays mounted during hook processing.
- **Composer "+" add-menu rework**: Both desktop and mobile "MCP Connectors" replaced with `DropdownMenuSub` showing flat connector list (via `groupConnectorsByType`) + "Browse all integrations" link to `/connectors` page.
- **DocumentsSidebar Import menu cleanup**: Removed Google Drive / OneDrive / Dropbox entries. Import menu now only offers "Upload Files" and "Watch Local Folder" (desktop). Cloud-drive connectors are managed via the connector catalog.

## References

- Upstream PR: `MODSetter/SurfSense#1624`
- `nowing_web/app/dashboard/[workspace_id]/connectors/callback/` — existing OAuth callback route (page route adds alongside)
- `nowing_web/components/assistant-ui/connector-popup.tsx` + `connector-popup/hooks/use-connector-dialog.ts` — modal + view logic to extract
- `nowing_web/atoms/connector-dialog/connector-dialog.atoms.ts` — `connectorDialogOpenAtom`, `importConnectorRequestAtom` (deep-link contract, mode `auto`/`connect`)
- `nowing_web/atoms/connectors/connector-query.atoms.ts` — `connectorsAtom`, `connectorsApiService`, `cacheKeys.connectors.all`
- `nowing_web/components/assistant-ui/thread.tsx` (lines 47, 291, 1100) — popup consumers to rewire
- `nowing_web/components/layout/ui/sidebar/DocumentsSidebar.tsx` (lines 22, 256) — Import menu to trim
- `nowing_web/components/settings/model-connections/model-provider-connections-panel.tsx`, `model-connections-settings.tsx` (line 150) — existing panel views to reuse/extract
- `nowing_web/components/icons/providers/*.svg` — icon set; MCP icon `mask: currentColor` check
- `nowing_web/app/dashboard/[workspace_id]/layout.tsx` / shell layout — workspace shell for the nav entry
- `_bmad-output/planning-artifacts/epics.md` — FR-25, FR-7, FR-8; story 7.4 ACs (flat catalog, MCP icon mask, rail health)
