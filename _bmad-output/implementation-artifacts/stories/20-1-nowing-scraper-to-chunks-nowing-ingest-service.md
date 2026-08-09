# Story 20.1: Nowing Scraper `to_chunks()` + `NowingIngestService`

Status: ready-for-dev

## Story

As a Nowing user / chat user,
I want my scraper data to be searchable through chainlens,
so that the agent can answer with fresh data.

## Acceptance Criteria

1. **Given** a scraper result (e.g. `batdongsan` listings, `vn_jobs.aggregate` entities), **When** `to_chunks()` is called, **Then** it returns `Chunk[]` with `metadata` containing: `source: 'nowing_scraper'`, `sourceId` (stable fingerprint), `domain`, `fetchedAt`, `contentType`, and `canonicalEntityId` if applicable.
2. **Given** `Chunk[]` from any scraper, **When** `NowingIngestService.ingest(scraper_id, chunks)` is called, **Then** it calls `POST /v1/ingest/scraper` on `chainlens-research` with service auth, `workspace_id`, `source: 'nowing_scraper'`, and the chunk batch; it returns `ingestJobId` and stores the job mapping in `Nowing` Postgres.
3. **Given** a batch larger than 1,000 chunks, **When** ingesting, **Then** `NowingIngestService` paginates the batch and tracks a parent `ingestJobId` plus child job IDs.
4. **Given** `chainlens-research` returns `409` for duplicate `sourceId`, **When** handling the response, **Then** `NowingIngestService` maps duplicates to `noop` status and continues the rest of the batch.
5. **Given** a scraper result is missing required fields (`title`, `company`, `location` for jobs; equivalent for other domains), **When** `to_chunks()` is called, **Then** it raises `ChunkValidationError` with field details and the batch is not sent.
6. **Given** `chainlens-research` returns `5xx` or times out, **When** `NowingIngestService.ingest()` is called, **Then** it retries with exponential backoff (max 3 attempts) and stores the failed batch in a dead-letter queue; after max retries it marks the job `failed` and emits a `chainlens_ingest_failed` counter.
7. **Given** a chunk has `content` larger than 8,000 tokens, **When** `to_chunks()` is called, **Then** it splits into multiple `Chunk` objects with sequential `metadata.chunkIndex` / `metadata.chunkTotal` and stable `sourceId` suffixes.
8. **Given** any `Chunk` produced by `to_chunks()`, **When** it is validated, **Then** it conforms to the canonical `Chunk` schema defined by `chainlens-research` Story `47-1` (`FR-62`, `AD-34`) — including the `source` enum value `nowing_scraper` and required `metadata` fields.

## Tasks / Subtasks

- [ ] Define canonical `Chunk` and `ChunkMetadata` schemas (AC: #1, #5, #7)
  - [ ] Create `nowing_backend/app/services/scraper_chunks/schemas.py` with pydantic models
  - [ ] Add `source`, `sourceId`, `domain`, `fetchedAt`, `contentType`, `chunkIndex`, `chunkTotal`, `canonicalEntityId` fields
  - [ ] Add `ChunkValidationError` and per-domain required-field rules
- [ ] Implement `to_chunks()` helpers/mixins (AC: #1, #5, #7)
  - [ ] Add `nowing_backend/app/services/scraper_chunks/serializer.py` with token-splitting and fingerprinting utilities
  - [ ] Wire `to_chunks()` into `app/capabilities/batdongsan/scrape/executor.py`
  - [ ] Wire `to_chunks()` into `app/capabilities/vn_jobs/aggregate/executor.py` and `app/services/jobs_aggregator/orchestrator.py`
  - [ ] Wire `to_chunks()` into `app/services/bds_aggregator/orchestrator.py`
  - [ ] Add 8,000-token split logic with stable `sourceId` suffixes
- [ ] Implement `NowingIngestService` (AC: #2, #3, #4, #6)
  - [ ] Create `nowing_backend/app/services/chainlens/ingest.py`
  - [ ] Implement `ingest(scraper_id, chunks, workspace_id)` with `ChainLensServiceAuth` headers
  - [ ] Implement 1,000-chunk pagination and parent/child `ingestJobId` tracking
  - [ ] Handle `409` duplicate `sourceId` as `noop`
  - [ ] Add exponential-backoff retry (max 3) and dead-letter queue for `5xx`/timeout
  - [ ] Emit `chainlens_ingest_failed` counter via `app/observability/metrics.py`
  - [ ] Persist job mapping (`ChainLensIngestJob` table or JSONB on `Run`/`ResearchThread`)
- [ ] Integrate ingest into scraper/aggregator executors
  - [ ] Call `NowingIngestService.ingest()` after scraper run completes
  - [ ] Surface `ingestJobId` in `Run` output / `ResearchThread` provenance
- [ ] Tests
  - [ ] Unit tests for `to_chunks()`, token splitting, and validation
  - [ ] Unit tests for `NowingIngestService` batching, retry, 409 handling
  - [ ] Integration test for end-to-end `batdongsan.scrape` -> `POST /v1/ingest/scraper`
  - [ ] Integration test for `vn_jobs.aggregate` -> `NowingIngestService`

## Dev Notes

- Relevant architecture patterns and constraints
  - `AD-34` (Nowing Scraper Feed Contract) defines the canonical `Chunk` schema and `POST /v1/ingest/scraper` contract.
  - `AD-35` (Nowing Does Not Build Public/Vertical Search Corpus) forbids Nowing from creating a `pgvector`/full-text index for vertical data; `chainlens-research` owns canonical indexing.
  - `AD-27` (re-scoped 2026-08-08) requires domain scraper/aggregator output to be normalized to `Chunk[]` with `source: 'nowing_scraper'` and sent to `chainlens-research`.
  - `AD-3` (Scraper capabilities self-register routes) applies to the `<platform>.scrape` / `<domain>.aggregate` capability wiring.
  - `AD-15` treats `chainlens-research` as an external deep-research dependency, not a scraper capability, so `NowingIngestService` is a service adapter rather than a capability.
  - `AD-16` license boundary: fetcher/anti-bot logic stays in `app/proprietary/` (BSL 1.1); `to_chunks()` schemas and the ingest service are Apache-2.0 and live outside `app/proprietary/`.
  - `FR-58` (Scraper Feed), `FR-62` (Chunk Schema), and `PRD §4.2/4.9` provide product requirements.

- Source tree components to touch
  - `nowing_backend/app/services/scraper_chunks/schemas.py` — canonical `Chunk` / `ChunkMetadata` pydantic models
  - `nowing_backend/app/services/scraper_chunks/serializer.py` — `to_chunks()` mixin, token splitting, fingerprinting
  - `nowing_backend/app/services/chainlens/ingest.py` — `NowingIngestService`
  - `nowing_backend/app/services/chainlens/auth.py` (Story 20.4) — `ChainLensServiceAuth` dependency
  - `nowing_backend/app/capabilities/batdongsan/scrape/executor.py`
  - `nowing_backend/app/capabilities/muaban_bds/scrape/executor.py`
  - `nowing_backend/app/capabilities/chotot/scrape/executor.py`
  - `nowing_backend/app/capabilities/vn_jobs/aggregate/executor.py`
  - `nowing_backend/app/services/jobs_aggregator/orchestrator.py`
  - `nowing_backend/app/services/bds_aggregator/orchestrator.py`
  - `nowing_backend/app/capabilities/core/runs.py` — `Run` recording, provenance
  - `nowing_backend/app/db.py` — `Run`, `TokenUsage`, `Chunk` (document chunks), `Memory` models
  - `nowing_backend/app/observability/metrics.py` — add `chainlens_ingest_failed` counter

- Testing standards summary
  - Unit tests in `tests/unit/services/scraper_chunks/` and `tests/unit/services/chainlens/`
  - Integration tests in `tests/integration/services/chainlens/`
  - Mock `chainlens-research` `POST /v1/ingest/scraper` with `httpx` / `respx`
  - Assert `source: 'nowing_scraper'`, stable `sourceId`, and `metadata.domain` on every chunk
  - Validate 409 duplicate handling, 1,000-chunk pagination, retry limits, dead-letter queue

### Project Structure Notes

- Alignment with unified project structure
  - New service modules go under `nowing_backend/app/services/chainlens/` (auth, ingest, gap-fill, private provider) and `nowing_backend/app/services/scraper_chunks/`.
  - Capability executors remain in `nowing_backend/app/capabilities/<platform>/` per `AD-3`.
  - Tests mirror the `tests/unit/` and `tests/integration/` layout.

- Detected conflicts or variances
  - `app/services/jobs_aggregator/orchestrator.py` and `app/services/bds_aggregator/orchestrator.py` currently call `app/canonical/services/canonical_persist_service.py` to persist merged entities locally.
  - `AD-35` / `AD-27` now say Nowing does **not** build a public/vertical search corpus and should send merged `Chunk[]` to `chainlens-research` instead of storing in `canonical_entities`.
  - Decision needed: keep local canonical persistence for product state/provenance (e.g. `Run` logs, billing, conflict flags) but stop using it as the user-facing search index; route search queries to `chainlens-research`.
  - `app/db.py` already has a `Chunk` model (`chunks` table) for uploaded documents; do not overload it for scraper `Chunk[]` meant for `chainlens-research`.

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` §Epic 20 / Story 20.1]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-3]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-15]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-16]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-27]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-34]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-35]
- [Source: `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` §FR-58, FR-62]
- [Source: `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-ecosystem-search.md` §2B Ingest / Sync Status]
- [Source: `nowing_backend/app/capabilities/chainlens/research/executor.py`]
- [Source: `nowing_backend/app/capabilities/core/billing.py`]
- [Source: `nowing_backend/app/db.py` §TokenUsage / Run / Chunk]

## Dev Agent Record

### Agent Model Used

TBD

### Debug Log References

### Completion Notes List

### File List
