# Sprint Priority — Dependency Order

> Generated: 2026-08-22
> Updated: 2026-08-22
> Sorting: dependency impact (foundation first, standalone last)
> Source: `_bmad-output/implementation-artifacts/sprint-status.yaml` + `planning-artifacts/epics.md` + architecture spine

## Next recommended work

The next item to pick is **`td-2`** (Redis event bus subscribe failure state leak), then **`25-4`** (Realtime LLM Token Cost / Proxy Health / Celery Queue Telemetry).

These two are platform primitives: every real-time event, async task, and LLM/scraper call depends on them. Fix them before taking on higher-level features.

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
14. `24-8` — Browser Operator CDP tool for DSH crawl subgraph
15. `4-8c-followup` — Production Query Sampler (follow-up)
16. `4-8d-followup` — Chat Quality LLM-as-Judge (follow-up)
17. `4-8h-followup` — Mode-Aware Chat Policy (follow-up)

## Tier 2 — Vertical data + dashboard (affects one domain or UI)

18. `16-2` — Official Business Registry (dangkykinhdoanh.gov.vn)
19. `17-1` — Lazada Product Data
20. `17-5` — TikTok Shop Product & Trending SKUs
21. `8-14` — Cost & Auto-Extract Budget Dashboard
22. `7-8` — Vietnamese i18n & Smart Geo-Locale Auto-Detection

## Tier 3 — New product surface / business-gated / post-MVP

23. `27-1` — Full-Stack Web App Builder, 1-Click Hosting, Design Mark Tool
24. `27-2` — Manus Slides + Speaker Diarization
25. `28-1` — Workspace Memory & Research Data Export
26. `28-2` — Encryption-at-Rest for Cloud Memory
27. `28-3` — ToS / Legal Review & Retention Policy
28. `28-4` — Self-Host OSS Onboarding in Under 10 Minutes
29. `6-6a-playbook-reuse` — Playbook Reuse (business-gated)
30. `6-7a-schema-form-ui` — Schema-Driven Form UI (business-gated)
31. `6-9a-workspace-vertical` — Workspace Vertical & Playbook Library (business-gated)

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
