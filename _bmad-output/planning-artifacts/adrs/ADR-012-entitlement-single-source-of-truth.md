# ADR-012: Entitlement Plan IDs — Single Source of Truth

**Status:** Proposed
**Date:** 2026-05-02
**Deciders:** Winston (Architect), Product Owner
**Triggers:** Story 11-5 round-1 review; promoted to Story 11-6 T3

## Context

The Pro plan SKU list is currently duplicated in **3 places** in the codebase:

1. **`nowing_backend/app/config/__init__.py:317-348`** — `PLAN_LIMITS` dict mapping plan_id → token/page limits (`pro_monthly`, `pro_yearly`, `max_monthly`, `max_yearly`).
2. **`nowing_backend/app/schemas/stripe.py:14-17`** — `PlanId(str, Enum)` declaring the canonical 4 plan SKUs.
3. **`nowing_web/lib/entitlements.ts:30`** — `PRO_PLANS = ["pro_monthly", "pro_yearly", "max_monthly", "max_yearly"]` — frontend-side hardcoded array driving `hasProEntitlement()`.

**Failure mode:** When BE adds a new plan SKU (e.g. `team_yearly` for organisation tier), the FE `entitlements.ts` continues to deny it because the new SKU isn't in `PRO_PLANS`. Symptom: paying customers see redacted Pro content. Detection: depends on customer support; mean-time-to-detect ≈ days. Revenue loss: direct.

This is a **silent drift** vector — no compile-time check, no runtime alarm, no migration trigger.

## Decision

**Backend `PlanId` enum is the canonical source. Frontend consumes it via build-time codegen.**

Pipeline:

1. BE `nowing_backend/app/schemas/stripe.py:PlanId` is the single source of truth.
2. A build-time codegen step (run as part of `pnpm build` or as a `prebuild` script) reads `PlanId` and emits a generated TypeScript file:

   ```ts
   // nowing_web/lib/generated/plan-ids.ts (DO NOT EDIT — generated from BE schema)
   export const PRO_PLANS = ["pro_monthly", "pro_yearly", "max_monthly", "max_yearly"] as const;
   export type ProPlan = (typeof PRO_PLANS)[number];
   ```

3. `nowing_web/lib/entitlements.ts` imports from the generated file instead of declaring inline.
4. CI fails if `pnpm build` produces a `plan-ids.ts` that differs from the committed version (drift detector).

**Codegen mechanism options** (pick one in implementation):
- **Option A (recommended):** A small Python script `scripts/generate_plan_ids.py` reads `app/schemas/stripe.py` AST and emits TS. Runs in CI before FE typecheck.
- **Option B:** OpenAPI schema export from FastAPI → typed TS client (heavier; affects all schemas, not just plan IDs).
- **Option C:** BE exposes `GET /entitlements/plans` returning canonical list; FE fetches at app boot. Trade-off: runtime call (1 extra network round-trip per page load), graceful failure semantics needed.

**Recommendation:** Option A for minimum scope. Option B if future stories need broader BE→FE schema sharing.

## Consequences

### Positive
- **Eliminates silent drift** — adding a new plan in BE forces FE to either regenerate or fail CI.
- **Type-safe consumer** — FE code gets `ProPlan` literal type; mistypes caught at compile time.
- **Audit trail** — generated file under git; PR diff shows plan changes alongside BE schema changes.

### Negative
- **Build-step complexity** — `pnpm build` now requires Python or a parser to read BE schema. CI step ordering matters (BE schema → codegen → FE build).
- **Local dev friction** — developers running FE-only need to run codegen once or commit the generated file.

### Neutral
- `nowing_backend/app/config/__init__.py:PLAN_LIMITS` retains plan-specific business config (token limits) — that's BE-only and doesn't need FE sync. Codegen only exports the SKU list, not limits.

## Alternatives considered

1. **Status quo (3-way duplication)** — Rejected. Silent drift = silent revenue loss.
2. **Manual sync with PR template checkbox** — Rejected. Process control without enforcement = drift over time.
3. **JSON file as canonical source** (BE + FE both read it) — Rejected. Loses type safety; still requires FE build step to consume.
4. **Runtime fetch (Option C above)** — Considered. Simple to implement but adds a runtime dependency for an entirely static list. Defer unless plan list becomes dynamic (e.g. tenant-specific SKUs).

## Implementation pointers

- File: `nowing_web/lib/generated/plan-ids.ts` (new, gitignored OR committed with drift-detector CI check)
- File: `scripts/generate_plan_ids.py` (new) — parses `app/schemas/stripe.py` AST, emits TS.
- Modify `nowing_web/lib/entitlements.ts` to `import { PRO_PLANS, ProPlan } from "@/lib/generated/plan-ids";`
- Add `pnpm prebuild` script: `python scripts/generate_plan_ids.py > nowing_web/lib/generated/plan-ids.ts`
- CI: re-run codegen, fail if file diff non-empty.

## Owner

Story 11.6 Task T3 (Developer + DevOps for CI step).
