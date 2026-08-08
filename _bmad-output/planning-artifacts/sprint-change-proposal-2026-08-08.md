# Sprint Change Proposal — ChainLens/Exa Citation Gap

**Date:** 2026-08-08
**Trigger:** Story 3.15 (Run Citations as Verifiable Sources) — post-implementation review
**Scope Classification:** Moderate
**Recommended Approach:** Direct Adjustment — 3 new stories within existing epics

---

## Section 1: Issue Summary

### Problem Statement

Story 3.15 implemented `RUN` citations for sync scraper runs (Batdongsan, Reddit, YouTube, etc.) — allowing the agent to cite scraper runs as verifiable sources with `[citation:run_<uuid>]` chips in chat. However, post-implementation review revealed **3 gaps** where citations are missing for ChainLens Research and Exa MCP search results:

**Gap A — ChainLens sync mode: `ResearchOutput.sources[]` not registered as `WEB_RESULT` citations**

When `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED=true` and mode is speed/balanced, ChainLens runs synchronously through `_capability_tool` in `agent.py`. The tool mints a `RUN` citation (pointing to the run row), but the `ResearchOutput.sources[]` array — which contains the actual web URLs that ground the answer — is **never parsed or registered as `WEB_RESULT` citations**. The `CitationSourceType.WEB_RESULT` enum value exists, `markers.py` knows how to render it, but **no code calls `registry.register(WEB_RESULT, ...)`** anywhere in `app/`.

**Gap B — ChainLens async mode (default): results + sources[] never flow back to chat with citations**

When `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED=false` (the default — State A per NFR-9), ChainLens runs asynchronously. `agent.py:203-240` returns a plain dict `{"run_id": "run_...", "status": "running"}` — no `Command`, no citation. The async runner (`async_runner.py`) finalizes the run, publishes `run.finished` to `run_event_bus`, but:
- `run.finished` event only contains metadata (`run_id`, `status`, `item_count`) — **not the output or sources[]**
- The chat streaming flow (`event_relay.py`) **does not subscribe to `run_event_bus`** — it only handles LangGraph events
- No mechanism exists to stream the research result + citations back into the chat thread when the async run completes

This means: when a user asks a deep research question, the agent says "research started" and the chat turn ends. When the research finishes (57-198s later), **the result and its sources never appear in the chat**. The user must navigate to the runs page to find it.

**Gap C — Exa MCP connector: `web_search_exa`/`web_fetch_exa` results have no citations**

Story 2.10 added Exa as an MCP search connector. `web_search_exa` and `web_fetch_exa` are MCP tools that return text directly to the agent — they do **not** go through `_capability_tool` or the citation registry. The agent receives search results but has no `[n]` labels to cite them.

### Discovery Context

Discovered during E2E verification of Story 3.15 with real Batdongsan data. After verifying RUN citations work for scraper runs, the question was raised: "What about ChainLens Research and Exa?" Code trace revealed the gaps.

### Evidence

| Gap | Evidence |
|-----|----------|
| A | `grep -rn "registry.register" app/` → only 2 call sites: `run_citation.py` (RUN) and `document.py` (KB_CHUNK). Zero for WEB_RESULT. |
| B | `grep -rn "run_event_bus\|run.finished" app/tasks/chat/streaming/` → 0 hits. Chat streaming doesn't subscribe to run events. |
| B | `agent.py:236-240` — async return is `{"run_id": ..., "status": "running", "message": ...}` — no `Command`, no `citation_registry` |
| C | `web_search_exa`/`web_fetch_exa` are MCP tools outside the capability tool adapter — no citation registration path |

---

## Section 2: Impact Analysis

### Epic Impact

| Epic | Impact | Details |
|------|--------|---------|
| **Epic 3** (Knowledge Base + Long-Term Memory) | Moderate | Story 3.15 is `done` but only covers sync RUN citations. Needs follow-up stories for WEB_RESULT and async citation delivery. |
| **Epic 9** (Deep Research đáng tin cậy) | Moderate | Stories 9.1b, 9.3 are `done` but have undocumented gaps: 9.1b preserves sources[] order but no code uses it; 9.3 built async door but didn't wire citation delivery back to chat. |
| **Epic 2** (Connectors) | Low | Story 2.10 (Exa) is `done` — MCP tools work but lack citation integration. |
| **Epic 4** (Chat & Agents) | Low | Story 4.8d (Chat quality LLM-as-judge, `ready-for-dev`) will measure "citation accuracy" — but ChainLens answers currently have 0 citations, making the metric misleading. |

### Story Impact

| Story | Status | Impact |
|-------|--------|--------|
| 3.15 (Run Citations) | `done` | No change needed — scope was explicitly sync RUN citations. Gap is follow-up work. |
| 9.1b (Contract Regression) | `done` | AC says "sources[] preserves citation order so it maps correctly to the citation UI" — but the mapping code doesn't exist. Test passes (order is preserved), but the consumer is missing. |
| 9.3 (Latency Budget + State A) | `done` | AC says "emit Notification when run.finished" — notification exists but doesn't carry citation data. The bigger gap: result + citations don't flow back to chat thread. |
| 2.10 (Exa MCP Connector) | `done` | AC says "agent receives clean, ready-to-use text from top web results" — works, but no citation labels. |
| 4.8d (Chat quality LLM-as-judge) | `ready-for-dev` | Will judge "citation accuracy" — needs ChainLens citations to exist first, otherwise metric is meaningless for deep-research tag. |

### Artifact Conflicts

#### PRD

| FR | Conflict | Action |
|----|----------|--------|
| **FR-24** | "câu trả lời tổng hợp **có trích dẫn**" + "sources[] giữ nguyên thứ tự trích dẫn để map về citation UI" — **VIOLATED** for ChainLens. Sources[] order is preserved in the parser but never mapped to citation UI. | Add AC to new story: "ChainLens research answer renders with URL citation chips for each source in sources[]" |
| **FR-38** | "không bịa citation" — OK, no fabrication, but also no citation when should cite. | No change needed — existing AC still holds. |
| **SM-3** | "Tỷ lệ chat message có citation ≥ X%" — degraded because ChainLens answers (a significant chat category) have 0 citations. | No PRD change — SM-3 target unchanged, but new stories needed to achieve it. |

#### Architecture

| AD | Conflict | Action |
|----|----------|--------|
| **AD-15** | "ChainLens sở hữu citations/quality" — engine returns sources[] in SSE, but Nowing doesn't register them. | Add architecture note: "Nowing registers WEB_RESULT citations from ResearchOutput.sources[] after executor returns" |
| **AD-17** | "Async door: submit → progress → notify → deliverable" — notify exists but doesn't carry citations; deliverable doesn't flow back to chat. | Add architecture note for async citation delivery mechanism |
| **AD-19** | "Engine returns null on 403 → loses full-text" — citation coverage gate. | No change — gate still valid, measurement still needed. |

#### UI/UX

| Component | Conflict | Action |
|-----------|----------|--------|
| `UrlCitation` component | **Already exists** — renders URL chip with domain + favicon, click opens external link. | No new component needed — just wire backend to emit `[citation:url]` markers. |
| `citation-parser.ts` | **Already supports** `kind: "url"` — parses `[citation:https://...]` | No change needed. |
| `citation-panel.atom.ts` | Only `chunk` + `run` kinds — no URL panel. | **No change needed** — URL chips open external links, not a panel. This is correct UX. |
| Previous WEB_RESULT hover cards | **Removed** — `citation-metadata-context.tsx` says "removed with multi-engine web_search tool" | No restore needed — `UrlCitation` component is the replacement and already works. |

### Technical Impact

| Area | Impact |
|------|--------|
| **Backend — citation registry** | Need `register_web_citations()` helper that takes `ResearchOutput.sources[]` and registers each URL as `WEB_RESULT` in the registry |
| **Backend — sync path** | `agent.py` sync ChainLens path (after executor returns) needs to call `register_web_citations()` before returning `Command` |
| **Backend — async path** | Need mechanism to deliver async research result + citations back to chat thread. Options: (a) chat streaming subscribes to `run_event_bus`, (b) notification carries run_id → frontend fetches result + renders citations, (c) agent "resume" turn when run completes |
| **Backend — Exa MCP** | MCP tool results need citation registration. Either hook into MCP tool wrapper or add post-processing in the tool adapter |
| **Frontend** | No new components needed — `UrlCitation` chip already renders URL citations. May need frontend handling for async research result delivery (depends on backend approach). |
| **Tests** | Need unit tests for `register_web_citations()`, integration test for sync ChainLens citation flow, E2E test for async delivery |

---

## Section 3: Recommended Approach

### Selected: Direct Adjustment — 3 new stories within existing epics

### Rationale

1. **No rollback needed** — Story 3.15 is correct for its scoped purpose (sync RUN citations). The gap is uncovered scope, not broken work.
2. **No MVP scope reduction** — FR-24 is already in MVP scope and marked `[DONE]`. The gap is implementation incompleteness, not scope creep.
3. **Existing infrastructure reusable** — `UrlCitation` component, `WEB_RESULT` enum, `markers.py` rendering, `citation-parser.ts` URL parsing all already exist. The work is wiring, not building.
4. **3 stories fit naturally into existing epics** — Epic 3 (citations), Epic 9 (deep research), Epic 2 (connectors).

### Effort Estimate

| Story | Effort | Risk |
|-------|--------|------|
| 3.17 — WEB_RESULT citations for sync ChainLens | Low-Medium | Low — same path as RUN citations, `UrlCitation` already exists |
| 9.7 — Async research result + citation delivery to chat | **High** | Medium-High — changes streaming flow, needs design decision on delivery mechanism |
| 2.11 — Exa MCP citation registration | Low | Low — hook into existing MCP tool wrapper |

### Timeline Impact

- Stories 3.17 + 2.11 can be done in parallel, ~1-2 days each
- Story 9.7 is the hard one — needs architecture decision on async delivery mechanism, ~3-5 days
- Total: ~1 week with 1 developer
- Does not block any `ready-for-dev` stories (3.16, 4.7, 4.8d can proceed in parallel)

### Alternatives Considered

| Option | Verdict | Reason |
|--------|---------|--------|
| **Rollback 3.15** | Not viable | 3.15 works correctly for its scope. Rollback would break verified RUN citations. |
| **Defer to post-MVP** | Not viable | FR-24 is in MVP scope and marked DONE. Gap is implementation incompleteness on a shipped FR. |
| **Single mega-story** | Not viable | 3 gaps have different complexity levels and epic affiliations. Separate stories allow independent prioritization. |
| **Modify 3.15 scope** | Not recommended | 3.15 is `done` with passing tests. Reopening it mixes sync RUN work (verified) with new WEB_RESULT/async work (unverified). Clean separation is safer. |

---

## Section 4: Detailed Change Proposals

### Proposal 1: New Story 3.17 — WEB_RESULT Citations for ChainLens Sources

**Epic:** 3 — Knowledge Base + Long-Term Memory
**Priority:** HIGH
**FRs:** FR-24, FR-13
**Dependencies:** Story 3.15 (done)

#### Story

As a researcher, I want ChainLens Research answer to cite its web sources with clickable URL chips, So that I can verify claims by opening the original web pages.

#### Acceptance Criteria

1. **Given** a sync ChainLens research call completes with `ResearchOutput.sources[]`, **When** the capability tool finalizes, **Then** each source URL is registered as a `WEB_RESULT` citation in the `CitationRegistry` with its title and URL.
2. **Given** the registry contains `WEB_RESULT` entries, **When** `normalize_citations()` resolves `[n]` ordinals, **Then** they are rewritten to `[citation:https://...]` markers.
3. **Given** an assistant message contains `[citation:https://...]`, **When** rendered in chat, **Then** the `UrlCitation` chip displays with domain name + favicon, and clicking opens the URL in a new tab.
4. **Given** a ChainLens answer with 5 sources, **When** the model emits `[1][3][5]` labels, **Then** exactly 3 URL chips render, each linking to the correct source URL.
5. **And** existing `RUN` and `KB_CHUNK` citations continue to work unchanged.

#### Technical Notes

- Add `register_web_citations(registry, sources: list[Source]) -> None` helper in `app/agents/chat/multi_agent_chat/shared/citations/` (or `app/capabilities/core/access/`)
- Call it in `agent.py` sync ChainLens path, after executor returns, before `attach_run_citation()`
- `WEB_RESULT` marker in `markers.py` already returns the URL string — verify it outputs `https://...` format
- Frontend: no changes needed — `citation-parser.ts` already handles `kind: "url"`, `UrlCitation` component already renders
- The `RUN` citation (pointing to the run row) and `WEB_RESULT` citations (pointing to URLs) coexist — the run citation shows "Source" chip opening run panel, URL citations show domain chips opening external links

#### Tasks

1. Backend: Create `register_web_citations()` helper
2. Backend: Wire into `agent.py` sync ChainLens path
3. Backend: Unit tests for `register_web_citations()` + integration test with mock ResearchOutput
4. Evals: Update citation parity test to include `WEB_RESULT` tokens
5. E2E: Test with real ChainLens call (sync mode) — verify URL chips render

---

### Proposal 2: New Story 9.7 — Async Research Result + Citation Delivery to Chat

**Epic:** 9 — Deep Research đáng tin cậy
**Priority:** HIGH
**FRs:** FR-24, NFR-9 State A
**Dependencies:** Story 9.3 (done), Story 3.17 (proposed)

#### Story

As a researcher, I want async ChainLens Research results to appear in my chat thread with URL citations when the run completes, So that I don't have to navigate to the runs page to see my research answer.

#### Acceptance Criteria

1. **Given** an async ChainLens research run completes successfully, **When** `run.finished` fires, **Then** the research answer + sources[] are delivered back to the originating chat thread as a new assistant message with `[citation:url]` markers.
2. **Given** the async run was initiated from a chat turn, **When** it completes, **Then** the user sees a notification in the chat thread (not just the notifications bell) with the synthesized answer and clickable URL citation chips.
3. **Given** the async run fails or degrades, **When** `run.finished` fires with `status=error`, **Then** a message appears in the chat thread explaining the failure with the `next_action` guidance.
4. **Given** the user has closed the chat tab, **When** the async run completes, **Then** the notification (existing `notifications` table) includes the run_id so the user can navigate to the result from the notification.
5. **And** the existing async door (`?mode=async` → 202 + SSE `runs/{id}/events`) continues to work unchanged for REST API callers.
6. **And** the `run.finished` event is extended to include `sources[]` (or the delivery mechanism fetches the result from DB) so citations can be minted.

#### Technical Notes — Design Decision Needed

Three approaches for delivering async results back to chat:

**Option A — Chat streaming subscribes to run_event_bus (backend)**
- `event_relay.py` subscribes to `run_event_bus` for `run_id`s started during the turn
- When `run.finished` fires, fetch `Run.output_text` from DB, parse `ResearchOutput.sources[]`, register `WEB_RESULT` citations, stream a new assistant message
- Pro: result appears in the same chat stream, seamless UX
- Con: chat streaming connection must stay open for 57-198s; if user disconnects, result is lost from chat
- Risk: changes the streaming flow's event loop

**Option B — Notification → frontend fetches result (frontend-driven)**
- `run.finished` → emit `Notification` (existing table, already in `ZERO_PUBLICATION`)
- Frontend receives notification with `run_id` → fetches run detail → renders result + citations in chat
- Pro: works even if user closed tab (notification persists), no streaming changes
- Con: result appears as a notification-driven message, not a natural chat continuation; needs frontend logic to inject into chat thread
- Risk: less seamless UX, but more robust

**Option C — Agent "resume" turn (backend)**
- When `run.finished` fires, enqueue a new agent turn that reads the run result and emits a cited answer
- Pro: agent can synthesize a natural-language answer with proper `[n]` labels
- Con: costs an extra LLM call; agent might hallucinate or rephrase
- Risk: highest complexity, but best UX

**Recommendation:** Option B — lowest risk, reuses existing notification infrastructure, works with tab closed. Frontend already has `RunDetail` component for rendering run output.

#### Tasks

1. Backend: Extend `run.finished` event (or notification payload) to include `run_id` + `thread_id` linkage
2. Backend: Wire `run.finished` → `Notification` with `run_id` + `thread_id` metadata
3. Frontend: Handle research-complete notification in chat view → fetch run detail → render answer + URL citations inline
4. Frontend: Render `UrlCitation` chips for each source in the run result
5. Backend: Tests for `run.finished` → notification wiring
6. E2E: Test async ChainLens call → notification → chat thread shows result with citations

---

### Proposal 3: New Story 2.11 — Exa MCP Search Citation Registration

**Epic:** 2 — Connectors
**Priority:** MEDIUM
**FRs:** FR-24, FR-8
**Dependencies:** Story 2.10 (done)

#### Story

As a researcher, I want Exa web search results to be citable sources in chat, So that I can trace agent claims back to the web pages Exa found.

#### Acceptance Criteria

1. **Given** the agent calls `web_search_exa` and receives results with URLs, **When** the tool returns, **Then** each result URL is registered as a `WEB_RESULT` citation in the `CitationRegistry`.
2. **Given** the agent calls `web_fetch_exa` for a specific URL, **When** the tool returns, **Then** the fetched URL is registered as a `WEB_RESULT` citation.
3. **Given** the registry contains Exa `WEB_RESULT` entries, **When** the model emits `[n]` labels referencing them, **Then** URL citation chips render in chat.
4. **And** existing MCP tool behavior (readonly, no HITL) is unchanged.

#### Technical Notes

- MCP tools (`web_search_exa`, `web_fetch_exa`) return text directly to the agent — they don't go through `_capability_tool`
- Need to hook into the MCP tool wrapper or add a post-processing step that extracts URLs from the tool result and registers them
- `web_search_exa` results contain URLs in the response text — need to parse or have the tool return structured URL metadata
- `web_fetch_exa` takes a URL as input — register that URL directly
- Alternative: have the MCP tool adapter wrap results with citation labels, similar to how `_capability_tool` wraps scraper runs

#### Tasks

1. Backend: Investigate MCP tool result format — extract URLs from `web_search_exa` results
2. Backend: Add citation registration hook in MCP tool wrapper (or post-processing)
3. Backend: Unit tests for Exa citation registration
4. E2E: Test Exa search in chat → URL chips render

---

### Proposal 4: Architecture Update — AD-15 Amendment

**Artifact:** `ARCHITECTURE-SPINE.md`, AD-15 section

#### OLD (verbatim):
> - **Ranh giới.** Nowing sở hữu: account/auth/onboarding, workspace/RBAC, memory, connectors, chat, deliverables, automations, **billing/credit/metering**, đa client, distribution. ChainLens sở hữu: deep-research pipeline (classifier → planner → researcher → writer → reflection), provider chain search/extract + failover, cost-optimized LLM routing, semantic cache, **citations/quality**. **ChainLens không có end-user auth và không có billing.**

#### NEW:
> - **Ranh giới.** Nowing sở hữu: account/auth/onboarding, workspace/RBAC, memory, connectors, chat, deliverables, automations, **billing/credit/metering**, đa client, distribution, **citation registration for web sources**. ChainLens sở hữu: deep-research pipeline (classifier → planner → researcher → writer → reflection), provider chain search/extract + failover, cost-optimized LLM routing, semantic cache, **in-engine citation generation**. **ChainLens không có end-user auth và không có billing.**
> - **Citation bridge.** ChainLens trả `sources[]` trong SSE terminal event; Nowing register mỗi URL sebagai `WEB_RESULT` citation trong `CitationRegistry` sau khi executor return. Cho sync mode, registration xảy trong `_capability_tool` path. Cho async mode, registration xảy khi result được deliver back to chat thread (Story 9.7).

**Rationale:** AD-15 currently says ChainLens owns "citations/quality" — but this is ambiguous. ChainLens generates citations *inside* the synthesized answer, but Nowing is responsible for registering them in the citation registry and rendering them as chips. The amendment clarifies the boundary.

---

### Proposal 5: Architecture Update — AD-17 Amendment

**Artifact:** `ARCHITECTURE-SPINE.md`, AD-17 section, "Three Missing Pieces"

#### OLD (piece 3, verbatim):
> 3. **Không có notify khi xong, và kết quả không thành deliverable.** `run.finished` chỉ là event trên bus — grep `Notification|notify` trong `rest.py`/`runs.py` = **0 hit**. Client đóng tab là mất. Và kết quả deep research nằm trong `runs.output_text` (TTL 30 ngày), **không** phải deliverable hạng nhất như `Report`/`Podcast`. **Rule:** State A hoàn chỉnh cần (a) emit `Notification` khi `run.finished` — bảng `notifications` đã có (`app/notifications/persistence.py`) và **đã nằm trong `ZERO_PUBLICATION`** nên realtime sẵn; (b) persist kết quả thành deliverable nếu user yêu cầu, không dựa vào TTL của `runs`.

#### NEW:
> 3. **Không có notify khi xong, và kết quả không thành deliverable.** `run.finished` chỉ là event trên bus — grep `Notification|notify` trong `rest.py`/`runs.py` = **0 hit**. Client đóng tab là mất. Và kết quả deep research nằm trong `runs.output_text` (TTL 30 ngày), **không** phải deliverable hạng nhất như `Report`/`Podcast`. **Rule:** State A hoàn chỉnh cần (a) emit `Notification` khi `run.finished` — bảng `notifications` đã có (`app/notifications/persistence.py`) và **đã nằm trong `ZERO_PUBLICATION`** nên realtime sẵn; (b) persist kết quả thành deliverable nếu user yêu cầu, không dựa vào TTL của `runs`; (c) **deliver result + WEB_RESULT citations back to originating chat thread** — notification carries `run_id` + `thread_id`, frontend fetches run detail and renders answer with URL citation chips (Story 9.7).

**Rationale:** The original AD-17 identified the missing notification + deliverable but did not mention citation delivery. Story 9.7 adds this third piece.

---

### Proposal 6: Story 4.8d Update — Citation Accuracy Baseline

**Story:** 4.8d — Chat quality benchmark with LLM-as-judge
**Section:** Acceptance Criteria

#### OLD:
> `nowing_evals run chat quality` judges each turn; reports aggregate score + per-tag breakdown; uses judge model separate from the tested model.

#### NEW:
> `nowing_evals run chat quality` judges each turn; reports aggregate score + per-tag breakdown; uses judge model separate from the tested model.
> **Citation accuracy baseline:** for `deep-research` tag, citation accuracy is measured against `WEB_RESULT` citations from ChainLens sources[] (Story 3.17 + 9.7 must land before baseline ratification for deep-research tag).

**Rationale:** Without ChainLens citations, the `deep-research` tag would have 0 citation accuracy — making the baseline meaningless. The dependency ensures stories land in the right order.

---

## Section 5: Implementation Handoff

### Scope Classification: Moderate

- 3 new stories across 3 epics
- 2 architecture amendments
- 1 existing story update
- No rollback, no MVP scope reduction
- Requires PO/DEV coordination for story sequencing

### Handoff Plan

| Role | Responsibility | Stories |
|------|---------------|---------|
| **Developer** | Implement 3.17 (WEB_RESULT citations) + 2.11 (Exa citations) | 3.17, 2.11 |
| **Developer + Architect** | Design + implement 9.7 (async delivery) — needs architecture decision on delivery mechanism (Option A/B/C) | 9.7 |
| **Product Owner** | Sequence stories: 3.17 → 9.7 (3.17 is dep); 2.11 independent; 4.8d baseline after 3.17+9.7 | Sequencing |
| **Architect** | Approve AD-15 + AD-17 amendments | Architecture |

### Sequencing

```
Phase 1 (parallel):
  3.17 — WEB_RESULT citations (sync)     2.11 — Exa MCP citations
  ─────────────────────────────          ──────────────────────
         │                                      │
         ▼                                      │
Phase 2:                                        │
  9.7 — Async delivery + citations             │
  ─────────────────────────────                │
         │                                      │
         ▼                                      ▼
Phase 3:                                        │
  4.8d — Chat quality baseline (deep-research tag)
  ──────────────────────────────────────────
```

### Success Criteria

1. **Sync ChainLens** — Chat answer from sync ChainLens research shows URL citation chips for each source in `sources[]`
2. **Async ChainLens** — When async research completes, result + URL citations appear in chat thread (via notification → frontend fetch)
3. **Exa** — `web_search_exa` results show URL citation chips in chat
4. **No regression** — Existing `RUN` and `KB_CHUNK` citations work unchanged
5. **Eval gate** — `chat/quality` deep-research tag citation accuracy > 0 (baseline measurable)

---

## Appendix: Checklist Completion Summary

| Section | Status |
|---------|--------|
| 1. Understand the Trigger and Context | [x] Done — trigger identified (3.15 post-review), problem categorized (technical limitation: uncovered scope), evidence collected (code traces) |
| 2. Epic Impact Assessment | [x] Done — Epic 3, 9, 2, 4 impacted; 3 new stories proposed; no epic obsolete |
| 3. Artifact Conflict and Impact Analysis | [x] Done — FR-24 violated, AD-15/AD-17 need amendment, UI/UX no new components needed |
| 4. Path Forward Evaluation | [x] Done — Direct Adjustment selected; rollback not viable; MVP scope unchanged |
| 5. Sprint Change Proposal Components | [x] Done — all sections complete |
| 6. Final Review and Handoff | [ ] Pending user approval |
