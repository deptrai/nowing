---
name: test-e2e-browser
description: 'Drive a real browser through Playwright MCP to smoke-test an existing web feature end to end. Use when the user asks to test browser E2E, validate a UI flow, or reproduce a frontend issue in the browser.'
---

# Browser E2E Testing with Playwright MCP

Use this skill to test Nowing through a real browser session driven by the Playwright MCP tools.

## Required capability

1. Check whether Playwright MCP browser tools are available in the current session.
2. If they are unavailable, state that browser automation is blocked by the missing MCP server/tool. Do not claim that CLI Playwright execution is MCP-driven.
3. Only use the Playwright CLI when the user explicitly asks for the CLI fallback.

## Safety and scope

- Prefer the local development stack: frontend at `http://localhost:3000` and backend at `http://localhost:8000`.
- Use a dedicated test user and an isolated test workspace. Never use production data or credentials.
- Create only data needed for the test and remove it after validation.
- Start with the smallest user-visible journey that proves the requested behavior.
- Use stable locators in this order: accessibility id/role, explicit test id, label, and text. Avoid XPath unless no stable alternative exists.

## Browser workflow

1. **Check readiness**
   - Confirm the frontend and backend are reachable.
   - Confirm a test user can authenticate.
   - Record the base URL, workspace, and scenario under test.

2. **Inspect before interacting**
   - Use the browser/page inspection tool to discover current controls and their accessible labels.
   - Do not guess selectors from source code when the live page can be inspected.

3. **Execute the journey**
   - Navigate to the required page.
   - Authenticate through the approved local test mechanism.
   - Perform the minimum interactions needed to cover the requested behavior.
   - Assert visible UI state and, where useful, verify the corresponding local API result.

4. **Collect evidence**
   - Capture a screenshot when the user-facing outcome or a failure needs evidence.
   - Report each assertion as pass, fail, or blocked.
   - Include the failing step, observed state, and relevant browser/tool error for failures.

5. **Clean up**
   - Delete temporary test records and isolated workspaces through the local API or UI.
   - State explicitly what was cleaned up and any leftovers.

## Nowing defaults

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- Browser suite: `nowing_web/tests/`
- Playwright configuration: `nowing_web/playwright.config.ts`
- Local backend E2E entrypoint: `nowing_backend/tests/e2e/run_backend.py`

## Definition of done

A browser E2E result is complete only when it includes:

- the tested scenario and environment,
- browser-level evidence for the requested user outcome,
- API or persisted-state confirmation when relevant,
- cleanup status, and
- an explicit blocker if Playwright MCP was unavailable.
