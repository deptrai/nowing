# Story 20.3: `NowingPrivateProvider` for `POST /v1/private-data/search`

Status: ready-for-dev

## Story

As a Nowing user,
I want my private data to stay in Nowing while still being used for answers,
so that privacy is preserved.

## Acceptance Criteria

1. **Given** `chainlens-research` calls `POST /v1/private-data/search` with `{ query, userId, workspaceId, connectorId?, sources? }`, **When** the request arrives, **Then** Nowing validates the service auth token and `workspaceId` RLS, then runs the search against the user's private data sources.
2. **Given** private search executes, **When** results are collected, **Then** it returns `SearchProviderResult { chunks: Chunk[], costDollars? }` with `metadata.source = 'private_provider'` and `sourceId` scoped per document/connector.
3. **Given** a `connectorId` is provided, **When** searching, **Then** only data from that connector is returned, and OAuth tokens are fetched from `Nowing` Postgres (never sent to `chainlens-research`).
4. **Given** the request has no matching data, **When** complete, **Then** it returns `chunks: []` and `costDollars: 0`, not 404.

## Tasks / Subtasks

- [ ] Define `NowingPrivateProvider` contract and route (AC: #1)
  - [ ] Create `nowing_backend/app/services/chainlens/private_provider.py` with `PrivateProviderService.search(...)`
  - [ ] Create Pydantic request/response schemas in `nowing_backend/app/services/chainlens/schemas.py`
  - [ ] Add `nowing_backend/app/routes/chainlens_internal.py` route `POST /v1/private-data/search`
  - [ ] Register the route in `nowing_backend/app/routes/__init__.py`
- [ ] Service-to-service auth and RLS (AC: #1)
  - [ ] Reuse `ChainLensServiceAuth` (Story 20.4) to validate the inbound Bearer token
  - [ ] Load the target workspace and confirm `workspaceId` matches the token scope / request path
  - [ ] Apply `SET LOCAL app.workspace_id` RLS context (`AD-5` tenant isolation pattern)
  - [ ] Enforce workspace membership for `userId` (resolve via `app/users.py` or workspace membership lookup)
- [ ] Search private data sources (AC: #1, #2)
  - [ ] Call `app/retriever/chunks_hybrid_search.py` `ChucksHybridSearchRetriever.hybrid_search` for workspace `Document` / `Chunk` data
  - [ ] Call `app/retriever/documents_hybrid_search.py` `DocumentHybridSearchRetriever.hybrid_search` as fallback/variant
  - [ ] Call `app/services/memory/search.py` `MemoryHybridSearch.search` for workspace `Memory` facts
  - [ ] Optionally call `app/services/connector_service.py` connector-specific search when `sources` includes connector types
  - [ ] Merge and deduplicate results from all private sources
- [ ] Connector-scoped search and OAuth tokens (AC: #3)
  - [ ] Filter by `connectorId` to `SearchSourceConnector.id` when provided
  - [ ] Fetch connector credentials / OAuth tokens from `SearchSourceConnector.config` in `app/db.py` (never include in the response)
  - [ ] Use connector-specific `*_kb_sync_service.py` modules only if live data refresh is required; otherwise search indexed `Document`/`Chunk` rows
- [ ] Build `SearchProviderResult` chunks (AC: #2, #4)
  - [ ] Map each result to a `Chunk` with `metadata.source = 'private_provider'`
  - [ ] Set `sourceId` to a stable scoped value such as `nowing://documents/{document_id}` or `nowing://connectors/{connector_id}`
  - [ ] Include `document_id`, `chunk_id`, `connector_id`, `workspace_id` in `metadata` for citation resolution
  - [ ] Return `costDollars: 0` and `chunks: []` when there are no matches (AC: #4)
- [ ] Tests
  - [ ] Unit test `PrivateProviderService` query parsing, RLS scoping, and result mapping
  - [ ] Unit test connector-scoped search and redaction of OAuth tokens
  - [ ] Integration test `POST /v1/private-data/search` with valid and invalid service tokens
  - [ ] Integration test empty results return `200` with `chunks: []` and `costDollars: 0`
  - [ ] Integration test cross-workspace access is denied (RLS / membership check)

## Dev Notes

- Relevant architecture patterns and constraints
  - `AD-15` (Nowing owns private data, `chainlens-research` is the external engine) requires the provider to run inside Nowing and return chunks on demand; no private data is pushed to `chainlens-research` for indexing.
  - `AD-35` (Nowing does not build a public/vertical search corpus) reaffirms that private search is the only workspace-owned search surface.
  - `AD-5` (Zero sync / workspace RLS) — tenant isolation must be applied before any query, ideally via `SET LOCAL app.workspace_id` and workspace-membership checks.
  - `AD-16` (license boundary) — OAuth/connector logic and proprietary fetchers stay in `app/proprietary/` and `app/connectors/`; the `SearchProvider` endpoint contract and RBAC live in Apache-2.0 code outside `app/proprietary/`.
  - `AD-4` (multi-agent chat runtime) — the agent may call this provider indirectly via `chainlens-research`; keep citations on `Run` / `TokenUsage` for audit.
  - `FR-60` and `PRD §4.2/4.9` define the product contract.
  - `ux-contract-private-data-provider.md` defines the required UX trust indicators and citation behavior.

- Source tree components to touch
  - `nowing_backend/app/services/chainlens/private_provider.py` — new `PrivateProviderService`
  - `nowing_backend/app/services/chainlens/schemas.py` — `PrivateDataSearchRequest`, `PrivateDataSearchResponse`, `PrivateProviderChunk`
  - `nowing_backend/app/services/chainlens/auth.py` (Story 20.4) — inbound service token validation
  - `nowing_backend/app/routes/chainlens_internal.py` — `POST /v1/private-data/search`
  - `nowing_backend/app/routes/__init__.py` — router registration
  - `nowing_backend/app/retriever/chunks_hybrid_search.py` — chunk-level hybrid search
  - `nowing_backend/app/retriever/documents_hybrid_search.py` — document-level hybrid search
  - `nowing_backend/app/services/memory/search.py` — memory search
  - `nowing_backend/app/services/connector_service.py` — connector lookup and OAuth config
  - `nowing_backend/app/services/token_tracking_service.py` — record `chainlens_private_search` `TokenUsage`
  - `nowing_backend/app/db.py` — `SearchSourceConnector`, `Document`, `Chunk`, `Memory`, `Workspace`, `User`
  - `nowing_backend/app/auth/context.py` / `app/users.py` — workspace/membership validation
  - `nowing_backend/app/utils/rbac.py` — `check_workspace_access` reuse
  - `nowing_backend/app/observability/metrics.py` — add `chainlens_private_search` latency/counter if needed

- Testing standards summary
  - Mock `chainlens-research` inbound call with valid/invalid `Authorization: Bearer <service-token>`
  - Assert every response chunk has `metadata.source = 'private_provider'` and a scoped `sourceId`
  - Assert no OAuth token, `config` JSON, or raw credential leaves the response
  - Assert cross-workspace requests return `403` and no data
  - Assert empty results are `200 OK` with `chunks: []` and `costDollars: 0`

### Project Structure Notes

- Alignment with unified project structure
  - The `NowingPrivateProvider` is a service, not a capability, so it belongs in `nowing_backend/app/services/chainlens/` alongside `ingest.py` and `gap_fill.py`.
  - The public endpoint is exposed under `nowing_backend/app/routes/chainlens_internal.py` with a dedicated internal-service router.
  - Private data search reuses existing `app/retriever/` and `app/services/memory/search.py` modules rather than building a new index.

- Detected conflicts or variances
  - `TokenUsage` has no `run_id` column and no pre-defined `usage_type` for `chainlens_private_search`; the row must use `call_details` or a new schema migration.
  - `chainlens-research` `SearchProvider` chunk schema may differ from Nowing's internal `Chunk` model; an adapter layer in `private_provider.py` is required.
  - `sourceId` for private chunks must be stable within a workspace but scoped so `chainlens-research` cannot reconstruct document IDs without the Nowing citation resolver.
  - Connector `config` stores OAuth tokens and credentials in `JSONB`; the provider must read them for live sync but must never forward them.

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` §Epic 20 / Story 20.3]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-5]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-15]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-16]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-35]
- [Source: `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` §FR-60]
- [Source: `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-private-data-provider.md`]
- [Source: `nowing_backend/app/retriever/chunks_hybrid_search.py` §`ChucksHybridSearchRetriever`]
- [Source: `nowing_backend/app/retriever/documents_hybrid_search.py` §`DocumentHybridSearchRetriever`]
- [Source: `nowing_backend/app/services/memory/search.py` §`MemoryHybridSearch.search`]
- [Source: `nowing_backend/app/services/connector_service.py`]
- [Source: `nowing_backend/app/db.py` §`SearchSourceConnector`, `Document`, `Chunk`, `Memory`]
- [Source: `nowing_backend/app/utils/rbac.py` §`check_workspace_access`]

## Dev Agent Record

### Agent Model Used

TBD

### Debug Log References

### Completion Notes List

### File List
