# Sprint Priority — Dependency Order

> Generated: 2026-08-22
> Updated: 2026-08-30
> Sorting: dependency impact (foundation first, standalone last)
> Source: `_bmad-output/implementation-artifacts/sprint-status.yaml` + `planning-artifacts/epics.md` + architecture spine

## Next recommended work

The next item to pick is **`td-2`** (Redis event bus subscribe failure state leak), then **`25-4`** (Realtime LLM Token Cost / Proxy Health / Celery Queue Telemetry). **After platform primitives are stable, Epic 29 (SaaS Operations & Admin Analytics) becomes the next business-critical stream.**

These two are platform primitives: every real-time event, async task, and LLM/scraper call depends on them. Fix them before taking on higher-level features. Epic 29 has been declared READY FOR CREATE-STORY and should enter Tier 2 once 29-1 (Custom Workspace Roles) is created.

---

## Tier 0 — Platform primitives / correctness (affects all epics)

1. `td-2` — Redis event bus subscribe failure state leak (Epic 9.3, 6.8, 11, 12.9, 22.3)
2. `td-5` — `title_gen.py` timeout/retry on `litellm.acompletion` (every chat turn)
3. `25-4` — Realtime LLM Token Cost, Proxy Health & Celery Queue Telemetry
4. `25-5` — Dynamic Scraper Rule Engine & ReDoS Sandbox
5. `6-10` — Inbound Mail Gateway + Stateful Scheduled Tasks 2.0
6. `6-11` — Vertical Alert Rule Templates on Generic Alert Engine
7. `9-6-followup` — Memory Provenance & Re-Validation (follow-up)

## Tier 1 — Shared engines / chat / memory / observability (affects multiple epics)

8. `3-7-followup` — Retention Hardening (concurrent safety + test robustness)
9. `3-18` — Recall Precision / Noise Gate Ratification
10. `6-12` — Narrative Report Engine for Indexed Data
11. `8-11-followup` — Admin Global LLM Model Configuration (follow-up)
12. `25-6` — Security Audit Trail Logs & In-App Broadcast Announcements
13. `14-2` — News Entity Enrichment
14. `24-8` — Browser Operator CDP capability (`browser_operator.execute`) + Human Live Takeover bridge
15. `4-8c-followup` — Production Query Sampler (follow-up)
16. `4-8d-followup` — Chat Quality LLM-as-Judge (follow-up)
17. `4-8h-followup` — Mode-Aware Chat Policy (follow-up)

## Tier 2 — Vertical data + dashboard + SaaS admin/analytics (affects one domain or UI)

18. `29-1` — Custom Workspace Roles & Permissions Builder (Epic 29, FR-100) — **foundation for 29-2/29-4**
19. `29-2` — Workspace Health & Adoption Analytics Dashboard (Epic 29, FR-101)
20. `29-3` — Tenant Subscription Tier & Quota Management (Epic 29, FR-102)
21. `29-4` — Admin Bulk Operations Console (Epic 29, FR-103) — depends on 29-1 and 29-3
22. `29-5` — Memory Browser & Research Timeline for Analyst (Epic 29, FR-104)
23. `29-6` — Data Governance & Retention Policy Console (Epic 29, FR-104)
24. `16-2` — Official Business Registry (dangkykinhdoanh.gov.vn)
25. `17-1` — Lazada Product Data
26. `17-5` — TikTok Shop Product & Trending SKUs
27. `8-14` — Cost & Auto-Extract Budget Dashboard
28. `7-8` — Vietnamese i18n & Smart Geo-Locale Auto-Detection

## Tier 3 — New product surface / business-gated / post-MVP

29. `27-1` — Full-Stack Web App Builder, 1-Click Hosting, Design Mark Tool
30. `27-2` — Manus Slides + Speaker Diarization
31. `28-1` — Workspace Memory & Research Data Export
32. `28-2` — Encryption-at-Rest for Cloud Memory
33. `28-3` — ToS / Legal Review & Retention Policy
34. `28-4` — Self-Host OSS Onboarding in Under 10 Minutes
35. `6-6a-playbook-reuse` — Playbook Reuse (business-gated)
36. `6-7a-schema-form-ui` — Schema-Driven Form UI (business-gated)
37. `6-9a-workspace-vertical` — Workspace Vertical & Playbook Library (business-gated)

## Tech debt remaining (interleave with related epics)

- `td-1` — Idempotency key for `POST /automations/{id}/run`
- `td-3` — Storage sum does not reconcile deleted backend files
- `td-4` — Concurrent notification preference merge race condition
- `td-6` — `verify_chat_image_capability.py` lacks `num_retries`
- `td-7` — No unit test coverage for `test_model` function

---

## How this is used

This file is the canonical dependency-ordered priority list.

- It is referenced by `_bmad/custom/bmad-sprint-status.toml` as a `persistent_fact` for the `bmad-sprint-status` skill.
- When the skill exits, it runs `_bmad/scripts/print_next_priority.py`, which prints the first unfinished item from this list and the next two upcoming items.

To update the priority, edit this file. The `print_next_priority.py` script will pick up the new order on the next skill run.
