---
title: 'Story 9.1a: Research Degradation & Self-Host Independence'
description: ''
createdAt: '2026-07-28T10:28:33.303Z'
updatedAt: '2026-07-28T15:17:33.705Z'
tags:
  - bmad
  - bmad-source-bmad-output-implementation-artifacts-9-1a-research-degradation-selfhost-independence-md
---

---
baseline_commit: 25ba542c2a3dec95b0a4020da8c129242ba748e2
baseline_branch: develop
story_key: 9-1a-research-degradation-selfhost-independence
status: ready-for-dev
---

# Story 9.1a: Research Degradation & Self-Host Independence

**Status:** ready-for-dev
**Epic:** 9 — Deep Research dang tin cay: khong vo, khong treo, tinh phi dung
**Priority:** P0 — tien de truoc khi public repo
**Requirements:** FR-38; AD-15; AD-17; AD-19 measurement seam
**Baseline:** `25ba542c2a3dec95b0a4020da8c129242ba748e2` on `develop`
**Dependencies:** Existing capability REST/agent doors, run recorder, Nowing hybrid KB retrieval. No production-code dependency on Story 9.1b, 9.2, 9.3, 9.4 or 9.5.

## Story

La self-hoster,
toi muon Nowing dung duoc day du ma khong can deep-research engine, va deep research khong hard-fail khi engine cham, chet, bi rate-limit, bi 5xx, hoac chua cau hinh,
de toi khong cai xong moi phat hien mot tinh nang vo, va duong OSS/PLG cua Nowing khong sup.

## Current Reality

Tai baseline `25ba542c2a3dec95b0a4020da8c129242ba748e2`:

- `chainlens.research` da la capability that su: `definition.py` dang ky `Capability(name="chainlens.research")`, `ResearchInput`, `ResearchOutput`, executor `build_research_executor()`, va `BillingUnit.CHAINLENS_QUERY`.
- `_call_chainlens()` goi `POST {CHAINLENS_API_URL}/api/v1/search` voi Bearer service key. Neu `CHAINLENS_API_KEY` rong, ham raise `ConfigurationError(code="CHAINLENS_NOT_CONFIGURED")`; day la 500 tren REST/agent, khong phai degradation.
- `build_research_executor()` hien chi bat `httpx.TimeoutException` thanh `ExternalServiceError(code="CHAINLENS_TIMEOUT")` va `httpx.RequestError` thanh `ExternalServiceError(code="CHAINLENS_UNREACHABLE")`; upstream 401/429/5xx va SSE error deu thanh `ChainLensError`. Khong co fallback.
- `_parse_sse()` hien chi xu ly `error`, `done`, `block`, `updateBlock`; no bo im lang `partial`, `insufficientEvidence`, `heartbeat`, `progress`, `evidence_ready`, `synthesizing`, `noop`.
- `_parse_sse()` dang suy doan insufficient evidence bang heuristic: neu khong co `answer` va khong co `sources`, `saw_done=True` thi `status="insufficient_evidence"`, nguoc lai `timeout`. Dieu nay gop "engine noi khong du bang chung" voi "stream chet giua duong".
- `ResearchOutput.status` hien chi la `complete | partial | timeout | insufficient_evidence`. Chua co `engine_unavailable`; `billable_units` tra `0` khi khong co answer/sources, nen no-content degraded state co the khong bi tinh tien gia.
- REST door da co sync va async. Sync route goi executor inline, ghi `Run`, charge, tra typed output va `X-Run-Id`. Async `?mode=async` tao `Run` running, tra 202, stream `/runs/{id}/events`, cancel, history va terminal `run.finished`.
- Agent door hien sync-only, nhung dung cung registry executor, gate/charge, ghi `Run`, va tra inline output/preview. Story 9.3 moi so huu async agent door; 9.1a chi dam bao agent sync khong raise khi engine unavailable.
- MCP `nowing_chainlens_research` di qua `run_scraper()`, tuc goi REST scraper route. Neu REST output typed dung, MCP nhan cung degradation contract.
- Nowing co hybrid KB retrieval san co: `app/agents/chat/multi_agent_chat/shared/retrieval/hybrid_search.py::search_chunks()` nhan `AsyncSession`, `workspace_id`, `SearchScope`, `top_k`, loc `Document.workspace_id`, va tra `DocumentHit` voi real `document_id`/`chunk_id`. Legacy `app/retriever/chunks_hybrid_search.py::hybrid_search()` cung loc theo `workspace_id` va preserve chunk IDs.
- Quan trong: executor hien chi nhan `payload`. Fallback sang hybrid search can `session` va `workspace_id`, nen khong the lam dung bang cach sua rieng `executor.py` ma khong them context seam. Context san co o REST/agent doors la `CapabilityContext(session, workspace_id)`.
- PRD/AD-15 van co dong mo ta SSE theo `event:`/`data:` va `[DONE]`, nhung OQ-7/readiness da verify ChainLens thuc te phat NestJS `@Sse()` data-only frames, `type` nam trong JSON, terminal la `{"type":"done"}`. 9.1a phai parse typed degradation events theo wire behavior that; 9.1b moi so huu full contract-regression/doc correction.
- AD-19 da verify Nowing co `BlockType` classifier (`ok`, `cloudflare`, `captcha_recaptcha`, `captcha_hcaptcha`, `datadome`, `kasada`, `rate_limited`, `empty`, `unknown`). 9.1a khong build crawler escalation, nhung khi payload partial/insufficientEvidence co blocked URL/citation metadata thi phai do coverage counter theo taxonomy san co.

## Resolved Decisions

### D1 — Honest output, no fake success

Degradation is a successful transport response only, not a complete research result. REST/agent/MCP may return HTTP/tool success so self-host does not break, but `ResearchOutput.status` must be one of the degraded statuses and must never be `complete` unless ChainLens produced a complete result.

Required output taxonomy:

| Situation | `ResearchOutput.status` | Required details |
|---|---|---|
| ChainLens complete with answer/sources | `complete` | Preserve answer, sources order, chat_id, web_url |
| ChainLens explicit partial with usable partial evidence | `partial` | Preserve engine `reason`, partial evidence, citations |
| ChainLens explicit insufficient evidence and no useful evidence | `insufficient_evidence` | Preserve engine `reason`; do not re-derive by heuristic |
| Engine unavailable and KB fallback has citable hits | `partial` | `degraded=true`; reason identifies engine failure; sources are labelled KB citations |
| Engine unavailable and no citable fallback evidence | `engine_unavailable` | `degraded=true`; no fabricated answer or citation; human-readable `next_action` |
| Stream ends without terminal after heartbeat/no terminal and fallback unavailable | `engine_unavailable` or `timeout` only if preserving backward compatibility requires `timeout` | Must not be `insufficient_evidence` unless engine explicitly said so |

Additive schema fields are allowed and expected where needed, for example `degraded: bool`, `degradation_reason`, `engine_reason`, `source_type`, `document_id`, `chunk_id`, `block_type`. Do not remove existing fields or break existing successful responses.

### D2 — Self-host no-key is an expected runtime state

`CHAINLENS_API_KEY=""` is normal for self-host Phase 1. `_call_chainlens()` must not raise an uncaught `ConfigurationError` for this path. Deep research returns typed `engine_unavailable` with setup guidance; all other Nowing capabilities continue to run.

Do not add a fake local ChainLens, do not ship a closed-source engine binary, and do not point self-host directly at ChainLens. Phase 2 metered self-host access is Story 9.5 and must go through Nowing Cloud API.

### D3 — Bounded hybrid fallback uses Nowing KB, not open-web synthesis

Fallback is allowed only when the shared access layer has an authorized `CapabilityContext` with `workspace_id` and `AsyncSession`. It searches the caller's workspace KB using existing hybrid retrieval. It is not a replacement for open-web deep research and must be labelled as degraded workspace-KB evidence.

Fallback bounds:

- `top_k` fixed at a small constant, max 5 documents.
- Per-document chunks follow existing retriever bounds; do not full-scan all chunks.
- No LLM synthesis is required in this story. A deterministic answer may summarize that the engine is unavailable and list relevant KB passages; claims must come only from cited chunks.
- If no context is available, return `engine_unavailable` without fallback.
- If hybrid retrieval itself returns no hits, return `engine_unavailable` without fabricated citations.

### D4 — Add a minimal context seam in the shared doors

Do not use globals or request payload fields to infer tenant context. Implement a small explicit execution seam in the capability core so REST sync, REST async and agent calls can pass `CapabilityContext` to context-aware executors while preserving existing `executor(payload)` behavior for all other capabilities.

One acceptable shape: add a context-aware invocation helper in `app/capabilities/core/` and let only `chainlens.research` opt into it. REST and agent doors must both use the same helper. The seam must not require adding `workspace_id` or any Nowing tenancy concept to the ChainLens HTTP contract.

### D5 — Parse engine degradation events before heuristics

Parser priority is explicit engine event first, fallback heuristic second:

1. Parse data-only JSON frames where `type` is inside the payload.
2. Parse `partial` with `state`, `reason`, optional partial answer/sources.
3. Parse `insufficientEvidence` with `partial`, `reason`, optional source/citation metadata.
4. Parse `heartbeat` and record last-alive state so "engine alive but not terminal yet" is not classified as "no evidence".
5. Preserve forgiving behavior for unknown event types; unknown events are ignored with debug logging, not raised.
6. Keep defensive `event: error` handling if desired, but tests for 9.1a must use the verified data-only typed frames for partial/insufficientEvidence/heartbeat.

### D6 — Citations must stay real and typed

ChainLens web citations remain web `Source` entries in engine order. KB fallback citations must carry real Nowing locators (`document_id`, `chunk_id`) and must not fabricate web URLs. If an internal locator is placed in `Source.url`, it must be clearly internal, such as `nowing://documents/{document_id}/chunks/{chunk_id}`, with additive structured fields for clients that can render chunk citations.

Agent/subagent prompts must be updated so `engine_unavailable` and degraded `partial` are reported as partial/error-like states, not as success. Existing rule "never invent titles, URLs, or claims" stays binding.

### D7 — Failure taxonomy is stable and observable

Use stable reason strings for logs/metrics/output:

| Upstream/fallback condition | Reason |
|---|---|
| Missing API key | `not_configured` |
| Request timeout | `timeout` |
| DNS/connect/request error | `unreachable` |
| HTTP 401/403 | `auth_failed` |
| HTTP 429 | `rate_limited` |
| HTTP 5xx or typed upstream error | `upstream_error` |
| Explicit insufficient evidence | `insufficient_evidence` |
| Explicit partial | `partial` |
| Stream ended without terminal | `stream_incomplete` |
| KB fallback returned hits | `fallback_kb_hits` |
| KB fallback returned none | `fallback_kb_empty` |
| KB fallback failed | `fallback_kb_error` |

Observability must include fallback/degradation rate for SM-11c and a separate coverage counter for blocked URL/citation evidence when partial/insufficientEvidence payload permits. Metric labels must not contain raw query text, URL, API key, answer text, user id or workspace name.

### D8 — REST, agent, async and MCP doors must agree

The same typed output contract applies across:

- REST sync `POST /workspaces/{id}/scrapers/chainlens/research`;
- REST async `POST .../chainlens/research?mode=async` and stored `runs.output_text`;
- agent tool `chainlens_research`;
- MCP `nowing_chainlens_research`, because it goes through REST `run_scraper()`.

Async transport remains Story 9.3's domain. 9.1a must not build a new job table, new progress endpoint, Redis-backed bus, notification persistence or deliverable persistence.

### D9 — Security and tenant isolation are part of acceptance

Fallback search must use the `workspace_id` authorized by `check_workspace_access()` and passed through `CapabilityContext`. Never trust workspace information from `ResearchInput`, `system_instructions`, ChainLens payload, or agent text. Do not send `workspace_id`, user id, tenant metadata, API key or KB contents to ChainLens beyond the existing request fields.

No degraded output may leak whether another workspace has matching KB content. Logs and metrics use low-cardinality reasons only.

## Acceptance Criteria

1. **Self-host without ChainLens is honest and non-breaking** (FR-38, D1, D2)
   - **Given** `CHAINLENS_API_KEY` is empty,
   - **When** REST sync, REST async, agent tool or MCP calls `chainlens.research`,
   - **Then** the call does not raise an uncaught `ConfigurationError`, does not return HTTP 500 for the no-key path, and returns typed output with `status="engine_unavailable"` unless authorized KB fallback provides citable evidence,
   - **And** `next_action` explains that hosted deep research is unavailable/configuration-gated,
   - **And** all other Nowing capabilities remain unaffected.

2. **Timeout, unreachable and upstream failures degrade instead of hard-failing** (FR-38, D1, D3, D7)
   - **Given** ChainLens times out, cannot be reached, returns 5xx, emits typed upstream error, rejects auth, or rate-limits,
   - **When** the caller has an authorized `CapabilityContext`,
   - **Then** Nowing attempts bounded hybrid KB fallback,
   - **And** returns `partial` with KB citations when fallback has evidence,
   - **And** returns `engine_unavailable` with no fabricated answer/citation when fallback has no evidence,
   - **And** the output carries a stable `degradation_reason`.

3. **Fallback is tenant-safe and bounded** (D3, D4, D9)
   - **Given** two workspaces contain different indexed documents,
   - **When** ChainLens is unavailable for a caller authorized only to workspace A,
   - **Then** fallback search can return only documents/chunks from workspace A,
   - **And** query, candidate pool and output size are bounded by explicit constants,
   - **And** no workspace or user identifiers are sent to ChainLens.

4. **Citations are preserved and never invented** (FR-24 carryover, FR-38, D6)
   - **Given** ChainLens returns sources in a complete or partial response,
   - **When** Nowing parses the stream,
   - **Then** source order and citation-bearing answer text are preserved.
   - **Given** fallback uses Nowing hybrid search,
   - **When** output is built,
   - **Then** every fallback source has a real `document_id` and `chunk_id`, internal sources are clearly labelled as KB evidence, and no external URL/title is fabricated.

5. **Explicit partial and insufficientEvidence events drive state** (FR-38, D5)
   - **Given** ChainLens emits data-only frames such as `{"type":"partial","state":"insufficient_evidence","reason":"..."}` or `{"type":"insufficientEvidence","partial":...,"reason":"..."}`,
   - **When** `_parse_sse()` runs,
   - **Then** Nowing maps the explicit event into `partial` or `insufficient_evidence`, preserves `reason`, preserves any partial evidence/citations,
   - **And** the old no-answer/no-sources heuristic is not the primary source of truth for insufficient evidence.

6. **Heartbeat is parsed as liveness, not progress scope creep** (FR-38, D5, non-goal 9.3)
   - **Given** ChainLens emits `{"type":"heartbeat"}` before a terminal event,
   - **When** parsing the stream,
   - **Then** Nowing records that the engine was alive and avoids classifying the run as insufficient evidence solely because no answer was seen yet,
   - **And** 9.1a does not map full phase progress to UI; that work remains Story 9.3.

7. **REST sync and async doors store the same typed degradation** (AD-17, D8)
   - **Given** REST sync receives degraded output,
   - **When** the response is returned,
   - **Then** the body has the typed degraded status and `X-Run-Id` points to a run whose serialized output contains the same status.
   - **Given** REST async receives degraded output,
   - **When** the background run finalizes,
   - **Then** `/runs/{id}` stores the same typed output and `/runs/{id}/events` terminates cleanly; no new async route, job table or Zero publication is created.

8. **Agent and MCP doors do not mask degraded states** (D6, D8)
   - **Given** the agent tool or `nowing_chainlens_research` receives `engine_unavailable`, `partial`, `timeout` or `insufficient_evidence`,
   - **When** it renders or maps output,
   - **Then** the result is reported as partial/error-like per subagent contract, includes `next_step`, and does not claim success.

9. **Observability proves degradation without leaking secrets** (SM-11c, AD-19, D7, D9)
   - **Given** any degraded path runs,
   - **When** logs/metrics are emitted,
   - **Then** counters include stable reason, final status, fallback attempted/used, and fallback hit count,
   - **And** partial/insufficientEvidence payloads that include blocked URL/citation metadata increment coverage counters using `BlockType` values where available,
   - **And** labels exclude query text, URLs, answer text, API keys, user ids and workspace names.

10. **Billing does not charge fake no-content success** (FR-38, AD-8 carryover)
    - **Given** output has `status="engine_unavailable"` and no answer/sources,
    - **When** `charge_capability()` runs,
    - **Then** `ResearchOutput.billable_units == 0` and no fake ChainLens query charge is created.
    - **Given** degraded `partial` returns citable KB evidence,
    - **Then** this story does not introduce new wallet debit semantics beyond existing capability billing; Story 9.2 owns real `deep_research` cost metering.

11. **Public-repo gate evidence is reproducible** (D5, FR-38)
    - **Given** reviewers run the targeted suite with ChainLens unconfigured,
    - **When** they inspect evidence for Story 9.1a,
    - **Then** it shows self-host no-key behavior, timeout/degrade behavior, parser partial/insufficientEvidence/heartbeat behavior, REST/agent consistency, no fabricated citations, and no secret-bearing logs,
    - **And** broad public docs positioning remains Story 9.4 while the minimal operator-facing no-key behavior is documented where this story touches config/self-host surfaces.

## Tasks / Subtasks

- [ ] **T1 — Extend research schemas for honest degraded state** (AC 1, 2, 4, 5, 8, 10)
  - [ ] Add `engine_unavailable` to `ResearchOutput.status`.
  - [ ] Add minimal additive fields for degradation/engine reason and KB citation locators.
  - [ ] Preserve backward-compatible fields for complete ChainLens success.
  - [ ] Keep no-answer/no-source `billable_units == 0`.

- [ ] **T2 — Add shared context-aware capability invocation seam** (AC 2, 3, 7, 8)
  - [ ] Implement one shared helper in capability core so REST sync, REST async and agent doors can pass `CapabilityContext`.
  - [ ] Preserve existing `executor(payload)` behavior for all non-ChainLens capabilities.
  - [ ] Use the same helper in `access/rest.py` and `access/agent.py`.
  - [ ] Do not add tenancy fields to `ResearchInput` or ChainLens HTTP request.

- [ ] **T3 — Implement bounded KB fallback for ChainLens failures** (AC 1, 2, 3, 4, 10)
  - [ ] Detect `not_configured`, timeout, unreachable, auth, rate-limit, upstream error and stream-incomplete cases.
  - [ ] When context exists, call existing hybrid retrieval with `workspace_id` from `CapabilityContext`, `SearchScope()` and `top_k <= 5`.
  - [ ] Map hits to degraded `ResearchOutput` with real `document_id`/`chunk_id` citation locators.
  - [ ] Return `engine_unavailable` without fallback when context is absent or fallback has no hits.
  - [ ] Do not run LLM synthesis or open-web crawling in fallback.

- [ ] **T4 — Parse ChainLens partial, insufficientEvidence and heartbeat events** (AC 5, 6, 9)
  - [ ] Parse verified data-only typed JSON frames.
  - [ ] Preserve explicit engine `reason`, partial content and citations.
  - [ ] Track heartbeat/liveness internally and use it to avoid the old insufficient-evidence heuristic.
  - [ ] Keep unknown event types forgiving.
  - [ ] Leave full progress-to-UI mapping for Story 9.3.

- [ ] **T5 — Keep REST, async, agent and MCP behavior consistent** (AC 1, 7, 8)
  - [ ] REST sync returns typed degraded output and records a run.
  - [ ] REST async stores the same typed output in `runs.output_text` and terminates the existing run event stream cleanly.
  - [ ] Agent tool returns degraded dict/preview instead of raising for expected engine-unavailable cases.
  - [ ] MCP inherits REST output via `run_scraper()`; update rendering only if needed to avoid masking status.
  - [ ] Update ChainLens subagent status mapping for `engine_unavailable` and degraded `partial`.

- [ ] **T6 — Observability and public-repo gate evidence** (AC 9, 11)
  - [ ] Add low-cardinality metrics/logs for degradation reason, final status, fallback attempted/used and fallback hit count.
  - [ ] Add blocked URL/citation coverage counters using `BlockType` when partial/insufficientEvidence payloads include enough metadata.
  - [ ] Verify logs do not include raw query text, URLs, API keys, answer text, user ids or workspace names.
  - [ ] Produce implementation evidence under `_bmad-output/implementation-artifacts/evidence/` for the public-repo gate.

- [ ] **T7 — Minimal self-host/operator documentation** (AC 1, 11)
  - [ ] Document in `nowing_backend/.env.example` and/or `docker/.env.example` that empty `CHAINLENS_API_KEY` is supported and yields `engine_unavailable`.
  - [ ] Do not write broad Nowing/ChainLens marketing or README positioning here; Story 9.4 owns that.
  - [ ] Do not instruct self-hosters to run ChainLens locally.

- [ ] **T8 — Deterministic tests** (AC 1-11)
  - [ ] Add parser unit tests for `partial`, `insufficientEvidence`, `heartbeat`, unknown event, and stream-incomplete cases.
  - [ ] Add executor/fallback unit tests for no key, timeout, unreachable, 401/403, 429 and 5xx.
  - [ ] Add tenant-negative fallback test with two workspaces.
  - [ ] Add REST sync and async tests for typed degraded output and stored run output.
  - [ ] Add agent-door test that expected degradation returns output rather than raising.
  - [ ] Add MCP or `run_scraper()` rendering test if status is currently hidden.
  - [ ] Add billing test for `engine_unavailable` no-content `billable_units == 0`.
  - [ ] Add observability tests with redaction assertions.

## Testing Requirements

### Test Matrix

| Case | Door | Expected invariant |
|---|---|---|
| Complete ChainLens answer with sources | parser + executor | `complete`; source order and citations preserved |
| Missing `CHAINLENS_API_KEY` | REST sync, REST async, agent, MCP path | No uncaught config error; typed `engine_unavailable` or KB-backed `partial` |
| Timeout / network down | executor with fake search | Fallback attempted where context exists; no fake complete |
| HTTP 401/403/429/5xx | executor with fake response | Stable reason; typed degradation |
| Explicit `partial` event | parser | `partial`; reason and partial citations preserved |
| Explicit `insufficientEvidence` event | parser | `insufficient_evidence` or degraded `partial` per payload; reason preserved; no heuristic override |
| Heartbeat-only then no terminal | parser | Liveness recorded; not misclassified as insufficient evidence |
| Unknown event type | parser | Ignored without raising |
| KB fallback hits | fallback mapper | `partial`; real `document_id`/`chunk_id`; no fabricated web URL |
| KB fallback empty | fallback mapper | `engine_unavailable`; no sources; `billable_units == 0` |
| Two-workspace fallback | fallback integration/unit | Only authorized workspace chunks appear |
| REST async degraded run | access/rest | 202 first; final run stores typed degraded output; SSE closes on existing `run.finished` |
| Agent degraded output | access/agent + subagent prompt | Tool returns partial/error-like contract with `next_step` |
| Logs/metrics | observability | Reason/status/fallback counters present; secrets/content absent |

### Suggested Commands

Run focused backend tests first, then relevant regression slices:

```bash
cd nowing_backend
uv run --active python -m pytest tests/unit/capabilities/chainlens/research tests/unit/capabilities/access/test_rest_router.py tests/unit/capabilities/access/test_agent_tools.py -q
uv run --active python -m pytest tests/unit/capabilities/test_billing.py tests/unit/utils/test_crawl_classifier.py -q
```

If implementation adds DB-backed fallback tests, run the repo's established integration target for those tests with the normal test database configuration. Do not require live ChainLens or network access; all engine behavior must be mocked/faked deterministically.

## Project Structure / File Ownership

Likely touch points; verify current code before editing:

- `nowing_backend/app/capabilities/chainlens/research/schemas.py` — `ResearchOutput` status and citation/degradation fields.
- `nowing_backend/app/capabilities/chainlens/research/executor.py` — parser, upstream failure taxonomy, fallback orchestration.
- `nowing_backend/app/capabilities/chainlens/research/definition.py` — register ChainLens with any context-aware execution hook.
- `nowing_backend/app/capabilities/core/types.py` — minimal context-aware executor contract/helper if chosen.
- `nowing_backend/app/capabilities/core/access/rest.py` — pass `CapabilityContext` consistently in sync/async paths.
- `nowing_backend/app/capabilities/core/access/agent.py` — pass same context and avoid raising for expected degraded ChainLens output.
- `nowing_backend/app/agents/chat/multi_agent_chat/shared/retrieval/hybrid_search.py` — reuse only; do not duplicate hybrid search SQL.
- `nowing_backend/app/agents/chat/multi_agent_chat/subagents/builtins/chainlens/system_prompt.md` — map `engine_unavailable` and degraded `partial` honestly.
- `nowing_mcp/mcp_server/features/scrapers/platforms/chainlens.py` and shared scraper renderer — only if MCP output hides degraded status.
- `nowing_backend/app/observability/metrics.py` — low-cardinality counters/log helpers.
- `nowing_backend/.env.example`, `docker/.env.example` — minimal operator note for empty ChainLens key behavior.
- `nowing_backend/tests/unit/capabilities/chainlens/research/` — parser/schema/executor tests.
- `nowing_backend/tests/unit/capabilities/access/` — REST/agent door consistency tests.
- `nowing_backend/tests/unit/capabilities/test_billing.py` — no-content degraded billing invariant.
- `nowing_backend/tests/unit/utils/test_crawl_classifier.py` — reuse `BlockType` vocabulary; extend only if event payload mapping needs it.

Do not move `app/capabilities/chainlens/` out of capabilities; AD-15 says governance changed, code layout stays to avoid churn.

## Dependencies / Non-Goals

Dependencies:

- Existing `CapabilityContext(session, workspace_id)` in shared access paths.
- Existing Nowing hybrid KB retrieval and chunk citation model.
- Existing REST async run/event infrastructure from AD-17.
- Existing `BlockType` taxonomy for blocked evidence counters where payload permits.

Non-goals:

- Story 9.1b: full ChainLens contract regression guard, golden fixtures, PRD/AD-15 doc correction for `event:` vs data-only frames, request-shape guard, and defensive `[DONE]` cleanup.
- Story 9.2: parse `costDollars`, introduce `usage_type="deep_research"`, wallet debit with real engine cost, or pricing/subscription decisions.
- Story 9.3: phase progress UI mapping, Redis-backed `run_event_bus`, async agent submit-and-return, notifications, deliverable persistence, or mode default `quality` to `balanced`.
- Story 9.4 / 8.10: broad README, docs, landing, and vision/messaging sync for Nowing vs hosted engine.
- Story 9.5: metered self-host endpoint through Nowing Cloud.
- AD-19 future escalation: Nowing crawler fallback for blocked engine URLs, cross-service callback, crawler re-fetch, CAPTCHA solving, proxy routing, or inline enrichment.
- Any new public multi-tenant surface on the ChainLens engine.
- Any production code implementation during this story-authoring task.

## Failure Taxonomy

Expected implementation behavior:

| Failure | Catch point | User/output behavior | Fallback |
|---|---|---|---|
| Missing API key | before HTTP call | `engine_unavailable`, `degradation_reason="not_configured"` | Try KB only with context |
| Timeout | executor wrapper / httpx | `partial` with KB evidence or `engine_unavailable` | Yes |
| Request error | executor wrapper / httpx | `partial` with KB evidence or `engine_unavailable` | Yes |
| 401/403 | response handling | `engine_unavailable`, `degradation_reason="auth_failed"` | Yes |
| 429 | response handling | degraded state with `degradation_reason="rate_limited"` | Yes |
| 5xx | response handling | degraded state with `degradation_reason="upstream_error"` | Yes |
| Typed SSE error | parser | degraded state with safe message | Yes |
| Explicit partial | parser | `partial`, engine reason preserved | Optional KB supplement, still degraded |
| Explicit insufficientEvidence | parser | `insufficient_evidence` or degraded `partial`, engine reason preserved | Optional KB supplement, still degraded |
| Heartbeat then no terminal | parser | not heuristic insufficient; classify stream incomplete/unavailable | Yes |
| Hybrid fallback error | fallback helper | safe degraded output plus log/metric; no secret leak | No chained fallback |

## Public-Repo Gate Evidence

The dev agent must leave reviewer-readable evidence that public repo gate 1 is satisfied:

- command list and results for targeted tests;
- sample REST sync response with no ChainLens key showing typed `engine_unavailable` or KB-backed `partial`;
- sample REST async run detail showing same typed output persisted;
- sample agent/MCP-rendered degraded response;
- parser tests proving `partial`, `insufficientEvidence` and `heartbeat` are not ignored;
- citation check proving KB fallback uses real chunk locators and no fabricated web URL;
- log/metric redaction check;
- statement that gate 2, legal attribution (`AI-2026-07-25-7`), is independent and still owned outside this story.

## References

- `_bmad-output/planning-artifacts/epics.md:415-460` — Epic 9 and Story 9.1a scope, P0 public-repo gate, degradation ACs.
- `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md:565-638` — FR-24/FR-38 and self-host Phase 1 behavior.
- `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md:639-656` — Phase 2 self-host boundary and ban on direct self-host-to-engine calls.
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md:185-203` — AD-15 external dependency, degradation, no merge, self-host boundary.
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md:283-313` — AD-17 existing async door and agent sync gap owned by Story 9.3.
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md:364-433` — AD-19 blocked URL/CAPTCHA measurement seam and non-goal for escalation.
- `_bmad-output/planning-artifacts/implementation-readiness-report-2026-07-25.md:826-850` — OQ-7 correction: Nowing parser ignores partial/insufficientEvidence/heartbeat and docs misstate SSE contract.
- `_bmad-output/planning-artifacts/oq7-answers-to-chainlens-2026-07-25.md:80-118` — verified ChainLens emits progress/evidence/heartbeat; parser defect belongs to Nowing.
- `nowing_backend/app/capabilities/chainlens/research/executor.py:46-181` — current parser and heuristic.
- `nowing_backend/app/capabilities/chainlens/research/executor.py:184-268` — current executor failure behavior and no-key raise.
- `nowing_backend/app/capabilities/chainlens/research/schemas.py:67-97` — current output status and billing behavior.
- `nowing_backend/app/capabilities/core/access/rest.py:312-423` — REST sync/async execution and run recording.
- `nowing_backend/app/capabilities/core/access/rest.py:493-557` — existing run SSE events.
- `nowing_backend/app/capabilities/core/access/agent.py:61-128` — current sync agent door.
- `nowing_backend/app/agents/chat/multi_agent_chat/shared/retrieval/hybrid_search.py:31-72` — context-required hybrid search seam.
- `nowing_backend/app/agents/chat/multi_agent_chat/shared/retrieval/models.py:15-44` — `SearchScope`, `DocumentHit`, `ChunkHit` citation locators.
- `nowing_backend/app/utils/crawl/classifier.py:18-94` — `BlockType` taxonomy.
- `nowing_mcp/mcp_server/features/scrapers/platforms/chainlens.py:68-82` — MCP ChainLens tool calls REST scraper path.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log

| Date | Version | Description | Author |
|---|---:|---|---|
| 2026-07-27 | 0.1 | Created implementation-ready Story 9.1a from verified planning artifacts and backend pipeline reality. | Codex Story Architect |
