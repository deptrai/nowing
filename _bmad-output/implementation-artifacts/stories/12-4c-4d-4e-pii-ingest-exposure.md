---
title: Story 12.4c+4d+4e — PII Redaction, Chunk Ingest & Aggregator Exposure
epic: 12
story: 4c-4d-4e
status: ready-for-dev
priority: P0
---

# Story 12.4c+4d+4e — PII Redaction, Chunk Ingest & Aggregator Exposure

**Epic:** 12 — HR/Recruitment Vertical — Vietnam Job Market Pilot
**As a:** workspace owner + platform engineer + research analyst
**I want:** PII redacted before ingest, chunks reliably sent to chainlens-research, and the aggregator callable from REST/MCP/chat
**So that:** the research index stays fresh without retaining PII, and I can ask job market questions anywhere.

Covers epics.md stories **12.4c** (PII) + **12.4d** (ingest) + **12.4e** (exposure). These three are grouped because they're nearly done — only small gaps remain.

---

## Acceptance Criteria

### From 12.4c — PII Redaction

1. **Given** PII (phone, email, person names) is found in `job_description` or `job_requirement`, **When** chunks are built, **Then** AD-25 redaction is applied before any data is sent to `chainlens-research` or stored in `Memory`.
2. **Given** redaction completes, **When** the chunk is persisted or sent, **Then** it contains only masked/dropped PII and audit stats log counts (not values).

### From 12.4d — Chunk Ingest

3. **Given** the aggregator has normalized listings, **When** `to_chunks()` is called, **Then** each listing becomes a `Chunk` with `metadata.source: 'nowing_scraper'`, `sourceId` (stable: `sha256(company|title|location|posted_at)`), `domain`, `fetchedAt`, `contentType: 'job'`, `salary`, `confidence_score`, `salary_consistency_score`, and `conflict_flags`.
4. **Given** a `Chunk[]` batch, **When** `NowingIngestService.ingest()` is called, **Then** it calls `POST /v1/ingest/scraper` on `chainlens-research` with service auth, `workspace_id`, and the batch; it returns `ingestJobId` and stores the job mapping in Nowing Postgres.
5. **Given** `chainlens-research` returns `5xx` or times out, **When** `NowingIngestService.ingest()` is called, **Then** it retries with exponential backoff (max 3 attempts) and stores the failed batch in a dead-letter queue; after max retries it marks the job `failed` and emits a `chainlens_ingest_failed` counter.

### From 12.4e — Exposure

6. **Given** the aggregator is exposed, **When** called via REST, MCP (`nowing_vn_jobs_aggregate`), or chat agent, **Then** it returns `VnJobAggregateOutput { items, degraded, degradationReasons, sourceBreakdown, costMicros, ingestJobId }`; it does not query a local Nowing search corpus.
7. **Given** `to_chunks()` produces a `Chunk[]`, **When** the batch is sent to `chainlens-research`, **Then** each `Chunk` conforms to the canonical schema and `source` enum (AD-35); if `chainlens-research` rejects a chunk for schema violation, `NowingIngestService` logs the first failing chunk and fails the batch.

---

## [BUILT] — DO NOT re-implement

### PII (12.4c)
- **`redact_job_pii`** — `app/services/pii/redact.py:91`: masks phone/email/names. Returns `RedactedText` with `.text`, `.has_pii`, `.counts`.
- **Wired into orchestrator** — `orchestrator.py:63-72` (`_redact_listing`): runs before dedupe. Sets `pii_redacted = True`.
- **Canonical PII** — `app/canonical/services/canonical_pii.py:122` (`redact_canonical_data`): second-pass for canonical storage.
- **Chunk serializer redaction** — `scraper_chunks/serializer.py`: `_redact_text()` during chunk building. Test `test_to_chunks_redacts_pii_before_chunking` verifies masking.

### Ingest (12.4d)
- **`to_chunks()`** — `app/services/scraper_chunks/serializer.py:354-413`: job domains map to canonical domain (`itviec.com`, etc.) + `contentType = "job"` (Story 12.3 fix).
- **`ChunkMetadata`** — `app/services/scraper_chunks/schemas.py`: carries `source`, `sourceId`, `domain`, `fetchedAt`, `contentType`, `confidence_score`, `source_count`, `conflict_flags`.
- **`NowingIngestService`** — `app/services/chainlens/ingest.py:262-469`: pagination (default 1000), retry with backoff, auth via `ChainLensServiceAuth`.
- **Route wiring** — `app/routes/chainlens_internal.py:165-207`: `to_chunks()` → `NowingIngestService.ingest()`.
- **Tests** — `tests/unit/services/scraper_chunks/` (14 tests), `tests/unit/routes/test_chainlens_internal.py` (14 tests). All passing.

### Exposure (12.4e)
- **MCP tool** — `nowing_mcp/mcp_server/features/scrapers/platforms/vn_jobs.py`: `nowing_vn_jobs_aggregate` registered, all params wired.
- **REST route** — `chainlens_internal.py:35,136`: `_DOMAIN_CAPABILITY_MAP["vn_jobs"] = "vn_jobs.aggregate"`.
- **Chat subagent** — `app/agents/chat/multi_agent_chat/subagents/builtins/vn_jobs/`: agent, tools, system prompt.
- **Capability + billing** — `app/capabilities/vn_jobs/aggregate/`: registered with `BillingUnit.VN_JOBS_AGGREGATE_QUERY`. 4 tests passing.

## [GAP] — still to build

### PII gaps (AC-1, AC-2)
1. **Audit stats logging.** AC-2 requires "audit stats log counts (not values)". `redact_job_pii` returns `.counts` but orchestrator doesn't log them. Add structured log with PII type counts (e.g., `{"phones": 2, "emails": 1}`).
2. **NER for person names.** `redact_job_pii` handles phone + email via regex. Person names in JD text need NER or heuristic. Check if `redact_pii` already has name detection — if not, gap from Story 12.5 AC-2.

### Ingest gaps (AC-3, AC-4, AC-5)
3. **`sourceId` fingerprint alignment.** AC-3 says `sha256(company|title|location|posted_at)`. Current `_identity_fields()` in `serializer.py:207-214` uses `{title, company, location, salary, employment_type}` — missing `posted_at`, has extra fields. Fix: for job domains, use `{company, title, location, posted_at}` (remove `salary` + `employment_type`, add `posted_at`).
4. **`salary` + `salary_consistency_score` not in ChunkMetadata.** AC-3 requires both. `ChunkMetadata` doesn't have these fields. Decision: add `salary: dict | None = None` and `salary_consistency_score: float | None = None` to `ChunkMetadata` for job domains, OR document that salary is in-content only (chunk content text includes salary range).
5. **Dead-letter queue — ALREADY EXISTS.** `ChainLensIngestJob.dead_letter_payload` JSONB column (db.py:4219) stores failed batch payload. Populated in `ingest.py:455`. No new table needed. Gap: add reprocessing/admin endpoint if manual retry is needed.
6. **`ingestJobId` → Postgres mapping — ALREADY EXISTS.** `ChainLensIngestJob` table (db.py:4183) persists mapping. Route returns `ingest_job_id` (chainlens_internal.py:203). No new code needed.
7. **`chainlens_ingest_failed` counter — ALREADY EXISTS.** Counter in `metrics.py:1174-1178`, called in `ingest.py:367,391`. No new code needed.

### Exposure gaps (AC-6, AC-7)
8. **`ingestJobId` not in `VnJobAggregateOutput`.** AC-6 requires it. Output schema has `persistence_status` but no `ingest_job_id`. Add `ingest_job_id: str | None = None`.
9. **Schema violation handling — PARTIALLY EXISTS.** `NowingIngestService._post_batch_core()` (ingest.py:143) already handles 400/422 as non-retryable `ConnectorAPIError`. Gap: add specific logging of first failing chunk details before failing batch (AC-7 requirement).

---

## Tasks / Subtasks

- [ ] AC-1: PII covers all fields (AC: #1)
  - [x] `job_description` + `job_requirement` redacted in orchestrator + chunk serializer
  - [ ] Verify `skills`, `title`, `company` don't carry PII
  - [ ] Add/verify NER for person names
- [ ] AC-2: Audit logging (AC: #2)
  - [ ] Log PII redaction counts (structured, no values)
- [ ] AC-3: Chunk metadata completeness (AC: #3)
  - [x] `source`, `domain`, `fetchedAt`, `contentType: 'job'`, `confidence_score`, `conflict_flags`
  - [ ] Align `sourceId` to `sha256(company|title|location|posted_at)` for job domains
  - [ ] Add `salary` + `salary_consistency_score` to ChunkMetadata (or document in-content only)
- [ ] AC-4: Ingest + job mapping (AC: #4)
  - [x] `NowingIngestService.ingest()` + pagination
  - [x] Persist `ingestJobId` → Postgres mapping (`ChainLensIngestJob` table, db.py:4183)
- [ ] AC-5: Retry + DLQ + counter (AC: #5)
  - [x] Exponential backoff retry
  - [x] DLQ: `ChainLensIngestJob.dead_letter_payload` column (db.py:4219)
  - [x] `chainlens_ingest_failed` counter (metrics.py:1174-1178, called in ingest.py:367,391)
  - [ ] Add admin reprocessing endpoint if manual retry needed (optional)
- [ ] AC-6: Output includes `ingestJobId` (AC: #6)
  - [x] REST + MCP + chat all wired
  - [ ] Add `ingest_job_id: str | None = None` to `VnJobAggregateOutput`
- [ ] AC-7: Schema violation handling (AC: #7)
  - [x] `NowingIngestService` handles 400/422 as non-retryable `ConnectorAPIError` (ingest.py:143)
  - [ ] Log first failing chunk details before failing batch

---

## Dev Notes

### `to_chunks()` is in the route, NOT the orchestrator
Aggregator (`aggregate_jobs`) produces `VnJobAggregateOutput`. Route (`chainlens_internal.py:165-207`) iterates items, calls `to_chunks()`, then `NowingIngestService.ingest()`. This separation is by design (AD-34). Don't merge ingest into orchestrator.

### PII redaction is defense-in-depth
Orchestrator redacts before dedupe (`orchestrator.py:63-72`). Chunk serializer redacts during content building (`serializer.py:86-104`). Both use same `redact_job_pii` function — this is intentional defense-in-depth. Canonical storage has a second pass via `redact_canonical_data` (`canonical_pii.py:122`).

### `NowingIngestService` already has pagination + retry + DLQ + counter
`ingest.py:300-303` paginates via `CHAINLENS_INGEST_MAX_BATCH_SIZE`. Retry in batch loop. DLQ via `ChainLensIngestJob.dead_letter_payload` column. Counter via `chainlens_ingest_failed` in metrics.py. Don't re-implement — only add: (1) `ingest_job_id` to output schema, (2) first-failing-chunk logging on 400/422, (3) `sourceId` alignment, (4) salary fields in ChunkMetadata.

### Architecture compliance
- **AD-25**: PII redaction before chunk + ingest (already wired, verify completeness).
- **AD-34**: Chunk schema conformance with chainlens-research Story 47-1.
- **AD-35**: `source` enum — `nowing_scraper` is canonical.

### Testing
```bash
cd nowing_backend && uv run pytest tests/unit/services/scraper_chunks tests/unit/routes/test_chainlens_internal.py tests/unit/capabilities/vn_jobs -q
cd nowing_backend && uv run pytest tests/integration/services/chainlens/test_ingest.py -q  # requires Postgres
cd nowing_mcp && uv run --active python -m mcp_server.selfcheck  # nowing_vn_jobs_aggregate present
cd nowing_backend && ruff check app/services/scraper_chunks app/services/chainlens/ingest.py app/routes/chainlens_internal.py app/services/pii
```

### References
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/services/pii/redact.py" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/services/scraper_chunks/serializer.py" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/services/scraper_chunks/schemas.py" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/services/chainlens/ingest.py" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/routes/chainlens_internal.py" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_mcp/mcp_server/features/scrapers/platforms/vn_jobs.py" />
