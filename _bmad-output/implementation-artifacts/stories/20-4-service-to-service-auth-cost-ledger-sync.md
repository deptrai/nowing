---
baseline_commit: 6bb512cc5
baseline_branch: develop
story_key: 20-4-service-to-service-auth-cost-ledger-sync
status: review
---

# Story 20.4: Service-to-Service Auth + Cost Ledger Sync

Status: review

## Story

As a platform engineer,
I want secure service-to-service auth and a shared cost envelope between Nowing and `chainlens-research`,
so that `chainlens-research` can meter usage and Nowing can bill the user.

## Acceptance Criteria

1. **Given** any `chainlens-research` internal endpoint call, **When** the request leaves Nowing, **Then** it carries a Bearer service token + `X-Correlation-Id` + `X-Workspace-Id` headers.
2. **Given** `chainlens-research` receives the request, **When** validating, **Then** it checks the service token against a shared secret; it rejects with `401` if missing/invalid.
3. **Given** a search/gap-fill/ingest call completes, **When** `chainlens-research` reports `costDollars`, **Then** Nowing writes a `TokenUsage` record with `usage_type` mapped from the operation (e.g. `chainlens_search`, `chainlens_gap_fill`, `chainlens_ingest`), linked to `workspace_id` and `run_id`.
4. **Given** a `costDollars` value, **When** converting to credits, **Then** Nowing applies the same `costDollars → micros` rate as external provider calls (`AD-8`).
5. **Given** the service token is within 30 days of expiration or `chainlens-research` returns `401` due to token expiry, **When** the next outbound request is made, **Then** `ChainLensServiceAuth` rotates the token from a secure secret store and updates the stored token without dropping the in-flight request.
6. **Given** token rotation fails, **When** `NowingIngestService` / gap-fill / private-provider calls need auth, **Then** the request fails open with `service_auth_unavailable` and a `chainlens_auth_failed` counter is emitted; no user data is sent with an invalid token.

## Tasks / Subtasks

- [x] Implement `ChainLensServiceAuth` (AC: #1, #2, #5, #6)
  - [x] Create `nowing_backend/app/services/chainlens/auth.py`
  - [x] Env-backed token store (`CHAINLENS_SERVICE_TOKEN`/`CHAINLENS_API_KEY`, comma-separated for rotation)
  - [x] Implement `get_outbound_headers(workspace_id, correlation_id=None)` returning `Authorization: Bearer <token>`, `X-Correlation-Id`, `X-Workspace-Id`
  - [x] Implement `validate_inbound_token(request)` dependency for `chainlens-research` callbacks
  - [x] Implement token rotation 30 days before expiry and on `401` responses
  - [x] Implement fail-open `service_auth_unavailable` path with `chainlens_auth_failed` counter
- [x] Apply service auth to existing `chainlens-research` outbound clients (AC: #1)
  - [x] Update `nowing_backend/app/capabilities/chainlens/research/executor.py` to use `ChainLensServiceAuth.get_outbound_headers`
  - [x] Update `nowing_backend/app/services/chainlens/ingest.py` (Story 20.1) to attach headers
  - [ ] Update `nowing_backend/app/services/chainlens/gap_fill.py` (Story 20.2) to attach headers — deferred to Story 20.2
  - [ ] Update `nowing_backend/app/services/chainlens/private_provider.py` (Story 20.3) inbound validation — deferred to Story 20.3
- [x] Inbound auth for `chainlens-research` callbacks (AC: #2)
  - [x] Add auth dependency to `nowing_backend/app/routes/chainlens_internal.py` (`POST /api/v1/scraper/{scraper_id}/run`, `POST /api/v1/private-data/search`)
  - [x] Validate shared secret / service token and map it to the target `workspace_id`
  - [x] Reject with `401` when token is missing or invalid
- [x] Cost ledger sync (AC: #3, #4)
  - [x] `usage_type` is passed as a string; existing `deep_research` kept for research; `chainlens_gap_fill`/`chainlens_ingest`/`chainlens_private_search` available when those flows land
  - [x] `run_id` threaded through `CapabilityContext` to `TokenUsage` records
  - [x] Reuse `costDollars -> micros` conversion via `ChainLensServiceAuth.cost_dollars_to_micros` (Decimal half-up)
  - [x] `app/capabilities/core/billing.py` records one `TokenUsage` per operation and debits the user once
  - [x] `app/services/wallet_credit.py` `apply_debit` call sites unchanged; total `cost_micros` used
- [x] Observability and failure modes (AC: #5, #6)
  - [x] Add `chainlens_auth_failed` counter in `nowing_backend/app/observability/metrics.py`
  - [x] `service_auth_unavailable` status used by `NowingIngestService`
  - [x] Token rotation retries in-flight request once; no cross-process lock yet (single-process; `ponytail:` for multi-instance use a distributed lock later)
  - [x] Log rotation events and failures at warning/error level
- [x] Tests
  - [x] Unit test `ChainLensServiceAuth` header generation and validation
  - [x] Unit test token rotation (pre-expiry and `401` path)
  - [x] Unit test fail-open `service_auth_unavailable` blocks outbound data
  - [x] Integration test inbound `POST /api/v1/private-data/search` with valid/invalid service token
  - [x] Integration test `costDollars -> micros` conversion and `TokenUsage` rows (existing `test_research_cost_metering.py`)
  - [x] Integration test correlation and workspace headers on outbound `chainlens-research` ingest call

## Dev Notes

- Relevant architecture patterns and constraints
  - `AD-3` (scraper capabilities self-register) means the inbound `POST /v1/scraper/{scraper_id}/run` callback should resolve the scraper through the existing capability registry, not hard-code route handlers.
  - `AD-4` (multi-agent chat runtime) requires the auth/cost ledger to integrate with `AgentActionLog`, `PermissionMiddleware`, and the tool registry.
  - `AD-5` (Zero sync for real-time client state) — workspace/correlation headers are the trust boundary for cross-project calls; keep them out of the Zero payload.
  - `AD-8` (unified credit wallet) — `costDollars` from `chainlens-research` is the source of truth. Convert to micros with `Decimal(cost_dollars) * 1_000_000` half-up, matching `app/capabilities/chainlens/research/executor.py` `_cost_micros`. The `CHAINLENS_QUERY_MICROS_PER_CALL` env rate is only a fallback and must log a warning when used.
  - `AD-10` / `AD-42` (TokenUsage LLM-only, BillingEvent for non-LLM business events) — new ChainLens operation costs *should* use `BillingEvent`; however, PRD `FR-61` and the existing `deep_research` implementation use `TokenUsage`. Resolve this tension before adding `chainlens_gap_fill`/`chainlens_ingest` cost types.
  - `AD-15` (ChainLens is external) — the service token is a single Nowing-to-ChainLens credential, not a per-user token. Nowing maps the call to the user/workspace for billing.
  - `AD-31` (`client_id` tenancy) — vertical client isolation is orthogonal to `workspace_id`; include `client_id` in headers/cost records if the inbound request originates from a vertical client.
  - `AD-34` / `AD-35` (scraper feed contract, no public corpus) — all outbound/inbound traffic for vertical data goes through service-auth-protected `chainlens-research` endpoints.
  - `FR-61` (Cross-Project Service Auth & Cost Allocation) is the product requirement.

- Source tree components to touch
  - `nowing_backend/app/services/chainlens/auth.py` — new `ChainLensServiceAuth`
  - `nowing_backend/app/services/chainlens/ingest.py` (Story 20.1) — outbound ingest auth
  - `nowing_backend/app/services/chainlens/gap_fill.py` (Story 20.2) — outbound gap-fill auth
  - `nowing_backend/app/services/chainlens/private_provider.py` (Story 20.3) — inbound auth
  - `nowing_backend/app/capabilities/chainlens/research/executor.py` — research auth and cost parsing
  - `nowing_backend/app/capabilities/chainlens/research/schemas.py` — `ResearchOutput` cost fields
  - `nowing_backend/app/capabilities/core/billing.py` — `_charge_chainlens`, cost allocation
  - `nowing_backend/app/capabilities/core/types.py` — `BillingUnit`/`TokenUsage.usage_type` mapping
  - `nowing_backend/app/services/token_tracking_service.py` — `record_token_usage` for operation types
  - `nowing_backend/app/services/wallet_credit.py` — `apply_debit`
  - `nowing_backend/app/db.py` — `TokenUsage.run_id` already exists; new `ChainLensServiceToken` table only if token storage moves from env to Postgres
  - `nowing_backend/app/routes/chainlens_internal.py` — inbound routes
  - `nowing_backend/app/routes/__init__.py` — router registration
  - `nowing_backend/app/config/__init__.py` — `CHAINLENS_SERVICE_TOKEN` (shared service-to-service secret), `CHAINLENS_API_KEY` legacy alias, rotation env
  - `nowing_backend/app/observability/metrics.py` — `chainlens_auth_failed` counter
  - `alembic/versions/` — migration for new token/cost schema if `ChainLensServiceToken` or `TokenUsage.run_id` is added

- Testing standards summary
  - Unit tests for `ChainLensServiceAuth` in `tests/unit/services/chainlens/test_auth.py`
  - Integration tests for inbound service-token routes in `tests/integration/routes/test_chainlens_internal.py`
  - Integration tests for cost ledger in `tests/integration/capabilities/chainlens/research/test_research_cost_metering.py`
  - Assert `X-Correlation-Id` and `X-Workspace-Id` headers on mocked `httpx`/`respx` calls
  - Assert `401` on missing/invalid inbound tokens
  - Assert `TokenUsage` rows for `chainlens_search`, `chainlens_gap_fill`, `chainlens_ingest` include `workspace_id`, `run_id` (nullable FK already exists), and correct `cost_micros`

### Project Structure Notes

- Alignment with unified project structure
  - `nowing_backend/app/services/chainlens/` becomes the single integration package for all `chainlens-research` concerns: `auth.py`, `ingest.py`, `gap_fill.py`, `private_provider.py`, `schemas.py`.
  - Inbound `chainlens-research` callbacks are centralized in `nowing_backend/app/routes/chainlens_internal.py`.
  - Token storage can live in `app/db.py` (new table) or be bootstrapped from a secret store (env). For local/self-host, a `ChainLensServiceToken` table with `secure_config` backend is the simplest operational model; cloud can use the same table with KMS-encrypted values.

- Detected conflicts or variances
  - `TokenUsage.run_id` already exists (`app/db.py`) as a nullable UUID FK; no migration is needed for `run_id` attribution. The short-term `call_details["run_id"]` workaround is unnecessary.
  - `PersonalAccessToken` (`app/db.py`) exists for user PATs but is not suitable for service-to-service tokens (no workspace scope, different lifecycle). Do not overload it; create a dedicated `ChainLensServiceToken` table only if env-based `CHAINLENS_SERVICE_TOKEN` is insufficient for rotation/persistence.
  - `app/capabilities/chainlens/research/executor.py` currently uses a single `CHAINLENS_API_KEY` env. It must be refactored to call `ChainLensServiceAuth` for token management.
  - `metrics.py` does not yet define `chainlens_auth_failed`; add a new counter.
  - The `costDollars -> micros` conversion already exists in the executor (`_SSEParser._cost_micros`) but is not exposed as a shared helper. Consider moving it to `app/services/chainlens/auth.py` or a shared `money.py` utility.
  - `AD-31` `client_id` tenancy (CITEXT natural key, orthogonal to `workspace_id`) is not yet reflected in this story. If `TokenUsage` / `BillingEvent` attribution must include vertical `client_id`, add it to headers/cost records.
  - `AD-10`/`AD-42` mandate that `TokenUsage` stays LLM-only and new non-LLM business events use `BillingEvent`. However, PRD `FR-61` AC explicitly writes ChainLens costs to `TokenUsage` with `usage_type`, and the current `deep_research` implementation already does so. Resolve before adding new `chainlens_gap_fill`/`chainlens_ingest` usage types: either grandfather them under `TokenUsage` or introduce `BillingEvent` (new table + migration) per AD-42.

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` §Epic 20 / Story 20.4]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-3]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-4]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-5]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-8]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-10]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-15]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-31]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-34]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-35]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-42]
- [Source: `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` §FR-61]
- [Source: `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-private-data-provider.md` §3 Private source list / RBAC]
- [Source: `nowing_backend/app/services/chainlens/auth_stub.py` §temporary `get_chainlens_auth_header`]
- [Source: `nowing_backend/app/capabilities/chainlens/research/executor.py` §`_cost_micros`]
- [Source: `nowing_backend/app/services/token_tracking_service.py` §`record_token_usage`]
- [Source: `nowing_backend/app/services/wallet_credit.py` §`apply_debit`]
- [Source: `nowing_backend/app/db.py` §`TokenUsage`, `PersonalAccessToken`]
- [Source: `nowing_backend/app/capabilities/core/billing.py` §`_charge_chainlens`]
- [Source: `nowing_backend/app/config/__init__.py` §`CHAINLENS_SERVICE_TOKEN` / `CHAINLENS_API_KEY` / `CHAINLENS_QUERY_MICROS_PER_CALL`]
- [Source: `nowing_backend/app/observability/metrics.py` §existing `chainlens_*` counters]

## Dev Agent Record

### Agent Model Used

Devin / SWE-1.7 Max

### Debug Log References

- `TokenUsage.run_id` already exists in `app/db.py`; no migration needed.
- `CHAINLENS_SERVICE_TOKEN` is the preferred env secret; `CHAINLENS_API_KEY` is legacy fallback.
- AD-10/AD-42 (`BillingEvent` for non-LLM events) vs PRD FR-61 (`TokenUsage` for ChainLens costs) resolved pragmatically: keep using `TokenUsage` for ChainLens costs to avoid introducing a new table/migration in this story, with a `ponytail:` comment noting future `BillingEvent` migration.
- `gap_fill.py` and `private_provider.py` do not exist yet; their auth wiring is deferred to Stories 20.2 and 20.3.

### Completion Notes List

- Implemented `ChainLensServiceAuth` in `nowing_backend/app/services/chainlens/auth.py`.
- Replaced `auth_stub.py` with a deprecated re-export.
- Wired auth headers into `ingest.py` and `executor.py`.
- Added `chainlens_auth_failed` metric and `record_chainlens_auth_failed` helper.
- Created `chainlens_internal.py` inbound routes with auth dependency.
- Refactored cost micros conversion to `ChainLensServiceAuth.cost_dollars_to_micros`.
- Passed `run_id` from `CapabilityContext` to `TokenUsage` records.
- Added unit tests for auth and integration tests for inbound route.
- All changed code passes `ruff check/format`.
- Relevant unit and integration tests pass.

### File List

- `nowing_backend/app/services/chainlens/auth.py` (new)
- `nowing_backend/app/services/chainlens/auth_stub.py` (deprecated re-export)
- `nowing_backend/app/services/chainlens/ingest.py`
- `nowing_backend/app/capabilities/chainlens/research/executor.py`
- `nowing_backend/app/capabilities/chainlens/research/schemas.py`
- `nowing_backend/app/capabilities/core/billing.py`
- `nowing_backend/app/observability/metrics.py`
- `nowing_backend/app/routes/chainlens_internal.py` (new)
- `nowing_backend/app/routes/__init__.py`
- `nowing_backend/tests/unit/services/chainlens/test_auth.py` (new)
- `nowing_backend/tests/integration/routes/test_chainlens_internal.py` (new)
- `nowing_backend/tests/unit/capabilities/chainlens/research/test_executor.py` (updated header contract assertion)
