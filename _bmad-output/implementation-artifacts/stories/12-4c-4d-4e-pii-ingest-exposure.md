---
title: Story 12.4c+4d+4e — PII Redaction, Chunk Ingest & Aggregator Exposure
epic: 12
story: 4c-4d-4e
status: approved
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
1. ~~**Audit stats logging.**~~ ✅ Done: `_redact_listing` calls `record_vn_jobs_pii_detected` and logs structured counts.
2. **NER for person names.** `redact_job_pii` handles phone + email via regex. Person names in JD text need NER or heuristic. Check if `redact_pii` already has name detection — if not, gap from Story 12.5 AC-2.

### Ingest gaps (AC-3, AC-4, AC-5)
3. ~~**`sourceId` fingerprint alignment.**~~ ✅ Done: job-domain uses `{company, title, location, posted_at}`; canonical_id path keeps `canonical_id + posted_at`.
4. ~~**`salary` + `salary_consistency_score` not in ChunkMetadata.**~~ ✅ Done: both fields added.
5. **Dead-letter queue — ALREADY EXISTS.** `ChainLensIngestJob.dead_letter_payload` JSONB column (db.py:4219) stores failed batch payload. Populated in `ingest.py:455`. No new table needed. Gap: add reprocessing/admin endpoint if manual retry is needed (optional).
6. **`ingestJobId` → Postgres mapping — ALREADY EXISTS.** `ChainLensIngestJob` table (db.py:4183) persists mapping. ✅ Exposed in `VnJobAggregateOutput` via executor.
7. **`chainlens_ingest_failed` counter — ALREADY EXISTS.** Counter in `metrics.py:1174-1178`, called in `ingest.py:367,391`. No new code needed.

### Exposure gaps (AC-6, AC-7)
8. ~~**`ingestJobId` not in `VnJobAggregateOutput`.**~~ ✅ Done: `ingest_job_id`, `ingest_status`, `ingested_count`, `noop_count` added. Executor ingests before returning.
9. ~~**Schema violation handling.**~~ ✅ Done: `NowingIngestService` logs first failing chunk details + `validation_error` from response body on 400/422.

---

## Tasks / Subtasks

- [ ] AC-1: PII covers all fields (AC: #1)
  - [x] `job_description` + `job_requirement` redacted in orchestrator + chunk serializer
  - [ ] Verify `skills`, `title`, `company` don't carry PII
  - [ ] Add/verify NER for person names
- [x] AC-2: Audit logging (AC: #2)
  - [x] Log PII redaction counts (structured, no values)
- [x] AC-3: Chunk metadata completeness (AC: #3)
  - [x] `source`, `domain`, `fetchedAt`, `contentType: 'job'`, `confidence_score`, `conflict_flags`
  - [x] Align `sourceId` to `sha256(company|title|location|posted_at)` for job domains
  - [x] Add `salary` + `salary_consistency_score` to ChunkMetadata
- [x] AC-4: Ingest + job mapping (AC: #4)
  - [x] `NowingIngestService.ingest()` + pagination
  - [x] Persist `ingestJobId` → Postgres mapping (`ChainLensIngestJob` table, db.py:4183)
- [x] AC-5: Retry + DLQ + counter (AC: #5)
  - [x] Exponential backoff retry
  - [x] DLQ: `ChainLensIngestJob.dead_letter_payload` column (db.py:4219)
  - [x] `chainlens_ingest_failed` counter (metrics.py:1174-1178, called in ingest.py:367,391)
  - [ ] Add admin reprocessing endpoint if manual retry needed (optional)
- [x] AC-6: Output includes `ingestJobId` (AC: #6)
  - [x] REST + MCP + chat all wired via executor
  - [x] Add `ingest_job_id`, `ingest_status`, `ingested_count`, `noop_count` to `VnJobAggregateOutput`
- [x] AC-7: Schema violation handling (AC: #7)
  - [x] `NowingIngestService` handles 400/422 as non-retryable `ConnectorAPIError` (ingest.py:143)
  - [x] Log first failing chunk details before failing batch

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

---

## Challenge Log (grill-me)

### Q1 — Already implemented?

**CRITICAL FINDING — `record_vn_jobs_pii_detected()` metric function exists but is NEVER CALLED.**

`app/observability/metrics.py:1463-1467` defines `record_vn_jobs_pii_detected(*, source, pii_type, count)` — a structured metric for PII detection counts. It is exported in `__all__` (line 1533) but **no caller in the codebase invokes it**. This is dead code that should be wired up, NOT reinvented.

**Action:** Call `record_vn_jobs_pii_detected(source=source, pii_type="phones", count=redacted.phones_detected)` etc. in `orchestrator.py:_redact_listing()` after `redact_job_pii()` returns.

**Other findings:**
- `sourceId` fingerprint (posted_at): DOES NOT EXIST — `_identity_fields()` job branch (serializer.py:207-214) has no `posted_at`
- `salary` in ChunkMetadata: DOES NOT EXIST — `ChunkMetadata` (schemas.py:21-46) has no salary field
- `ingest_job_id` in VnJobAggregateOutput: DOES NOT EXIST — output schema (schemas.py:74-99) has no field
- First-failing-chunk logging: DOES NOT EXIST — `ConnectorAPIError` handling (ingest.py:231-236) logs generic error only

### Q2 — Simpler alternative?

No simpler alternative found. Existing code structure is clean:
- `_identity_fields()` already has job-domain branch → just add `posted_at`, remove `salary`/`employment_type`
- `record_vn_jobs_pii_detected()` already exists → just call it
- `ChunkMetadata` has `model_config = ConfigDict(extra="allow")` → salary field can be added without breaking existing chunks

### Q3 — Edge cases spec misses (Pattern 3)

- [ ] **Boundary:** `posted_at` is None in sourceId fingerprint → fingerprint includes "None" string. Is this stable across re-scrapes? (Yes, if scraper consistently omits posted_at, but document it.)
- [ ] **Null/empty:** Salary is None (negotiable/hidden) in ChunkMetadata → should `salary: dict | None = None` be set or omitted?
- [ ] **Null/empty:** `ingest_job_id` when ingest fails → should be `None` (not the failed job ID, since no job was created)
- [ ] **Concurrent:** Two concurrent `aggregate_jobs` calls for same query → both call `NowingIngestService.ingest()` → duplicate chunks in ChainLens? (ChainLens should dedupe via sourceId, but verify.)
- [ ] **Boundary:** PII redaction counts are 0 → `record_vn_jobs_pii_detected` already guards `if count <= 0: return` (metrics.py:1465) — no action needed

### Q4 — Failure modes unspecified (Pattern 2, 4)

- [ ] **ChainLens returns 400 with no body:** How to log "first failing chunk"? Fallback: log batch metadata (sourceId range, domain, count) since chunk-level detail unavailable
- [ ] **ChainLens returns 422 with array of validation errors:** Which error is "first"? Use response body `errors[0]` if available, else log batch metadata
- [ ] **PII redaction fails (regex error):** `redact_job_pii` should not raise — it's a regex-based function. If it does, orchestrator's try/except around source calls will catch it. Verify redact.py has no unhandled exceptions.
- [ ] **ingest_job_id mapping fails (DB error):** `ChainLensIngestJob` insert fails → ingest already succeeded in ChainLens but mapping lost. Outbox pattern should handle this. Verify `create_persist_outbox` is called for ingest mapping.

### Triage

- **Critical:** `record_vn_jobs_pii_detected` dead code → wire up, don't reinvent
- **Non-critical:** Edge cases (Q3) + failure modes (Q4) → add to test skeleton
- **Clean to proceed:** No HALT — all gaps are buildable with existing infrastructure

### ATDD Description Skeleton (4.4 — 2026-08-13)

**Output:** `_bmad-output/test-artifacts/atdd-checklist-12-4c-4d-4e.md`

Summary per AC (6 anti-patterns):
- **AC-1 (PII redaction):** 8 descriptions (Pattern 1-5, integration)
- **AC-2 (Audit logging):** 6 descriptions (Pattern 1-4, observability)
- **AC-3 (Chunk metadata):** 12 descriptions (Pattern 1-6)
- **AC-4 (Ingest job):** 8 descriptions (Pattern 1-6)
- **AC-5 (Retry/DLQ):** 8 descriptions (Pattern 1-6)
- **AC-6 (Exposure):** 8 descriptions (Pattern 1-6)
- **AC-7 (Schema violation):** 8 descriptions (Pattern 1-6)

**Pattern 6 flagged for integration test with real Postgres.**

### Red-Phase Unit Tests (4.5 — 2026-08-13)

**Files created:**
- `tests/unit/services/jobs_aggregator/test_pii_redaction.py` (2 red, 3 active)
- `tests/unit/services/scraper_chunks/test_serializer_identity.py` (5 red, 1 active)
- `tests/unit/services/scraper_chunks/test_chunk_metadata.py` (5 red)
- `tests/unit/services/jobs_aggregator/test_output_ingest_job_id.py` (3 red)
- `tests/unit/services/chainlens/test_ingest_schema_violation.py` (3 red)

**Result:** `uv run pytest tests/unit/services/jobs_aggregator tests/unit/services/scraper_chunks tests/unit/services/chainlens -m unit -q`
- 301 passed
- 18 skipped (red phase)
- 0 failures in existing tests

### Integration Tests (4.6 — 2026-08-13)

**File created:**
- `tests/integration/services/chainlens/test_ingest_job_mapping.py`

**Pattern 6 SQL tests:**
- ChainLensIngestJob row created with workspace_id, ingest_job_id, status
- Failed batch stores dead_letter_payload
- All marked `@pytest.mark.integration` + `@pytest.mark.skip` (requires Postgres)

**Note:** Integration tests need `docker compose -f docker/docker-compose.deps-only.yml up -d db redis` and `uv run alembic upgrade head` before running.
