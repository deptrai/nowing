# Mutation Gate CI — Story 24.3

## Purpose

Trigger `cosmic-ray` mutation testing on GitHub Actions for the P0 backend surfaces introduced by **Story 24.3: Multi-Seat Team CRM Pipeline & Shared Workspace Credit Pooling**.

The user explicitly requested **not** to run the mutation gate locally (`mutation gate thì trigger cho ci run`). Instead, this CI workflow delegates to the canonical runner `scripts/mutation-gate.py` and uploads per-service reports as artifacts.

## Workflow

- **File:** `.github/workflows/mutation-gate-24.3.yml`
- **Name:** `Story 24.3 Mutation Gate`
- **Triggers:**
  - `pull_request` to `main` / `dev` / `develop` touching the P0 source files, tests, the runner script, or the workflow itself
  - `push` to `main` / `dev` / `develop` touching the same paths
  - `workflow_dispatch` (manual)

## P0 services / modules under test

| Story 24.3 surface | Source file | Service key passed to `scripts/mutation-gate.py` |
|---|---|---|
| `workspace_credit_service` | `nowing_backend/app/services/workspace_credit_service.py` | `workspace_credit_service` |
| `lead_assignment_service` | `nowing_backend/app/services/lead_assignment_service.py` | `lead_assignment_service` |
| `lead_pipeline_routes` | `nowing_backend/app/routes/lead_pipeline_routes.py` | `routes/lead_pipeline_routes` |
| `billing_event_service` | `nowing_backend/app/services/billing_event_service.py` | `billing_event_service` |
| `capabilities/core/billing` | `nowing_backend/app/capabilities/core/billing.py` | `capabilities/core/billing` |

## Test selection

| Service | Test file(s) | Marker |
|---|---|---|
| `workspace_credit_service` | auto-discovered (`tests/unit/capabilities/test_billing.py`, `tests/unit/services/test_billing_event_service.py`, `tests/unit/services/test_contact_relock.py`, `tests/unit/services/test_contact_unlock_billing.py`, `tests/unit/services/test_contact_unlock_refund.py`, `tests/unit/services/test_workspace_credit_pooling.py`) | `unit or not integration` |
| `lead_assignment_service` | auto-discovered (`tests/unit/services/test_lead_assignment.py`) | `unit or not integration` |
| `billing_event_service` | auto-discovered (`tests/unit/services/test_billing_event_service.py`) | `unit or not integration` |
| `capabilities/core/billing` | auto-discovered (all `tests/unit/**/test_billing*.py` files that reference the billing capability) | `unit or not integration` |
| `routes/lead_pipeline_routes` | `tests/integration/routes/test_kanban_concurrency.py` | `integration` |

The `lead_pipeline_routes` module has no dedicated unit test, so the workflow runs the real-DB integration test `test_kanban_concurrency.py` against a PostgreSQL + pgvector service container. The runner script now detects integration test-file overrides and switches the pytest marker to `-m "integration"`.

## Runner command

For each matrix job:

```bash
python scripts/mutation-gate.py \
  --services <service> \
  --timeout 120.0 \
  --project-root . \
  [--test-files <integration-test-file>]
```

## P0 triage update

The `P0_SERVICES` set in `scripts/mutation-gate.py` was extended to include the five Story 24.3 P0 surfaces so that Pattern 3 (boundary/security), Pattern 4 (arithmetic/credit), and Pattern 6 (SQL mock) survivors are treated as blockers for these modules.

## Artifacts

Each job uploads:

- `_bmad-output/test-artifacts/mutation-nowing-<safe-service>-<timestamp>.json`
- `_bmad-output/test-artifacts/mutation-nowing-<safe-service>-<timestamp>.sqlite`
- `_bmad-output/test-artifacts/mutation-nowing-summary-latest.json`

Artifact name pattern: `mutation-nowing-24-3-<safe-service>`, with `/` in service names replaced by `-`.

## Notes

- The Postgres service uses `pgvector/pgvector:pg17` and exposes `localhost:5432`.
- `TEST_DATABASE_URL` is set to `postgresql+asyncpg://postgres:postgres@localhost:5432/nowing_test`.
- The `EMBEDDING_MODEL` env var is set to avoid fixture defaults that may require network access.
- Jobs run in parallel; `fail-fast: false` so a single service failure does not abort the other four.
- Verdict thresholds follow `docs/nowing-mutation-gate-reference.md`: **FAIL** if `mutationScore < 60%` or any P0 mutant survives.
