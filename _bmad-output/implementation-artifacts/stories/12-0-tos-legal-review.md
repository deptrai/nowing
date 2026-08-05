---
title: Story 12.0 — ToS & Legal Review
epic: 12
story: 0
status: proposed
priority: P0
---

# Story 12.0 — ToS & Legal Review

**Epic:** 12 — HR/Recruitment Vertical — Vietnam Job Market Pilot  
**As a:** product owner  
**I want:** to confirm ToS and legal classification for VietnamWorks, TopCV, and ITviec  
**So that:** we do not build or launch a non-compliant pilot.

---

## Acceptance Criteria

1. **Given** the source list, **When** ToS review is performed, **Then** each source's automated access / commercial use status is documented in `_bmad-output/planning-artifacts/legal/`.
2. **Given** the pilot design, **When** legal counsel reviews, **Then** an opinion exists confirming Nowing is not classified as an "employment service provider" / "môi giới việc làm".
3. **Given** a source is blocked by ToS or legal, **When** the decision is made, **Then** that source is removed from the default `sources` list and the implementation plan is updated.
4. **Given** legal approval, **When** the pilot launches, **Then** public messaging clearly positions Nowing as a research/memory layer, not a job board/ATS/intermediary.

---

## Non-AC Technical Notes

- No code.
- Output: legal review memo + ToS decision log.
- Triggers: blocks 12.1, 12.2, 12.3 until resolved.

## References

- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/legal/tos-legal-epic-12-hr-vertical-2026-08-05.md" />
- AD-26 in <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md" />
