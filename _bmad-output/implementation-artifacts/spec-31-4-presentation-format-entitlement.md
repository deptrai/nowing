---
title: '31-4 Entitlement-driven Presentation Studio Format Selection (PPTX vs Marp)'
type: 'feature'
created: '2026-09-16'
status: 'done'
review_loop_iteration: 1
baseline_commit: '0c23ea87f'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `generate_presentation` lets the model pick `output_format` (pptx|marp) purely from the prompt with no plan gate — a free workspace can produce native PPTX, and the UI chips (`/slides pptx`) always advertise PPTX regardless of entitlement. Format is meant to be a plan-tier entitlement: free → Marp only, paid tiers → PPTX + Marp.

**Approach:** Resolve the workspace's `plan_tier` (via `WorkspaceLimitService.get_effective_limits`) inside the presentation generate path; if the requested `output_format` is `pptx` but the tier only entitles `marp`, fail closed with the existing 403 "not enabled on this workspace plan" upgrade pattern (do NOT silently downgrade). Mirror the gate in the frontend: hide/disable the PPTX chip + `/slides pptx` + `?format=pptx` when the workspace subscription's `plan_tier` is free.

## Boundaries & Constraints

**Always:**
- Entitlement rule: `plan_tier` in `{team, growth, enterprise}` → `pptx` allowed; otherwise (free / unknown / missing) → only `marp`. PPTX request on a non-entitled tier → **hard-block**, return the workspace-plan 403/upgrade error shape already used for gated chat modes — never auto-downgrade to Marp.
- Resolve tier through `WorkspaceLimitService.get_effective_limits(session, workspace_id)` → `limits.plan_tier or "free"` (existing reuse; do not re-implement plan resolution).
- Gate at the **service/capability layer** (`PresentationStudioService.generate` or the capability executor) so the tool schema cannot be bypassed by prompt injection — the model asking for pptx must not be enough.
- Preserve existing fail-closed chat-mode gating (`presentation_studio_enabled` + `PRESENTATION_STUDIO_ENABLED`); this story adds a *format* gate on top, not a replacement.
- Frontend reads `plan_tier` from the existing `GET /workspaces/{id}/subscription` response (already returns `plan_tier`/`current_plan`) — no new endpoint for this.
- On a non-entitled tier: the `/slides pptx` builtin chip and any PPTX affordance are hidden/disabled, and `/slides marp` remains. `?format=pptx`/`?mode=presentation_studio` requests still resolve to the mode but the generated output is Marp; the visible hint is Marp, not PPTX.

**Ask First:**
- Changing the tier→format mapping (e.g. allowing `team` PPTX, or adding new formats like Google Slides / PDF).
- Soft-downgrade behavior (auto-fallback to Marp with `degradation_reason`) instead of hard-block — the chosen contract is hard-block; only change if the human asks.
- Adding a workspace-level or env-level format override beyond the plan-tier rule.

**Never:**
- No forking the single `presentation_studio` ChatMode id (AD-120 — deliberate design; gate the format, not the mode).
- No new billing/plan catalog schema — reuse `plan_tier` + `WorkspaceLimit`.
- No silent downgrade to Marp on a PPTX request.
- No changes to PPTX/Marp generation internals, slide templating, or artifact rendering.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Free tier + pptx | `plan_tier=free`, `output_format=pptx` | 403 / "not enabled on this workspace plan" upgrade error; no generation | hard-block |
| Free tier + marp | `plan_tier=free`, `output_format=marp` | generation proceeds, format=marp | N/A |
| Paid tier + pptx | `plan_tier=team|growth|enterprise`, `output_format=pptx` | generation proceeds, format=pptx | N/A |
| Paid tier + marp | paid tier, `output_format=marp` | generation proceeds, format=marp | N/A |
| Missing workspace / unknown tier | workspace None or plan_tier None | treated as free → pptx blocked, marp allowed | fail-closed |
| Prompt asks pptx on free | LLM emits `output_format=pptx` for free ws | gate blocks before generation regardless of prompt | hard-block |
| FE free workspace | `plan_tier=free` | `/slides pptx` chip hidden/disabled; `/slides marp` shown | N/A |
| FE paid workspace | `plan_tier` paid | both `/slides pptx` + `/slides marp` shown | N/A |

## Code Map

- `nowing_backend/app/services/presentation/service.py` — `PresentationStudioService.generate(build_input, session)` (:229) is the SINGLE choke point: called by BOTH `execute_generate_presentation` AND the `POST /presentations/generate` REST route (`routes/presentation_routes.py:163`). Put the entitlement gate here so no caller bypasses it. It already normalizes `output_format` and has `session` + `build_input.workspace_id`.
- `nowing_backend/app/capabilities/presentation/generate/executor.py` — `execute_generate_presentation` builds `GeneratePresentationInput` and delegates to `service.generate`; no gate here (delegates to the service choke point).
- `nowing_backend/app/routes/presentation_routes.py:146` — `POST /generate` calls `service.generate` directly; the service-level gate is what covers it.
- `nowing_backend/app/capabilities/presentation/generate/schemas.py` — `PresentationCapabilityInput.output_format` (`pattern ^(pptx|marp)$`, default `pptx`). Keep the schema; the gate is entitlement, not validation.
- `nowing_backend/app/services/workspace_limits/service.py:120` — `WorkspaceLimitService.get_effective_limits(session, workspace_id)` → `EffectiveLimits.plan_tier` (None→treat as free). Reuse; do not re-resolve.
- `nowing_backend/app/tasks/chat/streaming/flows/new_chat/chat_modes.py:72` — `presentation_studio` ChatMode gated by `presentation_studio_enabled` + `PRESENTATION_STUDIO_ENABLED`; the 403 upgrade-message pattern lives here (`error_code`/`error_message`). Reuse the same shape for the format gate.
- `nowing_backend/app/routes/workspaces/subscriptions.py:38` — `GET /workspaces/{id}/subscription` already returns `plan_tier`/`current_plan`; FE reads it.
- `nowing_web/components/new-chat/prompt-picker.tsx:104` — `/slides pptx` + `/slides marp` builtin chips (filterable by entitlement).
- `nowing_web/components/assistant-ui/thread/ThreadWelcome.tsx:113` — presentation quick-card(s) (`mode: "presentation_studio"`, Marp card present).
- `nowing_web/app/dashboard/[workspace_id]/new-chat/[[...chat_id]]/page.tsx:181` — `?mode=presentation_studio` + `presentation_studio_enabled` param handling; format hint source.
- `nowing_web/lib/apis/workspaces-api.service.ts:228` — subscription fetcher returning `plan_tier`.

## Tasks & Acceptance

**Execution:**
- [x] `nowing_backend/app/services/presentation/service.py` — put the entitlement gate INSIDE `PresentationStudioService.generate` (the single choke point used by BOTH the capability executor AND the `POST /presentations/generate` REST route, so neither can bypass it): after `output_format` is normalized, resolve `plan_tier` via `get_effective_limits`; if `pptx` and tier not in `{team,growth,enterprise}` raise `HTTPException(403, detail="PPTX format generation is not enabled on this workspace plan; use Marp or upgrade")` — backend gate covering all callers
- [x] `nowing_web/components/new-chat/prompt-picker.tsx` + `ThreadWelcome.tsx` + `new-chat/[[...chat_id]]/page.tsx` — read `plan_tier` from workspace subscription via a shared `usePresentationStudioEntitlement` hook; hide/disable PPTX chip/card on a RESOLVED free tier. For `?format=pptx`/prompt: only rewrite to Marp when (a) subscription RESOLVED (`subscriptionData !== undefined`, not loading), (b) mode is `presentation_studio`, (c) tier non-entitled — never rewrite while unresolved (paid users must not lock to Marp on mount) — FE gate + no premature downgrade
- [x] `nowing_backend/tests/unit/.../test_*presentation*.py` — cover I/O matrix (free+pptx block, free+marp ok, paid+pptx ok, missing-workspace→free) — backend coverage
- [x] `nowing_web/tests/presentation-studio/...` — free hides PPTX chip; paid shows both — FE coverage (component or spec)

**Acceptance Criteria:**
- Given a free-tier workspace, when `generate_presentation` is called with `output_format=pptx` (by any path incl. prompt-injected), then the request is blocked with the workspace-plan 403/upgrade error and nothing is generated.
- Given a free-tier workspace, when `output_format=marp`, then generation succeeds as Marp.
- Given a paid-tier workspace (team/growth/enterprise), when `output_format=pptx`, then generation succeeds as PPTX.
- Given a missing/None workspace or plan_tier, when `output_format=pptx`, then it is treated as free and blocked.
- Given a free-tier workspace in the UI, when the new-chat entry points render, then the PPTX chip/affordance is not offered and Marp remains.

## Spec Change Log

- [loop 1 | bad_spec] Gate placed in `execute_generate_presentation` only — `POST /presentations/generate` (`routes/presentation_routes.py:163`) calls `service.generate` directly and bypassed it. Amended Code Map + Tasks to put the entitlement check inside `PresentationStudioService.generate` (single choke point covering both capability and REST callers) and gave the 403 a PPTX-specific detail ("...use Marp or upgrade"). KEEP: tier rule (team/growth/enterprise→pptx else marp), fail-closed free default, `get_effective_limits` reuse, and hard-block are correct — only placement moved.
- [loop 1 | bad_spec] Frontend rewrote `?format=pptx`/pitch prompts to Marp while `subscriptionData` was still loading, and applied keyword replacement outside presentation mode. Amended FE task: only downgrade when entitlement RESOLVED (subscriptionData !== undefined), only in `presentation_studio` mode, via `getWorkspaceIdNumber` for the param. KEEP: hiding the PPTX chip/`/slides pptx` on a resolved free tier is correct and must survive.

## Design Notes

- Hard-block (not downgrade) was chosen deliberately: silent PPTX→Marp hides the paywall; the 403 upgrade prompt matches the existing gated-mode UX and is the spec'd contract. `degradation_reason` is left for a future soft-fallback variant (Ask First).
- Gating at the executor/service layer (not the tool schema or the chat-mode registry) because the tool is invoked by the model — a prompt cannot be trusted to self-limit the format. The single `presentation_studio` mode id is preserved per AD-120.

## Verification

**Commands:**
- `cd nowing_backend && uv run pytest tests/unit -k "presentation" -q` — expected: all pass incl. new entitlement tests
- `cd nowing_backend && uv run ruff check app/capabilities/presentation app/services/presentation` — expected: clean
- `cd nowing_web && pnpm exec biome check components/new-chat/prompt-picker.tsx components/assistant-ui/thread/ThreadWelcome.tsx "app/dashboard/[workspace_id]/new-chat/[[...chat_id]]/page.tsx"` — expected: clean

## Suggested Review Order

**Backend entitlement gate (single choke point)**

- Gate inside `generate` — covers capability executor AND `POST /presentations/generate`; cannot be bypassed.
  [`service.py:248`](../../nowing_backend/app/services/presentation/service.py#L248)
- 403 detail is PPTX-specific, not "Studio disabled" — free tier still gets Marp.
  [`service.py:257`](../../nowing_backend/app/services/presentation/service.py#L257)
- Tool surfaces paywall as `plan_limited` (not generic error) so FE can render upgrade UX.
  [`generate_presentation.py:155`](../../nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/presentation/generate_presentation.py#L155)

**Frontend entitlement + no-premature-downgrade**

- Shared `usePresentationStudioEntitlement` hook — resolves subscription, `isResolvedFreeTier` only when loaded.
  [`use-presentation-studio-entitlement.ts:35`](../../nowing_web/hooks/use-presentation-studio-entitlement.ts#L35)
- `?format=pptx` downgrade only when resolved AND presentation mode — paid users not locked to Marp.
  [`page.tsx:226`](../../nowing_web/app/dashboard/[workspace_id]/new-chat/[[...chat_id]]/page.tsx#L226)
- PPTX chip/`/slides pptx` hidden on resolved free tier; Marp kept.
  [`prompt-picker.tsx`](../../nowing_web/components/new-chat/prompt-picker.tsx)

**Tests**

- Entitlement matrix incl. REST-route 403 (proves no executor bypass).
  [`test_presentation_format_entitlement.py`](../../nowing_backend/tests/unit/services/presentation/test_presentation_format_entitlement.py)
- Route integration: free→403, marp→200, paid→pptx.
  [`test_presentation_routes_atdd.py`](../../nowing_backend/tests/integration/routes/test_presentation_routes_atdd.py)

### Review Findings

- [x] [Review][Patch] Gate ran before input validation — empty/invalid-format on free raised 403 instead of validation_failed. Reordered: format+prompt first, then entitlement. [`service.py:240`]
- [x] [Review][Patch] `plan_limited` was an undocumented status — added to schema description + `_FAILURE_STATUSES` (thinking.py + emission.py) so chat streaming treats it as a failure, not success. [`schemas.py` / `thinking.py:26` / `emission.py:11`]
- [x] [Review][Patch] `except HTTPException` mapped 401/404/500 to `plan_limited` and skipped rollback. Now only 403 → `plan_limited`; others → `error`; rollback added. [`generate_presentation.py`]
- [x] [Review][Patch] Missing unit test for `plan_limited` when service raises 403 — `test_tool_returns_plan_limited_when_service_raises_403` added. [`test_generate_presentation_tool_atdd.py`]
- [x] [Review][Patch] E2E AC-2 lacked `mockWorkspaceSubscription(..., "team")` so live-run would 403. Added. [`presentation-studio-chat.spec.ts`]
- [x] [Review][Patch] Backend `plan_tier` lacked `.strip()` (FE had it) — whitespace-padded paid tiers would 403. [`service.py`]
- [x] [Review][Patch] PPTX chips fail-open on `isError`/loading (layout-shift). Gated chips on `canUsePptx` (true only for resolved paid) — hide while loading/error. [`prompt-picker.tsx` / `ThreadWelcome.tsx`]
- [x] [Review][Patch] `?format=PPTX` bypassed presentation-mode detection (no lowercase). [`page.tsx`]
- [x] [Review][Patch] `rewritePresentationPromptToMarp` `\bpptx\b` rewrote `.pptx` filenames to `.marp` (invalid ext). Now `(?<!\.)\bpptx\b(?!\.)`. [`use-presentation-studio-entitlement.ts`]
- [x] [Review][Patch] `appliedPromptRef` never reset on submit → blocked later initial-prompt apply. Reset on send. [`Composer.tsx`]
- [x] [Review][Patch] URL-downgrade `useEffect` deps omitted `formatParam`/`rawInitialPrompt`. [`page.tsx`]
- [x] [Review][Defer] `PresentationStudioService.generate` raises `fastapi.HTTPException` (HTTP coupling) — deferred: in-contract for this story (spec asked 403); domain-exception refactor is follow-up. [`service.py`]
- [x] [Review][Defer] Self-hosted instances default `plan_tier=free` → PPTX blocked despite unlimited licensing. Product/licensing decision. [`service.py`]

**Rejected**
- `workspace_id=None` unit test "would IntegrityError in real DB" — `false`: the test only asserts the gate path under a mock session; no persist happens.
- `execute_generate_presentation` does not catch HTTPException — `false`: the tool wrapper is the intended catcher; REST route FastAPI-handles it; bubbling is the contract.
- Invalid-format coerced to pptx then 403 — now a `validation_failed` (patched).
