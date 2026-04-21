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
- `BASE_URL` — app URL (default: `http://localhost:3999`)
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
│   │   └── auth-provider.ts    # JWT token reader from localStorage
│   ├── factories/
│   │   └── user-factory.ts     # Data factory with auto-cleanup
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
| `page` | Playwright built-in | Browser page |
| `apiRequest` | playwright-utils | Authenticated API client |
| `auth` | playwright-utils | Auth session management |
| `intercept` | playwright-utils | Network interception helpers |
| `recurse` | playwright-utils | Retry/poll helpers |
| `log` | playwright-utils | Test logging |
| `networkErrorMonitor` | playwright-utils | Catch unexpected network errors |
| `testUser` | custom-fixtures | Creates a user + auto-cleanup after test |

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
