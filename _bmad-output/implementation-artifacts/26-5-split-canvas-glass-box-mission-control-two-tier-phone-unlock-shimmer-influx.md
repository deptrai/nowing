---
story_key: "26-5"
epic: "epic-26"
story: "26.5"
title: "Split Canvas Glass Box Mission Control, Two-Tier Phone Unlock & Shimmer Influx"
status: "in-progress"
baseline_commit: "3b1705689"
---

# Story 26.5: Split Canvas Glass Box Mission Control, Two-Tier Phone Unlock & Shimmer Influx

## CRITICAL DESIGN DECISIONS — Resolve Before Dev

1. **Token-velocity source of truth for the Glass Box widget**
   - The DSH worker (`app/tasks/dsh_worker.py`) currently writes progress into `dsh_missions.checkpoint` but does **not** record `TokenUsage` rows and does **not** set `token_usage.run_id`. As of the 26.3 implementation, the worker also does not call `HybridLLMRouter`.
   - **Decision (recommended):** The worker self-reports token counts and cost into `checkpoint.subtasks[].tokens_used`, `tokens_per_second`, and `cost_micros` after each subtask. `MissionControlService.build_control_data` uses these checkpoint values as the primary source. If `token_usage` is later populated (e.g. Story 26.3 / HybridLLMRouter integration), the service can cross-check and fall back to `TokenUsage`.
   - **Fallback if token counts are missing:** The service may also read `Run.cost_micros` from the ChainLens `run_id` stored in the checkpoint. The Glass Box must render `0 tokens/sec` and the available `cost_micros` gracefully instead of failing.

2. **Public checkpoint must be PII-safe and redacted**
   - `dsh_missions.checkpoint` is an internal JSONB column (not in `zero_publication`). The public `GET .../dsh/missions/{id}/control` endpoint must return a **redacted** view of the checkpoint: `subtasks` (id, title, status, phase, reasoning_content, tokens_used, tokens_per_second, run_id, cost_micros, started_at, completed_at) and aggregate token velocity.
   - It must **not** expose `checkpoint.sources`, `checkpoint.leads`, `payload.query`, or any subtask output that may contain phone/email/PII.

3. **Two-Tier Unlock "undo" semantics**
   - The 5-second undo toast is a UI affordance for an **accidental unlock**. Clicking "Hoàn tác" calls a new backend endpoint that re-locks the contact (`is_unlocked = FALSE`) and refunds 1.5 credits.
   - To limit abuse, the refund is only accepted when an original `BillingEvent.event_type='contact_unlock'` exists for the contact and the request arrives within a configurable window (default 60 seconds; the UI toast shows for 5 seconds).
   - **Architecture compliance note:** AD-110 Rule 4 caps "Auto-Refund SLA 24h" at 15% of total unlocked leads per billing cycle. The 5s accidental relock is an automatic refund, so it must also respect an anti-fraud budget. Implement `BillingEventService.record_contact_relock` with an accidental-relock budget (configurable, default 15% of unlocked leads per billing cycle, tracked separately from the opt-out cap) and record a `contact_relock` negative `BillingEvent`. Because the relock window is only 60 seconds, normal accidental-undo usage will rarely hit the cap.

4. **PII Opt-Out UI is intentionally OUT OF SCOPE for 26.5**
   - Story 26.4 implemented the backend `POST /api/v1/workspaces/{workspace_id}/pii-opt-out` endpoint, but there is still no UI trigger for Right-to-be-Forgotten.
   - **Decision:** Keep 26.5 focused on Two-Tier Phone Unlock and Glass Box. The PII opt-out / refund UI is a separate small follow-up story `26.5a` and is not implemented under 26.5. The existing `DncManagementModal` only manages the DNC list; it does **not** call `pii-opt-out`.

5. **Zero-Cache `leads` does not publish phone / is_unlocked**
   - `zero_publication.py` publishes only non-PII lead columns (`id`, `workspace_id`, `company_name`, `domain`, `fit_score`, `status`, etc.) and explicitly excludes `phone`, `email`, `name`, `value_hmac`, and `is_unlocked` per AD-104.
   - **Decision:** The `NowingLeadMatrix` may subscribe to `leads` for live row presence, but it must refetch `LeadRead` via REST to get the masked phone and `is_unlocked` state. New rows from Zero render with a "Đang giải mã SĐT..." placeholder until the next REST refresh.

6. **`verified_contacts` is not in `zero_publication`**
   - Live `is_unlocked` flips (unlock, relock, or opt-out) cannot be pushed to the frontend via Zero. The UI must optimistically update local lead state and periodically refetch `LeadRead`, or trigger a refetch after each unlock/relock. Document this limitation explicitly.

7. **Two-Tier unlock must not break Zalo / dial actions**
   - `ZaloOutreachButton` and the `tel:` link in `LeadDetailFlyoutDrawer` currently render using `lead.phone` even when masked. If `is_unlocked=false`, these actions must be disabled/hidden to prevent dialling a masked placeholder.

---

## Story

As a Nowing sales user working in the Split Canvas,
I want a live Glass Box Mission Control widget that shows the 4-stage DSH progress, a two-tier phone unlock experience with a session-level "1-Click Fast Unlock" toggle, and shimmering real-time lead rows,
So that I can track autonomous AI reasoning transparently, unlock phone numbers with minimal friction, and immediately spot when new leads land in the matrix.

---

## Acceptance Criteria

### AC-1 — Glass Box Mission Control Widget

- **Given** a DSH mission is active (`status` in `pending` or `running`) for the current workspace,
- **When** the user is in the Split Canvas / Lead Intelligence view,
- **Then** a compact, collapsible **Glass Box Mission Control Widget** appears in the right panel (above or beside the Lead Matrix) and shows:
  1. A 4-stage progressive stepper: **Crawl -> Reasoning -> Extraction -> Ingest**.
  2. The current active stage derived from `dsh_missions.phase`.
  3. A progress bar driven by `dsh_missions.progress_percent`.
  4. Token velocity (tokens/sec, total tokens, cost in credits) and a "token burn" mini sparkline. **If token counts are not available in the checkpoint, the widget displays `0 tokens/sec` and the available `cost_micros` gracefully.**
  5. A collapsible drawer of CoT / reasoning trace from the redacted `checkpoint.subtasks[].reasoning_content`.
  6. Mission status, elapsed time, and a one-click "cancel" affordance (optional UI-only for 26.5; actual cancel can be a no-op or call DELETE in a follow-up).
  7. The widget updates in real time via Zero-Cache `dsh_missions` subscription; token-velocity numbers update when the mission checkpoint changes.

### AC-2 — DSH mission list and public control endpoint

- **Given** an authenticated workspace member,
- **When** they call `GET /api/v1/workspaces/{workspace_id}/dsh/missions?status=running,pending,success,error&hours=24`,
- **Then** the backend returns a paginated list of `DshMissionResponse` filtered by workspace and status within the requested time window.

- **Given** a mission id,
- **When** they call `GET /api/v1/workspaces/{workspace_id}/dsh/missions/{mission_id}/control`,
- **Then** the backend returns a `DshMissionControlResponse` containing:
  - `id`, `workspace_id`, `mission_type`, `status`, `phase`, `progress_percent`, `current_subtask_id`.
  - `token_velocity`: `{ tokens_total, tokens_per_second, cost_micros, cost_credits }`. `tokens_total`/`tokens_per_second` are read from the redacted `checkpoint.subtasks[]` first, then optionally reconciled with `token_usage` or `Run.cost_micros`. Missing counts default to `0`.
  - `subtasks`: array of `{ id, title, status, phase, reasoning_content, tokens_used, tokens_per_second, run_id, cost_micros, started_at, completed_at }`.
  - The checkpoint is redacted; no PII, no raw `payload.query`, no `sources` or `leads` arrays are exposed.

### AC-3 — Zero-Cache integration for DSH missions and shimmer influx

- **Given** `dsh_missions` is in the backend `zero_publication` (already true),
- **When** the frontend adds `dshMissionsTable` to `zero/schema/index.ts` and `zero/queries/dsh.ts`,
- **Then** the Glass Box widget subscribes to the active mission in the current workspace and re-renders within 10ms of a checkpoint/phase change.

- **Given** a mission is in `running` status and the lead matrix is visible,
- **When** the worker reaches the `ingestion` phase,
- **Then** the `NowingLeadMatrix` renders 1-3 shimmer skeleton rows at the bottom of the table and highlights newly-arrived rows with a short pulse/shimmer animation that fades after 800ms.
- **And** new rows are discovered either via the existing `useLeads` REST refresh or a Zero `leads` subscription (the `leads` table is already published without PII). **New rows from Zero only carry non-PII fields; the phone cell shows a "Đang giải mã SĐT..." mint placeholder until the next REST refresh provides `LeadRead.phone`.**

### AC-4 — Two-Tier Smart Confirmation Popover and 1-Click Fast Unlock

- **Given** a lead with a masked phone number (`0908 *** 456`) and `is_unlocked = FALSE`,
- **When** the user clicks the phone pill for the **first time in the current session** (or when fast unlock is disabled),
- **Then** a **Smart Confirmation Popover** renders next to the pill with:
  - The masked phone preview.
  - The cost: "1.5 credits" (1,500 micros).
  - A session-level checkbox `[x] 1-Click Fast Unlock cho phiên này` ("Enable 1-Click Fast Unlock for this session").
  - Primary action `[Mở khóa SĐT]` and secondary `[Hủy]`.

- **Given** the user has enabled the session toggle,
- **When** they click any masked phone pill in the same session (before 30 minutes of inactivity or session end),
- **Then** the confirmation popover is skipped, the UI immediately decrypts/unmasks the number with a 150ms flip-in animation, and a 5s undo toast appears.

- **Given** the user has enabled fast unlock and then disables it via the undo toast or the toggle,
- **When** they click a masked phone pill again,
- **Then** the Smart Confirmation Popover reappears for the next click.

### AC-5 — Phone unlock in Lead Matrix, Detail Flyout, and Bulk Selection

- **Given** a single masked phone pill in `NowingLeadMatrix`, `LeadDetailFlyoutDrawer`, or `LeadCard`,
- **When** the user confirms unlock,
- **Then** the frontend calls `POST /api/v1/workspaces/{workspace_id}/leads/{lead_id}/contacts/{contact_id}/unlock`,
- **And** on success:
  - The pill flips from masked to the unmasked `phone`.
  - The credit balance in the top-right badge decrements by 1.5 credits.
  - A toast confirms "Đã mở khóa SĐT -1.5 credits".
  - The `ZaloOutreachButton` and the `tel:` / "Gọi ngay" action become active with the real number.
- **And** on `402 Payment Required`, a credit top-up modal or message appears.
- **And** on `403` (DNC blocked), a "Số điện thoại bị chặn bởi DNC" message appears.

- **Given** the lead is still masked (`is_unlocked = false`),
- **When** `ZaloOutreachButton` or the `tel:` link would render,
- **Then** it is disabled, hidden, or shows a "Mở khóa SĐT để gọi/Zalo" placeholder. This applies everywhere `lead.phone` is used for dial/Zalo.

- **Given** two or more leads are selected and the `FloatingBulkActionBar` is visible,
- **When** the user clicks `[Mở khóa SĐT hàng loạt]`,
- **Then** the Smart Confirmation Popover appears once with the total cost (`selectedCount * 1.5 credits`) and the session fast-unlock toggle.
- **And** the action is disabled if any selected lead has no `contact_id`, is DNC-blocked, or is not `is_valid`.
- **And** on confirm, the frontend unlocks each selected lead sequentially (or a batch endpoint if added) and updates each row.

### AC-6 — 150ms Number Flip animation and 5s Undo Toast

- **Given** a successful phone unlock,
- **When** the number is revealed,
- **Then** the transition from masked to unmasked plays a 150ms flip-in animation using the existing `motion` (framer-motion) library. Animate the whole pill with `rotateX`/opacity/scale, not per-digit.

- **Given** a successful unlock,
- **When** 0-5 seconds pass,
- **Then** a toast with action `Hoàn tác` is shown.
- **And** clicking `Hoàn tác` calls `POST /api/v1/workspaces/{workspace_id}/leads/{lead_id}/contacts/{contact_id}/relock` and, on success:
  - Re-masks the number in the UI.
  - Refunds 1.5 credits to the original payer wallet via `BillingEventService.record_contact_relock` (or `record_contact_unlock_refund` if the PO accepts no separate cap).
  - Enforces an accidental-relock budget (configurable; default 15% of total unlocked leads per billing cycle, separate from opt-out cap, per AD-110 anti-fraud intent). If the budget is exhausted, return `403` with a clear message so the UI shows "Không thể hoàn tác: đã hết hạn mức hoàn tiền tự động".
  - Appends an audit log `relock` with `reason='accidental_unlock'`.
  - Shows "Đã hoàn tác mở khóa - +1.5 credits".

### AC-7 — Backend unlock/relock contracts and LeadRead PII masking

- **Given** the existing `POST /api/v1/workspaces/{workspace_id}/leads/{lead_id}/contacts/{contact_id}/unlock` endpoint,
- **When** it returns `ContactUnlockResponse`,
- **Then** the response includes `contact_id`, `is_unlocked`, `cost_micros`, `name`, `title`, `email`, `phone`.

- **Given** the new `POST .../relock` endpoint,
- **When** called on an unlocked contact,
- **Then** it:
  1. Verifies the caller has `LEADS_WRITE` permission and workspace scoping.
  2. Checks that the request is within the accidental-relock window (default 60 seconds since unlock).
  3. Checks that an original `BillingEvent.event_type='contact_unlock'` exists and has not already been refunded by a `contact_relock`/`contact_unlock_refund` event.
  4. Verifies the accidental-relock budget has not been exhausted (default 15% of total unlocked leads in the current billing cycle per workspace, per AD-110 anti-fraud intent).
  5. Sets `VerifiedContact.is_unlocked = FALSE`.
  6. Calls `BillingEventService.record_contact_relock` to credit the payer, decrement `WorkspaceMembership.monthly_spent_micros`, and write a negative `BillingEvent` (`event_type='contact_relock'`, `cost_micros=-1_500`).
  7. Appends `pii_access_audit_logs` with `access_type='relock'`, `actor_id`, `timestamp`, `ip_address`, `reason='accidental_unlock'`.
  8. Returns `ContactUnlockResponse` with `is_unlocked=False` and `cost_micros=0`.
  9. Is idempotent: a second relock call for the same contact returns the existing result.

- **Given** a lead list or detail response,
- **When** `is_unlocked = FALSE`,
- **Then** `LeadRead` masks `phone`, `email`, and `name` and includes `contact_id`, `is_unlocked`, `is_valid`, and `consent_status` so the UI can decide whether to render the unlock pill or a DNC/refunded badge.

### AC-8 — Tests and verification

- **Given** the updated test suite,
- **When** run,
- **Then**:
  - Backend `ruff check` and `ruff format` pass for all touched Python files.
  - Frontend `pnpm tsc --noEmit` passes.
  - Playwright E2E: `tests/leads/mission-control-glass-box.spec.ts` and `tests/leads/two-tier-phone-unlock.spec.ts` cover the popover, fast-unlock toggle, unlock, undo, bulk, and shimmer.
  - Backend integration: `tests/integration/routes/test_dsh_mission_control.py` and `tests/integration/routes/test_contact_relock.py` pass.

---

## Tasks / Subtasks

### Backend

- [x] **Task B1: DSH public list and control endpoints (AC-2, AC-1)**
  - [ ] Add `DshMissionListResponse` and `DshMissionControlResponse` to `app/schemas/dsh.py`.
  - [ ] Add `GET /workspaces/{workspace_id}/dsh/missions` to `app/routes/dsh_routes.py`.
  - [ ] Add `GET /workspaces/{workspace_id}/dsh/missions/{mission_id}/control` to `app/routes/dsh_routes.py`.
  - [ ] Add `DshMissionService.list_missions_for_workspace(session, workspace_id, status_filter, hours)`.
  - [ ] Add `MissionControlService.build_control_data(session, mission)` that:
    - Redacts `checkpoint` to a PII-safe shape (strips `payload`, `sources`, `leads`).
    - Reads `tokens_used`, `tokens_per_second`, `cost_micros` from `checkpoint.subtasks[]` as primary source.
    - Optionally reconciles with `TokenUsage` by `run_id` or `workspace_id + created_at + usage_type='dsh_mission'` when those rows exist.
    - Falls back to `Run.cost_micros` via `run_id` if token counts are missing; never fails if data is unavailable.
  - [ ] Ensure both endpoints check `LEADS_READ` permission and workspace scoping.

- [x] **Task B2: Contact relock / accidental unlock refund endpoint (AC-7, AC-6)**
  - [ ] Add `POST /workspaces/{workspace_id}/leads/{lead_id}/contacts/{contact_id}/relock` to `app/routes/lead_batch_routes.py`.
  - [ ] Implement `BillingEventService.record_contact_relock(session, verified_contact_id, workspace_id, user_id)` that:
    - Finds the original `contact_unlock` `BillingEvent` and payer.
    - Checks the accidental-relock window (default 60 seconds). If expired, return `403`.
    - Checks the accidental-relock budget (configurable; default 15% of total unlocked leads in the current billing cycle per workspace) to honor AD-110 anti-fraud intent. If exhausted, return `403`.
    - Sets `VerifiedContact.is_unlocked = FALSE`.
    - Credits `User.credit_micros_balance` via `wallet_credit.apply_credit`, decrements `WorkspaceMembership.monthly_spent_micros`.
    - Writes a negative `BillingEvent` (`event_type='contact_relock'`, `cost_micros=-1_500`).
    - Appends `pii_access_audit_logs` with `access_type='relock'`, `reason='accidental_unlock'`.
    - Is idempotent (returns existing relock `BillingEvent` on retry).
  - [ ] Return `ContactUnlockResponse` with `is_unlocked=False` and `cost_micros=0`.

- [x] **Task B3: LeadRead contact metadata and masking (AC-7)**
  - [ ] Extend `app/lead_intelligence/schemas.py:LeadRead` with `contact_id`, `is_unlocked`, `is_valid`, `consent_status`.
  - [ ] Update `app/routes/leads_routes.py:_map_lead_to_read` to populate these from the first `VerifiedContact`.
  - [ ] Ensure masked display for `phone`, `email`, `name` when `is_unlocked=False`.

- [ ] **Task B4: Worker token/cost reporting (AC-1, AC-2)**
  - [ ] Update `app/tasks/dsh_worker.py` to write `tokens_used`, `tokens_per_second`, and `cost_micros` into each `checkpoint.subtasks[]` after a subtask completes (e.g. from `run.cost_micros` for `chainlens.research` and batch-ingest execution time).
  - [ ] Alternatively, when `HybridLLMRouter` is used, write `TokenUsage` rows with `run_id = str(mission_id)` and `usage_type='dsh_mission'`.
  - [ ] Add an index on `token_usage(run_id, workspace_id, created_at)` if missing.
  - [ ] If token counts are missing, `MissionControlService` falls back to `Run.cost_micros` and shows `0 tokens/sec`.

### Frontend

- [~] **Task F1: Types and API services (AC-1, AC-2, AC-5)**
  - [ ] Add `DshMission`, `DshMissionControl`, `DshMissionSubtask` schemas to `nowing_web/contracts/types/dsh.types.ts` (new file or extend `leads.types.ts`).
  - [ ] Add `contactId`, `isUnlocked`, `isValid`, `consentStatus` to `Lead` schema in `nowing_web/contracts/types/leads.types.ts`.
  - [ ] Create `nowing_web/lib/apis/dsh-api.service.ts` with `listMissions`, `getMissionControl`, `createMission`.
  - [ ] Extend `nowing_web/lib/apis/leads-api.service.ts` with `unlockContact(workspaceId, leadId, contactId)` and `relockContact(...)`.

- [ ] **Task F2: Zero-Cache schema for missions and leads (AC-3)**
  - [ ] Create `nowing_web/zero/schema/dsh.ts` with `dshMissionsTable` mirroring the published columns.
  - [ ] Create `nowing_web/zero/queries/dsh.ts` with `dshMissionQueries.byWorkspace`.
  - [ ] Register `dshMissionsTable` in `nowing_web/zero/schema/index.ts`.
  - [ ] (Optional) Extend `zero/queries/leads.ts` for live lead row presence. **Important:** the `leads` Zero stream does not include `phone`, `is_unlocked`, or PII; it is only used to detect new rows early. The full `LeadRead` (with masked phone and `is_unlocked`) must come from REST.

- [ ] **Task F3: Session fast-unlock state (AC-4)**
  - [ ] Add `fastUnlockSessionAtom` in `nowing_web/atoms/leads/leads-canvas.atoms.ts`.
  - [ ] Persist in `sessionStorage` with key `nowing:fast-unlock-session:{workspaceId}:{userId}`.
  - [ ] Auto-expire after 30 minutes of inactivity (reset on every unlock action).

- [ ] **Task F4: Smart Unlock Confirmation Popover (AC-4, AC-5)**
  - [ ] Create `nowing_web/components/leads/SmartUnlockPopover.tsx`.
  - [ ] Props: `lead`, `contactId`, `maskedPhone`, `costCredits`, `fastUnlockEnabled`, `onToggleFastUnlock`, `onConfirm`, `onCancel`.
  - [ ] Use `@radix-ui/react-popover` and Tailwind tokens.

- [ ] **Task F5: Phone unlock pill (AC-4, AC-5, AC-6)**
  - [ ] Create `nowing_web/components/leads/PhoneUnlockPill.tsx` (or extend `PhoneCopyPill`).
  - [ ] Detects `is_unlocked`:
    - `false` -> masked display (e.g. `0908***456`); on click opens `SmartUnlockPopover` (or fast-unlocks if enabled); click event must `stopPropagation` so the row drawer does not open.
    - `true` -> unmasked display; behaves like existing `PhoneCopyPill` (copy on click).
  - [ ] Renders a disabled/placeholder state when `consent_status='withdrawn'` or `is_valid=False`, with a DNC/Invalid badge.
  - [ ] Implements 150ms flip-in animation using `motion` (framer-motion) with `rotateX`/opacity/scale. **Do not use `NumberFlow` for phone strings** — it is for numeric values only (credit count).
  - [ ] On unlock success, shows a 5s Sonner toast with `Hoàn tác` action calling `relockContact`.
  - [ ] Replace `PhoneCopyPill` with `PhoneUnlockPill` in `NowingLeadMatrix` and `LeadDetailFlyoutDrawer` for 26.5. Other surfaces (`LeadCard`, `LeadKanbanBoard`, `LeadIntelligenceTable`, `CompanyGraphDrawer`) are out of scope for 26.5 unless explicitly approved.

- [ ] **Task F6: Floating Bulk Action Bar unlock (AC-5)**
  - [ ] In `NowingSplitCanvas`, compute `selectedLeads = displayLeads.filter(l => selectedLeadIds.includes(l.id))` and pass them to `FloatingBulkActionBar` as `selectedLeads: Lead[]` (keep `selectedCount` for display).
  - [ ] Extend `FloatingBulkActionBar` props to include `selectedLeads`, `workspaceId`, and `onUnlockSelected`.
  - [ ] Disable `[Mở khóa SĐT hàng loạt]` when any selected lead has no `contact_id`, `is_valid=false`, or is DNC-blocked (`consent_status='withdrawn'`).
  - [ ] Clicking `[Mở khóa SĐT hàng loạt]` opens `SmartUnlockPopover` once with `selectedCount * 1.5` credits and the fast-unlock toggle. Bulk unlock always shows the popover regardless of fast-unlock session state (large-cost safety).
  - [ ] On confirm, iterate selected leads and call `unlockContact` sequentially; handle partial failures and show a summary toast.

- [ ] **Task F7: Lead Detail Flyout unlock + invalid report wiring (AC-5, AC-6)**
  - [ ] In `LeadDetailFlyoutDrawer`, replace the static `PhoneCopyPill` with `PhoneUnlockPill`.
  - [ ] Disable the `tel:` / "Gọi ngay" link and `ZaloOutreachButton` when `is_unlocked=false`; they become active only after unlock.
  - [ ] Wire `onReportInvalidPhone` to call `POST .../leads/{lead_id}/report-invalid-phone` and show the refund result. **This is the existing 24h SLA endpoint tied to `PhoneWaterfallLog`; it is separate from the 5s undo relock and from `pii-opt-out`.**
  - [ ] Add DNC/refunded badges when `is_unlocked=False` and `consent_status='withdrawn'` or `is_valid=False`.
  - [ ] For other phone surfaces (`LeadCard`, `LeadKanbanBoard`, `LeadIntelligenceTable`, `CompanyGraphDrawer`), keep `PhoneCopyPill` for 26.5 or duplicate the `is_unlocked` guard. 26.5 explicitly scopes phone unlock to `NowingLeadMatrix` and `LeadDetailFlyoutDrawer`.

- [ ] **Task F8: Glass Box Mission Control Widget (AC-1, AC-2, AC-3)**
  - [ ] Create `nowing_web/components/leads/MissionControlWidget.tsx`.
  - [ ] In `NowingSplitCanvas` or `DynamicRightPanelCanvas`, add `activeMission` state via Zero `dsh_missions` query (`status IN ('running','pending')`, `workspaceId`, order by `createdAt DESC`, `.one()`).
  - [ ] `DynamicRightPanelCanvas` renders `MissionControlWidget` as a collapsible top bar above the Lead Matrix when `activeMission` exists; collapse state stored in a local atom.
  - [ ] `MissionControlWidget` subscribes to the active mission via Zero and re-renders on checkpoint/phase changes; falls back to polling `GET .../dsh/missions?status=running,pending` every 3 seconds if Zero is down.
  - [ ] Render 4-stage stepper, progress bar, token velocity (with fallback to `0 tokens/sec` and `cost_micros`), collapsible CoT drawer.
  - [ ] Mission "cancel" is UI-only (disabled or no-op); real cancel is out of scope.

- [ ] **Task F9: Shimmer Influx in Lead Matrix (AC-3)**
  - [ ] In `NowingLeadMatrix`, render `ShimmerSkeletonRow` at the bottom while `isLoading` or an active mission is in `ingestion`.
  - [ ] Track `newlyArrivedLeadIds` and apply `animate-pulse` / `bg-emerald-500/10` for 800ms when new rows appear.
  - [ ] If using Zero leads, merge the live stream with the REST `leads` prop. New Zero rows initially show placeholder phone "Đang giải mã SĐT..."; the next REST refresh replaces placeholders with masked/unmasked `LeadRead.phone` and `is_unlocked`.

### Tests

- [ ] **Task T1: Playwright E2E**
  - [ ] `tests/leads/mission-control-glass-box.spec.ts`: create a DSH mission, verify stepper updates, expand CoT, verify token velocity appears.
  - [ ] `tests/leads/two-tier-phone-unlock.spec.ts`: first unlock shows popover, enable fast unlock, second unlock is instant, undo toast, bulk unlock.

- [x] **Task T2: Backend integration tests**
  - [ ] `tests/integration/routes/test_dsh_mission_control.py`: list, control endpoint, redacted checkpoint, token velocity aggregation.
  - [ ] `tests/integration/routes/test_contact_relock.py`: relock refunds and audit log, double relock idempotent, DNC/permission failures.

- [~] **Task T3: Quality gates**
  - [ ] `ruff check app/schemas/dsh.py app/routes/dsh_routes.py app/services/dsh_mission_service.py app/services/dsh_control_service.py app/routes/lead_batch_routes.py app/lead_intelligence/schemas.py app/routes/leads_routes.py`.
  - [ ] `ruff format` on same.
  - [ ] `cd nowing_web && pnpm tsc --noEmit`.
  - [ ] `cd nowing_web && pnpm exec biome check` on touched TSX/TS files.

---

## Dev Notes

### Architecture Compliance & Invariants

- **AD-110 — PII Opt-Out Blacklist, Anti-Fraud Refund & Two-Tier Unlock UX:**
  - Two-Tier UX is the primary deliverable. The backend unlock path is hardened in 26.4; this story only adds the popover, session toggle, and relock endpoint.
  - The 15% refund cap in AD-110 Rule 4 is an anti-fraud ceiling for **all automatic refunds**. The 5s accidental relock is a separate, short-window intent, but the backend still enforces an accidental-relock budget (configurable, default 15% of unlocked leads per billing cycle, tracked separately from the opt-out cap). Because the relock window is only 60 seconds, normal usage rarely hits the cap.
  - Do **not** confuse the accidental relock refund with the `POST /pii-opt-out` refund flow.

- **AD-104 — Zero-Cache CDC Reactivity:**
  - `dsh_missions` is already in `zero_publication` with safe columns (`id`, `workspace_id`, `mission_type`, `status`, `phase`, `progress_percent`, `current_subtask_id`, `created_at`, `updated_at`). Add it to the frontend Zero schema.
  - `verified_contacts` and `pii_access_audit_logs` are **not** in `zero_publication`; the UI must not try to subscribe to them. Live `is_unlocked` changes require a REST refetch or a server-sent event.
  - `leads` is already published, but **only with non-PII columns** (no `phone`, `email`, `name`, `is_unlocked`, `value_hmac`). If the hybrid live-leads approach is used, it can subscribe to `leads` for row presence but must refetch `LeadRead` for phone/masked state.

- **AD-105 — PII Vault:**
  - Only the `unlock` and `relock` endpoints may decrypt or re-encrypt PII. No other UI code should touch encrypted values.
  - Masked display must use the same helpers as the backend: `mask_phone` (`0908***456`), `mask_email` (`a***@example.com`), `mask_name` (`Nguyễn***`).

### Existing Code to Reuse

- `nowing_backend/app/services/dsh_mission_service.py` — create/get/update mission.
- `nowing_backend/app/routes/dsh_routes.py` — existing public/internal routers.
- `nowing_backend/app/services/billing_event_service.py` — `record_contact_unlock`, `record_contact_unlock_refund`.
- `nowing_backend/app/services/workspace_credit_service.py` — `record_spend`, `refund_member_spend` (for relock spend reversal).
- `nowing_backend/app/services/wallet_credit.py` — `apply_credit` (called inside refund path).
- `nowing_backend/app/routes/lead_batch_routes.py` — existing `unlock_contact` and `pii_opt_out`.
- `nowing_backend/app/services/pii/opt_out_service.py` — refund pattern for opt-out; do not call directly for accidental relock.
- `nowing_backend/app/services/export_service.py` — `mask_phone` (returns `0908***456`), `mask_email` (`a***@example.com`), `mask_name` (`Nguyễn***`).
- `nowing_backend/app/lead_intelligence/schemas.py` — `LeadRead`, `PhoneRefundResponse`, `InvalidPhoneReportRequest`.
- `nowing_web/components/leads/PhoneCopyPill.tsx` — base pill UX; do **not** replace in 26.5 outside `NowingLeadMatrix` and `LeadDetailFlyoutDrawer`.
- `nowing_web/components/leads/FloatingBulkActionBar.tsx` — bulk selection UX.
- `nowing_web/components/leads/LeadDetailFlyoutDrawer.tsx` — detail flyout.
- `nowing_web/components/leads/NowingSplitCanvas.tsx` and `DynamicRightPanelCanvas.tsx` — split canvas layout.
- `nowing_web/lib/hooks/use-leads.ts` — REST data source.
- `nowing_web/zero/schema/leads.ts` and `zero/queries/leads.ts` — patterns for Zero schema.
- `nowing_web/atoms/leads/leads-canvas.atoms.ts` — canvas state.

### Gaps & Implementation Hints

- **Token velocity:** The most fragile part. As of baseline `3b1705689`, the DSH worker does not call `HybridLLMRouter` and does not write `TokenUsage`. `chainlens.research` does not record `TokenUsage` with `run_id`. The pragmatic primary source is the worker self-reporting `tokens_used`, `tokens_per_second`, and `cost_micros` into `checkpoint.subtasks[]` after each subtask. `MissionControlService` falls back to `Run.cost_micros` and shows `0 tokens/sec` when counts are missing.
- **Mission cancel:** Not implemented in 26.5. The widget can show a disabled "Hủy" button or skip it. A real cancel endpoint is out of scope.
- **PII Opt-Out UI gap:** The `DncManagementModal` and `LeadDetailFlyoutDrawer` have no flow to call `pii-opt-out`. This is deferred to a separate follow-up story `26.5a`; do **not** implement it under 26.5.
- **Report invalid phone vs. 5s undo:** `POST .../report-invalid-phone` is the old 24h SLA endpoint tied to `PhoneWaterfallLog`. The new 5s undo uses the new `relock` endpoint. Keep both flows separate in the UI; the "Báo SĐT sai" button should still call `report-invalid-phone` (legacy flow), not `relock`.
- **Relock refund cap:** The 5s accidental relock enforces a separate 15% accidental-relock budget per billing cycle (per AD-110 anti-fraud intent). The 60s relock window means normal accidental-undo usage will not hit the cap.
- **Zero `leads` PII boundary:** New Zero rows have no `phone`/`is_unlocked`. The matrix must show a placeholder until REST refresh.
- **Phone pill scope:** Only `NowingLeadMatrix` and `LeadDetailFlyoutDrawer` are required to use `PhoneUnlockPill` in 26.5. Other surfaces can keep `PhoneCopyPill` but must disable dial/Zalo when masked.
- **Bulk unlock cost projection:** Use `selectedCount * 1.5` credits (or `selectedCount * 1500000` micros). The backend unlocks one by one unless a batch endpoint is added; for 26.5, sequential calls are acceptable. Always show the confirmation popover for bulk (fast-unlock session does not bypass).
- **Number Flip animation:** Use a simple `motion.span` with `rotateX` or opacity/scale. Do not introduce a new dependency; `motion` is already in `package.json`.
- **Fast unlock session storage:** Store as a boolean in `sessionStorage` with a last-used timestamp. On app load, if `now - lastUsed > 30 minutes`, treat as disabled.

### Project Structure Notes

- New backend files likely:
  - `nowing_backend/app/services/dsh_control_service.py` (MissionControlService).
  - `nowing_backend/tests/integration/routes/test_dsh_mission_control.py`.
  - `nowing_backend/tests/integration/routes/test_contact_relock.py`.

- New frontend files likely:
  - `nowing_web/contracts/types/dsh.types.ts`.
  - `nowing_web/lib/apis/dsh-api.service.ts`.
  - `nowing_web/zero/schema/dsh.ts`.
  - `nowing_web/zero/queries/dsh.ts`.
  - `nowing_web/components/leads/SmartUnlockPopover.tsx`.
  - `nowing_web/components/leads/PhoneUnlockPill.tsx`.
  - `nowing_web/components/leads/MissionControlWidget.tsx`.
  - `nowing_web/components/leads/ShimmerSkeletonRow.tsx` (or inline in `NowingLeadMatrix`).
  - `nowing_web/tests/leads/mission-control-glass-box.spec.ts`.
  - `nowing_web/tests/leads/two-tier-phone-unlock.spec.ts`.

- Files to modify:
  - `nowing_backend/app/schemas/dsh.py`
  - `nowing_backend/app/routes/dsh_routes.py`
  - `nowing_backend/app/services/dsh_mission_service.py`
  - `nowing_backend/app/services/dsh_control_service.py` (new)
  - `nowing_backend/app/services/billing_event_service.py` (add `record_contact_relock`)
  - `nowing_backend/app/routes/lead_batch_routes.py`
  - `nowing_backend/app/lead_intelligence/schemas.py`
  - `nowing_backend/app/routes/leads_routes.py`
  - `nowing_backend/app/tasks/dsh_worker.py` (self-report token/cost in checkpoint)
  - `nowing_web/contracts/types/leads.types.ts`
  - `nowing_web/contracts/types/dsh.types.ts` (new)
  - `nowing_web/lib/apis/leads-api.service.ts`
  - `nowing_web/lib/apis/dsh-api.service.ts` (new)
  - `nowing_web/zero/schema/index.ts`
  - `nowing_web/zero/schema/dsh.ts` (new)
  - `nowing_web/zero/queries/dsh.ts` (new)
  - `nowing_web/zero/schema/leads.ts` (if adding live lead subscription)
  - `nowing_web/atoms/leads/leads-canvas.atoms.ts`
  - `nowing_web/components/leads/PhoneUnlockPill.tsx` (new; keep `PhoneCopyPill` in other surfaces)
  - `nowing_web/components/leads/NowingLeadMatrix.tsx`
  - `nowing_web/components/leads/LeadDetailFlyoutDrawer.tsx`
  - `nowing_web/components/leads/FloatingBulkActionBar.tsx`
  - `nowing_web/components/leads/NowingSplitCanvas.tsx`
  - `nowing_web/components/leads/DynamicRightPanelCanvas.tsx`
  - `nowing_web/components/leads/zalo-outreach-button.tsx` (disable when masked)

### P0 Surface Assessment

This story touches:
- **Credit wallet and billing events** (unlock/relock) — P0.
- **PII display and masking** — P0.
- **DNC / consent gating** — P0.
- **Mission progress live UI** — P1 (no financial risk, but high visibility).

Per `nowing-quality-pipeline.md`:
- Integration tests on real Postgres are P0-gated.
- Human-review gate is required for billing/PII changes.
- Mutation gate is required for `app/services/dsh_mission_service.py`, `app/services/dsh_control_service.py`, `app/routes/lead_batch_routes.py`, `app/services/billing_event_service.py` (if touched).

### Important Do-Nots

- Do **not** create a new `pii_blacklists` table or duplicate opt-out backend logic. Use existing `pii-opt-out` endpoint if a separate UI story is approved.
- Do **not** decrypt PII in list responses; only `unlock`/`relock` endpoints return decrypted phone/email.
- Do **not** call `wallet_credit.apply_debit` directly; route unlock billing through the existing `BillingEventService.record_contact_unlock` path.
- Do **not** call `wallet_credit.apply_credit` directly; route relock refund through `BillingEventService.record_contact_relock`.
- Do **not** expose `dsh_missions.payload` or full `checkpoint` to the frontend.
- Do **not** use the `POST .../report-invalid-phone` endpoint for the 5s accidental undo; use the new `relock` endpoint. The `report-invalid-phone` endpoint remains for the legacy 24h PhoneWaterfallLog flow.
- Do **not** enable Zalo/dial actions when `is_unlocked=false`; masked `lead.phone` is not a valid number.

### References

- Epic context: `_bmad-output/planning-artifacts/epics.md` lines 3382-3391 (Story 26.5).
- Architecture: `_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` §AD-104, AD-105, AD-110.
- Experience: `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/EXPERIENCE.md` §4.1, §5 (Shimmer), §8 (Flow 1).
- Backend stories: `26-4-pii-vault-hmac-deduplication-decree-13-opt-out.md`, `26-3-multi-tier-hybrid-llm-router.md`, `26-2-dsh-worker-sidecar-redis-streams-and-task-resumption.md`, `26-1-fastmcp-batch-ingest-and-stateless-chainlens-pipeline.md`.
- Existing code:
  - `nowing_backend/app/routes/dsh_routes.py`
  - `nowing_backend/app/services/dsh_mission_service.py`
  - `nowing_backend/app/routes/lead_batch_routes.py`
  - `nowing_backend/app/lead_intelligence/schemas.py`
  - `nowing_backend/app/services/billing_event_service.py`
  - `nowing_backend/app/db.py` (`DshMission`, `VerifiedContact`, `TokenUsage`)
  - `nowing_web/components/leads/NowingSplitCanvas.tsx`
  - `nowing_web/components/leads/NowingLeadMatrix.tsx`
  - `nowing_web/components/leads/LeadDetailFlyoutDrawer.tsx`
  - `nowing_web/components/leads/FloatingBulkActionBar.tsx`
  - `nowing_web/lib/hooks/use-leads.ts`
  - `nowing_web/zero/schema/index.ts`

---

## Challenge Log (grill-me)

> Grill-me re-run against current code (baseline `3b1705689`) before red-phase ATDD.

### Q1 — Already implemented or overlapping?

- **Phone unlock endpoint** đã có: `app/routes/lead_batch_routes.py:188-327` (`unlock_contact`) — unlock, bill 1_500 micros, decrypt PII, ghi audit log `unlock`, xử lý 402/403/409.
- **Relock / refund primitives** đã gần đủ: `BillingEventService.record_contact_unlock` và `record_contact_unlock_refund` tại `app/services/billing_event_service.py:63-169`; `OptOutService` (`app/services/pii/opt_out_service.py`) đã implement 15% refund cap, original-unlock lookup, wallet credit, audit log. **Có thể reuse pattern** nhưng phải tách budget/event-type cho accidental-relock.
- **DSH primitives** đã có: `DshMission` table, `dsh_missions` Zero publication (`app/zero_publication.py:198-231`), `DshMissionService` (`app/services/dsh_mission_service.py`) với `create_mission`, `get_mission_for_workspace`, `get_mission_or_404`, `update_checkpoint`.
- **Masking helpers duplicate:** `mask_phone` xuất hiện ở `app/services/phone_waterfall_service.py:174` **và** `app/services/export_service.py:579`; `mask_email`/`mask_name` cũng nằm ở `export_service.py`. Đây là **duplicate logic** cần consolidate.
- **Frontend components exist but unsafe:** `PhoneCopyPill` (`components/leads/PhoneCopyPill.tsx`), `ZaloOutreachButton` (`components/leads/zalo-outreach-button.tsx`), `FloatingBulkActionBar` (`components/leads/FloatingBulkActionBar.tsx`), `NowingSplitCanvas`/`NowingLeadMatrix`/`LeadDetailFlyoutDrawer` chưa xử lý `is_unlocked` và chưa có `PhoneUnlockPill`/`SmartUnlockPopover`.
- **Zero schema thiếu DSH:** `zero/schema/index.ts` chưa có `dshMissionsTable`; `zero/queries` chưa có `dsh.ts`.
- **Lead contract thiếu unlock fields:** `LeadRead` (`app/lead_intelligence/schemas.py:38`) và frontend `leads.types.ts` (`nowing_web/contracts/types/leads.types.ts`) không có `contact_id`, `is_unlocked`, `is_valid`, `consent_status`.
- **No public DSH list/control endpoints:** `app/routes/dsh_routes.py` chỉ có `create`, `get` và sidecar `patch`; chưa có `GET /dsh/missions` hay `GET /dsh/missions/{id}/control`.
- **No relock endpoint:** `lead_batch_routes.py` có `/pii-opt-out` (24h SLA/refund) và `/unlock`, nhưng chưa có `POST .../relock` cho 5s accidental undo.
- **Summary:** No duplicate implementation of the new 26.5 surface, but several helper/functions overlap and must be consolidated before coding.

### Q2 — Is there a simpler alternative?

- **Mask phone/email/name:** Reuse/consolidate `mask_*` từ `app/services/export_service.py` thay vì viết hàm mới hoặc để 2 hàm `mask_phone` tồn tại song song. Đảm bảo format output là `0908***456`.
- **Relock refund:** Tạo `BillingEventService.record_contact_relock` bằng cách refactor phần "find original unlock + credit payer + refund member spend" của `record_contact_unlock_refund` thành helper dùng chung, nhưng ghi `event_type='contact_relock'` và tính budget từ `contact_relock` riêng biệt (không tính `contact_unlock_refund` của opt-out).
- **Relock budget count:** Reuse hàm `_count_refundable_unlocks_this_cycle` trong `OptOutService` nhưng lọc `event_type='contact_relock'` thay vì `contact_unlock_refund`.
- **Audit log:** Append JSONB vào `VerifiedContact.pii_access_audit_logs` giống `unlock_contact` / `OptOutService`, chỉ đổi `access_type='relock'`, `reason='accidental_unlock'`.
- **DSH control:** Dùng `DshMissionService.get_mission_for_workspace` và `update_checkpoint`; chỉ cần thêm `list_missions_for_workspace` và `build_control_data` để redact checkpoint.
- **Wallet/credit:** Dùng `wallet_credit.apply_credit` và `WorkspaceCreditService.refund_member_spend` đã có — không viết lại.
- **Phone pill:** Nên tạo `PhoneUnlockPill` wrapper quanh `PhoneCopyPill` + popover thay vì sửa `PhoneCopyPill` (vẫn dùng ở surfaces không cần unlock). Hoặc extend `PhoneCopyPill` với `isUnlocked`/`contactId`/`onUnlock` props.
- **Zero schema:** Thêm `dshMissionsTable` theo mẫu `leadsTable` (`zero/schema/leads.ts`) và tạo `zero/queries/dsh.ts` tương tự `automations.ts`.
- **Bulk unlock:** `NowingSplitCanvas.handleUnlockPhones` hiện chỉ toast (`components/leads/NowingSplitCanvas.tsx:160-162`) và `FloatingBulkActionBar` chỉ nhận `selectedCount`; cần truyền `selectedLeads` xuống để validate `contact_id`, DNC, `is_valid`, tính tổng cost.

### Q3 — Edge cases the spec misses

- [ ] **Boundary — Wallet chính xác:** balance = 1_500 micros -> success; 1_499 -> `402 Payment Required`. `wallet_credit.check_balance` dùng `required > available` với `available = balance - reserved`.
- [ ] **Boundary — DNC after unlock:** Admin thêm phone vào DNC sau khi user unlock -> `pii-opt-out` set `is_unlocked=False` và refund; UI phải refetch `LeadRead` vì `verified_contacts` không publish lên Zero.
- [ ] **Boundary — Multiple verified contacts per lead:** `LeadRead` hiện chọn `first_contact` (`leads_routes.py:75-89`). Nếu contact đầu bị DNC/withdrawn nhưng contact sau unlockable, UI không có cơ chế chọn contact khác.
- [ ] **Boundary — LeadRead missing unlock fields:** Schema thiếu `contact_id`, `is_unlocked`, `is_valid`, `consent_status`; UI không biết nên render unlock pill, DNC badge, hay Zalo/dial.
- [ ] **Boundary — Bulk unlock + fast unlock:** Dù fast unlock đã bật, bulk unlock vẫn hiện popover một lần với tổng cost; fast unlock chỉ áp dụng single click.
- [ ] **Boundary — Relock window:** Tại đúng 60s+1ms -> `403` "relock window expired".
- [ ] **Boundary — Accidental-relock budget:** 15% của tổng unlocked leads trong billing cycle; đúng 15.0% -> 403, dưới 15% -> allow. Phải tách khỏi opt-out cap.
- [ ] **Concurrent — Double first-time unlock:** Hai request `unlock_contact` đồng thời trên cùng contact. `BillingEvent` chưa có UNIQUE constraint trên `(event_entity_type, event_type, event_id, workspace_id)`, `SELECT FOR UPDATE` không khóa row chưa tồn tại => **có thể double-billing**.
- [ ] **Concurrent — Cross-user relock:** User A relock trong khi user B đang mở detail drawer; B nhìn thấy trạng thái cũ cho đến khi REST/Zero refresh.
- [ ] **Null/empty — No contact/phone:** `lead.phone` rỗng hoặc lead không có `verified_contacts` -> `PhoneUnlockPill` hiển thị "Chưa có SĐT" và không mở popover.
- [ ] **Null/empty — Masked phone malformed:** `mask_phone` với < 7 digits trả về `***`; UI cần hiển thị placeholder thay vì Zalo/dial.
- [ ] **Null/empty — DSH checkpoint missing subtasks:** `MissionControlService` phải trả `0 tokens/sec` và `cost_micros` từ `Run.cost_micros` nếu worker chưa self-report.
- [ ] **Multi-tab — Fast unlock session state:** Cần `storage` event listener hoặc Jotai atom đọc `sessionStorage` mỗi click để đồng bộ tab.

### Q4 — Failure modes unspecified

- [ ] **Billing transaction split (MONEY RISK):** `wallet_credit.apply_debit` gọi `session.commit` bên trong (`app/services/wallet_credit.py:112`). `_record_business_event` gọi `apply_debit`, sau đó `unlock_contact` route mới set `contact.is_unlocked=True` và `session.commit()` lần nữa (`lead_batch_routes.py:317`). Nếu lỗi xảy ra sau khi ví đã bị trừ, user mất 1.5 credits mà không unlock. **Cần transaction duy nhất hoặc refactor `apply_debit` không tự commit.**
- [ ] **`BillingEvent` duplicate under concurrency (MONEY RISK):** `ix_billing_events_event_lookup` (`app/db.py:4593-4597`) không unique; `_record_business_event` dùng `FOR UPDATE` trên kết quả select. Nếu 2 request first-time unlock chạy song song, cả 2 đều select ra 0 row, không khóa future insert, cả 2 đều insert `BillingEvent` và debit. Cần unique partial index hoặc serializable transaction.
- [ ] **Relock rollback:** Nếu `wallet_credit.apply_credit` hoặc `WorkspaceCreditService.refund_member_spend` fail trong `record_contact_relock`, transaction phải rollback toàn bộ; `VerifiedContact.is_unlocked` phải vẫn là `True`.
- [ ] **DNC fail-closed:** `DncComplianceService.is_blocked` nếu throw exception hoặc Redis fail, unlock phải trả `403 forbidden` (fail-closed) như hiện tại.
- [ ] **`VerifiedContactEncryption.decrypt` failure:** `unlock_contact` hiện trả `None` cho field lỗi (`lead_batch_routes.py:239-248`); relock không cần decrypt nhưng phải đảm bảo không lộ PII.
- [ ] **WorkspaceMembership missing on refund:** `WorkspaceCreditService.refund_member_spend` trả về `amount_micros=0` nếu membership không tồn tại (`workspace_credit_service.py:537-545`); cần rõ ràng trong response/test.
- [ ] **Zero-Cache down:** Glass Box chuyển polling `GET /dsh/missions?status=running` 3 giây.
- [ ] **DSH worker writes PII into checkpoint:** `MissionControlService.redact_checkpoint` phải strip `payload`, `sources`, `leads`, `subtasks[].output` chứa PII trước khi trả response.
- [ ] **Token velocity missing:** DSH worker hiện không gọi `HybridLLMRouter` và không viết `TokenUsage`; `MissionControlService` phải ưu tiên `checkpoint.subtasks[]` rồi fallback `Run.cost_micros`, cuối cùng `0 tokens/sec`.
- [ ] **Bulk unlock partial failure:** Một số contact DNC/credit hết, UI phải tiếp tục xử lý các contact còn lại và hiển thị summary "Mở khóa 18/20 SĐT, 2 số bị chặn DNC".
- [ ] **Frontend state out of sync after relock:** UI cần optimistic update `is_unlocked`/`phone` rồi confirm bằng API response.

### Triage

| Finding | Severity | Action |
|---------|----------|--------|
| **Duplicate `mask_phone` logic** in `phone_waterfall_service.py` and `export_service.py` | Critical | **RESOLVED** — consolidated thành `app/services/pii/mask.py` single source of truth; `export_service` và `phone_waterfall_service` import from there. E.164 (`+84908123456`) now đồng bộ về domestic `0908***456`. |
| **Billing transaction split** (`apply_debit` commits before `is_unlocked` set) | Critical (money) | **RESOLVED** — `unlock_contact` route now sets `contact.is_unlocked=True` và `pii_access_audit_logs` **before** `BillingEventService.record_contact_unlock` so `wallet_credit.apply_debit` commits everything in one transaction. If billing fails, the contact stays locked. |
| **`BillingEvent` no unique constraint on `(entity, type, id, workspace)`** | Critical (money) | **RESOLVED (workaround)** — `BillingEventService` now acquires a per-event `pg_advisory_xact_lock` in `_record_business_event` and `record_contact_unlock_refund`. This serializes concurrent first-time billing/refund attempts where `FOR UPDATE` cannot lock a non-existing row. A proper unique index remains the long-term fix. |
| **Zalo/dial use masked phone** (`ZaloOutreachButton`, `tel:` link không check `is_unlocked`) | Critical | **Must fix in 26.5** — disable/hide khi `is_unlocked=false`. |
| **`LeadRead` and `leads.types.ts` missing `contact_id`, `is_unlocked`, `is_valid`, `consent_status`** | Critical | **Must fix in 26.5** — UI không render unlock affordance đúng. |
| **No public DSH list/control endpoints** | Critical | **Must fix in 26.5** — thêm `GET /dsh/missions` và `GET /dsh/missions/{id}/control` với redacted checkpoint. |
| **No `relock` endpoint / `record_contact_relock`** | Critical | **Must fix in 26.5** — thêm endpoint + service. |
| **DSH `dshMissionsTable` missing in Zero schema** | Non-critical | Thêm trong dev. |
| **PII Opt-Out UI** | Non-critical | Đã defer sang `26.5a`. |

### Resolved design decisions (PO/UX)

1. **PII Opt-Out UI scope:** Out of scope for 26.5. Separate `26.5a`.
2. **Accidental-relock refund cap:** 15% budget per billing cycle, **separate** from opt-out cap, 60s window.

### Recommended pre-dev actions

1. ~~Resolve duplicate `mask_*` helpers~~ — **done**: single `app/services/pii/mask.py`.
2. ~~Resolve billing transaction & `BillingEvent` uniqueness~~ — **done**: atomic unlock + advisory lock.
3. Add `contact_id`, `is_unlocked`, `is_valid`, `consent_status` vào `LeadRead` (`app/lead_intelligence/schemas.py`) và `Lead` frontend schema (`nowing_web/contracts/types/leads.types.ts`).
4. Proceed sang `bmad-nowing-test-first-atdd` / `bmad-testarch-atdd`.
