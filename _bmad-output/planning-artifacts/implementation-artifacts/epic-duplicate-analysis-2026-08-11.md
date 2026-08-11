---
date: 2026-08-11
---

# Epic Duplicate / Overlap Analysis — Full `epics.md` Review

**Source:** `_bmad-output/planning-artifacts/epics.md`
**Method:** FR references counted only inside individual story sections (bounded by next story or next epic heading); title noise stripped before keyword matching.
**Date:** 2026-08-11

## 1. Executive Summary

- Total epics: 20
- Total stories: 102
- Unique FR references in stories: 53
- FRs appearing in stories of multiple epics: 9
- Cross-epic keyword-overlap pairs (≥3 shared keywords): 0

## 2. FRs Referenced in Stories of Multiple Epics

| FR | Epics | Verdict | Notes |
|---|---|---|---|
| FR-6 | E2, E3, E10, E21 | Reuse | Scrapers reused across E2, E10, E12, E21. Intended reuse of `CapabilityRegistry`. Not duplicate if each epic registers distinct scraper capability. |
| FR-7 | E7, E8 | Reuse | OAuth connectors reused as infrastructure for CRM, Zalo, enrichment. Not duplicate if modeled as `Connection` records. |
| FR-8 | E2, E3, E7 | Reuse | MCP connectors reused. Not duplicate if each new capability exposes new MCP tools. |
| FR-10 | E4, E8 | Shared primitive | RBAC 3 roles reused across chat/admin features. Not duplicate. |
| FR-18 | E6, E7 | Overlap risk | Automation actions: E6 generic; E21 adds sales-specific sequence action. Risk: rebuild generic automation runtime. |
| FR-24 | E3, E9 | Reuse | ChainLens deep-research/cost/degradation/provenance. E9 owns; other epics consume via `chainlens-research`. Not duplicate. |
| FR-32 | E3, E7, E10, E12 | Reuse | Memory storage/retrieval reused across E3, E4, E10, E12. Shared primitive; not duplicate. |
| FR-37 | E9, E18 | Reuse | ChainLens deep-research/cost/degradation/provenance. E9 owns; other epics consume via `chainlens-research`. Not duplicate. |
| FR-39 | E3, E9, E10, E12 | Reuse | ChainLens deep-research/cost/degradation/provenance. E9 owns; other epics consume via `chainlens-research`. Not duplicate. |

## 3. FRs Referenced in Multiple Stories (within the same epic)

| FR | Stories | Notes |
|---|---|---|
| FR-1b | 3-13, 3-14, 3-17 | Same epic — split into sub-tasks; not duplicate. |
| FR-3 | 8-12, 8-13 | Same epic — split into sub-tasks; not duplicate. |
| FR-6 | 2-6, 2-7, 2-8, 2-9, 3-6, 10-1, 10-2, 10-3, 10-4, 21-4 | Cross-epic; see Section 2. |
| FR-7 | 7-4, 8-3 | Cross-epic; see Section 2. |
| FR-8 | 2-10, 3-9, 3-14, 7-7 | Cross-epic; see Section 2. |
| FR-10 | 4-8a, 4-8b, 4-8c, 4-8e, 4-8f, 4-8g, 4-8h, 8-11 | Cross-epic; see Section 2. |
| FR-11 | 12-0, 12-5 | Same epic — split into sub-tasks; not duplicate. |
| FR-18 | 6-4, 7-7 | Cross-epic; see Section 2. |
| FR-24 | 3-15, 9-3, 9-1b | Cross-epic; see Section 2. |
| FR-32 | 3-14, 3-16, 7-7, 10-4, 12-4 | Cross-epic; see Section 2. |
| FR-37 | 9-2, 9-5, 18-7 | Cross-epic; see Section 2. |
| FR-38 | 9-4, 9-5, 9-1a | Same epic — split into sub-tasks; not duplicate. |
| FR-39 | 3-15, 9-6, 9-6c, 10-4, 12-4 | Cross-epic; see Section 2. |
| FR-42 | 4-8a, 4-8b, 4-8c, 4-8d, 4-8f, 4-8g, 4-8h | Same epic — split into sub-tasks; not duplicate. |
| FR-43 | 12-0, 12-1 | Same epic — split into sub-tasks; not duplicate. |
| FR-47 | 12-0, 12-4, 12-5 | Same epic — split into sub-tasks; not duplicate. |
| FR-63 | 21-1, 21-7 | Same epic — split into sub-tasks; not duplicate. |
| FR-66 | 21-4, 21-7 | Same epic — split into sub-tasks; not duplicate. |

## 4. Cross-Epic Keyword Overlaps (potential semantic duplicates)

No significant keyword overlaps found.

## 5. High-Priority Duplicate / Overlap Risks

| Risk | Severity | Why | Recommended Action |
|---|---|---|---|
| FR-18 Automation actions in E6 vs E21 (outbound sequences) | Medium | E21 outbound is a sales-specific automation use case. | Reuse E6 `Automation`/`Sequence` runtime; only add sales step templates. |
| FR-47 PII redaction in E12 vs E21 | Medium | Both redact PII before ingestion. | Build one shared `pii_redaction` service with per-vertical rules; keep consent/legal basis separate. |
| FR-63/66 Intent signals / Outbound in E21 vs E6 automations + E11 notifications | Medium | E21 must reuse AD-33 AlertRule engine and E11.1 notification dispatch. | Store `SignalEvent`; route through existing alert/notification runtime. |
| FR-6 Scrapers reused in E2, E10, E12, E14-E21 | Low | `CapabilityRegistry` is designed for reuse. | Register each as distinct capability with billing unit. |
| FR-32 Memory across E3, E4, E10, E12 | Low | Shared primitive. | Use `Memory` table; avoid per-epic copy. |
| FR-30/31 Credit wallet in E8 vs E21 (outcome pricing) | Low | Outcome-pricing builds on wallet. | Extend `TokenUsage` with new usage types; reuse dashboard. |
| E14-E17 Vietnam verticals (News/Finance/Company/E-commerce) vs E12 HR / E10 BĐS | Medium | All follow scraper → aggregate → alerts pattern. | Reuse `Aggregate` (E10.4/E12.4) and `AlertRule` (AD-33). |
| E6 Playbook Reuse / Schema-Driven Form vs E21 Onboarding / Tables directory | Low | Both use schema-driven UI. | Share a single schema-driven renderer. |

## 6. Conclusion

No hard duplicate feature was detected across epics. The main risk is **reusing vs rebuilding** shared infrastructure: automations, PII redaction, signal/alert engine, credit tracking, aggregation, and schema-driven UI. The architecture (`CapabilityRegistry`, AD-33 alert engine, AD-39 sequencer, shared PII pipeline) supports reuse, but implementation must enforce it.