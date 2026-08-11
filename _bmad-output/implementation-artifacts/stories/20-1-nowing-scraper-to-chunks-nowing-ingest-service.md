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

## Common LLM Mistakes to Avoid

- Do not reuse or extend the existing `Chunk` SQLAlchemy model/table in `nowing_backend/app/db.py` for scraper `Chunk[]`. That table stores document-upload chunks with embeddings; scraper `Chunk[]` are transient, schema-bound payloads sent to `chainlens-research` (AD-35).
- Do not build a local pgvector/full-text search corpus, `canonical_entities` table, or a new `bds_search`/`jobs_search` index in Nowing. All public/vertical search goes through `chainlens-research` (AD-27, AD-35).
- Do not place `to_chunks()` or `NowingIngestService` inside `nowing_backend/app/proprietary/`. Fetchers, anti-bot logic, and platform-specific parsers stay BSL 1.1 in `app/proprietary/platforms/*`; chunk schemas, serializer, and ingest service are Apache-2.0 in `app/services/*` (AD-16).
- Do not call `chainlens-research` synchronously inside a scraper executor that blocks a chat turn. Ingest should be invoked after child scraper results are aggregated and off the chat critical path (AD-15, AD-17).
- Do not treat `chainlens-research` as a scraper capability governed by AD-3. It is an external dependency; `NowingIngestService` is a service adapter, not a registered capability (AD-15).
- Do not use random UUIDs for `sourceId`. It must be a stable, deterministic fingerprint (e.g., SHA-256 of sorted canonical identity fields) so `POST /v1/ingest/scraper` is idempotent on retry and duplicate detection works (FR-58, FR-62).
- Do not silently drop `409 Conflict` responses. Map each duplicate `sourceId` to a `noop` ingest status and continue processing the rest of the batch (AC #4).
- Do not retry `409` or other `4xx` schema/client errors with exponential backoff. Only `5xx`, `504`, and network/timeout errors get retries (max 3 attempts). Reuse `app/utils/async_retry.py` with a predicate limited to those cases; do not add a new retry library.
- Do not emit raw PII in chunk `content` or metadata. Run the appropriate redactor (`redact_source_snapshot`, `redact_job_pii`, or `redact_pii`) before chunking, per AD-25 and FR-58.
- Do not split oversized `content` at arbitrary byte or character boundaries. Splitting >8,000 tokens must preserve word/sentence boundaries and produce sequential `metadata.chunkIndex` / `metadata.chunkTotal` with stable `sourceId` suffixes (AC #7).
- Do not coerce `workspace_id` to UUID or treat `client_id` as UUID. `workspace_id` is an integer foreign key to `workspaces.id`; `client_id` is the CITEXT natural key of `vertical_clients.client_id` (AD-31).
- Do not record business-event ingest costs in `TokenUsage`. `TokenUsage` is for LLM token consumption; use `BillingEvent`/`BillingEvent.cost_micros` or the `chainlens_ingest_failed` metric for operational counters (AD-8, AD-10).
- Do not implement `ChainLensServiceAuth` from scratch. It is a Story 20.4 dependency. Story 20.1 should define a small `ChainLensAuthProvider` protocol/interface and a temporary stub that reads `CHAINLENS_API_KEY`, with a TODO pointing to Story 20.4.

## Architecture Compliance

| Decision | Requirement in this story | Source |
|---|---|---|
| **AD-27** — Nowing scraper output feeds `chainlens-research` | `to_chunks()` returns `Chunk[]` with `source: 'nowing_scraper'` and metadata `domain`, `sourceId`, `fetchedAt`, `contentType`. `NowingIngestService` sends the batch to `POST /v1/ingest/scraper` and stores the returned `ingestJobId`. Nowing does not create a canonical index for vertical data. | `ARCHITECTURE-SPINE.md` §AD-27 |
| **AD-34** — Scraper feed contract | `Chunk` schema matches the canonical `@chainlens/types` contract: `content` (string) + strict `metadata` with required `source`, `sourceId`, `domain`, `fetchedAt`, `contentType` and optional `confidence_score`, `source_count`, `conflict_flags`. `source` enum is limited to the values owned by `chainlens-research`. Ingest is idempotent by `sourceId` and returns `ingestJobId`. | `ARCHITECTURE-SPINE.md` §AD-34 |
| **AD-35** — Nowing does not build a public/vertical search corpus | Do not add pgvector columns, FTS indexes, or `canonical_entities` rows for BĐS/jobs/news listings as a search index. `Memory` stays scoped to private workspace facts. Raw scraper logs and `Run`/`ResearchThread` provenance are allowed for product state and billing only. | `ARCHITECTURE-SPINE.md` §AD-35 |
| **AD-3** — Scraper capabilities self-register routes | The individual scraper/aggregator executors (`batdongsan.scrape`, `chotot.scrape`, `muaban_bds.scrape`, `vn_jobs.aggregate`, `vn_bds.aggregate`) remain registered capabilities in `app/capabilities/<platform>/` with `definition.py` and `build_capabilities_router()`. `to_chunks()` is a pure helper/mixin, not a new route. `NowingIngestService` is a service adapter, not a capability, and is not governed by AD-3. | `ARCHITECTURE-SPINE.md` §AD-3 |
| **AD-16** — License three-tier boundary | New modules `app/services/scraper_chunks/*` and `app/services/chainlens/*` are Apache-2.0. They may import from `app/proprietary/*` one-way if needed to transform raw results, but no proprietary fetcher/anti-bot code is copied into `app/services/*`, and no Apache-2.0 logic is moved into `app/proprietary/*`. | `ARCHITECTURE-SPINE.md` §AD-16 |

`AD-15` and `AD-25` are also relevant: `NowingIngestService` is an external-service adapter (AD-15), and PII must be redacted before chunk content is built (AD-25).

## File Structure Requirements

### Create (Apache-2.0)

- `nowing_backend/app/services/scraper_chunks/__init__.py`
- `nowing_backend/app/services/scraper_chunks/schemas.py` — `Chunk`, `ChunkMetadata` Pydantic models and `ChunkValidationError`.
- `nowing_backend/app/services/scraper_chunks/serializer.py` — `to_chunks()` mixin/helper, token splitter, fingerprint utilities.
- `nowing_backend/app/services/chainlens/__init__.py`
- `nowing_backend/app/services/chainlens/ingest.py` — `NowingIngestService`, batching, retry, dead-letter handling, `ingestJobId` persistence.
- `nowing_backend/app/services/chainlens/auth_stub.py` (temporary) — minimal `ChainLensAuthProvider` protocol/stub until Story 20.4 lands.
- `tests/unit/services/scraper_chunks/test_schemas.py`
- `tests/unit/services/scraper_chunks/test_serializer.py`
- `tests/unit/services/chainlens/test_ingest.py`
- `tests/integration/services/chainlens/test_ingest.py`
- Alembic migration if a new `chainlens_ingest_jobs` table is chosen: `nowing_backend/alembic/versions/NNN_add_chainlens_ingest_jobs.py`.

### Update (Apache-2.0 unless already BSL)

- `nowing_backend/app/capabilities/batdongsan/scrape/executor.py` — call `to_chunks()` and pass `Chunk[]` to `NowingIngestService` after scrape.
- `nowing_backend/app/capabilities/chotot/scrape/executor.py` — same, for each supported category.
- `nowing_backend/app/capabilities/muaban_bds/scrape/executor.py` — same.
- `nowing_backend/app/capabilities/vn_jobs/aggregate/executor.py` — call `to_chunks()` on normalized job listings.
- `nowing_backend/app/services/bds_aggregator/orchestrator.py` — replace or augment current `canonical_entities` persistence with `to_chunks()` -> `NowingIngestService` for the merged `VnBdsAggregatedListing` list.
- `nowing_backend/app/services/jobs_aggregator/orchestrator.py` — same for `VnJobAggregatedListing`.
- `nowing_backend/app/observability/metrics.py` — add `chainlens_ingest_failed` counter (follow `record_canonical_persist_failure` pattern).
- `nowing_backend/app/capabilities/core/runs.py` — surface `ingestJobId`/`parent_ingest_job_id` on `Run` output/provenance.
- `nowing_backend/app/config/__init__.py` — add `CHAINLENS_INGEST_URL`, `CHAINLENS_INGEST_MAX_BATCH_SIZE` (default 1000), `CHAINLENS_INGEST_TIMEOUT_SECONDS`, `CHAINLENS_INGEST_RETRY_MAX_ATTEMPTS` (default 3) if not present.
- `nowing_backend/app/db.py` — only if adding a `ChainLensIngestJob` model or a JSONB column on `Run`/`ResearchThread`; requires a matching Alembic migration.

### Do not touch

- `nowing_backend/app/proprietary/platforms/*` fetcher/parser files (BSL 1.1). Modify only capability/aggregator executors and service modules.
- `nowing_backend/app/db.py` existing `Chunk` table and `Memory` search indexes; do not overload them for scraper chunks.
- `sprint-status.yaml`.

### License boundaries

- `app/services/scraper_chunks/` and `app/services/chainlens/` are Apache-2.0. No BSL code should be copied there.
- `app/proprietary/platforms/*` remains BSL 1.1. One-way import from Apache-2.0 into proprietary is allowed; reverse is not.

## Testing Requirements

### Unit tests

- `tests/unit/services/scraper_chunks/test_schemas.py`
  - Validate `Chunk`/`ChunkMetadata` enforce required fields (`source`, `sourceId`, `domain`, `fetchedAt`, `contentType`), correct `source` enum, and optional metadata (`confidence_score`, `source_count`, `conflict_flags`, `chunkIndex`, `chunkTotal`, `canonicalEntityId`).
  - Validate `ChunkValidationError` is raised with field details when required domain fields are missing (e.g., jobs: `title`, `company`, `location`; BĐS: `title`, `city`/`district`, `price`).

- `tests/unit/services/scraper_chunks/test_serializer.py`
  - Test `to_chunks()` for representative batdongsan, chotot, muaban_bds, and vn_jobs raw outputs produces `Chunk[]` with `source: 'nowing_scraper'`, stable `sourceId`, `fetchedAt`, `contentType`.
  - Test token splitting >8,000 tokens produces sequential `metadata.chunkIndex` / `metadata.chunkTotal` and deterministic `sourceId` suffixes.
  - Test fingerprinting is deterministic across runs and stable when optional fields vary.
  - Test redacted PII does not appear in `content`.

- `tests/unit/services/chainlens/test_ingest.py`
  - Test `NowingIngestService.ingest()` calls `POST /v1/ingest/scraper` with `Authorization` Bearer header, `workspace_id`, and `source: 'nowing_scraper'`.
  - Test batch size >1,000 is paginated into child jobs with a parent `ingestJobId`; child job IDs are recorded.
  - Test `409` duplicate `sourceId` responses map to `noop` status and the rest of the batch continues.
  - Test `5xx`/timeout triggers exponential backoff retry (max 3 attempts) and, after final failure, records the batch in a dead-letter queue and emits `chainlens_ingest_failed`.
  - Test `ingestJobId` and `parent_ingest_job_id` are persisted in Postgres.
  - Test service auth unavailable fails open with `service_auth_unavailable` and does not send user data with an invalid token (per Epic 20 `ChainLensServiceAuth` AC).

### Integration tests

- `tests/integration/services/chainlens/test_ingest.py`
  - End-to-end `batdongsan.scrape` (mocked child) -> aggregator -> `to_chunks()` -> mocked `POST /v1/ingest/scraper`; assert `source`, `sourceId`, `metadata.domain` on every chunk.
  - End-to-end `vn_jobs.aggregate` (mocked sources) -> `to_chunks()` -> ingest; assert `contentType: 'job'`, `metadata.salary`, `confidence_score`, `salary_consistency_score`, `conflict_flags` if present.
  - Degraded source still allows remaining sources to be ingested and `degraded=true`/`degradation_reasons` are surfaced.
  - Use `respx`/`httpx` to mock `chainlens-research`. Use real PostgreSQL for `Run`/`chainlens_ingest_jobs` persistence.

### Contract / regression

- Add a fixture-based test under `tests/unit/services/chainlens/fixtures/` with canonical `Chunk` samples and assert `NowingIngestService` serializes exactly to the schema `chainlens-research` Story 47-1 expects (FR-62, AD-34).
- Run `python3 scripts/check-docs-drift.py` before final commit.

### Mutation gate

- Run `python scripts/mutation-gate.py` on the new service modules (e.g., `scraper_chunks/serializer` and `chainlens/ingest`) with `--project-root . --timeout 120.0`.

## Previous Story Intelligence

- Epic 10 built the BĐS scraper foundation (`batdongsan`, `chotot`, `muaban_bds`) and the `vn_bds.aggregate` aggregator. The current `app/services/bds_aggregator/orchestrator.py` still persists to `canonical_entities` via `upsert_canonical_entity`; Story 20.1 must keep `Run`/provenance/billing state but route the canonical search index to `chainlens-research` (AD-27/AD-35).
- `app/services/bds_aggregator/normalize.py` and `dedupe.py` already produce stable canonical fingerprints:
  - `make_canonical_id()` hashes sorted source IDs.
  - `fingerprint()` falls back to a SHA-256 of canonical identity fields (`title`, `address`, etc.).
  Reuse these hashing conventions for `Chunk.sourceId` instead of inventing a new scheme.
- Deduplication is union-find over `phone_key`, `address_key`, and `image_key` with transitive merging. Conflicts are detected when prices diverge >20% and surfaced as `ConflictFlag` with `price_range` / `price_sources`. These should map to `metadata.conflict_flags` in the `Chunk`.
- Confidence scoring (`app/services/bds_aggregator/scoring.py`) blends `source_trust`, `overlap_score`, `freshness_score`, and `price_consistency_score`; the result goes into `metadata.confidence_score` and `source_count` per FR-62.
- `app/services/jobs_aggregator/orchestrator.py` already redacts PII (`redact_job_pii`) before deduplication and carries `salary_consistency_score` and `pii_redacted` flags; mirror these in job `Chunk` metadata.
- Degraded child source handling is already implemented: `_execute_source` catches `ValidationError` and generic exceptions, returns `degraded=true` with a reason, and lets other sources continue. `NowingIngestService` must not fail the whole batch because one source was degraded.
- Anti-bot/captcha escalation is handled asynchronously (`capture_platform_anti_bot_screenshot_task`) and is not a hard failure. Ingest should be off the chat critical path.
- Capability wiring uses `get_capability()`, `cap.input_schema`, and `execute_with_context()`. `to_chunks()` should be a pure helper called after normalization, not a separately registered capability.
- Billing is recorded per returned listing (`BATDONGSAN_ITEM`, `CHOTOT_BDS_ITEM`, `MUABAN_BDS_ITEM`); the ingest service itself is a cost-free outbound adapter, but `chainlens-research` may report ingestion cost in `costDollars` if that changes later (track with `BillingEvent` if so).

## Git Intelligence

Recent `git log --oneline -10` (from repo root):

```
b48d5f17d docs(planning): align Epic 20 story numbering across epics.md, sprint-status, and architecture
48bf5e7ab docs(planning): re-run implementation readiness, update sprint-status dependencies, and harden 4.8h ACs
feff6bba4 docs(planning): append cleanup addendum to implementation readiness report
aa5dc178c docs(planning): reorder epics, split 12.4, add 6.8, extract Epic 21 proposal
63c9343d4 docs(architecture): close Epic 21 literal seams and align code with AD-43/46/47/49
13f766b33 Resolve Epic 21 architecture conflicts and hand off UX contracts
c43ef5846 docs(planning): align open-core messaging and vision copy across planning artifacts
6021e9f5c docs(planning): commit aligned planning artifacts and updated readiness report
bb171a13e fix(epics): add explicit error-path acceptance criteria to 45 active stories
8c27d1ef3 fix(epics): resolve forward dependencies and surface cross-cutting prerequisites
```

Patterns:
- Recent commits are almost all `docs(planning)`, `docs(architecture)`, and `fix(epics)` focused on artifact alignment, AC hardening, readiness reports, and dependency cleanup.
- No Epic 20 code has landed on `develop` yet. Story 20.1 will set the code pattern for 20.2–20.4.
- For code changes, follow the existing conventional-commit style: `feat(services): ... Story 20.1` for new modules, `test(services): ...` for tests, `fix(services): ...` for fixes. Planning-only edits should use `docs(planning):` or `docs(architecture):`.
- Do not edit `sprint-status.yaml` from this story; it is updated by planning commits only.

## Dev Agent Record

### Agent Model Used

TBD

### Debug Log References

### Completion Notes List

### File List
