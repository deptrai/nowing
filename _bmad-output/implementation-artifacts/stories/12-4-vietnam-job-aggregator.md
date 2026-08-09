---
title: Story 12.4 — Vietnam Job Aggregator
epic: 12
story: 4
status: ready-for-dev
priority: P0
---

# Story 12.4 — Vietnam Job Aggregator

**Epic:** 12 — HR/Recruitment Vertical — Vietnam Job Market Pilot  
**As a:** research analyst  
**I want:** the Vietnamese job market data scraped, normalized, and indexed by `chainlens-research`  
**So that:** the Nowing chat agent can answer job market questions with fresh, cited, cross-source results.

---

## Acceptance Criteria

1. **Given** a query and optional filters (`location`, `salaryMin/Max`, `employmentType`, `experienceYears`), **When** `vn_jobs.aggregate` is called, **Then** it fan-outs to `vietnamworks.scrape`, `topcv.scrape`, `itviec.scrape` (default all 3; `sources` list configurable; `maxItemsPerSource` and `maxPages` caps enforced per source).

2. **Given** results from multiple sources, **When** normalized, **Then** they map to `VnJobAggregatedListing` with `salary`, `location`, `employment_type`, `experience`, `posted_at`, `source`, and `source_url` fields, using the shared `JobItem` schema from `vn_jobs`.

3. **Given** normalized listings, **When** deduplicated, **Then** it matches by `company` + `title` + `location` + `posted_at` (±3 days) across sources; fuzzy title matching uses Jaro-Winkler ≥ 0.85 and location normalization uses `app/services/location_normalize/`.

4. **Given** two listings matched with salary difference ≤ 10%, **When** compared, **Then** `confidence_score ≥ 0.8` and `salary_consistency_score = stable`; the aggregated record is kept as a single `Chunk` with `metadata.source_count` and `metadata.confidence_score`.

5. **Given** two listings matched with salary difference > 20% or a location mismatch, **When** compared, **Then** it sets `conflict_flag = SALARY_MISMATCH` or `LOCATION_MISMATCH`, lowers `confidence_score` to 0.5–0.7, and preserves both source `Chunk[]` so `chainlens-research` can display conflict metadata.

6. **Given** PII (phone, email, person names) is found in `job_description` or `job_requirement`, **When** chunks are built, **Then** the shared PII pipeline (FR-47) masks or drops those fields, logs only counts, and the raw unredacted JD is not stored in `Memory` or sent to `chainlens-research`.

7. **Given** a source fails or is blocked by anti-bot, **When** aggregation completes, **Then** it returns `degraded=true` with `degradation_reasons` drawn from `{SOURCE_FAILED, ANTI_BOT, RATE_LIMIT, PARTIAL_DATA}` and `degraded_source_ids`; chunks from successful sources are still ingested.

8. **Given** the aggregator has normalized listings, **When** `to_chunks()` is called, **Then** each listing becomes a `Chunk` with `metadata.source: 'nowing_scraper'`, `sourceId` (stable: `sha256(company|title|location|posted_at)`), `domain`, `fetchedAt`, `contentType: 'job'`, `salary`, `confidence_score`, `salary_consistency_score`, and `conflict_flags`.

9. **Given** a `Chunk[]` batch, **When** `NowingIngestService.ingest()` is called, **Then** it calls `POST /v1/ingest/scraper` on `chainlens-research` with service auth, `workspace_id`, and the batch; it returns `ingestJobId` and stores the job mapping in Nowing Postgres.

10. **Given** a batch larger than 1,000 chunks, **When** ingesting, **Then** `NowingIngestService` paginates the batch and tracks a parent `ingestJobId` plus child job IDs.

11. **Given** `chainlens-research` returns `409` for a duplicate `sourceId`, **When** handling the response, **Then** the duplicate is mapped to `noop` status and the rest of the batch continues.

12. **Given** `chainlens-research` returns `5xx` or times out, **When** `NowingIngestService.ingest()` is called, **Then** it retries with exponential backoff (max 3 attempts), stores the failed batch in a dead-letter queue, and after max retries marks the job `failed` and emits a `chainlens_ingest_failed` counter.

13. **Given** the aggregator is exposed, **When** called via REST, MCP (`nowing_vn_jobs_aggregate`), or chat agent, **Then** it returns `VnJobAggregateOutput { items: VnJobAggregatedListing[], degraded, degradationReasons, sourceBreakdown, costMicros, ingestJobId }`; it does not query a local Nowing search corpus.

---

## Non-AC Technical Notes

- Implementation skeleton exists at `app/services/jobs_aggregator/` and `app/capabilities/vn_jobs/aggregate/`.
- Copy-modify from `bds_aggregator` (Apache-2.0) for normalize/dedupe/conflict logic.
- Location filter at aggregator level; `max_items_per_source` and `max_pages` caps per source.
- Apply PII redaction before `to_chunks()`; call `NowingIngestService.ingest()` per AD-34 / AD-35.
- No local search corpus or `Memory`/`ResearchThread` expansion for job search.

## References

- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/pilot-plan-c-memo-2026-08-05.md" />
