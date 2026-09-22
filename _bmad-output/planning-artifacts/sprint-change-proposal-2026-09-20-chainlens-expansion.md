# Sprint Change Proposal: ChainLens Full Capability Suite Integration (Epic 20 Extension & Story 26.9c)

**Document ID:** `SCP-2026-09-20-CHAINLENS-EXPANSION`  
**Date:** 2026-09-20  
**Author:** Winston (System Architect) & Luisphan  
**Status:** PROPOSED (Ready for Review & Approval)  
**Affected Epics:** Epic 20 (Nowing Ecosystem Integration), Epic 26 (DSH Missions & Wide Research), Epic 6 (Automations & Triggers)

---

## 1. Issue Summary

### 1.1 Problem Statement
Nowing currently connects to `chainlens-research` (`https://research-api.chainlens.net`) via a narrow subset of its API: `POST /api/v1/search` for basic Q&A text research (`chainlens.research`), news entity lookup (`news.entity_search`), and the baseline scraper-feed / gap-fill contracts (Stories 20.1–20.4).

An audit of the official ChainLens MCP tool suite (`apps/mcp/src/tools/`) and production REST controllers reveals that Nowing is currently missing **70%+ of ChainLens production capabilities**, including:
1. **Token-efficient URL Content Extraction (`output=contents` / `chainlens_contents`):** Clean markdown page extraction with highlights via Crawl4AI without spinning up heavy headless browser containers.
2. **High-Signal Code Search (`output=code_context` / `chainlens_code_search`):** Targeted search across GitHub repositories, official documentation, and Stack Overflow for coding sub-agents.
3. **Native 50-Entity Wide Research Matrix (`output=wide_research` / `chainlens_wide_research`):** Multi-entity comparative intelligence. Story 26.9a currently uses a temporary workaround (`output=table` + `outputSchema`).
4. **OpenAI-Compatible Chat Gateway (`POST /v1/chat/completions` + `GET /v1/models`):** Allows Nowing to treat ChainLens as a native LLM provider in Global Model Connections (`admin/global-model-connections`).
5. **Recurring Webhook Monitors (`POST /v1/monitors` / `chainlens_monitor`):** Proactive web change detection (cron + deduplication policies) that can push events into Nowing Automations (`AutomationTriggerType`).
6. **Asynchronous Research Jobs Dispatch (`POST /async-jobs`):** Non-blocking execution of long-running research tasks with SSE lifecycle resumption, preventing gateway socket timeouts.
7. **Pulse News — Intelligence Feed + Angle Research (`GET /v1/pulse/*` + `POST /v1/pulse/research`):** Pre-computed topic feed (`tech|ai|finance|science|security|startup`) where each item carries pre-generated research *angles* (`label`, `prompt`, `estimatedCredits`, `costDollars`). Distinct from on-demand `news.entity_search` — this is a proactive, curated feed with 1-click deep-research per angle (SSE).

### 1.2 Context & Discovery
During the production verification of ChainLens deployment (`8477f537`, Qwen3-Embedding-8B @ 768 dims, Claude Sonnet 4.6 writer), all above endpoints were verified as active and functional on `https://research-api.chainlens.net`. Integrating these capabilities into Nowing will dramatically reduce custom scraper overhead, provide superior code intelligence, unlock proactive automations, and allow seamless model connection reuse.

---

## 2. Impact Analysis

### 2.1 Epic Impact Matrix

| Epic | Impact Type | Description |
| :--- | :--- | :--- |
| **Epic 20 (Nowing Ecosystem Integration)** | **Direct Extension** | Add Stories **20.5** (Contents), **20.6** (Code Search), **20.7** (OpenAI Gateway), **20.8** (Webhook Monitors), **20.9** (Async Jobs), **20.10** (Pulse Feed), and **20.11** (Pulse Angle Research). |
| **Epic 26 (DSH Missions)** | **Story Upgrade** | Add Story **26.9c** to upgrade `dsh_worker_crawl_subgraph.py` from temporary `output=table` to native `output=wide_research`. |
| **Epic 6 (Automations & Triggers)** | **Additive Trigger** | Add `chainlens_monitor` to `AutomationTriggerType` and route inbound webhook callbacks to trigger automation workflows. |
| **Epic 8 / 29 (Model Connections)** | **Zero-Code Config** | Register ChainLens as a supported OpenAI-compatible provider template in admin global model connections. |

### 2.2 Technical & Architectural Impact
- **Reuse Existing Core:** Nowing already possesses `ChainLensServiceAuth` (`app/services/chainlens/auth.py`), `ResearchInput`/`ResearchOutput` infrastructure, and `app/capabilities/core/` registration framework. All new capabilities plug directly into this spine without architectural refactoring.
- **Cost Allocation & Ledger:** All new capabilities continue to report `costDollars` in response headers/events, automatically flowing into `TokenUsage` (`usage_type=chainlens_contents`, `chainlens_code_search`, `chainlens_wide_research`, etc.).
- **License Invariants:** Respects `AD-15` & `AD-16` — ChainLens remains an independent external service; Nowing acts as the client orchestration layer.

---

## 3. Recommended Approach

**Approach:** Direct Backlog Adjustment (Extend Epic 20 + Add Story 26.9c).  
**Scope Classification:** **Moderate** (8 modular stories, estimated 11–13 engineering days).  
**Risk Assessment:** **Low**. The upstream API contracts are already stabilized, documented, and actively running in production. Nowing already has authenticated connectivity verified.

---

## 4. Detailed Story Proposals

```
================================================================================
Story 20.5: `chainlens.contents` Token-Efficient URL Extraction Capability
================================================================================
Section: Epic 20 (Nowing Ecosystem Integration)
Status: ready-for-dev
Priority: P0
Effort: 1.5 days

Story:
As a Nowing agent or scraper pipeline,
I want to extract clean, token-efficient markdown content from one or more URLs via ChainLens,
so that I can read web pages, articles, and documentation without launching heavy browser sandboxes.

Acceptance Criteria:
1. GIVEN a request to read one or more URLs with optional focus query,
   WHEN the `chainlens.contents` capability is invoked,
   THEN it calls ChainLens `POST /api/v1/search` with payload:
        {
          "urls": ["..."],
          "output": "contents",
          "query": "optional focus query",
          "summary": true,
          "stream": false
        }
        and headers from `ChainLensServiceAuth`.
2. GIVEN ChainLens returns extracted page contents and highlights,
   WHEN parsing the response,
   THEN the output conforms to `ContentsOutput` containing clean markdown `content`,
        `sourceUrls`, confidence scores, and `cost_micros`.
3. GIVEN a URL that is behind a challenging anti-bot or dynamic JS wall,
   WHEN ChainLens crawls via Crawl4AI / Trafilatura,
   THEN it returns clean text content without client-side headless Chrome overhead in Nowing.
4. GIVEN the capability completes,
   WHEN billing is processed,
   THEN a `TokenUsage` record with `usage_type="chainlens_contents"` is recorded.

Technical Context:
- Register `CHAINLENS_CONTENTS` capability in `app/capabilities/chainlens/contents/`.
- Add `ContentsInput` and `ContentsOutput` schemas.
- Add `chainlens_contents` tool to multi-agent chat sub-agents.
```

```
================================================================================
Story 20.6: `chainlens.code_search` Technical Context & Code Search Capability
================================================================================
Section: Epic 20 (Nowing Ecosystem Integration)
Status: ready-for-dev
Priority: P0
Effort: 1.5 days

Story:
As a developer using Nowing Web Builder or coding sub-agents,
I want to search GitHub repositories, documentation, and Stack Overflow for high-signal code context,
so that my agent receives token-efficient code snippets and API usage instead of generic prose.

Acceptance Criteria:
1. GIVEN a technical programming query and optional language filter,
   WHEN `chainlens.code_search` is invoked,
   THEN it calls ChainLens `POST /api/v1/search` with:
        {
          "query": query,
          "output": "code_context",
          "sources": ["web"],
          "history": [],
          "stream": true
        }
2. GIVEN the SSE stream returns code blocks and citations,
   WHEN the stream finalizes,
   THEN the output returns formatted code blocks, repository references, and file path markers
        ready for direct injection into coding agent prompts.
3. GIVEN the capability tool completes,
   WHEN recording usage,
   THEN `TokenUsage` is recorded with `usage_type="chainlens_code_search"`.

Technical Context:
- Register `CHAINLENS_CODE_SEARCH` capability in `app/capabilities/chainlens/code_search/`.
- Wire into `app/agents/chat/multi_agent_chat/subagents/builtins/chainlens/tools/index.py`.
```

```
================================================================================
Story 26.9c: Native ChainLens `output=wide_research` Upgrade for DSH Missions
================================================================================
Section: Epic 26 (DSH Missions & Wide Research)
Status: ready-for-dev
Priority: P1
Effort: 1.5 days

Story:
As a DSH Mission researcher,
I want the LangGraph `crawl` subgraph to use ChainLens's native `output=wide_research` engine,
so that multi-entity competitive research matrices (up to 50 entities) are generated with
native matrix citations rather than the fallback `output=table` workaround.

Acceptance Criteria:
1. GIVEN a DSH mission with research targets (e.g. 10–50 competitors, companies, or technologies),
   WHEN the LangGraph crawl subgraph executes,
   THEN it calls ChainLens `POST /api/v1/search` with `output: "wide_research"`, `stream: true`,
        and `numEntities: N`.
2. GIVEN ChainLens streams `entity_result` events containing `entityName`, `attributes`, and `citations`,
   WHEN the stream completes,
   THEN `dsh_worker_crawl_subgraph.py` aggregates all entities into `checkpoint.wide_research_matrix`
        with structure `{ [entityName]: { attributes: Record<string, string>, citations: Citation[] } }`.
3. GIVEN `checkpoint.wide_research_matrix` is populated,
   WHEN Story 26.9b (Pro Excel Formatter in Daytona sandbox) executes,
   THEN it consumes the native entity matrix to format multi-tab comparative spreadsheets.
4. GIVEN a mission resumes from checkpoint,
   WHEN `checkpoint.wide_research_matrix` already exists,
   THEN the crawl node skips re-invoking ChainLens and transitions directly to reasoning.

Technical Context:
- Supersedes the temporary "Direction A" (`output=table`) in `Story 26.9a`.
- Updates `app/tasks/dsh_worker_crawl_subgraph.py` to handle SSE `type: "entity_result"`.
```

```
================================================================================
Story 20.7: ChainLens OpenAI Gateway in Global Model Connections
================================================================================
Section: Epic 20 (Nowing Ecosystem Integration) & Epic 8
Status: ready-for-dev
Priority: P0
Effort: 1.0 day

Story:
As a Nowing superadmin or workspace owner,
I want to connect ChainLens as an OpenAI-compatible model provider,
so that any chat agent in Nowing can directly select ChainLens grounded models without custom code.

Acceptance Criteria:
1. GIVEN the Admin Global Model Connections page (`admin/global-model-connections`),
   WHEN an admin adds a new connection,
   THEN ChainLens is available as a preset template:
        - Provider Type: `openai`
        - Base URL: `https://research-api.chainlens.net/v1`
        - Default Models: `claude-sonnet-4-6`, `haiku-4.5`, `deepseek-v4-pro`, `gpt-5.4`
2. GIVEN a chat request using a ChainLens-connected model,
   WHEN Nowing calls `POST https://research-api.chainlens.net/v1/chat/completions`,
   THEN ChainLens executes the request and streams standard OpenAI SSE chunks back to Nowing.
3. GIVEN the connection is validated via "Test Connection" button,
   WHEN Nowing calls `GET https://research-api.chainlens.net/v1/models`,
   THEN it returns HTTP 200 and displays active grounded models.

Technical Context:
- Zero backend schema change needed: `app/routes/model_connections_routes.py` already supports generic OpenAI providers.
- Add preset metadata to `nowing_web/app/admin/global-model-connections/page.tsx`.
```

```
================================================================================
Story 20.8: ChainLens Webhook Monitors Integration for Nowing Automations
================================================================================
Section: Epic 20 (Nowing Ecosystem Integration) & Epic 6
Status: ready-for-dev
Priority: P1
Effort: 2.0 days

Story:
As a Nowing user setting up automations,
I want to schedule recurring web search monitors on ChainLens that ping Nowing via webhook,
so that my automations trigger automatically when new market news or competitor updates emerge.

Acceptance Criteria:
1. GIVEN an Automation with trigger type `chainlens_monitor`,
   WHEN the automation is enabled,
   THEN Nowing calls ChainLens `POST /v1/monitors` with:
        {
          "name": automation.name,
          "query": automation.trigger_config.query,
          "cron": automation.trigger_config.cron,
          "webhookUrl": f"{NOWING_API_URL}/api/v1/webhooks/chainlens-monitor/{automation.id}",
          "dedupKeyPolicy": "content_hash" | "semantic_delta"
        }
        and stores the returned `monitorId` in automation trigger metadata.
2. GIVEN ChainLens executes the scheduled monitor and detects new delta results,
   WHEN ChainLens posts the findings to Nowing's webhook endpoint,
   THEN Nowing verifies HMAC / service signature, enqueues an `AutomationRun`, and passes the
        new search results into the automation workflow action steps.
3. GIVEN an automation is paused or deleted in Nowing,
   WHEN the status changes,
   THEN Nowing calls ChainLens API to delete or pause the recurring monitor.

Technical Context:
- Add `app/routes/webhooks/chainlens_monitor.py` webhook handler.
- Add `AutomationTriggerType.CHAINLENS_MONITOR = "chainlens_monitor"` in `app/models/automations.py`.
- Add monitor client in `app/services/chainlens/monitors.py`.
```

```
================================================================================
Story 20.9: Asynchronous Research Job Runner & Resilience Recovery
================================================================================
Section: Epic 20 (Nowing Ecosystem Integration)
Status: ready-for-dev
Priority: P2
Effort: 1.5 days

Story:
As a system operator,
I want long-running deep research queries (over 60 seconds) to execute via ChainLens Async Jobs,
so that client HTTP disconnections or reverse-proxy timeouts do not abort in-flight research.

Acceptance Criteria:
1. GIVEN an execution mode configured for asynchronous dispatch,
   WHEN research is requested,
   THEN Nowing calls ChainLens `POST /async-jobs` and receives `{ runId, status: "pending" }`.
2. GIVEN an active `runId`,
   WHEN Nowing polls status or listens to `GET /async-jobs/{runId}/events`,
   THEN it streams live research phases to the client and persists final deliverables.
3. GIVEN a network blip or worker restart during deep research,
   WHEN the worker recovers,
   THEN it inspects `GET /async-jobs/{runId}` to recover the completed report without re-paying
        token or search costs.

Technical Context:
- Add `AsyncJobsClient` in `app/services/chainlens/async_jobs.py`.
- Integrates with `app/capabilities/core/async_runner.py`.
```

```
================================================================================
Story 20.10: `chainlens.pulse_feed` Curated Intelligence Feed Capability
================================================================================
Section: Epic 20 (Nowing Ecosystem Integration)
Status: ready-for-dev
Priority: P1
Effort: 1.5 days

Story:
As a Nowing agent, dashboard surface, or automation,
I want to pull the ChainLens Pulse curated intelligence feed plus each item's pre-generated research angles,
so that users can browse proactive market/competitor news instead of only on-demand search.

Acceptance Criteria:
1. GIVEN a request for the intelligence feed with optional `topic` and `cursor`,
   WHEN `chainlens.pulse_feed` is invoked,
   THEN it calls ChainLens `GET /v1/pulse/feed?topic=&cursor=` (alias `GET /v1/news/feed`)
        and returns `{ items: PulseFeedItem[], pagination: { nextCursor, hasMore, limit } }`.
        `topic` ∈ `tech|ai|finance|science|security|startup`; `cursor` is an ISO date for
        keyset pagination (older-than), not an offset.
2. GIVEN a feed `itemId`,
   WHEN `chainlens.pulse_feed` requests angles via `GET /v1/pulse/items/{id}/angles`,
   THEN it returns `PulseAngleResponse[]` with `{ angleId, label, description, prompt,
        estimatedCredits, costDollars, model }` — the cost hint drives the UX cost
        transparency badge before any research runs.
3. GIVEN the feed or angles call completes,
   WHEN billing is processed,
   THEN `TokenUsage` records `usage_type="chainlens_pulse_feed"`.
4. GIVEN an empty feed page or an item with zero angles,
   WHEN the surface renders,
   THEN it shows a friendly empty state, never an error frame.

Technical Context:
- Register `CHAINLENS_PULSE_FEED` capability in `app/capabilities/chainlens/pulse/`
  (copy `news/entity_search/` structure; `billing_unit=BillingUnit.CHAINLENS_QUERY`).
- Schemas `PulseFeedInput{topic?,cursor?,itemId?}` / `PulseFeedOutput{items,angles,pagination}`.
- Service client `app/services/chainlens/pulse.py` — reuse `ChainLensServiceAuth.get_outbound_headers`.
- Feed/angles are PUBLIC throttled GETs (no SSE) — simple `httpx.get`, not the SSE parser.

================================================================================
Story 20.11: `chainlens.pulse_research` Angle Deep-Research (SSE) Capability
================================================================================
Section: Epic 20 (Nowing Ecosystem Integration)
Status: ready-for-dev
Priority: P1
Effort: 1.5 days

Story:
As a Nowing agent or automation acting on a Pulse angle,
I want to run the ChainLens angle deep-research stream on a chosen `{itemId, angleId}`,
so that a single click converts a curated news angle into a cited deep-research report.

Acceptance Criteria:
1. GIVEN a `{itemId, angleId}` pair plus optional `mode` and `chatId`,
   WHEN `chainlens.pulse_research` is invoked,
   THEN it calls ChainLens `POST /v1/pulse/research` with body
        `{ itemId, angleId, mode, output: "news", chatId }`
        (`mode` ∈ research|balanced|deep|speed|auto|fast|instant|quality) and streams SSE.
2. GIVEN the upstream SSE stream,
   WHEN parsing frames,
   THEN the executor reuses the existing `searchStream` parser — events are the SAME
        contract as `chainlens.research` (`init` → `text_delta` → `done{usage,chatId}`),
        so `sse_parser.py` and `ResearchOutput` are reused, NOT reimplemented.
3. GIVEN the `done` frame with `usage.costDollars`,
   WHEN billing is processed,
   THEN `TokenUsage` records `usage_type="chainlens_pulse_research"` and `cost_micros`
        via `cost_dollars_to_micros`.
4. GIVEN an angle that returns 402 (insufficient credits) or 404 (item/angle not found),
   WHEN the capability resolves,
   THEN it returns a typed degradation (engine_unavailable / insufficient_credits),
        never a raw upstream error.
5. GIVEN a `chatId` in the request or `done` frame,
   WHEN the research completes,
   THEN the session handle is persisted so `chainlens_chats` / `chainlens_ask`
        can resume the same SEP-2567 research thread.

Technical Context:
- Register `CHAINLENS_PULSE_RESEARCH` in `app/capabilities/chainlens/pulse_research/`.
- REUSE `app/capabilities/chainlens/research/sse_parser.py` + `ResearchOutput` — upstream
  `pulse-research.service.ts` pipes through `searchService.searchStream` (same event types).
- Executor mirrors `research/executor.py:_call_chainlens` but posts to `/v1/pulse/research`
  and forces `output="news"` + `tier="research"` (internal — upstream bills once).

---

## 5. Implementation Handoff & Rollout Plan

### 5.1 Phasing & Prioritization

```
Phase 1: High-Signal Capabilities (Sprint Current + 1)
├── Story 20.7: ChainLens OpenAI Gateway preset in Global Model Connections (P0 — 1 day)
├── Story 20.5: `chainlens.contents` URL Extraction Capability (P0 — 1.5 days)
└── Story 20.6: `chainlens.code_search` Code Context Capability (P0 — 1.5 days)

Phase 2: Deep Comparative Intelligence & Curated Feed (Sprint Current + 2)
├── Story 26.9c: Native ChainLens `wide_research` 50-Entity Matrix Upgrade (P1 — 1.5 days)
├── Story 20.10: `chainlens.pulse_feed` Curated Intelligence Feed (P1 — 1.5 days)
└── Story 20.11: `chainlens.pulse_research` Angle Deep-Research SSE (P1 — 1.5 days)

Phase 3: Proactive Automations & Async Scaling (Sprint Current + 3)
├── Story 20.8: ChainLens Webhook Monitors for Automations (P1 — 2.0 days)
└── Story 20.9: Async Research Jobs & Resilience Recovery (P2 — 1.5 days)
```

### 5.2 Success Criteria
1. **Zero Raw Browser Overhead for Simple Reads:** `chainlens.contents` replaces headless Playwright in 80%+ of document URL scraping tasks.
2. **Coding Sub-Agent Signal:** `chainlens.code_search` returns focused code blocks with line citations, reducing token waste by >40% compared to broad web search.
3. **Native Entity Matrices:** DSH Missions produce multi-entity comparison matrices natively via `output=wide_research` without tabular fallback parsing.
4. **Automations Powered by Web Signals:** Nowing automations can be triggered automatically via ChainLens recurring cron monitors.
5. **Proactive Intelligence Feed:** Users browse a curated Pulse news feed and trigger one-click angle deep-research (≤1 click from headline to cited report).

---

## 6. Architecture Review Addendum (Winston — 2026-09-20)

### 6.1 ADR Compliance Verification

| ADR | Verdict | Note |
| :--- | :---: | :--- |
| `AD-15` (ChainLens = external first-class service) | ✅ | All 6 stories communicate via REST/SSE with `ChainLensServiceAuth`. |
| `NG-5` / `AD-27` (No duplicate corpus) | ✅ | Results are ephemeral (chat context / sandbox), never stored as search index. |
| `AD-25` / `AD-49` (PII Dual-Vault) | ⚠️ **Guard required** | New guardrail: all outbound `query` payloads for contents/code_search MUST pass `redact_pii()` before leaving Nowing. |
| `AD-17` (Async door >60s) | ✅ | Story 20.9 directly implements this. |
| `AD-8` (Cost ledger) | ✅ | All capabilities record `TokenUsage` with distinct `usage_type`. |

### 6.2 Per-Story Technical Additions (binding for implementation)

1. **Story 20.7 (OpenAI Gateway):** UI must tag ChainLens models with a `[Web-Grounded]` badge — first-token latency is ~3–6s (grounded search) vs ~500ms plain LLM. Set user expectation in the model picker tooltip.
2. **Story 20.5 (Contents):** Position as "Fast-Reader" for public web only. Authenticated portals / interactive forms remain on Browser Operator (Epic 32). Document this boundary in the capability description.
3. **Story 20.6 (Code Search):** Output must map to PlateJS code-block schema (language tag + line numbers) for frontend rendering.
4. **Story 26.9c (Wide Research):** Mandatory checkpointing per `AD-108` — persist each `entity_result` incrementally to `checkpoint.wide_research_matrix` so a worker restart does not lose completed entities (query can run 45–120s).
5. **Story 20.8 (Monitors):** Webhook endpoint MUST verify HMAC-SHA256 signature (shared secret via `CHAINLENS_AUTH_CONTEXT_SECRET`) before enqueueing `AutomationRun` — prevents forged webhooks draining workspace credits.
6. **Story 20.9 (Async Jobs):** Defer to Phase 3 — current SSE path is stable; async adds value only for >60s deep research.

### 6.3 UX Review Addendum (Sally — 2026-09-20)

**📎 Full spec:** `_bmad-output/planning-artifacts/ux-spec-epic20-chainlens-agent-tools-2026-09-20.md` — contains the **binding agent-facing tool catalog** (Part A: all 9 ChainLens tools with exact names, when-to-use rules, parameter contracts, and guardrails pulled verbatim from `chainlens-research/apps/mcp/src/tools/*.ts`) plus per-surface designs and the i18n copy inventory. Dev agents MUST implement tool descriptions from that catalog — they are what the LLM reasons over to pick the correct capability.


#### Persona Lens Review

**Persona 1 — "Minh", Sales SDR (Lead-Gen beachhead):**
- *Need:* Monitor competitor news without manually re-searching.
- *UX impact (Story 20.8):* Automation builder must present `chainlens_monitor` trigger with a plain-language label ("Theo dõi tin tức web định kỳ") and a cron picker (daily/weekly presets), NOT a raw cron expression field. Monitor results should render as a digest card in the automation run timeline, with citations collapsible.
- *Edge case:* First monitor run may return zero deltas — show a friendly "Chưa có tin mới kể từ lần kiểm tra trước" empty state, never an error.

**Persona 2 — "An", Developer building automations (Web Builder):**
- *Need:* Fast, accurate API/code answers while building.
- *UX impact (Story 20.6):* Code results must render with syntax highlighting + copy button + source repo link. If ChainLens returns >5 snippets, collapse to top-3 with "Xem thêm N kết quả" expander to protect chat readability.
- *UX impact (Story 20.7):* In the model picker, ChainLens models appear under a distinct group "ChainLens (Web-Grounded)" with a globe icon. Tooltip: "Mô hình có khả năng tìm kiếm web trực tiếp — phản hồi chậm hơn nhưng luôn cập nhật."

**Persona 3 — "Lan", Analyst doing competitive research:**
- *Need:* Compare 20–50 companies/technologies without manual spreadsheet work.
- *UX impact (Story 26.9c):* During wide-research crawl, the DSH mission control must show a live progress indicator: "Đã phân tích 12/50 thực thể…" driven by incremental `entity_result` events. On resume after interruption, the UI must reflect already-completed entities immediately (from checkpoint), not restart from zero.
- *Edge case:* If an entity returns `null` attributes (no data found), render "Không tìm thấy dữ liệu" in the matrix cell — never leave a blank cell that reads as a bug.

#### Cross-Cutting UX Requirements (apply to all 6 stories)

1. **Cost transparency:** Every ChainLens-backed surface shows estimated cost BEFORE execution (reuse the existing cost-estimate pattern from deep research) — no surprise charges.
2. **Degradation UX:** If ChainLens is unavailable, all new capabilities degrade with the standard `degradation-ux` pattern (friendly banner + retry), consistent with Story 9.1a's established pattern. Never raw 5xx.
3. **Latency honesty:** Any action taking >5s must show progressive feedback (streaming text, skeleton loaders, or phase labels like "Đang đọc trang web…").
4. **Vietnamese-first copy:** All new UI strings (model picker labels, automation trigger names, empty states) must ship in both `vi.json` and `en.json` — following the i18n architecture (client-side next-intl).


**Pulse surfaces (Stories 20.10/20.11):** two-step browse→pick→research flow. Feed list keyed by `nextCursor` (infinite scroll, never offset); per-item `N góc nhìn` badge from `anglesCount`; angle picker shows `label` + `estimatedCredits` cost badge (transparency before charge). Angle tap → `pulse_research` SSE into the same deep-research renderer. Empty/402/no-credit states have friendly vi/en copy. See spec Part B.7.

### 6.4 Dev Review Addendum (Amelia — 2026-09-20)

Verified against live code — file paths below are exact.

**A. Copy-pattern map (what to reuse):**

| Story | Reuse | Path |
| :--- | :--- | :--- |
| 20.5 / 20.6 | Capability registration | `app/capabilities/news/entity_search/definition.py` — `Capability(name=..., billing_unit=BillingUnit.CHAINLENS_QUERY, context_aware=True)` + `register_capability()` |
| 20.5 / 20.6 | Upstream call + `output`/`outputSchema` forwarding | `app/capabilities/chainlens/research/executor.py` `_call_chainlens` (`:68`, forwards at `:91-94`) |
| 20.7 | OpenAI provider list + base_url + test | `app/routes/model_connections_routes.py` `list_model_providers` (`:262`) + `app/services/provider_registry.py` `REGISTRY` |
| 26.9c | `output`/`outputSchema` forwarding + checkpoint | `app/tasks/dsh_worker_crawl_subgraph.py` + `app/capabilities/chainlens/research/schemas.py` `ResearchInput.output` (`:116`) |
| 20.8 | HMAC webhook verify | `app/routes/gateway_webhook/webhooks.py` `hmac.compare_digest` (`:119`) — never `==` |
| 20.9 | Async run + event bus | `app/capabilities/core/async_runner.py` `start_async_run` (`:50`) + `run_event_bus` |

**B. Blocking gaps found (fix before implement):**

1. **Story 20.8 — `TriggerType.CHAINLENS_MONITOR` needs an Alembic migration.** `app/automations/persistence/enums/trigger_type.py` has only `schedule|event|manual|memory_change`; column is `SQLAlchemyEnum(name="automation_trigger_type")` (`models/trigger.py:31`) → Postgres enum `ALTER TYPE ... ADD VALUE` (cannot run inside a transaction block on PG<12). **Wrong file path in story:** `app/models/automations.py` does not exist — correct path is `app/automations/persistence/enums/trigger_type.py`.
2. **Story 20.8 — `params` JSONB already exists** (`models/trigger.py:39`) so no new schema; but `app/automations/services/trigger.py` must add an enable-path that calls `POST /v1/monitors` and stores `monitorId` in `params`, plus a new inbound route `app/routes/webhooks/chainlens_monitor.py` that enqueues `AutomationRun`.
3. **Agent tool wiring:** add `CHAINLENS_CONTENTS`, `CHAINLENS_CODE_SEARCH` to `_CI_VERBS` in `app/agents/chat/multi_agent_chat/subagents/builtins/chainlens/tools/index.py` (~`:17`). `build_capability_tools()` generates the LLM-facing tool — copy `description` verbatim from UX spec Part A.
4. **`ResearchInput.output` Literal too narrow** (`schemas.py:116` = `["answer","research","table"]`). For contents/code_search create dedicated `ContentsInput`/`CodeSearchInput` schemas (per plan) — do NOT widen `ResearchInput` for unrelated outputs.
5. **Story 20.9 — two different "run" systems.** `async_runner.py` is an in-process runner; the ChainLens `/async-jobs` is external HTTP. Implement `app/services/chainlens/async_jobs.py` `AsyncJobsClient` (external) then map `chainlens runId → nowing run_id` via `start_async_run`.

6. **Subagent exposure (CRITICAL — Option A adopted).** Today only `chainlens_research` + `news_entity_search` are live: `_CI_VERBS = [CHAINLENS_RESEARCH, NEWS_ENTITY_SEARCH]` in `tools/index.py:18` and `system_prompt.md` `<available_tools>` lists only `chainlens_research` + `read_run`/`search_run`. Registering a capability does NOT surface it to the agent — three edits are required per new tool:
   a. Create the `Capability` (`definition.py`) → `build_capability_tools` auto-generates `chainlens_<verb>` via `name.replace(".","_")`.
   b. Append the verb to `_CI_VERBS` in `app/agents/chat/multi_agent_chat/subagents/builtins/chainlens/tools/index.py`.
   c. Update `system_prompt.md` `<available_tools>` + `<playbook>` routing block (copy the UX spec Part A cheat-sheet verbatim) AND `description.md` triggers so the supervisor delegates correctly.
   **Decision:** Option A — keep ONE chainlens subagent but broaden it from "deep research" to "ChainLens intelligence": update `description.md` triggers to cover feed/browse/code/angles (not just deep research), and rewrite `system_prompt.md` playbook to the Part A routing cheat-sheet. Do NOT split subagents (Option B rejected — fragments routing, duplicates `ChainLensServiceAuth` wiring).

   **📎 Ready-to-apply rewrites (copy verbatim):** `_bmad-output/planning-artifacts/agent-prompts-chainlens-2026-09-20/system_prompt.md` and `…/description.md` — pre-written 9-tool routing playbook + updated supervisor triggers. Apply AFTER all new capabilities are registered; deploying the prompt before the tools exist makes the model reference unavailable tools.

   ✅ **Tool-name resolved:** the rewritten prompt already uses the real registered names — `chainlens_research` is the `ask` verb (existing `chainlens.research` capability → tool `chainlens_research`); no `chainlens.ask` duplicate needed. New capabilities must use `name` fields matching the prompt: `chainlens.contents`, `chainlens.code_search`, `chainlens.wide_research`, `chainlens.pulse_feed`, `chainlens.pulse_research`, `chainlens.monitor`, `chainlens.chats` → tools `chainlens_<verb>`.

---
*Created by BMAD Correct Course Workflow (`bmad-correct-course`).* (`bmad-correct-course`).*
