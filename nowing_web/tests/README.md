# Playwright E2E Suite

End-to-end tests for the full Nowing stack (Next.js + FastAPI +
Celery + Postgres + Redis). Designed to scale from one connector
(Composio Drive in Phase 1) to every connector + manual file upload
without rewriting the harness.

## How the deterministic harness works

There are **three layers of defense** against accidental real-world
calls. None of them touch production code.

1. `nowing_backend/tests/e2e/run_backend.py` and `run_celery.py` are
   separate entrypoints (not used by `python main.py`). They hijack
   `sys.modules["composio"]` BEFORE importing the app, swap in strict
   fakes for `langchain_litellm`/`langchain_openai`, and mount the
   `X-E2E-Scenario` middleware.
2. The fakes themselves are **strict**: every class implements
   `__getattr__` that raises `NotImplementedError` on unknown surface.
   Adding a new SDK call site without updating the fake fails CI loudly.
3. CI sets `HTTPS_PROXY=http://127.0.0.1:1` plus sentinel API keys
   (`COMPOSIO_API_KEY=e2e-deny-real-call-sentinel`). Any leaked outbound
   HTTP call fails before reaching the network.

## Running locally

The recommended flow runs only Postgres and Redis in Docker, and the backend
+ Celery worker on the host. The E2E entrypoints `setdefault` every backend
variable they need, so no `.env` file is required on a fresh checkout.

### One-time setup

From `nowing_web/`:

```bash
pnpm install
pnpm exec playwright install --with-deps chromium
```

### Each run

**1. Bring up Postgres + Redis** from the repo root:

```bash
docker compose -f docker/docker-compose.deps-only.yml up -d db redis
```

**2. Start the backend** in `nowing_backend/`, terminal A:

```bash
uv sync
uv run alembic upgrade head
uv run python tests/e2e/run_backend.py
```

**3. Start the Celery worker** in `nowing_backend/`, terminal B:

```bash
uv run python tests/e2e/run_celery.py
```

**4. Register the Playwright user**:

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"e2e-test@nowing.net","password":"E2eTestPassword123!"}'
```

**5. Run Playwright** from `nowing_web/`, terminal C:

```bash
pnpm test:e2e             # dev server (fast iteration)
pnpm test:e2e:headed      # show the browser
pnpm test:e2e:ui          # Playwright UI mode
pnpm test:e2e:debug       # Playwright Inspector
pnpm test:e2e:prod        # build + start (matches CI exactly)
pnpm test:e2e:report      # open the last HTML report
```

`playwright.config.ts` and the backend run scripts share defaults, so the
above works without exporting any env vars. Override
`PLAYWRIGHT_TEST_EMAIL`, `PLAYWRIGHT_TEST_PASSWORD`, or
`NEXT_PUBLIC_FASTAPI_BACKEND_URL` only when pointing tests at a different
stack.

To debug a single journey:

```bash
pnpm test:e2e:headed connectors/composio/drive/journey.spec.ts
```

### Hermetic alternative (matches CI)

To reproduce the CI environment exactly: backend and Celery in containers
with L3 egress denied, replace steps 1–3 with:

```bash
docker compose -f docker/docker-compose.e2e.yml up -d --build --wait
```

Then run steps 4 (curl register) and 5 (`pnpm test:e2e:prod`) as above. Tear
down with:

```bash
docker compose -f docker/docker-compose.e2e.yml down -v --remove-orphans
```

This builds the ~9 GB e2e backend image, so the deps-only flow is faster for
day-to-day work.

## Playwright configuration reference

`playwright.config.ts` reads the following environment variables (all have
sensible defaults, so a fresh checkout works without a `.env` file):

| Variable | Default | Purpose |
|---|---|---|
| `PLAYWRIGHT_BASE_URL` | `http://localhost:${PORT}` | Origin the browser navigates to. |
| `NEXT_PUBLIC_FASTAPI_BACKEND_URL` | `http://localhost:8000` | Public backend origin used by the Next.js app. |
| `NOWING_BACKEND_INTERNAL_URL` | same as backend | Server-side backend origin. |
| `PLAYWRIGHT_TEST_EMAIL` | `e2e-test@nowing.net` | E2E user email. |
| `PLAYWRIGHT_TEST_PASSWORD` | `E2eTestPassword123!` | E2E user password. |
| `E2E_MINT_SECRET` | `local-e2e-mint-secret-not-for-production` | Shared secret for `/__e2e__/auth/token`. |
| `PLAYWRIGHT_WORKERS` | `2` in CI, `1` locally | Parallel workers. |
| `PLAYWRIGHT_NO_WEB_SERVER` | unset | If `true`, Playwright will not start the Next.js dev server. |
| `PLAYWRIGHT_USE_PROXY_ORIGIN` | `false` | Route backend calls through the same origin proxy. |

Timeouts are configured in `playwright.config.ts`:

- Test timeout: **60s**
- Action timeout: **15s**
- Navigation timeout: **30s**
- Expect timeout: **15s**

Traces, screenshots, and videos are retained **on failure**.

## Adding a new connector

The directory tree is designed so a new connector lives mostly inside
its own folder. E2E is scoped to **one user expectation per connector**:
the smallest browser journey that proves the user-visible outcome works.
Follow this checklist:

1. **Backend fake.** Add a new file under
   `nowing_backend/tests/e2e/fakes/<sdk>_module.py` mirroring
   `composio_module.py`. Use `__getattr__` to raise on unknown surface.
2. **Hijack.** Wire the new module into `run_backend.py` and
   `run_celery.py` with `sys.modules["<sdk>"] = <fake>`.
3. **Backend tests.** Put edge cases in backend tests, not Playwright:
   OAuth state validation in unit tests, and route/error branches in
   `nowing_backend/tests/integration/<connector>/`.
4. **Fixtures.** Drop a fixture file into `tests/fixtures/connectors/`
   that returns a pre-connected connector row.
5. **Journey spec.** Create exactly one
   `tests/connectors/<vendor>/<service>/journey.spec.ts` for the user
   expectation. For indexable connectors this usually means
   connect -> select scope -> index -> assert canary content. For
   connection-only connectors this means connect -> assert connected badge.
6. **Update this README's directory diagram.**

Do not add separate Playwright specs for expired OAuth state, duplicate
connectors, auth-expired classification, or route config persistence.
Those belong in backend unit/integration tests such as
`nowing_backend/tests/unit/utils/test_oauth_security.py` and
`nowing_backend/tests/integration/composio/`.

## Why API-driven?

Journey specs prefer a thin browser assertion followed by API-driven
configuration/indexing because:

- It keeps tests **deterministic** (no waiting on UI animation,
  React hydration, or Next.js compile time).
- It exercises the **same backend code path** the UI eventually calls.
- The expensive E2E assertion stays focused on what only E2E can prove:
  the cross-process seam from connector -> Celery -> indexing -> DB.

UI-only tests live under `helpers/ui/` for future Phase 2 work
(folder-tree drag-and-drop, indexing options switches, etc.).
