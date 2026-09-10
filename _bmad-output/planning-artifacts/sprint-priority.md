# Sprint Priority — Dependency Order

> Generated: 2026-08-22
> Updated: 2026-09-10
> Sorting: dependency impact (foundation first, standalone last)
> Source: `_bmad-output/implementation-artifacts/sprint-status.yaml` + `planning-artifacts/epics.md` + architecture spine

## Next recommended work

All **198 stories across 29 epics are `done`** as of 2026-09-10. The previous `backlog` stories (`12-7`, `12-8`, `14-3`, `14-4`, `15-3`, `15-4`, `16-3`, `16-4`, `17-3`, `17-4`) were identified as either `DROPPED` (per SCP 2026-08-08) or `MERGED` into completed stories `6.11` / `6.12`, and have been removed from active tracking.

**`epic-16-retrospective`** was completed 2026-09-10 and is now `done`.

The next action is to continue **`bmad-retrospective`** for the remaining open optional retrospectives, starting with **`epic-24-retrospective`**.

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



All Tier 2 implementation stories are now `done`, `merged` into 6.11/6.12, or `dropped` per SCP 2026-08-08. The remaining open work is optional epic retrospectives (19 `optional`, 10 `done`).

- `epic-1-retrospective` — Identity, Auth & Workspace RBAC retrospective (`done` 2026-09-10)
- `epic-4-retrospective` — Chat & Agents retrospective (`done` 2026-09-10)
- `epic-5-retrospective` — Deliverables retrospective (`done` 2026-09-10)
- `epic-6-retrospective` — Automations retrospective (`done` 2026-09-10)
- `epic-7-retrospective` — Multi-surface Clients retrospective (`done` 2026-09-10)
- `epic-8-retrospective` — Cost Control & Billing retrospective (`done` 2026-09-10)
- `epic-9-retrospective` — Deep Research retrospective (`done` 2026-09-10)
- `epic-10-retrospective` — Connector & Scraper Expansion (`done` 2026-09-10)
- `epic-11-retrospective` — Telegram Automation & Bot (`done` 2026-09-10)
- `epic-12-retrospective` — HR/Recruitment Vertical (`done` 2026-09-10)
- `epic-13-retrospective` — Canonical Entity Storage (`done` 2026-09-10)
- `epic-14-retrospective` — News Aggregation (`done` 2026-09-10)
- `epic-15-retrospective` — Financial Data (`done` 2026-09-10)
- `epic-16-retrospective` — Company Directory & Public Procurement (`done` 2026-09-10)
- `epic-17-retrospective` — E-commerce Intelligence (`done` 2026-09-10)
- `epic-18-retrospective` — Public Agent Chat & Agent Registry (`done` 2026-09-10)
- `epic-20-retrospective` — Service Mesh & Cost Ledger (`done` 2026-09-10)
- `epic-21-retrospective` — Lead Gen Intelligence (`done` 2026-09-10)
- `epic-22-retrospective` — Telegram Storage & Public Web Preview (`done` 2026-09-10)
- `epic-23-retrospective` — Lead Capture & Outreach Infrastructure (`done` 2026-09-10)
- `epic-24-retrospective` — Enterprise Lead Conversion & Team CRM (next)

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
