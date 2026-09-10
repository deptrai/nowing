# Sprint Priority — Dependency Order

> Generated: 2026-08-22
> Updated: 2026-09-10
> Sorting: dependency impact (foundation first, standalone last)
> Source: `_bmad-output/implementation-artifacts/sprint-status.yaml` + `planning-artifacts/epics.md` + architecture spine

## Next recommended work

The next item to pick is **`12-7-property-price-alerts`** (`12-7-property-price-alerts`), followed by **`12-8-cross-source-entity-timeline`**. These are the first two `backlog` stories from Epic 12 (HR/Recruitment Vertical), extending the completed scraper foundation (12.1–12.6, 12.9–12.10) into alert/timeline features.

All Epics 1–29 and Epic 30 are `done`. The remaining `backlog` stories are vertical data features across Epics 12, 14, 15, 16, and 17.

---

## Tier 0 — Platform primitives / correctness (affects all epics)

1. `30-2-redis-event-bus-subscribe-failure-state-leak` — Redis event bus subscribe failure state leak (Epic 9.3, 6.8, 11, 12.9, 22.3)
2. `30-5-title_gen-py-lacks-timeout-retry-on-litellm-acompletion` — `title_gen.py` timeout/retry on `litellm.acompletion` (every chat turn)
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
13. `14-2a` — News Entity Enrichment
14. `24-8` — Browser Operator CDP capability (`browser_operator.execute`) + Human Live Takeover bridge
15. `4-8c-followup` — Production Query Sampler (follow-up)
16. `4-8d-followup` — Chat Quality LLM-as-Judge (follow-up)
17. `4-8h-followup` — Mode-Aware Chat Policy (follow-up)

## Tier 2 — Vertical data + dashboard + SaaS admin/analytics (affects one domain or UI)

18. `12-7` — Property Price Alerts (Epic 12, backlog)
19. `12-8` — Cross-Source Entity Timeline (Epic 12, backlog)
20. `14-3` — News Alerts Topic Monitoring (Epic 14, backlog)
21. `14-4` — News Digest Synthesis (Epic 14, backlog)
22. `15-3` — Stock Price Alerts (Epic 15, backlog)
23. `15-4` — Financial Trend Detection (Epic 15, backlog)
24. `16-3` — Company Alerts (Epic 16, backlog)
25. `16-4` — Company Timeline (Epic 16, backlog)
26. `17-3` — Price Drop Alerts (Epic 17, backlog)
27. `17-4` — Competitor Tracking (Epic 17, backlog)

## Tier 3 — New product surface / business-gated / post-MVP

28. `27-1` — Full-Stack Web App Builder, 1-Click Hosting, Design Mark Tool
29. `27-2a` — Manus Slides + Speaker Diarization
30. `28-1` — Workspace Memory & Research Data Export
31. `28-2` — Encryption-at-Rest for Cloud Memory
32. `28-3` — ToS / Legal Review & Retention Policy
33. `28-4` — Self-Host OSS Onboarding in Under 10 Minutes
34. `6-6a-playbook-reuse` — Playbook Reuse (business-gated)
35. `6-7a-schema-form-ui` — Schema-Driven Form UI (business-gated)
36. `6-9a-workspace-vertical` — Workspace Vertical & Playbook Library (business-gated)

---

## How this is used

This file is the canonical dependency-ordered priority list.

- It is referenced by `_bmad/custom/bmad-sprint-status.toml` as a `persistent_fact` for the `bmad-sprint-status` skill.
- When the skill exits, it runs `_bmad/scripts/print_next_priority.py`, which prints the first unfinished item from this list and the next two upcoming items.

To update the priority, edit this file. The `print_next_priority.py` script will pick up the new order on the next skill run.
