---
stepsCompleted: ['step-03-scaffold-framework', 'step-04-docs-and-scripts', 'step-05-validate-and-summary']
lastStep: 'step-05-validate-and-summary'
lastSaved: '2026-05-01'
---

# Test Framework Setup Progress

## Status: Step 04 Complete

## Completed Files

### Support Layer
- `playwright/global-setup.ts` — auth-session v4, `storageDir` (not `authStoragePath`)
- `playwright/support/auth/auth-provider.ts` — full AuthProvider interface, `/auth/jwt/login` form-encoded
- `playwright/support/merged-fixtures.ts` — `base.extend<AuthFixtures>(...)` pattern; no `never` collapse
- `playwright/support/custom-fixtures.ts` — `testUser` ephemeral fixture
- `playwright/support/factories/thread-factory.ts` — chat thread factory
- `playwright/support/factories/user-factory.ts` — user factory (create + cleanup)
- `playwright/.env.test.example` — env var documentation

### Sample Tests
- `playwright/e2e/sample.spec.ts` — demonstrates authToken, apiRequest, interceptNetworkCall

### Backend
- `nowing_backend/tests/utils/factories.py` — make_user, make_search_space, make_connector_document
- `nowing_backend/tests/unit/test_sample.py` — unit test patterns

### Documentation & Scripts (Step 04)
- `playwright/README.md` — updated: correct port (4998), correct auth-provider description, correct fixtures table
- `package.json` scripts — already complete: `test:e2e`, `test:e2e:headed`, `test:e2e:debug`, `test:e2e:ui`, `test:e2e:report`
- `nowing_backend/Makefile` — already complete: `test`, `test-unit`, `test-integration`, `test-api`, `test-cov`, `test-fast`

## Key Fixes Applied

### merged-fixtures.ts
- `base.extend<AuthFixtures>(createAuthFixtures())` — typed extension avoids `never` in mergeTests
- `@ts-expect-error` suppresses runtime-correct context/page override conflict

### auth-provider.ts
- Endpoint: `/auth/jwt/login` (FastAPI-Users), form-encoded with `username` field
- Full v4 interface: extractToken, extractCookies (→[]), clearToken (noop), isTokenExpired (→true)

### Spec files
- `log.step("msg")` → `log({ level: "step", message: "msg" })`
- `recurse(cmd, options)` → `recurse(cmd, predicate, options)`
- `route` callbacks typed as `import("@playwright/test").Route`
- `intervals: [...]` → `interval: N`

## TypeScript Status
- All playwright/**/*.ts: 0 errors ✅
- Pre-existing errors in nowing_web app code are unrelated
