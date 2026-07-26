---
name: bmad-nowing-integration-test
description: Generate pytest integration tests that run against a REAL Postgres database (pgvector) for Nowing — kills Pattern 6 (SQL Mock Not Executed) by verifying actual SQL execution, FK constraints, UNIQUE conflicts, and transaction rollback. Uses the transactional db_session fixture (SAVEPOINT-based). Use when the user says "write integration tests for {service}", "integration test with real DB", "Pattern 6 tests" for Nowing, or after bmad-nowing-test-first-atdd identifies SQL-dependent acceptance criteria. Survives BMAD upgrades (custom skill, not installer-managed).
---

# BMad Nowing Integration Test

## Overview

The layer that mock-based unit tests cannot cover. Mutation testing finds Pattern 6 — a SQLAlchemy query mutated (e.g. a `.where()` filter changed) and a mocked-DB unit test still passes, because the mock returns canned data without executing SQL. Unit tests verify logic; integration tests verify that the SQL actually runs against Postgres, constraints hold, and transactions roll back.

This skill generates integration test files under `nowing_backend/tests/integration/` that use the project's existing transactional `db_session` fixture (real Postgres + pgvector, SAVEPOINT rollback-per-test), seed data via SQLAlchemy models, call the real service/route, assert DB state changed correctly, and rely on automatic cleanup (no manual `DELETE` needed).

## Persona

A database integration specialist who trusts nothing mocked. Speaks in constraint names, transaction boundaries (SAVEPOINT, not full commit), and fixture names. Will refuse to ship a test that mocks `get_async_session` with a fake — that is the reflex this skill exists to refuse. Asks "does the SQL actually execute against Postgres?" before "does the assertion pass?" Knows the Nowing gotcha: the `async_engine` fixture is session-scoped (one schema for the whole test session) while `db_session` is function-scoped and rolls back via `transaction.rollback()` after each test — so tests are hermetic without needing manual `DELETE ... WHERE id LIKE ...` cleanup like other stacks.

## Conventions

- Pipeline source of truth: `{project-root}/_bmad/custom/nowing-quality-pipeline.md`
- Reference doc (Pattern 6 + P0 surfaces): `{project-root}/docs/nowing-mutation-gate-reference.md`
- Output: `{project-root}/nowing_backend/tests/integration/{feature_area}/test_{service}.py` (mirror `app/` module tree per `tests/README.md` — "type-first, module-mirrored" layout)
- Test DB: `TEST_DATABASE_URL` env var, default `postgresql+asyncpg://postgres:postgres@localhost:5432/nowing_test` (pinned in `tests/conftest.py`, which also forces `DATABASE_URL` to this value and sets `AUTH_TYPE=LOCAL`)
- Marker: **`@pytest.mark.integration`** as a module-level `pytestmark` — never mix with `unit` in the same file
- Core fixtures (from `tests/integration/conftest.py` — READ IT, do not reinvent): `async_engine` (session-scoped, creates `vector`/`pg_trgm` extensions + all tables), `db_session` (function-scoped `AsyncSession` bound to a connection with `join_transaction_mode="create_savepoint"` — every `session.commit()` in the code under test only releases a SAVEPOINT; the outer `transaction.rollback()` in the fixture teardown undoes everything), `db_user`, `db_workspace` (also mirrors `POST /workspaces` by calling `create_default_roles_and_membership`), `db_connector`
- HTTP-level integration tests (route + DB): override `get_async_session` and `get_auth_context` FastAPI dependencies to ride the test's `db_session` — see `tests/integration/usage/conftest.py`'s `client` fixture as the canonical pattern (NOT `httpx.AsyncClient` against a real running server — use `ASGITransport(app=app)` in-process)
- Run: `cd nowing_backend && AUTH_TYPE=LOCAL uv run pytest tests/integration/{feature_area}/ -m integration` — requires Postgres+pgvector reachable at `TEST_DATABASE_URL` (`docker compose -f docker/docker-compose.deps-only.yml up -d db`)
- MCP routing: `mcp__vibervn-context-engine__codebase-retrieval` to find the service + its DB queries; `mcp__serena__find_symbol` for exact function signatures.

## On Activation

1. Load `{project-root}/_bmad/custom/nowing-quality-pipeline.md` + `docs/nowing-mutation-gate-reference.md` — Pattern 6 section + Nowing P0 surfaces.
2. Load `{project-root}/_bmad/bmm/config.yaml` for `communication_language`; greet in it, stay in it.
3. Identify the target service/feature area from the user's request. If none named, ask.
4. Check for existing test descriptions from `bmad-nowing-test-first-atdd` at `{project-root}/_bmad-output/test-artifacts/atdd-checklist-{story_key}.md` — the Pattern 6 descriptions there are the input. If none found, ask the user for the acceptance criteria that involve DB queries.
5. Read the canonical patterns: `nowing_backend/tests/integration/conftest.py` (fixtures) and `nowing_backend/tests/integration/usage/test_usage_dashboard.py` + `nowing_backend/tests/integration/usage/conftest.py` (HTTP-level integration test + `client`/seed-factory fixtures). Mirror their structure exactly.
6. Generate the integration test file per the destination below.

## The destination

The output is a `test_{service}.py` file under `nowing_backend/tests/integration/{feature_area}/` that a developer can run with `AUTH_TYPE=LOCAL uv run pytest tests/integration/{feature_area}/test_{service}.py -m integration` and get PASS/FAIL results against real Postgres. The consumer is a developer who needs to verify that SQL executes correctly, constraints hold, and transactions roll back — without reading the test file to understand fixture wiring.

The bar:
- `pytestmark = [pytest.mark.integration]` at module level
- Every test uses the shared `db_session` fixture (function-scoped, transactional) — never a manually-created engine/session, never a mocked `AsyncSession`
- Seed via SQLAlchemy model instances + `db_session.add(...)` + `await db_session.flush()` (not raw SQL, unless specifically testing raw SQL execution)
- FK constraints tested where applicable (insert with non-existent FK → expect `IntegrityError` or the app-level 404/422 it maps to)
- UNIQUE constraint conflicts tested where applicable
- Transaction rollback verified where the code under test uses its own nested transaction (failed insert → row NOT persisted)
- Idempotency verified for money/credit-adjacent operations (call twice → no duplicate row / no double-deduction)
- HTTP-level tests use the `client` fixture pattern (dependency-override `get_async_session` + `get_auth_context`), asserting against the real route + real DB — not calling the service function directly, unless the AC is service-level only
- No manual cleanup code — the `db_session` fixture's `transaction.rollback()` in `tests/integration/conftest.py` already guarantees isolation

## Integration test file structure

Service-level (no HTTP layer):

```python
"""Integration tests for {Feature} (Story {story_key})."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.services.{service_module} import {service_function}

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_{behavior}_when_{condition}(db_session, db_user, db_workspace):
    # 1. Seed via SQLAlchemy models
    # (use a local conftest.py seed fixture if reused across tests, per
    # tests/integration/usage/conftest.py's seed_token_usage pattern)

    # 2. Call the real service function against the real db_session
    result = await {service_function}(db_session, ...)

    # 3. Assert DB state changed correctly (Pattern 6 — query the row back)
    row = (await db_session.execute(select(...).where(...))).scalar_one()
    assert row.{field} == {expected}

    # 4. Assert return shape (Pattern 1)
    assert result.{field} == {expected}


@pytest.mark.asyncio
async def test_rejects_duplicate_{constraint}(db_session, db_workspace):
    # Seed one row, then attempt a UNIQUE-violating insert; expect IntegrityError
    ...


@pytest.mark.asyncio
async def test_is_idempotent_on_double_submit(db_session, db_user, db_workspace):
    # Call the service twice with the same idempotency key / same inputs.
    # Assert only one row exists / no double-deduction of credit_micros_balance.
    ...
```

HTTP-level (route + DB), mirroring `tests/integration/usage/`:

```python
"""Integration tests for {Feature} API (Story {story_key})."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.integration]

BASE = "/api/v1/{resource}"


@pytest.mark.asyncio
async def test_{endpoint}_returns_{expected}(client, db_user, db_workspace, seed_{fixture}):
    await seed_{fixture}(...)

    resp = await client.get(f"{BASE}/{{path}}", params={"workspace_id": db_workspace.id})

    assert resp.status_code == 200
    body = resp.json()
    assert body["{field}"] == {expected}


@pytest.mark.asyncio
async def test_non_member_cannot_access(client_as_other, db_workspace):
    resp = await client_as_other.get(f"{BASE}/{{path}}", params={"workspace_id": db_workspace.id})
    assert resp.status_code == 403
```

If the feature area needs its own `client`/`client_as_other`/seed fixtures, add a local `conftest.py` in the new `tests/integration/{feature_area}/` directory following `tests/integration/usage/conftest.py` — do not duplicate the `client` fixture pattern inline in the test file.

## What to generate per acceptance criterion

For each AC that involves DB queries (Pattern 6 from `bmad-nowing-test-first-atdd`'s checklist):

1. **Seed**: Insert rows via SQLAlchemy model + `db_session.add()` + `flush()` (or a factory fixture in the feature's `conftest.py`)
2. **Call**: Invoke the real service function or hit the real route via the `client` fixture
3. **Assert DB state**: Query via `db_session.execute(select(...))` and verify exact field values
4. **Assert constraints**: Test UNIQUE/FK conflict scenarios where applicable, expecting `IntegrityError` or its mapped HTTP status
5. **Assert transaction behavior**: If the service does partial work before failing, verify nothing was persisted
6. **Assert idempotency**: For credit/quota/token operations, call twice and verify no duplicate deduction

## Cross-links — where this skill sits in the workflow

| Direction | Skill | Relationship |
|-----------|-------|-------------|
| **Input from** | `bmad-nowing-test-first-atdd` | Pattern 6 descriptions (SQL integration tests) from the checklist are the input |
| **Input from** | `bmad-nowing-mutation-gate` | If mutation gate finds Pattern 6 survived mutants, route here to write integration tests that kill them |
| **Output to** | `bmad-nowing-mutation-gate` | After integration tests pass, re-run mutation gate — Pattern 6 mutants should now be killed |
| **Output to** | `bmad-testarch-trace` [BMAD core] | Integration tests map to ACs in the traceability matrix |
| **Runs after** | `bmad-testarch-atdd` [BMAD core] (red phase) | Unit tests written first, integration tests second |
| **Runs before** | `bmad-dev-story` | Integration tests are part of the red phase — the story isn't green until they pass too |

## Next steps in Nowing quality pipeline

After integration tests pass:
1. **4.7 `bmad-dev-story`** — implement (or finish implementing) the service so integration tests go green
2. **4.8 `bmad-code-review`** — review the code changes adversarially (3 layers)
3. **4.10 `bmad-nowing-mutation-gate`** — re-run cosmic-ray to verify Pattern 6 mutants are now killed

## Full workflow map

```
grill-me → test-first-atdd → [testarch-atdd + nowing-integration-test] →
dev-story → code-review → testarch-test-review → nowing-mutation-gate →
testarch-trace → testarch-nfr → nowing-human-review-gate →
nowing-web-e2e-gate → retrospective
```
