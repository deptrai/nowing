---
date: 2026-08-05 (rerun)
project: Nowing
stepsCompleted: ["step-01-document-discovery", "step-02-prd-analysis", "step-03-epic-coverage-validation", "step-04-ux-alignment", "step-05-epic-quality-review", "step-06-final-assessment"]
---

# Implementation Readiness Assessment Report

**Date:** 2026-08-05 (rerun)
**Project:** Nowing

---

## 1. Document Discovery

### PRD Documents

**Selected PRD (sharded folder):**
- `prds/prd-Nowing-2026-07-22/prd.md` (108,914 bytes, modified 2026-08-05 15:37)

**Other PRD-related files in the same folder:**
- `prds/prd-Nowing-2026-07-22/.memlog.md`
- `prds/prd-Nowing-2026-07-22/review-prfaq-gap.md`
- `prds/prd-Nowing-2026-07-22/review-rubric.md`
- `prds/prd-Nowing-2026-07-22/validation-report.md`
- `prds/prd-Nowing-2026-07-22/validation-report.html`

No whole PRD `.md` file exists at the top level; the folder version is the authoritative PRD.

### Architecture Documents

**Selected Architecture:**
- `architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` (78,269 bytes, modified 2026-08-05 10:24)

**Other architecture-related file:**
- `epic-11-architecture-review-2026-08-03.md` — this is an architecture review artifact, not the primary architecture document; not used as the assessment source.

### Epics & Stories Documents

**Selected Epics document:**
- `epics.md` (110,502 bytes, modified 2026-08-05 16:05)

**Other epic-related file:**
- `epic-11-architecture-review-2026-08-03.md` — architecture review, not the primary epics source.

### UX Design Documents

**Selected UX contracts (sharded folder `ux-designs/ux-Nowing-2026-07-22/`):**
- `ux-contract-admin-global-model-config.md` (2,470 bytes, 2026-08-05 15:38)
- `ux-contract-async-deep-research.md` (7,417 bytes, 2026-08-04 20:16)
- `ux-contract-chat-benchmark.md` (2,203 bytes, 2026-08-05 15:39)
- `ux-contract-first-run-onboarding.md` (2,160 bytes, 2026-08-05 15:39)
- `ux-contract-sync-offline-indicator.md` (2,149 bytes, 2026-08-05 15:39)
- `ux-contract-usage-dashboard.md` (1,962 bytes, 2026-08-05 15:39)

**Other UX file (archive):**
- `archive/ux-audit-improvement-spec-2026-07-27.md` — archived, not selected as a current source.

### Issues Found

- No duplicate whole/sharded versions were found for PRD, epics, or UX.
- The `implementation-readiness-report-2026-08-05.md` file exists as the previous assessment run; it is **not** used as an assessment source.
- Required documents (PRD, Architecture, Epics, UX) are all present.

---

## 2. PRD Analysis

### Functional Requirements Extracted

#### §4.1 Identity, Auth & Workspace RBAC
- **FR-1 User Authentication:** Users can register, log in, refresh/revoke tokens, log out all sessions, and use Google OAuth. Desktop has a separate session endpoint.
- **FR-2 API Access for External Clients:** Desktop, browser extension, Obsidian plugin, and MCP server authenticate via Personal Access Token (`nw_pat_...`) or API key; `Workspace.api_access_enabled` controls API access per workspace.
- **FR-3 Workspace Lifecycle:** Users can create, list, view, update (name, description, `citations_enabled`, `qna_custom_instructions`), and delete workspaces.
- **FR-4 Workspace Invites & Memberships:** Owner/Editor can invite members; memberships bind to `WorkspaceRole`; invites have code, expiry, and usage limit.
- **FR-10 RBAC with three system roles:** Default system roles are Owner, Editor, Viewer. `Admin` system role was removed (migration 72). Editor lacks delete/member-management permissions; Viewer has read + comment create.

#### §4.2 Connectors
- **FR-6 Built-in Scraper Connectors:** Backend provides scraper endpoints for Reddit, YouTube, Instagram, TikTok, Google Search, Google Maps, Amazon, web crawl; each call creates a `Run` record.
- **FR-7 External OAuth Connectors:** Users can add Notion, Slack, Linear, Jira, Google Drive/Calendar/Gmail, Dropbox, OneDrive, Confluence, ClickUp, Airtable, Discord, Luma, … via OAuth.
- **FR-8 External MCP Connectors:** Users can add external MCP servers into a workspace through OAuth/composio so agents can use those tools.

#### §4.3 Knowledge Base
- **FR-9 Document Upload, Parse & Index:** Users upload files or URLs; system parses, chunks, embeds, and stores `Document`, `Chunk`, `DocumentVersion`, `DocumentFile`; 50+ formats supported.
- **FR-11 Folders & Document Management:** Create/rename/move/delete documents/folders with permission checks; versioning and revert supported.
- **FR-12 Hybrid Search over Knowledge Base:** Workspace search combines pgvector semantic, full-text, and reciprocal rank fusion; endpoint `/documents/search-semantic`.
- **FR-13 Citation Panel for Knowledge-base Chunks:** Clicking a citation badge in chat opens a right panel showing the cited chunk and a ±5 chunk window, with highlighted/auto-scroll behavior.
- **FR-32 Long-Term Research Memory `[BUILT/PARTIAL]:`** Workspace stores facts, decisions, observations, and research results as `Memory`; supports hybrid search and retrieval via REST/MCP. MVP focuses on semantic memory. Schema/endpoints/MCP tools/indexes/confidence built; dedupe primitive exists but needs tuning; recall-quality gate still open (NFR-8).
- **FR-33 Research Continuity `[BUILT/PARTIAL]:`** Agent can continue an existing `ResearchThread`, recalling ranked relevant memory and prior citations. `ResearchThread`/MCP tool built; quality depends on NFR-8.
- **FR-34 Memory Correction `[BUILT]:`** Users/agents can update or flag a memory; a `MemoryVersion` is created holding `previous_content`/`corrected_content`/`corrected_by`/timestamp; original memory is not hard-deleted. Graph propagation deferred post-MVP.
- **FR-36 Legacy Memory Data-Loss Assessment & Recovery `[RESOLVED 2026-07-25]:`** Migration 178 not yet applied in prod, legacy `memory_md` fields empty, snapshot created, so no data loss. Backfill command + guard + tests built; deploy order must be mig177 → backfill → mig178.
- **FR-5 AI File Sorting `[REMOVED]:`** Feature removed (`ai_file_sort_enabled` dropped in migration 172).

#### §4.4 Chat & Agents
- **FR-14 Chat Threads & Messages:** Users create threads, send messages, and receive streaming responses. Threads have `title`, `archived`, `visibility`, `workspace_id`, `created_by_id`.
- **FR-15 Multi-agent Runtime with Tools `[BUILT]:`** Main agent calls tools (scraper, filesystem, memory, report, podcast, …) with specialized subagents; recalls workspace memory; `AgentFeatureFlags` enable/disable middleware.
- **FR-16 Real-time Collaborative Chat:** Multiple users view/update threads via Zero sync; supports comments and mentions.
- **FR-17 Anonymous Chat with Quota:** Unauthenticated users can chat with an uploaded document and limited quota.
- **FR-42 Chat Response Benchmark `[NEW 2026-08-04]:**` The `nowing_evals` harness benchmarks chat responses with real/curated data, collecting latency, TTFB, tokens, `cost_micros`, citation count, finish status, and turn/message IDs.

#### §4.5 Deliverables
- **FR-21 Report Generation & Export:** Generate reports from documents/folders; export to ZIP/PDF/DOCX/HTML/LaTeX/EPUB/ODT/plain text.
- **FR-22 Podcast & Video Presentation:** Create 2-host podcasts from documents/folders in under 20 seconds; create video presentations with slides/scenes.
- **FR-23 Image Generation:** Generate images from prompt with model, size, style, quality, response_format.

#### §4.6 Automations
- **FR-18 Automation Action Types `[DONE]:`** Action registry includes `agent_task`, `continue_research`, `write_back_jira`, `write_back_linear`, `write_back_notion`, `write_back_slack`.
- **FR-19 Automation Triggers:** Supports `schedule` (cron) and `event` (webhook/connector event) triggers.
- **FR-20 Automation Runs & Retries:** Each activation creates an `AutomationRun` with status, error, progress, and retry policy.
- **FR-35 Memory-Driven Automations `[DONE]:`** Automation can trigger on memory changes (`memory_change` trigger) or continue a research thread (`continue_research` action).

#### §4.7 Multi-surface Clients
- **FR-25 Web Client (Next.js):** Main web frontend with landing, dashboard, chat, connectors, settings, docs.
- **FR-26 Desktop Client (Electron):** Wraps web app with global shortcut, quick assist, screenshot assist, folder watcher.
- **FR-27 Browser Extension (Plasmo):** Captures browsing history and sends to backend.
- **FR-28 Obsidian Plugin:** Syncs vault via REST API `/obsidian/*`.
- **FR-29 MCP Server `[BUILT]:`** Exposes scraper, KB, memory, and research tools via Model Context Protocol; clients use `Authorization: Bearer <NOWING_API_KEY>`.

#### §4.8 Billing, Credits & Usage
- **FR-30 Token Usage Tracking:** Each assistant turn records `TokenUsage` with prompt/completion/total tokens, `cost_micros`, model breakdown, `usage_type`, and ids.
- **FR-31 Credit Wallet & Purchases `[BUILT/PARTIAL]:`** `User.credit_micros_balance`/`credit_micros_reserved` wallets; `CreditPurchase` and `PagePurchase` track Stripe; `UserIncentiveTask` rewards credit. **Gap:** no usage/credit dashboard for users (also listed as NFR-7).
- **FR-41 Admin UI for Global LLM Model Configuration `[GAP — new 2026-07-26]:**` Platform admin (`is_superuser`) can view/add/edit/enable/disable global chat models via a web UI without editing YAML/env and restarting backend.

#### §4.9 Deep-Research Engine Integration (ChainLens)
- **FR-24 Deep Open-Web Research via ChainLens Engine `[DONE/PARTIAL]:**` Users/agents can run deep multi-source research and receive cited answers via REST and MCP. Contract/versioned SSE endpoint `POST {CHAINLENS_API_URL}/api/v1/search`. Mode default changed to `balanced`; quality opt-in. Contract regression tests in place.
- **FR-37 Deep-Research Cost Metering `[DONE]:**` Parse `costDollars` from terminal SSE event into `TokenUsage` (micros); fallback `CHAINLENS_QUERY_MICROS_PER_CALL` raised to 60,000 micros (~$0.06). Cost observed (research tier): speed $0.0353, balanced $0.0482, quality $0.0671.
- **FR-38 Research Degradation & Self-Host Independence `[DONE — P0]:**` If ChainLens is unavailable (timeout / 5xx / unconfigured), Nowing degrades to hybrid KB search and returns explicit `partial` or `engine_unavailable` status without fabricating citations. Self-host without engine still functions.
- **FR-39 Memory → Scraper-Run Provenance & Source Re-Validation `[GAP — defect schema, 2026-07-25]:**` Memory generated from a scrape run must reference the correct run and allow re-execution to re-validate. Needs `source_capability`/`source_input`/`source_run_id` on `Memory` and a re-validate API (`9.6a`/`9.6b`).
- **FR-40 First-Run Value — Research Runs Produce Memory `[GAP — HIGH]:**` First research/scrape run should produce memory (`source_type=SCRAPER_RUN` + provenance) so a new workspace has recallable facts without prior chat; target ≤ 15 minutes from signup to recall.

**Total FRs:** 41 numbered FRs extracted (FR-1 to FR-42, with FR-5 and FR-36 removed/resolved).

### Non-Functional Requirements Extracted

- **NFR-1 Performance:**
  - *NFR-1a — CRUD & scraper:* API p95 < 500ms for CRUD; scraper calls may take seconds but stream updates via SSE.
  - *NFR-1b — Memory injection (blocks every chat turn) `[GAP]:`* DB time p95 ≤ 150ms independent of memory row count (O(top-k)); total injected memory characters ≤ 8,000 on the read path.
  - *NFR-1c — Recall tool (`nowing_recall`, `/memories/search`):`* top_k ≤ 5, ranked hybrid, p95 ≤ 300ms. Similarity threshold exposure currently broken; assigned to `3-14`.
  - *NFR-1d — Auto-extract (Celery, off critical path):`* Must not block chat turn; new memory available within 60s; cost budget covered by `8-7`.
- **NFR-2 Security & Auth:** JWT/cookie from `fastapi-users`; PAT for external clients; permission checks on every workspace-scoped endpoint; secrets via `.env`.
- **NFR-3 Observability:** OpenTelemetry traces; `Log` model logs; SlowAPI rate limiter; Celery task monitoring.
- **NFR-4 Reliability:** Async DB I/O with SQLAlchemy async; Celery + Redis background tasks; retry policy for automation runs and scraper calls.
- **NFR-5 Multi-tenancy Isolation:** All workspace-scoped queries filter by `workspace_id`; `Workspace.api_access_enabled` controls API access.
- **NFR-6 Citation Full-Editor Highlight `[DONE]:`** Clicking a citation in chat scrolls/highlight the corresponding snippet in the full document editor.
- **NFR-7 Usage & Credit Dashboard `[GAP]:**` Token usage and credit balance data exist but no aggregated usage/credit dashboard for users.
- **NFR-8 Recall Quality (eval-gated) `[IN-PROGRESS]:**` Recall quality must be measured and meet thresholds before shipping memory layer; uses `nowing_evals` precision@k and noise rate. Story `3-9` implementation complete; baseline ratification pending.
- **NFR-9 Deep-Research Latency & Availability Budget (two states) `[PARTIAL]:**` State A (default) uses async deliverable (submit → progress → notify → deliverable) and does not block chat turns; fallback/degradation for engine unavailability. State B (sync chat-mode) is gated by ChainLens evals and Nowing `9.3` benchmarks.
- **NFR-10 Chat Response Regression Gate `[NEW 2026-08-04]:**` Every production deploy must pass a chat regression gate measuring p95 e2e latency, p95 TTFB, error rate, finish rate, citation count, cost/turn; thresholds in `gate.yaml` ratified after 3 stable runs.

### Additional Requirements / Constraints

- **License / OSS vs Cloud:** Core (excluding `nowing_backend/app/proprietary/`) is Apache-2.0; crawler engine is BSL 1.1; deep-research engine is closed-source/cloud. Self-host gets everything except deep research in Phase 1.
- **Nowing ↔ ChainLens boundary:** Nowing is the product; ChainLens is an internal microservice called via `POST /api/v1/search`. ChainLens has no end-user auth, billing, or independent distribution.
- **MVP scope:** Auth, workspace/RBAC, KB, memory (mostly built), multi-agent chat, scrapers, ChainLens integration (degradation + metering), deliverables, automations, multi-clients, credit wallet (backend).
- **Open Questions / Gaps retained:** OQ-1 external MCP marketplace (defer), OQ-2 agent tool default per-workspace in DB (defer), OQ-3 retention/right-to-delete for memory (must settle before GA cloud), OQ-7 ChainLens endpoint/cost/geo questions (answered, `42-1` remaining).
- **Non-Goals (frozen to 2026-08-24):** NG-1 selling raw research data, NG-2 consumer parity like Perplexity, NG-3 ChainLens as standalone product.
- **Success Metrics:** SM-1 active workspaces, SM-2 successful scraper runs, SM-3 citation rate, SM-4 deliverables, SM-5 automation runs, SM-6 invite acceptance, SM-7 memory operations, SM-8 continued research threads, SM-9 MCP memory calls, SM-10 recall quality, SM-11 deep-research cost/latency/fallback per mode.

### PRD Completeness Assessment

The PRD is comprehensive and well-structured. It contains globally numbered FR/NFRs, status tags tied to code verification, explicit acceptance criteria, consequences, cross-references to architecture decisions, and an open-questions/assumptions index. The main remaining PRD gaps are **FR-41 (admin global model UI)** and **FR-39 (provenance/re-validation)**. **FR-40, FR-31, NFR-7 and NFR-1b/1c/1d are still labeled `[GAP]` in the PRD but are marked `DONE` in the epics/UX contracts**, creating a documentation-truth drift that needs reconciliation. Several past gaps were resolved in 2026-07-25/08-04 updates (FR-18, FR-35, NFR-6, FR-37, FR-38, FR-24 contract).

---

## 3. Epic Coverage Validation

### FR Coverage Matrix

| FR | PRD Requirement | Epic Coverage | Status |
|----|-----------------|---------------|--------|
| FR-1 | User Authentication | E1 | ✅ DONE |
| FR-2 | API Access for External Clients (PAT/API key) | E1 | ✅ DONE |
| FR-3 | Workspace Lifecycle | E1 | ✅ DONE |
| FR-4 | Workspace Invites & Memberships | E1 | ✅ DONE |
| FR-10 | RBAC with three system roles | E1 | ✅ DONE |
| FR-6 | Built-in Scraper Connectors | E2 / E10.1 | ✅ DONE (core); 10.1 BĐS in review |
| FR-7 | External OAuth Connectors | E2 | ✅ DONE |
| FR-8 | External MCP Connectors | E2 | ✅ DONE |
| FR-9 | Document Upload, Parse & Index | E3 | ✅ DONE |
| FR-11 | Folders & Document Management | E3 | ✅ DONE |
| FR-12 | Hybrid Search over Knowledge Base | E3 | ✅ DONE |
| FR-13 | Citation Panel for Knowledge-base Chunks | E3 | ✅ DONE |
| FR-32 | Long-Term Research Memory | E3 (3.8/3.9/3.11/3.14) | ✅ BUILT; PARTIAL (dedupe tuning, recall-quality gate) |
| FR-33 | Research Continuity | E4 (4.6) | ✅ DONE |
| FR-34 | Memory Correction | E3/E4 | ✅ DONE |
| FR-36 | Legacy Memory Data-Loss | E3.10 | ✅ RESOLVED |
| FR-5 | AI File Sorting | — | 🗑️ REMOVED |
| FR-14 | Chat Threads & Messages | E4 | ✅ DONE |
| FR-15 | Multi-agent Runtime with Tools | E4 | ✅ DONE |
| FR-16 | Real-time Collaborative Chat | E4 | ✅ DONE |
| FR-17 | Anonymous Chat with Quota | E4 | ✅ DONE |
| FR-42 | Chat Response Benchmark | E4 (4.8a–g) | ✅ DONE |
| FR-21 | Report Generation & Export | E5 | ✅ DONE |
| FR-22 | Podcast & Video Presentation | E5 | ✅ DONE |
| FR-23 | Image Generation | E5 | ✅ DONE |
| FR-18 | Automation Action Types | E6.4 | ✅ DONE |
| FR-19 | Automation Triggers | E6 | ✅ DONE |
| FR-20 | Automation Runs & Retries | E6 | ✅ DONE |
| FR-35 | Memory-Driven Automations | E6.5 | ✅ DONE |
| FR-25 | Web Client (Next.js) | E7 | ✅ DONE |
| FR-26 | Desktop Client (Electron) | E7 | ✅ DONE |
| FR-27 | Browser Extension (Plasmo) | E7 | ✅ DONE |
| FR-28 | Obsidian Plugin | E7 | ✅ DONE |
| FR-29 | MCP Server | E7 / E7.7 | ✅ DONE; expansion in 7.7 ready-for-dev |
| FR-30 | Token Usage Tracking | E8 | ✅ DONE |
| FR-31 | Credit Wallet & Purchases | E8.3 | ✅ DONE |
| FR-41 | Admin UI for Global LLM Model Configuration | E8.11 | ❌ GAP |
| FR-24 | Deep Open-Web Research via ChainLens | E9.1b | ✅ DONE (contract + regression guard); mode default 9.3 pending |
| FR-37 | Deep-Research Cost Metering | E9.2 | ✅ DONE |
| FR-38 | Research Degradation & Self-Host Independence | E9.1a | ✅ DONE |
| FR-39 | Memory → Scraper-Run Provenance & Re-Validation | E9.6 | ❌ GAP |
| FR-40 | First-Run Value — Research Runs Produce Memory | E3.13 | ⚠️ Epics: DONE; PRD still labels `[GAP]` — doc drift |

### NFR Coverage Matrix

| NFR | PRD Requirement | Epic Coverage | Status |
|-----|-----------------|---------------|--------|
| NFR-1a | CRUD & scraper performance | E1/E2 (platform baseline) | ✅ Covered |
| NFR-1b | Memory injection (blocks every chat turn) | E3.14 | ⚠️ Epics: DONE; PRD still labels `[GAP]` — doc drift |
| NFR-1c | Recall tool latency/score | E3.14 | ⚠️ Epics: DONE; PRD still labels `[GAP]` — doc drift |
| NFR-1d | Auto-extract off critical path | E3.14 | ⚠️ Epics: DONE; PRD still labels `[GAP]` — doc drift |
| NFR-2 | Security & Auth | E1/E3 | ✅ DONE |
| NFR-3 | Observability | E8.9 / platform | ✅ DONE |
| NFR-4 | Reliability | E1/E6/E8 | ✅ DONE |
| NFR-5 | Multi-tenancy Isolation | E1/E3 | ✅ DONE |
| NFR-6 | Citation Full-Editor Highlight | E3.6 | ✅ DONE |
| NFR-7 | Usage & Credit Dashboard | E8.3 | ✅ DONE |
| NFR-8 | Recall Quality (eval-gated) | E3.9 | ✅ DONE (implementation); baseline ratification pending |
| NFR-9 | Deep-Research Latency & Availability (State A/B) | E9.3 | ⚠️ PARTIAL (State A done; State B not ratified) |
| NFR-10 | Chat Response Regression Gate | E4 (4.8b/e/f/g) | ✅ DONE |

### Missing / Gap Summary

| Item | Epic Coverage | Impact | Recommendation |
|------|---------------|--------|----------------|
| **FR-41 Admin UI for Global LLM Model Configuration** | E8.11 `[GAP — backlog]` | Operational/admin pain; not user-facing launch blocker | Create story 8.11 with superuser gate, `/admin/global-model-connections` route, catalog hot-reload, and tests. |
| **FR-39 Memory → Scraper-Run Provenance & Re-Validation** | E9.6 `[GAP]` | P0 if "re-validation" differentiator is marketed; otherwise can defer post-launch | Add `source_capability`/`source_input`/`source_run_id` to `Memory`, re-validate API, and migration/tests. |
| **FR-40 First-Run Value** | E3.13 `[DONE]` in epics / `[GAP]` in PRD | Conflicting truth source; could mislead readiness call | Reconcile PRD status with `sprint-status.yaml`/code; if truly done, update PRD §4.3. |
| **NFR-1b/1c/1d Memory latency/injection/recall score** | E3.14 `[DONE]` in epics / `[GAP]` in PRD | Conflicting truth source; affects NFR-8 baseline | Reconcile PRD §5 NFR-1 with epics/3.14 completion; update `gate.yaml` if score exposed. |

### Coverage Statistics

- **Total PRD FRs (excluding removed/resolved):** 38
- **Covered/Done in epics:** 36
- **Gaps:** 2 (FR-41, FR-39)
- **Coverage percentage:** ~95% (with 2 documentation-drift items to reconcile)

### New Epics Not Traceable to PRD

- **Epic 10: Connector & Scraper Expansion** (BĐS scrapers) — extends FR-6; not in original PRD but justified by pivot documents.
- **Epic 11: Telegram Automation & Bot** — introduces `FR-TELE-*` requirements not in PRD; a new pivot feature set.

These epics are valid for current work but should be either folded into the PRD as amendments or kept as post-MVP expansion epics.

---

## 4. UX Alignment Assessment

### UX Document Status

UX design is provided as **behavior contracts** (not full visual designs) in the sharded folder:

- `ux-contract-async-deep-research.md` — blocks Story 9.3 (NFR-9 State A)
- `ux-contract-admin-global-model-config.md` — blocks Story 8.11 (FR-41)
- `ux-contract-chat-benchmark.md` — blocks Stories 4.8a–g (FR-42, NFR-10)
- `ux-contract-first-run-onboarding.md` — blocks Story 3.13 (FR-40)
- `ux-contract-sync-offline-indicator.md` — blocks Stories 9.1a (FR-38) and 9.3 (NFR-9)
- `ux-contract-usage-dashboard.md` — blocks Story 8.3 (FR-31/NFR-7) and 8.12 (workspace limits)

### UX ↔ PRD Alignment

| UX Contract | PRD Requirement(s) | Alignment |
|-------------|-------------------|-----------|
| Async Deep Research | NFR-9 State A, FR-38, FR-24 | ✅ Aligned. Defines 10 UI states (`S1–S10`) for progress-first async deep research, including `partial`, `insufficientEvidence`, `engine_unavailable`, and `degraded`. Matches PRD §4.9 and NFR-9 State A. |
| Admin Global Model Config | FR-41 | ✅ Aligned. Contract A1–A7 matches FR-41 acceptance criteria: superuser-only, merged file/DB-backed list, hidden API key, test connection, hot-reload. |
| Chat Benchmark | FR-42, NFR-10 | ✅ Aligned. B1–B7 mirror NFR-10 metrics and FR-42 telemetry (p95 latency, TTFB, error rate, finish rate, citation count, cost/turn, per-mode matrix). |
| First-Run Onboarding | FR-40 | ⚠️ Mostly aligned. Contract focuses on a **research-run prompt** rather than sample-data seeding, matching PRD decision to *not* seed fake data. However, PRD still labels FR-40 `[GAP]` while this UX contract and epics say the story is `DONE`. |
| Sync & Offline Indicator | FR-38, NFR-9 | ✅ Aligned. Defines states for Zero sync, auth cookie cross-subdomain failure, and deep-research degradation. Supports PRD §4.9 and AGENTS.md production-auth cookie note. |
| Usage & Credit Dashboard | FR-31, NFR-7, Story 8.12 | ✅ Aligned. U1–U7 match FR-31/NFR-7 dashboard requirements and workspace limits. Depends on FR-37 `costDollars` for U4. |

### UX ↔ Architecture Alignment

| UX Contract | Architecture Dependencies | Assessment |
|-------------|---------------------------|------------|
| Async Deep Research | `AD-17` (async door), `AD-5` (Zero scope), `AD-18` (memory bounds) | ✅ Supported. Contract explicitly references AD-17 SSE delivery and AD-5 rule that `runs` do **not** enter Zero publication. |
| Admin Global Model Config | `AD-8` (cost registration), `AD-9` (RBAC 3 roles unchanged) | ✅ Supported. Contract does not introduce a new admin role, preserving AD-9. |
| Chat Benchmark | `AD-4` (multi-agent runtime), `AD-8` (cost tracking) | ✅ Supported. Telemetry sources (`NewChatClient`, `TokenUsage`) are architecture-standard. |
| First-Run Onboarding | `AD-18` (memory bounds), `FR-38` (degradation) | ✅ Supported. Contract requires research run memory and AD-18 bounds to keep first-run chat fast. |
| Sync & Offline Indicator | `AD-5` (Zero sync), `AD-4` (Redis/Celery), `FR-38` | ✅ Supported. Cross-subdomain cookie is a deployment/ops detail, not an architecture gap. |
| Usage & Credit Dashboard | `AD-8` (unified wallet), `AD-10` (token usage) | ✅ Supported. Uses `TokenUsage`, `credit_micros_balance`, and `costDollars` as canonical data sources. |

### Alignment Issues

No critical UX/PRD/Architecture misalignment was found. The main concern is **truth-source drift** already noted in §3:

- FR-40 and NFR-1b/1c/1d are marked `[GAP]` in the PRD but `DONE` in the epics/UX contracts. The UX contract for first-run onboarding is built on top of Story 3.13 being done, so if the PRD is not updated the three artifacts will tell different stories.

### Warnings

- **Deferred UX not yet spec'd:** UI memory browser / research timeline and a full visual design system are explicitly deferred. The UX contract file explains why, but any team building those UIs before `3-14` and `3-13` are truly complete is designing on unstable ground.
- **Story 8.11 (FR-41) remains `[GAP]`: ** A good UX contract exists, but the story is still in backlog. UX is ready; implementation is not.
- **Story 9.3 (NFR-9) still partial: ** UX contract covers State A well, but State B (sync chat-mode) cannot be fully designed until Nowing/ChainLatency p95 targets are ratified.

---

## 5. Epic Quality Review

### Epic-by-Epic Quality Summary

| Epic | User Value | Independence | Story Sizing | AC Format (G/W/T) | No Forward Deps | Notes |
|------|------------|--------------|--------------|-------------------|-----------------|-------|
| E1 Identity, Auth & Workspace RBAC | ✅ User-facing auth/RBAC | ✅ Independent | ✅ Sized | ✅ Mostly G/W/T | ✅ | Brownfield; done. |
| E2 Connectors | ✅ User-facing data sources | ✅ Independent | ✅ Sized | ✅ G/W/T | ✅ | 2.6–2.9 are `ready-for-dev` expansion; no forward dependencies. |
| E3 Knowledge Base + Long-Term Memory | ✅ User-facing research memory | ✅ Independent | ✅ Sized | ✅ G/W/T | ✅ | 3.13/3.14 now user-centric and `DONE`. 3.15/3.16 are `ready-for-dev`. |
| E4 Chat & Agents | ✅ User-facing chat | ✅ Independent | ✅ Sized | ✅ G/W/T | ✅ | 4.8h adds mode-aware policy; 4.7/4.8d ready-for-dev. |
| E5 Deliverables | ✅ User-facing outputs | ✅ Independent | ✅ Sized | ✅ (older done stories) | ✅ | Done. |
| E6 Automations | ✅ User-facing workflows | ✅ Independent | ✅ Sized | ✅ G/W/T | ✅ | 6.6/6.7/6.9 gated after BĐS pilot; no forward technical dependencies. |
| E7 Multi-surface Clients | ✅ User-facing clients | ✅ Independent | ✅ Sized | ✅ G/W/T | ✅ | 7.4/7.7 ready-for-dev. |
| E8 Billing / Usage | ✅ User-facing cost control | ✅ Independent | ✅ Sized | ✅ G/W/T | ✅ | 8.11 gap; 8.12/8.13 ready-for-dev. |
| E9 Deep Research | ✅ User-facing reliable research | ⚠️ Sequence constraint with ChainLens | ✅ Sized | ✅ G/W/T | ✅ | 9.1a→9.1b/9.2/9.3 is architecture sequence, not a forward business dependency. |
| E10 Connector & Scraper Expansion | ✅ User-facing BĐS scrapers | ✅ Independent | ✅ Sized | ✅ G/W/T | ✅ | New pivot epic; 10.1 in review, 10.4 backlog. |
| E11 Telegram Automation & Bot | ✅ User-facing notifications/bot | ✅ Independent | ✅ Sized | ✅ G/W/T | ✅ | New pivot epic; done. |

### Best Practices Compliance Checklist (per epic)

- [x] Epics deliver user value (no technical milestone epics).
- [x] Epics can function independently.
- [x] Stories are appropriately sized.
- [x] No forward dependencies on future epics.
- [x] Database tables are created when needed (brownfield; tables exist).
- [x] Acceptance criteria use Given/When/Then.
- [x] Traceability to FRs is maintained.

### Critical / Major / Minor Issues

#### 🔴 Critical Violations

*None found.* All epics are user-value focused, and no story is blocked by a future epic. The architecture-dependency sequence in Epic 9 (`9.1a` before `public repo` before `9.1b/9.2/8.7` before `9.3`) is an explicit, justified ordering constraint, not a hidden forward dependency.

#### 🟠 Major Issues

1. **PRD ↔ Epics truth-source drift (FR-40, NFR-1b/1c/1d)**
   - The PRD still labels FR-40 and NFR-1b/1c/1d as `[GAP]`, while the epics and UX contracts mark the corresponding stories as `DONE`. This is a documentation-level defect that can mislead the readiness call.
   - **Recommendation:** Reconcile the PRD with `sprint-status.yaml`/code and update status tags; or, if the code is not actually complete, retag the epics to `PARTIAL`/`GAP`.

2. **Story 4.8h — Mode-Aware Chat Policy AC contain implementation/tool-call specifics**
   - AC specify exact tool calls (`search_knowledge_base` `top_k=1, max_passages=4`), forbidden tools, and call budgets. These are verifiable but border on prescribing implementation inside acceptance criteria.
   - **Recommendation:** Move the detailed policy spec to a separate `doc/specs/` file and keep the AC at the user-observable level (latency, cost, quality outcomes per mode).

3. **Story 10.1 — BĐS Scraper AC prescribe obfuscation algorithm**
   - AC states `gzip → base64 → nibble-swap → Latin-1 JSON` decoding. This is a low-level implementation step, not a behavior a user can validate.
   - **Recommendation:** Keep the AC as "returns a typed listing list given a valid mobile API response" and move the decode chain to implementation notes.

#### 🟡 Minor Concerns

1. **Several ready-for-dev stories lack explicit error/edge AC.**
   - Story 4.7 (pointer tabs), 8.12 (workspace limits), 8.13 (PostHog) have happy-path AC but no negative cases (e.g., missing metadata, plan not configured, missing key). Add at least one negative AC before dev starts.

2. **Implementation hints sometimes live inside AC or immediately after them.**
   - Many stories have a `Kỹ thuật:` (technical) paragraph after the AC. In a few cases the paragraph appears under the AC section without an explicit "Implementation hints (not AC)" label (e.g., 2.6, 2.7, 3.15, 3.16). While most are clearly marked, a couple are ambiguous. Label all implementation paragraphs explicitly.

3. **Cross-epic impact of 7.7 (MCP tool expansion).**
   - Story 7.7 lists 11 new MCP tools spanning image generation, BĐS, automations, reports, and chat. Slice 4–5 is pending `bmad-dev-story`. This is a large expansion; ensure it is sequenced after the underlying capabilities (FR-21/23, FR-6 expansion, FR-18/19/20) are stable, otherwise it risks exposing incomplete tools.

### Dependency Analysis

- **Within-epic dependencies are natural:** Later stories consume outputs of earlier stories (e.g., `3.13` → `3.14`, `9.1a` → `9.1b`/`9.2`/`9.3`).
- **Cross-epic dependencies are minimal and well-documented:**
  - `3.13` has a soft dependency on `9.6a` for full provenance but can ship a minimal version first.
  - `4.8h` depends on FR-42/NFR-10 benchmark harness (already done).
  - `8.3` usage dashboard depends on FR-37 `costDollars` (done).
  - `10.4` (aggregator/backlog) depends on `10.1/10.2/10.3` and FR-39.
- **No circular or forward dependencies were found.**

### Story Sizing / Testability

- All active `[GAP]` and `[ready-for-dev]` stories have testable Given/When/Then acceptance criteria.
- The brownfield context means no "create all tables in Story 1.1" anti-pattern.
- Stories `6.6`, `6.7`, `6.9` are intentionally gated after BĐS pilot, which is a business gate, not a technical dependency.

---

## 6. Final Assessment

### Docs-Drift Check Result

`python3 /Users/luisphan/Documents/GitHub/nowing/scripts/check-docs-drift.py` was run during the assessment.

- **Result:** `Docs-drift check PASSED.`

### Overall Readiness Status

**READY**

The Nowing planning artifacts are ready for implementation. The major blockers from the previous assessment run (FR-18 automation action types, FR-35 memory-driven automations, NFR-6 citation full-editor highlight, NFR-7 usage/credit dashboard, FR-37 ChainLens cost metering, FR-38 research degradation, FR-24 contract regression guard, and the FR-40/NFR-1 memory gaps) have been addressed. PRD, epics, architecture, and UX contracts are largely aligned.

The remaining items below are non-blocking for the core launch but should be closed as fast-follows.

### Critical Issues Requiring Immediate Action

*None.* No issue identified in this assessment blocks implementation or launch.

### Major Issues Requiring Attention

1. **PRD ↔ Epics status drift (FR-31, NFR-7, FR-40, NFR-1b/1c/1d)**
   - The PRD still tags these as `[GAP]` while the epics and UX contracts tag the corresponding stories as `DONE` (E8.3, E3.13, E3.14). This is a documentation-level defect that can mislead the readiness call.
   - **Action:** Reconcile the three sources. If the code is truly complete, update the PRD; if not, retag the epics/UX to `PARTIAL`/`GAP`.

2. **FR-39 — Memory → Scraper-Run Provenance & Re-Validation**
   - Still `[GAP]` in epics (E9.6). Not a launch blocker per PRD, but it underpins the "memory with living source" differentiator.
   - **Action:** Schedule E9.6 as a P0 fast-follow if the re-validation story is part of launch positioning; otherwise keep it as post-MVP.

3. **FR-41 — Admin UI for Global LLM Model Configuration**
   - Still `[GAP]` in epics (E8.11 backlog). Operational pain for platform admin, not user-facing.
   - **Action:** Create the dev story and pull it into the next sprint; the UX contract is already complete.

### Minor Issues

- **Story 4.8h AC** mix user-observable outcomes with internal tool-call limits. Move detailed policy to a spec doc.
- **Story 10.1 AC** prescribes an obfuscation decode chain. Move to implementation notes.
- **Several ready-for-dev stories** (4.7, 8.12, 8.13) lack negative-case AC.
- **Implementation-hint paragraphs** in some stories are not always explicitly labeled as non-AC.

### Recommended Next Steps

1. Resolve PRD/epics/UX truth-source drift for FR-31, NFR-7, FR-40, and NFR-1b/1c/1d.
2. Decide whether FR-39 (E9.6) is launch-critical; if yes, staff it before public repo.
3. Schedule FR-41 (E8.11) and the ready-for-dev stories 8.12/8.13 for the next planning cycle.
4. Clean up AC implementation details in stories 4.8h and 10.1 before dev start.
5. Continue monitoring ChainLens `43-1/43-2/43-5` and Nowing `9.3` benchmarks for NFR-9 State B ratification.

### Final Note

This assessment identified **no critical issues**, **two non-blocking implementation gaps** (FR-39, FR-41), and **one documentation-drift cluster** (FR-31/NFR-7, FR-40, NFR-1b/1c/1d) across **five categories**. With those fast-follows tracked, the project can proceed to implementation. The `check-docs-drift.py` script passed, indicating public docs are currently consistent with the code artifacts.
