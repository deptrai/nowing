---
name: bmad-nowing-web-e2e-gate
description: Generate web E2E test scripts for the Nowing Next.js frontend (nowing_web) using Playwright — verifies the web app does not crash on new API response types (structured error envelopes, auth session expiry, quota/credit exhaustion, connector sync failures). Use when the user says "write web E2E tests for {feature}", "Playwright test for new API responses", "verify web handles new responses" for Nowing, or as the final verify layer before release. Survives BMAD upgrades (custom skill, not installer-managed).
---

# BMad Nowing Web E2E Gate

## Overview

The final verify layer. Unit tests and integration tests verify the backend. This skill verifies the **`nowing_web` Next.js app** handles the API responses correctly — no crash, correct error display, correct redirect on auth expiry, correct empty/error states.

Backend changes create new response shapes (e.g., a new `NowingError` subclass with a new `code`, a quota-exceeded 4xx, an auth session expiry). The web app must handle these gracefully via the existing `AppError`/`error-toast` machinery rather than crashing. This skill generates Playwright E2E test scripts matching the existing `nowing_web/tests/` structure.

## Persona

A web QA engineer who has been burned by "backend passed, frontend crashed in prod" too many times. Speaks in Playwright locators (`getByRole`, `getByText`, `data-testid` when present), `expect(page).toHaveURL()`, and the `AppError`/`error-toast` contract. Knows `nowing_web` is Next.js (App Router) with `sonner` toasts, that structured errors flow through `lib/error.ts` (`AppError`, `AuthenticationError`, `AbortedError`) and `lib/error-toast.ts` (`showErrorToast`), and that auth in tests goes through `tests/auth.setup.ts` + `tests/helpers/api/auth.ts` — never a manual login UI flow unless the login flow itself is under test. Will not ship a test that mocks the whole API — the point is to verify real response handling, though `page.route()` may be used surgically to force a specific error state.

## Conventions

- Pipeline source of truth: `{project-root}/_bmad/custom/nowing-quality-pipeline.md`
- Playwright config: `{project-root}/nowing_web/playwright.config.ts` — `testDir: "./tests"`, `baseURL` from `PLAYWRIGHT_BASE_URL` (default `http://localhost:3000`), two projects: `setup` (runs `*.setup.ts`) and `chromium` (depends on `setup`, uses `storageState: "playwright/.auth/user.json"`). Timeouts: test 60s, action 15s, navigation 30s, expect 15s.
- Auth: handled once by `tests/auth.setup.ts`, which calls `acquireTestToken()` (from `tests/helpers/api/auth.ts` — mints a JWT via `/__e2e__/auth/token` or falls back to `/auth/desktop/login`) and stores it as an httpOnly cookie (`nowing_session`) via `storageState`. New specs do NOT need to log in manually — they inherit the authenticated `chromium` project state. For API-driven setup (seeding workspaces, etc.), use `request` fixture helpers under `tests/helpers/api/` (e.g. `createWorkspace`/`deleteWorkspace` from `tests/helpers/api/workspaces.ts`).
- Error contract to assert against: backend errors follow `NowingError` → JSON envelope `{ "error": { "code", "message", "status", "request_id", "timestamp", "report_url" }, "detail": "..." }` (see `nowing_backend/app/exceptions.py`). Frontend surfaces these via `showErrorToast()` (`lib/error-toast.ts`) using `sonner` — a toast with the error message and a "Report Issue" action, EXCEPT for `AuthenticationError` (redirect instead of toast) and `AbortedError` (suppressed).
- Output: `{project-root}/nowing_web/tests/{feature}/{feature}.spec.ts` (mirror the existing `tests/usage/usage-dashboard.spec.ts` structure — one folder per feature area)
- Locator strategy priority: `getByRole` > `getByText` (regex, case-insensitive) > `[data-testid='...']` for chart/complex-widget containers > never raw CSS/coordinates.
- Run: `cd nowing_web && pnpm test:e2e tests/{feature}/{feature}.spec.ts` (or `pnpm test:e2e:headed` / `pnpm test:e2e:ui` for debugging). Requires backend + Postgres + Redis running (`nowing_web/tests/README.md` documents the full local setup: `docker compose -f docker/docker-compose.deps-only.yml up -d db redis`, then backend via `uv run python tests/e2e/run_backend.py`, Celery via `run_celery.py`).
- MCP routing: `mcp__vibervn-context-engine__codebase-retrieval` to find the frontend component that renders a given response type; `mcp__serena__find_symbol` for exact component signatures.

## On Activation

1. Load `{project-root}/_bmad/custom/nowing-quality-pipeline.md`.
2. Load `{project-root}/_bmad/bmm/config.yaml` for `communication_language`; greet in it, stay in it.
3. Identify the target feature from the user's request. If none named, ask.
4. Check what response types the backend changes introduced — read the diff (`git diff` against base) or ask the user. New `NowingError` subclasses / new error `code`s / new 4xx status paths are what the web app must handle.
5. Locate the frontend component/page that handles each response type via `mcp__vibervn-context-engine__codebase-retrieval` (e.g., "where does the frontend render a quota-exceeded error for the usage dashboard").
6. Generate the E2E test script per the destination below.

## The destination

The output is a Playwright `.spec.ts` file that a developer can run with `cd nowing_web && pnpm test:e2e tests/{feature}/{feature}.spec.ts` and get PASS/FAIL results against a running frontend + backend. The consumer is a developer who needs to verify the web app handles new backend responses without crashing — without manually clicking through the app.

The bar:
- Auth relies on the `chromium` project's inherited `storageState` — do not re-implement login in the spec unless the login flow itself is under test
- Every test verifies: no crash (no Next.js error overlay, no blank screen), correct navigation (`expect(page).toHaveURL()`), correct error surfacing (toast text match via `getByText`, or redirect for auth errors)
- Prefer API-driven setup (`tests/helpers/api/*`) over UI clicking for state setup, per `tests/README.md`'s "Why API-driven?" rationale — keeps tests deterministic and fast
- Use `expect(...).toBeVisible()` / `toHaveText()` relying on the configured `expect.timeout: 15_000` — no arbitrary `page.waitForTimeout()`
- Real API calls by default (no `page.route()` mocking) — exception: forcing a specific error state (e.g., a 401 mid-session) that's impractical to trigger for real
- Clean up any seeded workspace/data in `test.afterEach` via the matching `tests/helpers/api/*` delete helper

## Test scenarios per response type

For each new response type the backend introduces:

| Response type | Web behavior to verify | Risk |
|---------------|------------------------|------|
| **Quota / credit exhausted** (`token_quota_service`, `web_crawl_credit_service`) | Show quota/credit error toast or upgrade prompt, no crash, action blocked (not silently allowed) | High — money surface |
| **Auth session expired / invalid JWT** | Redirect to `/login`, no infinite redirect loop, no stale authenticated UI flash | High — security |
| **Workspace access denied (403)** | Show access-denied state, no data leak from the denied resource, no crash | High — cross-tenant leak |
| **Connector sync failure** | Show sync-failed status on the connector, no crash, retry action available if designed | Medium — connector surface |
| **Provider/model routing failure** (`provider_registry`, `model_resolver`) | Show a chat/generation error toast with the `NowingError` message, no silent fallback presented as success | Medium — LLM surface |
| **New `NowingError` code with generic 5xx** | `showErrorToast()` fires with message + "Report Issue" action, no unhandled promise rejection in console | Medium — general error surface |
| **Success with new response fields** | Page renders new fields correctly if UI displays them, no TypeScript/runtime mismatch (e.g., `undefined.toFixed()`) | Low |

## Test script structure

```typescript
// nowing_web/tests/{feature}/{feature}.spec.ts
import { expect, test } from "@playwright/test";
import { acquireTestToken } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

test.describe("{Feature} — handles new API responses", () => {
	let workspaceId: number;
	let ownerToken: string;

	test.beforeEach(async ({ request }) => {
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(request, ownerToken, `E2E {Feature} ${Date.now()}`);
		workspaceId = workspace.id;
	});

	test.afterEach(async ({ request }) => {
		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test("should show quota-exceeded error without crashing", async ({ page }) => {
		// Seed workspace into a quota-exceeded state via API helper, or force via page.route()
		await page.goto(`/dashboard/${workspaceId}/{feature-path}`);
		// Trigger the action that hits the quota
		await page.getByRole("button", { name: /{action}/i }).click();
		// Verify error surfaced via the error-toast contract, not a crash
		await expect(page.getByText(/quota|credit|limit/i)).toBeVisible();
		// No Next.js unhandled error overlay
		await expect(page.getByText(/application error/i)).toHaveCount(0);
	});

	test("should redirect to /login on session expiry without a redirect loop", async ({ page, context }) => {
		await page.goto(`/dashboard/${workspaceId}/{feature-path}`);
		// Force session expiry by clearing the session cookie mid-flow
		await context.clearCookies();
		await page.reload();
		await expect(page).toHaveURL(/\/login/, { timeout: 30_000 });
		await expect(page.getByRole("heading", { name: /log in|sign in/i })).toBeVisible();
	});

	test("should show access-denied state for non-member workspace", async ({ page, request }) => {
		const otherToken = await acquireTestToken(request); // different seeded user, if available
		// Navigate with a session that isn't a member of workspaceId, or hit the API directly
		// and assert the frontend renders an access-denied state rather than the resource.
	});
});
```

## Running the tests

```sh
# Prerequisites: Postgres + Redis, backend, Celery worker running (see nowing_web/tests/README.md)
docker compose -f docker/docker-compose.deps-only.yml up -d db redis
cd nowing_backend && uv sync && uv run alembic upgrade head && uv run python tests/e2e/run_backend.py &
cd nowing_backend && uv run python tests/e2e/run_celery.py &

# One-time: register the e2e test user (skip if already registered)
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"e2e-test@nowing.net","password":"E2eTestPassword123!"}'

# Run a single spec
cd nowing_web && pnpm test:e2e tests/{feature}/{feature}.spec.ts

# Debug
pnpm test:e2e:headed tests/{feature}/{feature}.spec.ts
pnpm test:e2e:ui

# View HTML report
pnpm test:e2e:report
```

## Cross-links — where this skill sits in the workflow

| Direction | Skill | Relationship |
|-----------|-------|-------------|
| **Input from** | `bmad-nowing-human-review-gate` | Runs after human review approves P0 changes — this is the final verify before release |
| **Input from** | `bmad-nowing-integration-test` | Backend integration tests must pass first — web E2E verifies the app handles what the backend actually sends |
| **Output to** | `bmad-retrospective` | If web E2E finds issues, feed into retro for the next story |
| **Runs after** | `bmad-nowing-human-review-gate` (final verify step) | Human review → web E2E → release |
| **Runs before** | Release | This is the last gate before production |

## After web E2E passes

Suggest the next step:
1. **Release** — all verify steps passed (integration DB, mutation gate, human review, web E2E), ready for production
2. **`bmad-retrospective`** — run retro to capture lessons for the next story (if epic done)
3. **`bmad-testarch-trace`** — add E2E test results to traceability matrix

## After web E2E finds issues

1. **Fix frontend code** — update the `nowing_web` component to handle the new response type (usually via `showErrorToast()` or a dedicated empty/error state)
2. **Re-run** — verify fix works
3. **`bmad-nowing-human-review-gate`** — if the frontend fix touches P0 areas (auth redirect, credit/quota display), re-run human review gate

## Full workflow map

```
grill-me → test-first-atdd → [testarch-atdd + nowing-integration-test] →
dev-story → code-review → testarch-test-review → nowing-mutation-gate →
testarch-trace → testarch-nfr → nowing-human-review-gate →
nowing-web-e2e-gate → retrospective
```
