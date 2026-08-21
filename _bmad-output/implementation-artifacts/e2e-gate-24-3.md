---
story_key: "24-3"
epic: "epic-24"
story: "24.3"
title: "E2E Gate — Multi-Seat Team CRM Pipeline & Shared Workspace Credit Pooling"
date: "2026-08-21"
---

# Story 24.3 Web E2E Gate

## Scope

Verify that the `nowing_web` Playwright E2E suite covers the new Kanban pipeline / shared-credit features and that the UI handles the new backend response shapes (OCC 409, credit/spend-cap errors, auth expiry) without crashing.

## Local stack used for the run

| Service | How it was started | Port / endpoint |
|---|---|---|
| Postgres + pgvector | `docker compose -f docker/docker-compose.deps-only.yml up -d db redis` | `localhost:5434` |
| Redis | same as above | `localhost:6380` |
| zero-cache | `docker compose ... up -d zero-cache` | `http://localhost:4848` |
| Backend (E2E entrypoint) | `cd nowing_backend && DATABASE_URL=... uv run python tests/e2e/run_backend.py` | `http://localhost:8000` |
| Frontend | `cd nowing_web && NEXT_PUBLIC_FASTAPI_BACKEND_URL=http://localhost:8000 ... pnpm exec next dev` | `http://localhost:3000` |

Migrations were applied with `uv run alembic upgrade head` against the test database.

## Tests executed

```bash
cd nowing_web
pnpm tsc --noEmit
pnpm exec biome check components/leads/pipeline/ tests/zero/kanban-multicontext-sync.spec.ts
PLAYWRIGHT_NO_WEB_SERVER=1 \
  NEXT_PUBLIC_FASTAPI_BACKEND_URL=http://localhost:8000 \
  NOWING_BACKEND_INTERNAL_URL=http://localhost:8000 \
  NEXT_PUBLIC_ZERO_CACHE_URL=http://localhost:4848 \
  AUTH_TYPE=LOCAL \
  pnpm exec playwright test tests/zero/kanban-multicontext-sync.spec.ts
```

### Results

| Test | File | Status | Notes |
|---|---|---|---|
| Kanban multi-context / OCC | `nowing_web/tests/zero/kanban-multicontext-sync.spec.ts` | **PASS** (2/2) | Green, but does not actually trigger or assert the 409 conflict path. |

`pnpm tsc --noEmit` passed.
`biome check` on the test + component reported two `noUnusedVariables` warnings:

- `leadCardB` is declared but never used.
- `conflictToast` is declared but never used.

## Relevant test inventory

### In `nowing_web/tests/zero/`

- `kanban-multicontext-sync.spec.ts` — the only Zero / Kanban spec; tagged for Story 24.3.

### In `nowing_web/tests/leads/`

No Playwright test in `tests/leads/` directly covers the Kanban pipeline, round-robin assignment, or the shared workspace credit / spend-cap flow. The closest are:

- `lead-orchestrator.spec.ts` — navigates `/leads` and the chat composer, but is for Story 21.15.
- `lead-clipper-multitab.spec.ts` — clipper UI, not pipeline/credit.
- `two-tier-phone-unlock.spec.ts` / `phone-waterfall-and-contact-data.spec.ts` — exercise credit costs for phone unlock, not the per-seat spend cap or shared credit pool.

### In `nowing_web/tests/usage/`

- `usage-dashboard.spec.ts` and `usage-pricing-ledger.spec.ts` are fully `test.skip`'d and pre-date the 24.3 shared credit model. They do not assert the per-seat `monthly_spend_cap_micros` / `monthly_spent_micros` fields.

### In `nowing_web/tests/workspace-settings/`

No spec for the `/dashboard/{workspace_id}/team` page or `MemberSpendCapDialog`.

## Coverage & robustness review

### 1. Kanban board (`LeadKanbanBoard.tsx`)

The component is now implemented with `@dnd-kit/core` and `data-testid` selectors (`kanban-column-{slug}`, `lead-card-{id}`), matching the E2E locators.

**Strengths**

- `useQuery` pulls live stage/lead updates through Zero-cache.
- Drag transitions call `leadPipelineApiService.transitionStage` with `expectedVersion`.
- On a non-2xx response, the card is rolled back to `previousStageId / previousStatus`.
- A visible conflict notice is shown for 409s.

**Weaknesses**

- The 409 body merge logic in `components/leads/pipeline/LeadKanbanBoard.tsx` (lines 415–432) looks for `err.data.current_version` and `err.data.current_stage_id`, but the backend now returns the structured `NowingError` envelope:

  ```json
  {
    "error": {
      "code": "CONFLICT",
      "message": "Lead was modified by another member (DB version: 1, expected: 999).",
      "status": 409,
      "request_id": "...",
      "timestamp": "...",
      "report_url": "..."
    },
    "detail": {
      "error_code": "concurrency_conflict",
      "message": "...",
      "current_version": 1,
      "current_stage_id": "..."
    }
  }
  ```

  The current version/stage are nested under `detail`, not at the top level of `data`. Therefore `data?.current_version` is `undefined` and the board falls back to the stale local rollback instead of merging the server-side current version. This was confirmed with a manual `PATCH /api/v1/workspaces/{id}/leads/{lead_id}/stage` call using an out-of-range `expected_version`.
- `loadData` swallows errors (`console.error` only), so an auth 401 or a network failure leaves the board in a blank/empty state rather than redirecting or showing a toast.

### 2. `kanban-multicontext-sync.spec.ts`

- **Does not exercise the second user / conflict path.** It declares `leadCardB` and `conflictToast` but never performs the User B drag or asserts the conflict toast.
- **Auth model is fragile.** The test uses `browser.newContext()` for both users, which does not inherit the `chromium` project's `storageState`. The spec happened to pass in this run, but in a clean environment both contexts could be unauthenticated and the assertions would fail. The standard pattern is to use the `context` fixture (or pass `storageState`) for authenticated sessions.
- **Lead id fallback is misleading.** `leadId` defaults to `test-lead-${Date.now()}` if the clip API call fails; the test would then attempt to locate a non-existent card. Better to fail fast with `expect(leadCreateRes.ok()).toBeTruthy()`.
- **Does not assert API response handling.** No checks for 401 redirect, 403 access-denied, 402 credit/spend-cap error, or structured `NowingError` toasts.
- **Timeline assertion is shallow.** The drawer visibility is checked, but the chronological order or presence of `stage_changed` / `assign` activity types is not asserted.

### 3. Shared workspace credit / spend cap UI

- `components/team/MemberSpendCapDialog.tsx` lets an owner set `monthly_spend_cap_micros`, `lead_capacity`, and `is_accepting_leads`.
- `handleSave` catches errors with a generic `toast.error("Cập nhật thất bại")` and `console.error`; it does not surface the structured `NowingError` code/message or handle 403/409/422 specifically.
- `app/dashboard/[workspace_id]/team/team-content.tsx` lists members and opens the dialog, but there is no Playwright journey that exercises this flow.
- There is no E2E spec for the 402 / `SpendCapExceededError` path, nor for the `getMySpendStatus` endpoint used by billable operations.

### 4. Lead detail drawer (`LeadDetailFlyoutDrawer.tsx`)

- Fetches activities with `leadPipelineApiService.listActivities` and catches errors by setting `activities([])`. This silently hides failures rather than showing an error state, which is a regression risk if the `/activities` response shape changes.

## Verdict

**Conditional Pass (Yellow).**

The single relevant Playwright spec is green and the happy-path Kanban + timeline drawer works end-to-end with a real backend and Zero-cache. However:

1. The 409 OCC conflict path is not actually exercised by the E2E test and the board does not merge the server-provided `current_version`/`current_stage_id` correctly because it expects them at the top of `err.data` while the backend places them under `err.data.detail`.
2. There is no Playwright coverage for the shared workspace credit / per-seat spend cap UI or API error responses.
3. The test uses unauthenticated `browser.newContext()` and has unused variables, making it fragile.

## Required follow-ups before release

1. **Fix `LeadKanbanBoard` 409 body merge** — read `err.data?.detail?.current_version` / `current_stage_id` (and fall back to `err.data?.current_version` for backward compatibility), then add a unit/E2E assertion that the card snaps to the server value after a 409.
2. **Harden `kanban-multicontext-sync.spec.ts`** — remove the unused `leadCardB` and `conflictToast`; perform the second-user drag from a stale state; assert the conflict notice and the final card position; use the `chromium` project `storageState` or explicit `context.addCookies` for both user contexts.
3. **Add workspace credit / spend cap E2E** — create `tests/team/workspace-credit-spend-cap.spec.ts` or `tests/workspace-settings/member-spend-cap.spec.ts` that opens the team page, edits a member's spend cap, and asserts the correct `monthly_spend_cap_micros` is persisted and that a 403/422/402 is handled without a crash.
4. **Add error-state tests** for auth expiry (401 → `/login`), access denied (403), and credit/spend-cap exhaustion (402) on the pipeline page.
5. Re-run `pnpm tsc --noEmit`, `pnpm exec biome check`, and the full `tests/zero/` and `tests/leads/` suites after the above changes.
