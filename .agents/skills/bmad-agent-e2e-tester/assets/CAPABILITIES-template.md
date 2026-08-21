# Capabilities

## Built-in

| Code | Name | Description | Source |
| :--- | :--- | :--- | :--- |
| [PREP] | prepare-infra | Prepare test infrastructure, seed/real accounts, cookies, and server lifecycle | `references/prepare-infra.md` |
| [UNIT] | run-unit-tests | Run Vitest unit tests across agents, client, scrapers, ai, and utils | `references/run-unit-tests.md` |
| [INTEG] | run-integration-tests | Run integration tests for Express API routes, database, A2A, and queues | `references/run-integration-tests.md` |
| [API] | run-real-api | Execute real HTTP API and MCP tool verification against live servers | `references/run-real-api.md` |
| [E2E] | run-e2e-browser | Control browsers via Playwright MCP or Chrome MCP for full E2E journeys | `references/run-e2e-browser.md` |
| [RECORD] | record-test-run | Persist test results, metrics, failure logs, and selector audits in sanctum | `references/record-test-run.md` |
| [TRIAGE] | triage-flaky-tests | Triage failures, detect selector drift, flakiness, and regressions | `references/triage-flaky-tests.md` |

## Learned

_Capabilities added by the owner over time. Prompts live in `capabilities/`._

| Code | Name | Description | Source | Added |
| :--- | :--- | :--- | :--- | :--- |

## How to Add a Capability

Tell me "I want you to be able to test X" and we'll create it together.
I'll write the prompt, save it to `capabilities/`, and register it here.
Load `references/capability-authoring.md` for the full creation framework.

## Supported Test Modes & Parameters

- `--feature <name>`: Target feature/suite (e.g. `agents`, `facebook`, `auth`, `scrapers`, `dashboard`, `x402`, `all`).
- `--mode <unit|integration|api-real|e2e-browser|full>`: Test execution tier.
- `--account <seed|real|cookie|guest>`: Infrastructure account auth profile.
- `--server <auto-start|existing>`: Express API server & MCP daemon lifecycle control.
- `--browser-engine <playwright|chrome>`: Browser automation MCP server selection.
