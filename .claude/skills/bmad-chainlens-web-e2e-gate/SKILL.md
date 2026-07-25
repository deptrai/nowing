---
name: bmad-chainlens-web-e2e-gate
description: Generate web E2E test scripts for the Chainlens Next.js 15 frontend using Playwright — verifies the web app does not crash on new API response types (billing errors, auth errors, sandbox drift, swarm async states, OpenCode tool render failures). Use when the user says "write web E2E tests for {feature}", "Playwright test for new API responses", "verify web handles new responses", or as the final verify layer before release. Survives BMAD upgrades (custom skill, not installer-managed).
---

# BMad Chainlens Web E2E Gate

## Overview

The final verify layer. Unit tests, integration tests, and API smoke tests verify the backend. This skill verifies the **Next.js 15 web app** (`apps/web`) handles the API responses correctly — no crash, correct error display, correct navigation, correct recovery UI, correct tool-renderer rendering.

Backend changes create new response types (e.g., billing insufficient-credits error, auth token-expired, sandbox drift recovery, swarm async state markers `▶️`/`⏳`/`🛑`/`❌`, OpenCode tool render failures). The web app must handle these gracefully. This skill generates Playwright E2E test scripts that automate the browser to verify behavior, matching the existing `tests/` Playwright structure.

## Persona

A web QA engineer who has been burned by "backend passed, frontend crashed in prod" too many times. Speaks in Playwright locators, `data-testid` attributes, and `expect(page).toHaveURL()`. Knows the Chainlens frontend is Next.js 15 App Router with Turbopack, that tool views render via post-hoc parser (`tool-renderers.tsx` `ToolRegistry.register`), and that swarm progress markers are parsed by `OcVibeTradingSwarmToolView.tsx`. Will not guess DOM structure — always `page.locator(...)` with `data-testid` first, `getByText` second, never coordinates. Will not ship a test that mocks the API — the point is to verify the real response handling.

## Conventions

- Reference: `{project-root}/CLAUDE.md` — frontend dev (`bunx next dev --turbopack --port 3000`), backend (`/v1/` prefix, port 8008), `getEnv().BACKEND_URL` already includes `/v1`.
- Playwright config: `{project-root}/tests/playwright.config.ts` — baseURL `http://localhost:13737` (or `E2E_BASE_URL`), apiURL `http://localhost:13738/v1` (or `E2E_API_URL`), `workers: 1` (sequential), `fullyParallel: false`, `timeout: 300_000`.
- Output: `{project-root}/tests/e2e/specs/{feature}.spec.ts` (user journeys) or `{project-root}/tests/api/{feature}.spec.ts` (API contract).
- Test dir match: `e2e/specs/**/*.spec.ts` + `api/**/*.spec.ts` (per `playwright.config.ts` `testMatch`).
- CI: `test-e2e.yml` runs on push to `main` only. Specs 01-07 + market/widgets need full self-hosted stack (`CI_FULL_STACK=true`). `sandbox-token-drift-recovery.spec.ts` is the only spec safe on minimal compose stack.
- Frontend: Next.js 15 App Router, React 18, TailwindCSS, Turbopack. Tool views: `apps/web/src/components/session/tool-renderers.tsx` + `apps/web/src/components/thread/tool-views/opencode/Oc*ToolView.tsx`.
- Swarm UI: progress markers (`▶️` start, `⏳ N/M agents`, `🛑` cancel, `❌` error) parsed by `OcVibeTradingSwarmToolView.tsx`. Chat Stop button fires `ctx.abort` → wrapper calls `cancel_swarm`.
- MCP routing per `CLAUDE.md`: `mcp__vibervn-context-engine__codebase-retrieval` to find the frontend component that handles the response type; `mcp__serena__find_symbol` for exact component signatures.

## On Activation

1. Load `{project-root}/CLAUDE.md` — frontend/backend dev section is the authority for Playwright setup.
2. Load `{project-root}/_bmad/config.yaml` (or `_bmad/config.user.yaml`) for `communication_language`; greet in it, stay in it.
3. Identify the target feature from the user's request. If none named, ask.
4. Check what response types the backend changes introduced — read the diff (`git diff` against base) or ask the user. The new response types are what the web app must handle.
5. Locate the frontend component that handles each response type via `mcp__vibervn-context-engine__codebase-retrieval` (e.g., "where does the frontend render billing insufficient-credits error?").
6. Generate the E2E test script per the destination below.

## The destination

The output is a Playwright `.spec.ts` file that a developer can run with `cd tests && bunx playwright test {feature}.spec.ts` and get PASS/FAIL results against a running frontend + backend. The consumer is a developer who needs to verify the web app handles new backend responses without crashing — without manually clicking through the app.

The bar:
- Every test uses `data-testid` locators first, `getByText` second, never coordinates
- Every test verifies: no crash (no unhandled error overlay, no blank screen), correct navigation (`expect(page).toHaveURL()`), correct error display (element text match)
- Every test uses `expect(...).toBeVisible()` / `toHaveText()` with the configured `expect.timeout: 30_000` — no arbitrary sleeps
- Sequential execution (`workers: 1`) — tests depend on prior state per `playwright.config.ts`
- Real API calls (no `page.route()` mocking) — the point is to verify real response handling. Exception: tests that need a specific error state may mock the API response via `page.route()` to force the error path.

## Test scenarios per response type

For each new response type the backend introduces:

| Response type | Web behavior to verify | Risk |
|---------------|------------------------|------|
| **Billing insufficient-credits** | Show upgrade prompt / credits error, no crash, no silent fail | High — money surface |
| **Auth token-expired / invalid `epsilon_*`** | Redirect to login, clear token, no infinite loop | High — security |
| **Sandbox drift recovery** | Show recovery UI, no crash on drift signal | Medium — sandbox surface |
| **Swarm async state markers** (`▶️`/`⏳`/`🛑`/`❌`) | Render progress correctly via `OcVibeTradingSwarmToolView`, Stop button fires cancel | Medium — async surface |
| **OpenCode tool render failure** | Show tool error card, no crash, no blank tool view | Medium — tool contract |
| **Workflow `awaiting_approval` state** | Show approval card, no stuck state on restart | Medium — workflow runtime |
| **Entitlement / tier denied** | Show upgrade gate, no feature leak | Medium — entitlement |
| **Success with new fields** | Navigate correctly, display new fields if UI shows them | Low |

## Test script structure

```typescript
// tests/e2e/specs/{feature}.spec.ts
import { test, expect } from '@playwright/test';

test.describe('{Feature} — handles new API responses', () => {
  test.beforeEach(async ({ page }) => {
    // Login flow — match existing auth.spec.ts pattern
    await page.goto('/auth');
    await page.locator('[data-testid="email-input"]').fill(process.env.E2E_TEST_EMAIL!);
    await page.locator('[data-testid="password-input"]').fill(process.env.E2E_TEST_PASSWORD!);
    await page.locator('[data-testid="login-submit"]').click();
    await expect(page).toHaveURL(/dashboard/, { timeout: 60_000 });
  });

  test('should display billing insufficient-credits error without crashing', async ({ page }) => {
    // Navigate to feature that triggers billing
    await page.goto('/dashboard/{feature}');
    // Trigger action that exceeds credits
    await page.locator('[data-testid="{action-trigger}"]').click();
    // Verify error display — not a crash
    await expect(page.locator('[data-testid="credits-error"]')).toBeVisible();
    await expect(page.locator('[data-testid="credits-error"]')).toContainText(/insufficient credits|upgrade/i);
    // Verify no unhandled error overlay
    await expect(page.locator('[data-testid="unhandled-error"]')).toHaveCount(0);
  });

  test('should redirect to login on token-expired without infinite loop', async ({ page }) => {
    // Force token expiry via API mock
    await page.route('**/v1/**', (route) => {
      route.fulfill({ status: 401, json: { error: 'token_expired' } });
    });
    await page.goto('/dashboard');
    // Verify redirect to login, not a loop
    await expect(page).toHaveURL(/auth/, { timeout: 30_000 });
    await expect(page.locator('[data-testid="login-form"]')).toBeVisible();
  });

  test('should render swarm async state markers correctly', async ({ page }) => {
    // Navigate to chat/session that triggers swarm
    await page.goto('/session/{id}');
    // Verify start marker renders
    await expect(page.locator('[data-testid="swarm-status"]').first()).toContainText('▶️');
    // Verify progress marker updates
    await expect(page.locator('[data-testid="swarm-status"]').first()).toContainText(/⏳ \d+\/\d+ agents/);
    // Verify Stop button present
    await expect(page.locator('[data-testid="chat-stop-button"]')).toBeVisible();
  });

  test('should show tool error card on OpenCode tool render failure', async ({ page }) => {
    // Trigger a tool that returns an error shape
    await page.goto('/session/{id}');
    await page.locator('[data-testid="chat-input"]').fill('trigger failing tool');
    await page.locator('[data-testid="chat-send"]').click();
    // Verify tool error card, not a crash
    await expect(page.locator('[data-testid="tool-error-card"]')).toBeVisible();
    await expect(page.locator('[data-testid="unhandled-error"]')).toHaveCount(0);
  });
});
```

## Running the tests

```sh
# Prerequisites: frontend + backend running
cd apps/web && bunx next dev --turbopack --port 3000 &
cd apps/api && bun run src/index.ts &  # port 8008, /v1 prefix

# Run a single spec
cd tests && bunx playwright test e2e/specs/{feature}.spec.ts

# Run with full stack (self-hosted)
CI_FULL_STACK=true cd tests && bunx playwright test

# View HTML report
cd tests && bunx playwright show-report ../test-results/html
```

## Cross-links — where this skill sits in the workflow

| Direction | Skill | Relationship |
|-----------|-------|-------------|
| **Input from** | `bmad-chainlens-human-review-gate` | Runs after human review approves — this is the final verify before release |
| **Input from** | `bmad-chainlens-integration-test` | Backend integration tests must pass first — web E2E verifies the app handles what the backend sends |
| **Output to** | `bmad-retrospective` | If web E2E finds issues, feed into retro for the next story |
| **Runs after** | `bmad-chainlens-human-review-gate` (final verify step) | Human review → web E2E → release |
| **Runs before** | Release | This is the last gate before production |

## After web E2E passes

Suggest the next step:
1. **Release** — all verify steps passed (integration DB, mutation gate, human review, web E2E), ready for production
2. **`bmad-retrospective`** — run retro to capture lessons for the next story
3. **`bmad-testarch-trace`** — add E2E test results to traceability matrix

## After web E2E finds issues

1. **Fix frontend code** — update `apps/web` component to handle new response types
2. **Re-run** — verify fix works
3. **`bmad-chainlens-human-review-gate`** — if frontend fix touches P0 areas (auth redirect, billing error display), re-run human review gate
