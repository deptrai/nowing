# Curated Memory

## Ratified Quality Gates Matrix

| Test Layer | Target Metric | Ratified Baseline | Gate Threshold | Ratified Date | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Unit Tests** | Pass Rate | 100% | 100% | 2026-08-21 | Vitest unit suites (agents, client, ai, utils) |
| **Integration Tests** | Pass Rate | 100% | 100% | 2026-08-21 | Express API routes, A2A protocol, DB models |
| **Real API** | P95 Response Latency | < 120ms | $\le 500\text{ms}$ | 2026-08-21 | Local Express API & MCP endpoints |
| **Browser E2E** | Console Errors | 0 | 0 errors | 2026-08-21 | Playwright/Chrome MCP UI audits |
| **Browser E2E** | Flow Completion | 100% | 100% | 2026-08-21 | Dashboard navigation & script injection |

## Historical Test Runs Summary

| Date & Time | Feature / Suite | Mode | Infra Profile | Passed / Total | Status | Duration | Notes / Failure Summary |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| _No runs recorded yet_ | - | - | - | - | - | - | - |

## Active Flaky Tests & Broken Selector Watchlist
- _No active flaky tests recorded._

## Infrastructure & Account Profiles
- **Seed Environment:** SQLite/Postgres test database + Prisma seed (`prisma/seed.js`).
- **Real Environment:** Twitter session cookies (`XACTIONS_SESSION_COOKIE`), session validator (`src/client/auth/sessionValidator.js`).
- **Server Ports:** Express API `:3000`, MCP Daemon `:3001`.
