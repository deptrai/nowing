# Playwright E2E Test Framework

## Setup

### 1. Install dependencies

```bash
pnpm add -D @playwright/test @seontechnologies/playwright-utils
pnpm exec playwright install chromium
```

### 2. Configure environment

```bash
cp .env.test.example .env.test
# Edit .env.test with your local values
```

Required vars:
- `BASE_URL` — app URL (default: `http://localhost:4998`)
- `API_URL` — backend URL (default: `http://localhost:8000`)
- `TEST_USER_EMAIL` / `TEST_USER_PASSWORD` — test account credentials

### 3. Auth session init

Auth sessions are cached in `playwright/auth-sessions/` (gitignored). They are generated automatically on first run via `global-setup.ts`.

---

## Running Tests

| Command | Description |
|---|---|
| `pnpm test:e2e` | Run all E2E tests (headless) |
| `pnpm test:e2e:headed` | Run with visible browser |
| `pnpm test:e2e:debug` | Open Playwright Inspector |
| `pnpm test:e2e:ui` | Open Playwright UI mode |
| `pnpm test:e2e:report` | View last HTML report |

Run a specific test file:
```bash
pnpm test:e2e playwright/e2e/auth.spec.ts
```

Run by tag:
```bash
pnpm test:e2e --grep "@smoke"
```

---

## Architecture

```
playwright/
├── auth-sessions/          # Cached auth state (gitignored)
├── e2e/                    # Test files (*.spec.ts)
│   └── auth.spec.ts
├── reports/                # HTML + JUnit reports (gitignored)
├── support/
│   ├── auth/
│   │   └── auth-provider.ts    # FastAPI-Users JWT auth (form POST /auth/jwt/login)
│   ├── factories/
│   │   ├── user-factory.ts     # Ephemeral user factory with auto-cleanup
│   │   └── thread-factory.ts   # Chat thread factory
│   ├── custom-fixtures.ts      # Project-specific fixtures (testUser, etc.)
│   └── merged-fixtures.ts      # Combined fixture set (use this as `test` import)
├── global-setup.ts         # Auth session initializer
└── README.md
```

### Import pattern

Always import `test` and `expect` from `merged-fixtures.ts`:

```ts
import { expect, test } from '../support/merged-fixtures';
```

---

## Fixtures

| Fixture | Source | Description |
|---|---|---|
| `page` | Playwright built-in | Browser page with auth cookies applied |
| `context` | auth-session v4 | Browser context with auth session |
| `authToken` | auth-session v4 | JWT Bearer token string |
| `authOptions` | auth-session v4 | Override environment/userIdentifier per test |
| `authSessionEnabled` | auth-session v4 | Toggle auth off for specific tests |
| `apiRequest` | playwright-utils | Typed HTTP client with retry + schema validation |
| `interceptNetworkCall` | playwright-utils | Spy/stub network requests |
| `recurse` | playwright-utils | Poll until predicate returns true |
| `log` | playwright-utils | Report-integrated structured logging |
| `networkErrorMonitor` | playwright-utils | Auto-detect unexpected 4xx/5xx responses |
| `testUser` | custom-fixtures | Creates an ephemeral user, deleted after test |

---

## Data Factories

Factories create test data via the backend API and register cleanup callbacks:

```ts
test('my test', async ({ testUser }) => {
  // testUser is created before test, deleted after
  console.log(testUser.email);
});
```

Add new factories in `support/factories/`. Pattern: call API endpoint, register `page.on('close', cleanup)`.

---

## Best Practices

### Selectors
- Prefer `data-testid` attributes: `page.getByTestId('submit-btn')`
- Use accessible roles when possible: `page.getByRole('button', { name: 'Submit' })`
- Avoid CSS class selectors (break on refactor)

### Test isolation
- Each test gets a fresh browser context
- Never share state between tests via variables — use fixtures
- Database records created in tests must be cleaned up (use factory cleanup pattern)

### Assertions
- Always use Playwright's auto-waiting assertions: `await expect(locator).toBeVisible()`
- Avoid `page.waitForTimeout()` — use `waitForLoadState` or element assertions instead

### Test format
```ts
test('given X, when Y, then Z', async ({ page }) => {
  // Given
  await page.goto('/');

  // When
  await page.getByRole('button', { name: 'Login' }).click();

  // Then
  await expect(page.getByText('Welcome')).toBeVisible();
});
```

---

## CI Integration

Tests run in CI via GitHub Actions. The workflow:
1. Starts the app (`pnpm dev`) or uses a deployed preview URL
2. Runs `pnpm test:e2e`
3. Uploads `playwright/reports/` as artifacts on failure

JUnit report at `playwright/reports/junit.xml` is parsed by CI for test result summary.

Set `CI=true` environment variable to enable CI-specific timeouts and retries (configured in `playwright.config.ts`).
