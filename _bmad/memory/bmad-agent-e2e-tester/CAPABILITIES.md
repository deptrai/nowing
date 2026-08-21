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

## Testing Modes & Toolsets

- `unit`: Fast Vitest unit test execution (`tests/agents/`, `tests/client/`, `tests/ai/`, `tests/utils/`)
- `integration`: Express API route tests, Prisma DB transactions, A2A communication (`tests/api/`, `tests/a2a/`)
- `api-real`: Live HTTP endpoint verification on `:3000` and MCP tool checks on `:3001`
- `e2e-browser`: Interactive browser automation with Playwright MCP or Chrome MCP
- `full`: Complete end-to-end pipeline (Infra -> Unit -> Integration -> API -> Browser E2E -> Record)
