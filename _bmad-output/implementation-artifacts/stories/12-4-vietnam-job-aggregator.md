---
title: Story 12.4 — Vietnam Job Aggregator
epic: 12
story: 4
status: done
priority: P0
---

# Story 12.4 — Vietnam Job Aggregator

**Epic:** 12 — HR/Recruitment Vertical — Vietnam Job Market Pilot  
**As a:** research analyst  
**I want:** to query Vietnamese job data in one call  
**So that:** I get a normalized, deduped, confidence-scored view of the job market from multiple sources.

---

## Acceptance Criteria

1. **Given** a query, **When** `vn_jobs.aggregate` is called, **Then** it fan-outs to `vietnamworks.scrape`, `topcv.scrape`, `itviec.scrape` (default all 3; source list configurable).
2. **Given** results from multiple sources, **When** normalized, **Then** they map to `VnJobAggregatedListing` with salary/location/employment-type/experience.
3. **Given** normalized listings, **When** deduplicated, **Then** it matches by company + title + location + posted_at across sources.
4. **Given** conflicting salary/location between sources, **When** compared, **Then** it flags conflict and computes `confidence_score` + `salary_consistency_score`.
5. **Given** a source fails, **When** aggregation completes, **Then** it returns `degraded=true` with `degradation_reasons`.
6. **Given** the aggregator is built, **When** exposed, **Then** it is available via REST, MCP (`nowing_vn_jobs_aggregate`), and chat agent.

---

## Non-AC Technical Notes

- Implementation skeleton exists at `app/services/jobs_aggregator/` and `app/capabilities/vn_jobs/aggregate/`.
- Replace stub orchestrator with real fan-out, normalize, dedupe, and PII redaction before memory.
- Location filter at aggregator level; `max_items_per_source` and `max_pages` caps.

## References

- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/pilot-plan-c-memo-2026-08-05.md" />
