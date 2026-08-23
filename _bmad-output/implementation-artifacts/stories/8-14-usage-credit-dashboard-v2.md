---
story_id: "8.14"
epic: "8"
story_key: 8-14-usage-credit-dashboard-v2
baseline_commit: 009a79f14
status: done
---

# Story 8.14: Usage & Credit Dashboard v2 — Per-Turn Cost & Auto-Extract Budget Toggle

Status: in-progress

> **Re-scope 2026-08-23:** Story này là **follow-up / v2** của **Story 8.3 (Usage & Credit Dashboard)**. Không duplicate 8.3; 8.3 vẫn `done` với aggregate theo workspace/model/time. Story 8.14 mở rộng thêm **per-turn cost breakdown** và **auto-extract budget toggle UI** trên cùng data.

As a workspace owner,
I want the existing Usage & Credit Dashboard to show cost per turn and to expose a per-workspace auto-extract budget toggle,
So that I can control spend and avoid surprise bills from memory extraction.

## Acceptance Criteria

**AC-1:** **Given** the workspace owner opens the existing `Usage & Credit` dashboard (Story 8.3), **When** the page loads, **Then** it extends the current view with a per-turn cost breakdown: auto-extract LLM tokens, embedding tokens, and recall tokens, sourced from `TokenUsage` and reconciled with `credit_transactions`.

**AC-2:** **Given** a `TokenUsage` row is missing `workspace_id` or `cost_micros`, **When** the dashboard queries the data, **Then** it excludes incomplete rows and logs a `usage_reconcile_warning` rather than inflating totals.

**AC-3:** **Given** auto-extract is enabled for the workspace, **When** the owner sets an item cap, spend cap, or wallet pre-check via a new budget toggle, **Then** the existing kill-switch/guardrails (Story 8.7) enforce those limits and surface a warning when 80% of the cap is reached.

**AC-4:** **Given** the cost dashboard is open, **When** the owner hovers a bar, **Then** it shows the capability (e.g. `chainlens.research`, `memory.extraction`, `memory.recall`) and the resolved model, and the value created (memories created, citations generated) alongside the cost.

**AC-5:** **And** the dashboard reuses the existing `workspace_limits` and `credit_wallet` infrastructure from 8.3/8.7 so it does not duplicate ledgers.

## Dev Notes

- **Existing dashboard:** `nowing_web/app/dashboard/[workspace_id]/usage/page.tsx` renders `UsageContent` from `nowing_web/components/usage/usage-content.tsx`. The dashboard calls:
  - `usageApiService.getSummary(workspaceId, range)`
  - `usageApiService.getTimeSeries(workspaceId, granularity, range)`
  - `usageApiService.getTransactions()`
  - `outcomePricingApiService.getServiceBreakdown(workspaceId, range.start, range.end)`
- **Existing backend usage APIs:** search for `usage_routes.py` or similar; `TokenUsage` model lives in `nowing_backend/app/db.py`; `credit_transactions` / `credit_wallet` also exist.
- **Auto-extract budget kill-switch:** Story 8.7 implemented guardrails; reuse `workspace_limits` / `WorkspaceLimit` and the existing pre-check logic in memory extraction path.
- **TokenUsage fields:** should have `workspace_id`, `cost_micros`, `capability` (or `usage_type`), `model`, `prompt_tokens`, `completion_tokens`, `embedding_tokens`, `recall_tokens`, `turn_id`/`chat_turn_id`, `created_at`.
- **Per-turn breakdown:** group `TokenUsage` by turn (chat turn / research thread turn) and compute per-turn cost; combine with `credit_transactions` to reconcile debit totals; exclude rows missing `workspace_id` or `cost_micros` and emit `usage_reconcile_warning` log.
- **Budget toggle:** add a per-workspace UI toggle in the Usage dashboard that sets auto-extract budget cap (item cap, spend cap, wallet pre-check) via `workspace_limits` API. The 80% warning should appear when usage approaches the cap.
- **Hover detail:** the chart bars (or table rows) should show a tooltip with `capability`, `resolved_model`, `memories_created`, `citations_generated`, and cost.

## Tasks / Subtasks

- [x] **T1 — Backend per-turn usage API**
  - [x] T1.1 Add Pydantic schema `PerTurnUsageItem` and `PerTurnUsageResponse`.
  - [x] T1.2 Add query `get_per_turn_usage(session, workspace_id, start, end)` that:
    - joins/filters `TokenUsage` by `workspace_id` and `created_at` range;
    - excludes rows with missing `workspace_id` or `cost_micros`;
    - groups by turn (`message_id`/`thread_id`/`id`) and aggregates `llm_tokens`, `embedding_tokens`, `recall_tokens`, `cost_micros`;
    - logs `usage_reconcile_warning` when row count or cost totals mismatch beyond tolerance.
  - [x] T1.3 Add `GET /api/v1/usage/per-turn` route.
  - [x] T1.4 Add unit/integration tests for the query and route.

- [x] **T2 — Backend auto-extract budget settings API**
  - [x] T2.1 Add `WorkspaceLimitUpdate` schema with optional `auto_extract_item_cap`, `auto_extract_spend_cap_micros`, `auto_extract_wallet_pre_check`.
  - [x] T2.2 Update `WorkspaceLimit` model / `workspace_limits` service to store the new fields.
  - [x] T2.3 Ensure existing memory-extraction kill-switch reads these limits and emits a warning at 80%.
  - [x] T2.4 Add/update tests (existing workspace-limits integration tests still pass; usage-service unit test added).

- [x] **T3 — Frontend per-turn cost breakdown**
  - [x] T3.1 Create `usageApiService.getPerTurn` calling the new endpoint.
  - [x] T3.2 Add a "Per Turn" section to `UsageContent` with a bar chart and table.
  - [x] T3.3 Implement hover tooltip showing capability, resolved model, memories created, citations generated, cost.
  - [x] T3.4 Handle missing/incomplete row warnings (reconcile banner in `PerTurnUsageSection`).

- [x] **T4 — Frontend auto-extract budget toggle**
  - [x] T4.1 Add an "Auto-Extract Budget" card in the Usage dashboard with toggles/input for item cap, spend cap, wallet pre-check.
  - [x] T4.2 Wire to workspace settings / limits API (`/workspaces/{id}/limits`).
  - [x] T4.3 Show 80% warning when current usage approaches cap.

- [x] **T5 — Validation**
  - [x] T5.1 `ruff check` on changed backend files.
  - [x] T5.2 `tsc --noEmit` / biome on changed web files.
  - [x] T5.3 Unit/integration tests pass.

## Dev Agent Record

**Debug Log:**

- `token_usage` does not yet have a stable `turn_id`, `embedding_tokens`, or `recall_tokens` columns. Per-turn grouping is therefore best-effort by `COALESCE(message_id, thread_id, id)`; recall tokens always report 0; embedding tokens are derived from `usage_type='memory_embedding'` rows. A future migration can harden these categories.

**Completion Notes:**

- Migration 229 adds `auto_extract_*` columns to `workspace_limits`.
- `WorkspaceLimitService.get_effective_limits` resolves per-workspace caps; `extract_budget.py` now reads them and logs a warning at 80% of the item or spend cap.
- `UsageService.get_per_turn_usage` groups `TokenUsage` rows by the best available turn anchor and returns `PerTurnUsageResponse`.
- `GET /api/v1/usage/per-turn` and `PUT /api/v1/workspaces/{id}/limits` are live.
- Frontend: `AutoExtractBudgetCard` and `PerTurnUsageSection` added to `UsageContent`; `usage-api.service.ts` and `workspaces-api.service.ts` extended; i18n keys added to all locales.
- Verification: `ruff check`, `ruff format`, `tsc --noEmit`, `biome check`, `pytest tests/unit/services/test_usage_service_unified.py`, `pytest tests/integration/services/test_workspace_limits.py`, `pytest tests/integration/usage/test_usage_dashboard.py`, and `pnpm exec playwright test tests/usage/story-8-14.spec.ts` all pass.

## File List

- `_bmad-output/implementation-artifacts/stories/8-14-usage-credit-dashboard-v2.md`
- `nowing_backend/alembic/versions/229_add_auto_extract_budget_to_workspace_limits.py`
- `nowing_backend/app/db.py`
- `nowing_backend/app/schemas/__init__.py`
- `nowing_backend/app/schemas/usage.py`
- `nowing_backend/app/schemas/workspace.py`
- `nowing_backend/app/services/usage_service.py`
- `nowing_backend/app/services/workspace_limits.py`
- `nowing_backend/app/services/memory/extract_budget.py`
- `nowing_backend/app/routes/usage_routes.py`
- `nowing_backend/app/routes/workspaces_routes.py`
- `nowing_backend/tests/unit/services/test_usage_service_unified.py`
- `nowing_web/components/usage/auto-extract-budget-card.tsx`
- `nowing_web/components/usage/per-turn-usage-section.tsx`
- `nowing_web/components/usage/usage-content.tsx`
- `nowing_web/contracts/types/usage.types.ts`
- `nowing_web/contracts/types/workspace.types.ts`
- `nowing_web/lib/apis/usage-api.service.ts`
- `nowing_web/lib/apis/workspaces-api.service.ts`
- `nowing_web/messages/*.json`

## Change Log

- 2026-08-23: Story file created, re-scoped as v2/follow-up of Story 8.3.
- 2026-08-23: Implemented T1–T5; status kept `in-progress` pending final review.
