---
story: 8-13-posthog-analytics
gate_type: story
date: '2026-08-04'
evaluator: Devin TEA
workflow: testarch-trace v5.0
---

# Traceability Matrix & Gate Decision — Story 8.13 PostHog Product Analytics

**Target:** Story 8.13 — PostHog Product Analytics privacy hardening
**Date:** 2026-08-04
**Coverage Oracle:** Story acceptance criteria (`_bmad-output/implementation-artifacts/8-13-posthog-analytics.md`)
**Oracle Confidence:** high
**Oracle Sources:**
- `_bmad-output/implementation-artifacts/8-13-posthog-analytics.md`
- Changed files: `nowing_web/lib/connector-telemetry.ts`, `nowing_web/app/global-error.tsx`
- Existing tests: `nowing_web/lib/posthog/events.selfcheck.ts`, `nowing_web/tests/posthog-privacy-smoke.spec.ts`

---

## Coverage Summary

| Priority | Total Criteria | FULL | PARTIAL | NONE | Status |
|---|---|---|---|---|---|
| P0 | 3 | 1 | 2 | 0 | ⚠️ CONCERNS |
| P1 | 3 | 0 | 3 | 0 | ⚠️ CONCERNS |
| **Total** | **6** | **1** | **5** | **0** | **⚠️ CONCERNS** |

- ✅ PASS — meets threshold
- ⚠️ CONCERNS — below threshold but not a hard blocker
- ❌ FAIL — blocker

P0 criteria: AC-4 (Privacy/secrets), AC-5 (Error capture scoping), AC-6 (Opt-out/self-host).
P1 criteria: AC-1 (Init & pageview), AC-2 (User identification), AC-3 (Key action events).

---

## Detailed Mapping

### AC-1: Initialization & pageview (P1)

- **Coverage:** PARTIAL ⚠️
- **Evidence:**
  - `nowing_web/instrumentation-client.ts` sets `capture_pageview: "history_change"`, `capture_pageleave: true`, and guards `posthog.init` with `NEXT_PUBLIC_POSTHOG_KEY`.
  - `tests/posthog-privacy-smoke.spec.ts` loads the page and checks for PostHog-related console errors.
- **Gaps:**
  - No dedicated assertion that `posthog.init` is called with pageview settings.
  - No E2E that verifies pageview events are captured on navigation.
- **Recommendation:** Add a unit/selfcheck for `instrumentation-client.ts` or a Playwright test that asserts `posthog.capture('$pageview')` is called.

### AC-2: User identification & superuser anonymization (P1)

- **Coverage:** PARTIAL ⚠️
- **Evidence:**
  - `lib/posthog/events.selfcheck.ts` asserts `identifyUser` omits `email`/`name` for superusers and includes them for non-superusers.
  - `components/providers/PostHogIdentify.tsx` exists and uses `identifyUser`.
- **Gaps:**
  - No component/E2E test for `PostHogIdentify.tsx` with real `currentUserAtom` values.
  - No test verifying `posthog.reset()` on public routes.
- **Recommendation:** Add unit test for `PostHogIdentify.tsx` or extend selfcheck to call the component render path.

### AC-3: Key action event capture (P1)

- **Coverage:** PARTIAL ⚠️
- **Evidence:**
  - `lib/posthog/events.selfcheck.ts` covers `trackWorkspaceCreated`, `trackWorkspaceInviteAccepted`, `trackWorkspaceInviteDeclined`, `trackWorkspaceUserAdded`, and `trackConnectorEvent` payload shapes.
- **Gaps:**
  - `trackYouTubeImport` and other key actions are not exercised.
  - Call-site updates (`CreateWorkspaceDialog`, invite pages, team content) were not changed or verified in this session.
- **Recommendation:** Extend selfcheck to all `track*` helpers with public call sites; verify call-sites compile without passing workspace content.

### AC-4: Privacy / secrets (P0)

- **Coverage:** FULL ✅
- **Evidence:**
  - `lib/posthog/events.selfcheck.ts` asserts `workspace_created` has no `name`, `workspace_invite_*` has no `workspace_name`, `connector_setup_started` has no `connector_title`.
  - `lib/connector-telemetry.ts` removes `connector_title` from `ConnectorTelemetryMeta` and `trackConnectorEvent` payload.
  - `bmad-code-review` (blind hunter + edge case hunter) passed, with privacy concerns triaged as pre-existing/out-of-diff.
  - `tests/posthog-privacy-smoke.spec.ts` and Playwright MCP smoke confirm no PostHog/analytics console errors with an empty `NEXT_PUBLIC_POSTHOG_KEY`.
- **Gaps:** None for the changed files.
- **Recommendation:** None.

### AC-5: Error capture scoping (P0)

- **Coverage:** PARTIAL ⚠️
- **Evidence:**
  - `app/global-error.tsx` now lazy-loads `posthog-js` and calls `posthog.captureException` inside `try/catch`; `error.tsx` and `dashboard/error.tsx` already follow this pattern.
  - `lib/posthog/events.selfcheck.ts` verifies `safeCapture` swallows thrown `posthog.capture` errors.
- **Gaps:**
  - `lib/apis/base-api.service.ts` was not modified in this session; it may still capture 4xx client errors.
  - No test verifying only 5xx/network failures are reported to PostHog.
- **Recommendation:** Update `base-api.service.ts` `catch` block to use a `captureApiException` helper limited to 5xx/network; add unit test.

### AC-6: Opt-out / self-host (P0)

- **Coverage:** PARTIAL ⚠️
- **Evidence:**
  - `.env.local` has `NEXT_PUBLIC_POSTHOG_KEY=` empty.
  - Playwright smoke (`/dashboard` and `/login`) loads without PostHog-related console errors when the key is empty.
  - `app/global-error.tsx` lazy `import('posthog-js')` will fail silently if ad-blocked or disabled.
- **Gaps:**
  - `lib/posthog/server.ts` still throws if `NEXT_PUBLIC_POSTHOG_KEY` is missing (per story file) and was not changed.
  - `instrumentation.ts` does not handle a no-op `PostHogClient` return.
  - No dedicated test that `posthog` is `undefined`/no-op when key is empty.
- **Recommendation:** Change `lib/posthog/server.ts` to return a no-op client when key is empty; add unit test.

---

## Quality Assessment

### Tests Passing Quality Gates

- `lib/posthog/events.selfcheck.ts` — passes, deterministic, no external dependencies.
- `tests/posthog-privacy-smoke.spec.ts` — passes when run with Playwright MCP smoke.
- `pnpm tsc --noEmit` — passes.
- `bmad-code-review` — PASS.

### Tests with Issues

- `tests/posthog-api-smoke.spec.ts` — not executed because E2E backend `nowing_e2e_test` DB is in a partially-migrated state. Status: ⚠️ evidence gap, not a code issue.

### Coverage by Test Level

| Test Level | Tests | Criteria Covered |
|---|---|---|
| E2E (Playwright) | `posthog-privacy-smoke.spec.ts` | AC-1, AC-4, AC-6 (partial) |
| Selfcheck | `lib/posthog/events.selfcheck.ts` | AC-2, AC-3, AC-4, AC-5 (partial) |
| Code review | `bmad-code-review` | AC-4, AC-5 (partial) |
| Typecheck | `tsc --noEmit` | All changed TS files compile |

---

## Traceability Recommendations

### Immediate (before considering story fully verified)

1. **AC-5 gap** — Update `lib/apis/base-api.service.ts` to scope PostHog error capture to 5xx/network failures only.
2. **AC-6 gap** — Make `lib/posthog/server.ts` return a no-op client when `NEXT_PUBLIC_POSTHOG_KEY` is empty, and guard `instrumentation.ts`.

### Short-term (this milestone)

1. Add E2E for `/status` or `/run` key actions or extend `events.selfcheck.ts` to cover all active `track*` helpers.
2. Add unit test for `PostHogIdentify.tsx` superuser anonymization.

### Long-term (backlog)

1. Migrate outcome events to a backend product-analytics module when it exists, removing optimistic frontend events.

---

## Phase 2: Quality Gate Decision

**Gate Type:** story
**Decision Mode:** manual

### Evidence Summary

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| P0 coverage | 100% | 1/3 FULL, 2/3 PARTIAL | ❌ below threshold |
| P1 coverage | ≥90% | 0/3 FULL, 3/3 PARTIAL | ⚠️ below threshold |
| P0 test pass rate | 100% | 100% (selfcheck + smoke + tsc passed) | ✅ |
| Overall test pass rate | ≥95% | N/A (some tests not run) | ⚠️ |
| Security issues (PII in PostHog) | 0 | 0 for changed code; pre-existing PII in unmodified helpers | ⚠️ |
| Flaky tests | 0 | 0 | ✅ |

### Gate Decision: ⚠️ CONCERNS

**Rationale:**
- The **changed** privacy fix (`connector_title` removal) and **error-boundary lazy-load** are correct and covered by selfcheck + privacy smoke + code review.
- However, **AC-5 (error capture scoping)** and **AC-6 (opt-out)** remain partially unimplemented in the files that matter (`base-api.service.ts`, `posthog/server.ts`, `instrumentation.ts`).
- **AC-1, AC-2, AC-3** are P1 and have only partial coverage; this is acceptable for a focused privacy-hardening diff but means the full story is not yet release-ready without the above two P0 gaps.

**Residual risk (medium):**
- If `base-api.service.ts` continues to send 4xx errors to PostHog, product analytics may include expected client-side failures and noise.
- If `posthog/server.ts` throws on self-hosted builds with no key, server-side error capture can crash the build.

### Next Steps

1. Fix AC-5 and AC-6 gaps (see Immediate recommendations).
2. Re-run `pnpm tsc --noEmit` and `events.selfcheck.ts`.
3. Re-run Playwright MCP privacy smoke.
4. Re-run this trace gate to move to **PASS**.
