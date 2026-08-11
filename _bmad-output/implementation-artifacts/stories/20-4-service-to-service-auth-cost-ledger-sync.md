---
baseline_commit: 6bb512cc5
baseline_branch: develop
story_key: 20-4-service-to-service-auth-cost-ledger-sync
status: done
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

### Review Findings

#### decision-needed

- [x] [Review][Decision] **Inbound callback route path: `/api/v1` vs spec `/v1`** — The PRD/UX contract (`ux-contract-ecosystem-search.md`, `architecture-Nowing-2026-07-22`) specifies `POST /v1/scraper/{scraper_id}/run` and `POST /v1/private-data/search`. The implementation currently mounts the routes under `/api/v1` because `chainlens_internal_router` is included in the `crud_router` that has prefix `/api/v1`. The integration tests also use `/api/v1/...` paths. Decision: mount the router at `/v1` directly in `app.app`, or update the spec to `/api/v1/...` (breaks cross-project contract).

#### patch

- [x] [Review][Patch] **Validate `workspace_id > 0` in inbound token validation** [`auth.py:212`] — `ChainLensServiceAuth.validate_inbound_token` converts `X-Workspace-Id` to int but accepts `0` and negative values. A negative workspace ID would propagate into billing/DB queries.
- [x] [Review][Patch] **Validate `cost_dollars` in `cost_dollars_to_micros`** [`auth.py:226`] — The converter accepts negative, NaN, infinity and extremely large floats. Negative costs would produce invalid billing; overflow can break `Decimal`/`int` conversion.
- [x] [Review][Patch] **Add rate limiting to inbound service-auth endpoints** [`chainlens_internal.py:39,57`] — `POST /v1/scraper/{scraper_id}/run` and `POST /v1/private-data/search` have no `@limiter.limit(...)`, leaving them open to brute-force token guessing.
- [x] [Review][Patch] **Use generic 401 error details** [`auth.py:193-217`] — `HTTPException` detail strings distinguish "Missing or invalid Authorization header", "Invalid chainlens service token", "Missing X-Workspace-Id header", etc. This leaks validation logic to attackers.
- [x] [Review][Patch] **Make Bearer prefix check case-insensitive** [`auth.py:193`] — `auth_header.startswith("Bearer ")` rejects `bearer token`, which is valid per RFC 7235 scheme case-insensitivity.
- [x] [Review][Patch] **Add locking around token rotation index** [`auth.py:126-143`] — `ChainLensServiceAuth` is exposed as a cached singleton (`get_chainlens_auth`) and `rotate()` mutates `self._index`. Even in asyncio, concurrent callers can race on the shared mutable state.
- [x] [Review][Patch] **Emit `chainlens_token_rotated` metric and richer failure reason** [`auth.py:138`, `executor.py:700`, `ingest.py:177`, `metrics.py:1162`] — Rotation is only logged; there is no metric. When 401 recurs after rotation, the `chainlens_auth_failed` counter uses a generic `reason`; add `reason="rotation_failed"`.
- [x] [Review][Patch] **Handle all tokens expired in `rotate_if_expiring`** [`auth.py:145-157`] — If every token is already expired, `rotate_if_expiring` rotates once to the next expired token and uses it. Should fail open or at least warn when the whole pool is expired.
- [x] [Review][Patch] **Remove unnecessary async wrapper for sync dependency** [`chainlens_internal.py:32-36`] — `chainlens_auth_dependency` wraps `_chainlens_auth_dependency` in `async def` for no benefit; FastAPI accepts sync `Depends`.
- [x] [Review][Patch] **Use `fastapi.status` instead of `starlette.status`** [`auth.py:31`] — Project convention uses `from fastapi import status`.
- [x] [Review][Patch] **Use Title-Case header keys when reading request headers** [`auth.py:192-221`] — Reads `"authorization"` / `"x-workspace-id"` / `"x-correlation-id"` in lowercase while outbound uses `"Authorization"` / `"X-Workspace-Id"` / `"X-Correlation-Id"`. Starlette is case-insensitive, but consistency reduces confusion.
- [x] [Review][Patch] **Remove deprecated `auth_stub.py` or migrate callers** [`auth_stub.py`] — No callers remain; the re-export is dead code and technical debt.
- [x] [Review][Patch] **Add audit logging for auth failures** [`auth.py:185-223`] — Failed validations raise `HTTPException` but are not logged with `workspace_id`/`correlation_id`, hindering incident response.
- [x] [Review][Patch] **Improve integration test fixture isolation** [`test_chainlens_internal.py:45-70`] — The `chainlens_auth_client` fixture mutates `auth_mod.config` and clears `get_chainlens_auth` cache; use `monkeypatch.setattr` with `addfinalizer` to guarantee cleanup.
- [x] [Review][Patch] **Add missing auth unit test cases** [`test_auth.py`] — Negative workspace_id, missing correlation_id, whitespace-stripped tokens, duplicate token deduplication, `CHAINLENS_API_KEY` fallback, and lowercase `bearer` are not covered.

#### defer

- [x] [Review][Defer] **CHOTOT_ITEM billing mapping in `billing.py`** [`billing.py:51,88,217`] — Not part of Story 20.4 scope; it is a pre-existing mapping needed by `app/capabilities/chotot/scrape/definition.py` but was committed in the 20.4 diff. Defer to a `chotot` billing cleanup commit/story.
- [x] [Review][Defer] **Distributed lock for token rotation in multi-instance deployments** [`auth.py:126-157`, `ingest.py:177`, `executor.py:696`] — In-process locking is patchable; cross-instance rotation consistency requires a shared store/lock and is explicitly deferred (`ponytail:`).
- [x] [Review][Defer] **JWT signature validation in `_token_expiry`** [`auth.py:106-124`] — The helper only extracts `exp` from locally-configured tokens for proactive rotation. Token trust is enforced by matching against the configured pool, not by JWT signature. Far-future `exp` and malformed JWT silently return `None`; acceptable for best-effort rotation.
- [x] [Review][Defer] **TokenUsage `usage_type` constants for future ChainLens operations** [`token_tracking_service.py`] — The implementation passes `usage_type` as a string (`deep_research`). Centralized constants can be added when Stories 20.2/20.3 introduce `chainlens_gap_fill`/`chainlens_ingest`/`chainlens_private_search`.
- [x] [Review][Defer] **Integration test asserting `cost_dollars_to_micros` is used end-to-end** [`test_research_cost_metering.py`] — Existing integration tests exercise the full research flow and produce `TokenUsage` rows; a dedicated assertion that `_SSEParser` calls the new static method is low priority.
