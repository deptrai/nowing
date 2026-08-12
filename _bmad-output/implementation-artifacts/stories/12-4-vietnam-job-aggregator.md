---
title: Story 12.4 — Vietnam Job Aggregator (UMBRELLA)
epic: 12
story: 4
status: split
priority: P0
---

# Story 12.4 — Vietnam Job Aggregator (UMBRELLA)

> **Split into 2 files** (2026-08-12) per `epics.md` 12.4a–e, grouped by remaining work size.

## Sub-stories

| Story | File | Status | Scope | Gap size |
|---|---|---|---|---|
| 12.4a+4b | [12-4a-4b-normalize-dedupe-conflict.md](./12-4a-4b-normalize-dedupe-conflict.md) | in-progress | Normalize + fuzzy dedupe + conflict detection | 11 gaps (real work) |
| 12.4c+4d+4e | [12-4c-4d-4e-pii-ingest-exposure.md](./12-4c-4d-4e-pii-ingest-exposure.md) | ready-for-dev | PII + chunk ingest + REST/MCP/chat exposure | 9 gaps (mostly small) |

## Implementation status (verified 2026-08-12)

- **Orchestrator** (`app/services/jobs_aggregator/orchestrator.py`, 342 lines): fan-out, normalize, PII redact, dedupe, score, persist. **8 unit tests passing.**
- **MCP tool** (`nowing_vn_jobs_aggregate`): registered, selfcheck OK.
- **REST route** (`chainlens_internal.py`): wired, 14 route tests passing.
- **Chat subagent** (`subagents/builtins/vn_jobs/`): agent + tools + system prompt.
- **Chunk serializer**: job domains registered, `contentType = "job"`, canonical domain mapping. 14 tests passing.

## Key gaps

1. **No fuzzy title matching** (12.4a+4b) — exact match only, Jaro-Winkler ≥ 0.85 required.
2. **No `posted_at` ±3 days tolerance** (12.4a+4b) — exact date match only.
3. **`app/services/location_normalize/` does NOT exist** (12.4a+4b) — AC references it.
4. **No `conflict_flag` enum** (12.4a+4b) — boolean only, `SALARY_MISMATCH`/`LOCATION_MISMATCH` required.
5. **No `source_count` on listing** (12.4a+4b) — `ChunkMetadata` has field but listing doesn't populate.
6. **No DLQ** (12.4c+4d+4e) — retry exists but dead-letter queue table missing.
7. **No `ingestJobId` in output** (12.4c+4d+4e) — route has it, capability output doesn't.

## References
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/epics.md" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/sprint-status.yaml" />
