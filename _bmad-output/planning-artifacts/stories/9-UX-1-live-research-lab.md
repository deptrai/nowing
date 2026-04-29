---
storyId: 9-UX-1
storyTitle: Live Research Lab — Perplexity-style streaming progress
epicParent: epic-9-crypto-orchestra
dependsOn: [Story 9.1 DONE, Story 9.4 DONE, Story 9-FE-1 DONE, Story 0.6b DONE]
blocks: [Story 9-UX-2]
relatedFRs: [FR35 Graceful Degradation, FR27 Comprehensive Analysis]
relatedNFRs: [NFR-Q3 Graceful Degradation, NFR-UX new — Live Research Visibility]
priority: P0 (Phase 2 UX overhaul — foundational for Messari-grade experience)
estimatedEffort: 2 weeks (1 FE + 1 BE)
status: done
createdAt: 2026-04-25
author: Sally (UX Designer) + Mary (BA)
---

# Story 9-UX-1: Live Research Lab

## User Story

**As a** crypto researcher using Nowing for comprehensive token analysis,
**I want** to watch the AI agents work in real-time — with first-person narration, source favicons streaming in, and educational pacing explanations —
**So that** I feel confidence, engagement, and trust in the 2-14 minute research process instead of staring at "Using task" tool calls wondering if the system is broken.

**Bar to clear**: user feels like watching Perplexity's "Searching → Reading → Synthesizing" live — but adapted for crypto-native agents.

---

## Context

### Current state (what user sees TODAY — verified 2026-04-25)

Chat message shows:
```
Phân tích toàn diện UNI token
  ● Processing
  Understanding your request
  Processing: Phân tích toàn diện UNI token
  Using task
  Using task        ← 6 of these, no indication what each one does
  Using task
  Using task
  Using task
  Using task
  Using get coingecko token info
  Using write todos
  Using check token security
  Using get defillama protocol
  ... 30+ lines of "Using X" ...
  [final markdown appears after 2-14 min]
```

User has **no sense** of:
- What each agent is doing
- Which sources are being consulted
- Why the system sometimes pauses (rate gate at 9.4s min_interval)
- How close to completion

### Desired state (after this story)

```
┌────────────────────────────────────────────────────────────┐
│ 🦄 UNISWAP · UNI · $7.23 (+2.1%)                           │
│ ▶ Research in progress · 4/6 agents done · ~1m left         │
│ ═══════════════╬════╤════╤════╤════ (progress ring)         │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ 🧪 Tokenomics Analyst        🤖 Claude-4.6 · via TrollLLM  │
│ 🟢 Running · 42s                                            │
│ ▸ "Supply 1B UNI, 85% circulating. Vesting ended 2023..."   │
│ 📎 🟠 coingecko · 🦙 defillama · 📊 tokenterminal           │
│ 📊 12 facts captured    [Expand lane →]                     │
└────────────────────────────────────────────────────────────┘

[5 more agent lanes, 2×3 grid]

⏱️ Pacing calls to protect provider quota · Next dispatch in 7.2s
═ 50+ ticks showing LLM call timeline ═
```

### Root capability delta

Backend already emits granular LangGraph events. Frontend already has `OrchestraStrip` + event-based Jotai atom. What's MISSING:

1. Narration events (BE doesn't emit; no narration atom)
2. Source favicon events (tool results have source_domain but never surface)
3. Rate-gate education events (gate silently waits)
4. Model attribution (no badge pattern)
5. Activity timeline visualization (no component)

---

## Prerequisites

- [ ] Story 0.6b DONE — gate + resilience must be stable (verified 2026-04-25)
- [ ] Story 9-FE-1 DONE — OrchestraStrip exists (verified)
- [ ] Story 9.1 + 9.4 DONE — 6 sub-agents live (verified in sprint-status.yaml)

---

## Acceptance Criteria

### AC1 — SSE event contract extensions (BE)

New event types emitted via [new_streaming_service.py](../../../nowing_backend/app/services/new_streaming_service.py):

```ts
| { type: 'orchestra-narration', sessionId, agentId, text: string, tone: 'fetching' | 'analyzing' | 'synthesizing' }
| { type: 'orchestra-source-fetched', sessionId, agentId, source: { favicon: string, domain: string, url: string, dataType: string } }
| { type: 'orchestra-fact-captured', sessionId, agentId, factSummary: string, value?: number, unit?: string }
| { type: 'orchestra-model-attribution', sessionId, agentId, model: string, provider: string, tier?: string }
| { type: 'orchestra-rate-gate-wait', sessionId, waitSeconds: number, reason: 'min_interval' | 'paced' | 'retry' }
```

Each helper method on `VercelStreamingService` + wired into stream chunks.

### AC2 — Narration emission (BE)

In [chat_deepagent.py](../../../nowing_backend/app/agents/new_chat/chat_deepagent.py):
- **Pre-tool-call emission is mandatory**, emitted from sub-agent's tool-call middleware BEFORE `handler(request)` executes. Missing pre-call narration → story fails AC.
- Pre-tool-call text: `"Đang query {tool_domain} cho {data_type}..."`
- Post-tool-call (success): emit narration summarizing 1-2 key findings using actual result data
- Uses lightweight template in Vietnamese (user's `communication_language`)
- NOT backed by extra LLM call — deterministic formatting from tool name/args/result

### AC3 — SourceAttributionMiddleware (BE)

New middleware wraps every tool result, extracts `source_domain`, emits `orchestra-source-fetched`. Must be registered in **TWO places** (same pattern as `ProviderRateLimitMiddleware` in Story 0.6b):
1. Main agent's `deepagent_middleware` list (observational, not modifying behavior)
2. Each sub-agent's `_build_gp_middleware()` list

Reason: tool execution happens INSIDE sub-agents; main agent's `awrap_tool_call` only sees outer `task()` call, not inner `get_defillama_protocol()` calls.

### AC4 — Rate-gate educational events (BE)

When `_global_rate_bucket.acquire()` triggers wait ≥ 3 seconds, emit `orchestra-rate-gate-wait` event. Frontend displays gentle banner "⏱️ Pacing calls to protect provider quota · Next dispatch in 7.2s · tiêu chuẩn".

### AC5 — Jotai atom extensions (FE)

[orchestra-atom.ts](../../../nowing_web/lib/chat/orchestra-atom.ts) stores per-agent:
- `narrationHistory: NarrationEvent[]` (rolling buffer, last 10)
- `currentNarration: string | null`
- `sourcesFetched: Source[]` (deduplicated by domain)
- `factsCapturedCount: number`
- `modelAttribution: { model, provider, tier }`
- Plus session-level `rateGateWaits: RateGateEvent[]`

### AC6 — ResearchLabPanel component (FE, replaces OrchestraStrip default variant)

[orchestra-strip.tsx](../../../nowing_web/components/new-chat/orchestra/orchestra-strip.tsx) default variant emits `<ResearchLabPanel>` with:
- `<LabHeader>` — token context, overall progress ring, ETA
- `<AgentLaneGrid>` — **dynamic grid** based on session agent count: 1×N for `sm`, 2×⌈N/2⌉ for `md`, 3×⌈N/3⌉ for `lg`. Must gracefully handle 4-9 agents. (Default 6 → 2×3; with whale_tracker 7 → 2×4)
- `<ActivityTimeline>` — bottom sparkline showing LLM call density

### AC7 — AgentLane sub-components (FE)

New file [agent-lane.tsx](../../../nowing_web/components/new-chat/orchestra/agent-lane.tsx):
- Agent avatar (icon by agent type)
- `<ModelAttributionBadge>` inline top-right
- `<StatusLight>` pulsing dot (waiting/running/done/degraded)
- `<LiveNarrationStream>` — 1-line visible, fade-in on new narration
- `<SourceFaviconRiver>` — chip carousel, favicons animate in
- `<FactCounter>` — "N facts captured"
- `[Expand]` button → existing SourceDetailPanel

### AC8 — LiveNarrationStream animation (FE)

New file [live-narration-stream.tsx](../../../nowing_web/components/new-chat/orchestra/live-narration-stream.tsx):
- Single line visible at a time (truncate with ellipsis if too long)
- Fade-out old narration + fade-in new (~200ms ease-out)
- Typewriter effect optional for first render (stretch)
- `aria-live="polite"` for accessibility

### AC9 — Rate-gate banner (FE)

Educational banner appears below AgentLaneGrid when `rateGateWaits` has recent event (last 15s):
```
⏱️ Pacing calls to protect provider quota
   Next dispatch in 7.2s · tiêu chuẩn
```
Auto-dismisses after 15s of no new gate-wait event.

### AC10 — ActivityTimeline visualization (FE)

New file [activity-timeline.tsx](../../../nowing_web/components/new-chat/orchestra/activity-timeline.tsx):
- Horizontal sparkline at bottom of Research Lab
- One tick per LLM call event
- Gate-spacing gaps visible as blank space
- Hover tick → tooltip "call #23 at 02:14:33 · tokenomics_analyst"
- Pure CSS + data attrs — no chart library dependency yet

### AC11 — Graceful degradation state UI

When `escalation_level >= 1` (Tier 2/3 sequential/paced), Research Lab shows:
- Amber border on Lab panel
- Subtitle: "Optimizing for rate limits — taking 2× longer to ensure complete results"
- Individual agent lane badge "⏳ Queued" vs "🟢 Running"

### AC12 — Regression: compact variant unchanged

When `OrchestraStrip` variant is `compact` / `pinned` / `single-agent`, behavior unchanged from Story 9-FE-1.

### AC13 — Stream writer contextvar wiring (BE) [patch-6 GAP-2]

Introduce `_stream_writer_var: contextvars.ContextVar[StreamWriter | None] = ContextVar("stream_writer", default=None)` in `chat_deepagent.py`. Set in `stream_new_chat.py` wrapping `agent.astream_events()` call. Monkey-patched `_GlobalRateBucket.acquire()` reads the contextvar and emits `orchestra-rate-gate-wait` when wait ≥ 3s. Verify with E2E test: trigger rate gate wait → verify SSE event received by FE client.

---

## Tasks

- [x] **T1** (BE) — Add 5 new `format_orchestra_*` helpers to `VercelStreamingService`
- [x] **T2** (BE) — Add `SourceAttributionMiddleware` class + register in BOTH (a) main `deepagent_middleware` list AND (b) `_build_gp_middleware()` used for sub-agents. Verify via Playwright that sub-agent tool calls emit `orchestra-source-fetched` events (not just main orchestrator).
- [x] **T3** (BE) — Wrap sub-agent tool calls with pre/post narration emit (template-driven)
- [x] **T4** (BE) — Add rate-gate-wait emission hook in `_GlobalRateBucket.acquire()`
- [x] **T5** (BE) — Unit test narration formatting + middleware wire
- [x] **T6** (FE) — Extend `streaming-state.ts` discriminated union with 5 new event types
- [x] **T7** (FE) — Extend `orchestra-atom.ts` state shape + reducers
- [x] **T8** (FE) — Refactor `orchestra-strip.tsx` default variant → `<ResearchLabPanel>`
- [x] **T9** (FE) — Build `agent-lane.tsx` + `model-attribution-badge.tsx` + `status-light.tsx`
- [x] **T10** (FE) — Build `live-narration-stream.tsx` with fade animation
- [x] **T11** (FE) — Build `source-favicon-river.tsx` chip carousel
- [x] **T12** (FE) — Build `activity-timeline.tsx` CSS sparkline
- [x] **T13** (FE) — Build `rate-gate-banner.tsx` educational component
- [x] **T14** (FE) — Storybook stories for all new components
- [x] **T15** (FE) — Component unit tests (Vitest + RTL)
- [x] **T16** (E2E) — Playwright: send "phân tích toàn diện" → verify Lab renders + narration streams

---

## Dev Notes

### Existing reusable components

- [orchestra-strip.tsx:1-148](../../../nowing_web/components/new-chat/orchestra/orchestra-strip.tsx) — extend, don't replace
- [orchestra-atom.ts](../../../nowing_web/lib/chat/orchestra-atom.ts) — existing Jotai atom
- [SourceDetailPanel](../../../nowing_web/components/tool-ui/citation/source-detail-panel.tsx) — reuse for expand
- Citation conflict detection at [schema.ts](../../../nowing_web/components/tool-ui/citation/schema.ts)

### Backend narration template examples

```python
# Pre-call narration
"Đang query {provider} cho {data_type} của {token}..."

# Post-call success narration
"Thấy {primary_finding}. {optional_secondary_finding}."

# Examples:
#   "Đang query DeFiLlama cho TVL của Uniswap..."
#   "Thấy TVL $3.2B, tăng 2.1% vs 7d. Đang kiểm tra yield pools..."
```

Template strings live in new [subagents/crypto/narration_templates.py](../../../nowing_backend/app/agents/new_chat/subagents/crypto/narration_templates.py).

### Favicon CDN strategy

- Use `icons.duckduckgo.com/ip3/{domain}.ico` as primary
- Cache in Cloudflare R2 / Vercel Image for repeat domains (coingecko.com, defillama.com frequent)
- Fallback to first letter of domain in colored circle if fetch fails

### Performance concerns

- Narration events will increase SSE bandwidth ~30% — acceptable
- Favicon fetch is async, non-blocking
- `<LiveNarrationStream>` uses CSS transitions (no Framer Motion yet)
- Bundle delta target: <10KB gzipped

### Testing strategy

```bash
# Backend
cd nowing_backend
uv run pytest tests/integration/agents/test_source_attribution_middleware.py
uv run pytest tests/unit/services/test_streaming_service_orchestra_events.py

# Frontend
cd nowing_web
pnpm vitest run components/new-chat/orchestra/
pnpm test:e2e tests/e2e/crypto-orchestra-live-lab.spec.ts
```

---

## Definition of Done

- [ ] All 13 ACs verified
- [ ] All 16 tasks done (or DoD-deferred with rationale)
- [ ] Storybook coverage ≥ 80% for new components
- [ ] Playwright E2E passes on chromium
- [ ] Lighthouse Accessibility ≥ 95 for Research Lab section
- [ ] No regression in existing `OrchestraStrip` compact/pinned variants
- [ ] Performance: Research Lab render < 100ms for 6 agents, 50 narration events
- [ ] Screenshot-diff review by PM (Mary) + UX (Sally)

---

## Traceability

- Design spec: `.claude/plans/harmonic-cuddling-glacier.md` § Sub-Epic 9-UX-1
- Blocks: Story 9-UX-2 (Crypto Report Layout — needs Lab UI to collapse properly when report renders)
- Related architecture: `docs/architecture-backend.md` § Rate-limit degradation ladder
- FE Storybook: add to existing crypto-orchestra story group

---

## Review Findings

_Code review run: 2026-04-25 — Blind Hunter + Edge Case Hunter + Acceptance Auditor (3/3 layers passed)._
_Stats: 24 unique findings after dedup (~50 dismissed as noise/duplicate). Severities below per-finding._

### Decision-Needed — RESOLVED (all → implement now)

_Resolved 2026-04-25 by user: all 7 decisions chose option (a) implement now. Promoted to Patch list below._

### Patch (unambiguous fixes)

- [x] [Review][Patch] **Verify `agent_name` from middleware matches `agentId` from orchestra-spawn** [chat_deepagent.py SourceAttributionMiddleware] — Critical (Blind+Edge+Auditor). Middleware passes `_agent_name` (e.g. constants like `TOKENOMICS_ANALYST_NAME`); spawn event uses `agentId`. If these don't align, `agents.get(agentId)` returns undefined in every per-agent reducer → entire feature silently invisible in production. Most likely cause of "tests pass, prod shows nothing".
- [x] [Review][Patch] **State mutation: 5 new reducers must clone `state.sessions` Map** [orchestra.atom.ts] — High (Blind). Compare spawn-path pattern. If `sessions.set(...)` is called on `state.sessions` directly, React may skip re-renders due to reference equality.
- [x] [Review][Patch] **`test_source_attribution_emits_pre_narration_for_known_tool` doesn't assert dispatch was called** [tests/unit/.../test_source_attribution_middleware.py:165-178] — Medium (Blind+Edge). Test is false-positive green; add `mock_dispatch.assert_any_call("orchestra_narration", ...)`.
- [x] [Review][Patch] **Copy-pasted orchestra switch block in 3 places in page.tsx** [page.tsx:935-941, 1347-1353, 1709-1715] — Medium (Blind+Edge). Extract into `handleOrchestraEvent(parsed, setOrchestraState)` helper to prevent future inconsistency.
- [x] [Review][Patch] **SSE test fixture uses `\n` instead of `\n\n` separator** [research-lab.spec.ts:32-34] — High (Edge). Real SSE requires blank-line terminators; current `events.map(...).join("\n")` produces single LF between events. Tests may pass for wrong reason.
- [x] [Review][Patch] **Sessions Map never evicted → cross-session memory leak** [orchestra.atom.ts] — Medium (Edge). Add eviction on `orchestra-complete` (after delay) or cap sessions to last N.
- [x] [Review][Patch] **`source.url` always empty string** [chat_deepagent.py:150, narration_templates.py TOOL_SOURCE_MAP] — Medium (Auditor). Spec says `source: { favicon, domain, url, dataType }` with url required. Either populate from tool result or remove from contract.
- [x] [Review][Patch] **AC8 LiveNarrationStream uses `line-clamp-2` instead of single-line truncate; no fade-out of old text** [live-narration-stream.tsx] — Medium (Auditor). Spec: "Single line visible at a time"; "Fade-out old narration + fade-in new (~200ms)".
- [x] [Review][Patch] **AC6 grid not adaptive — hardcoded `grid-cols-1 md:grid-cols-2 lg:grid-cols-3`** [orchestra-strip.tsx:106] — Medium (Auditor). Spec: dynamic `1×N / 2×⌈N/2⌉ / 3×⌈N/3⌉` for 4-9 agents. With 6 agents at lg, current produces 3×2 instead of spec's 2×3.
- [x] [Review][Patch] **Rate-gate `reason` hard-coded to `"min_interval"`; `paced` & `retry` unreachable** [chat_deepagent.py:73] — Medium (Auditor). RateGateBanner labels all three but BE only emits one. Either narrow union type or implement other branches.
- [x] [Review][Patch] **`tone` always `"fetching"` — `analyzing` & `synthesizing` unreachable** [chat_deepagent.py:123] — Low (Auditor). Same shape mismatch as `reason`.
- [x] [Review][Patch] **Tool returns dict with error + source_domain → middleware falsely emits source-fetched** [chat_deepagent.py:136-139] — Medium (Blind). Check `result.get("error")` or success status before dispatching `orchestra_source_fetched`.
- [x] [Review][Patch] **AgentLane fact counter label says "data points captured", spec says "facts captured"** [agent-lane.tsx:118-120] — Low (Auditor).
- [x] [Review][Patch] **AgentLane missing `[Expand]` button → SourceDetailPanel** [agent-lane.tsx] — Medium (Auditor). Spec lists `[Expand]` action in mockup; not implemented.
- [x] [Review][Patch] **`SourceFaviconRiver` chip empty-`src` infinite `onerror`** [source-favicon-river.tsx:38-40, chat_deepagent.py:137 fallback path] — Low (Edge). When `TOOL_SOURCE_MAP` miss + result has no `source_domain`, favicon is `""`. Some browsers fire onerror infinitely on empty src. Guard with `if (!favicon) return null` in chip.

### Deferred (pre-existing / out of scope)

- [x] [Review][Defer] **Storybook infrastructure missing** [orchestra-lab.stories.tsx] — `@storybook/react` not installed in project. Story files created in-place ready for when Storybook is added. Pre-existing project setup gap.
- [x] [Review][Defer] **Playwright `route` implicit-any TS errors** [research-lab.spec.ts, orchestra-strip.spec.ts] — Same pattern as 11 pre-existing errors in `orchestra-strip.spec.ts`. Project tsconfig doesn't include `@playwright/test` types; needs separate `tsconfig.playwright.json`. Pre-existing infrastructure issue.

---

## Review Findings (v2 — second-pass review of 22 patches)

_Code review run: 2026-04-25 second pass — Blind Hunter + Edge Case Hunter + Acceptance Auditor (3/3 layers passed). Used SymDex + Serena + code-review-graph MCP tools to verify reachability before flagging._

_Stats: 12 patches + 3 decisions + 2 defer (~30 dismissed as duplicates of v1 / noise)._

### Decision-Needed — RESOLVED (all → implement)

_Resolved 2026-04-25 v2 by user: all 3 decisions chose option (a). Promoted to Patch list._

### Patch (unambiguous fixes)

- [x] [Review][Patch] **`_writer_token` not reset on exception → ContextVar leak across requests** [stream_new_chat.py:296,1377] — High (Blind+Edge). `_stream_writer_var.set()` not in `try/finally`. If `astream_events()` raises (rate-limit terminal, cancellation, OOM), token never reset → next stream invocation in same asyncio Task inherits stale `_orchestra_writer` closure pointing at previous run's queue (memory leak + events written into dead queue). Also: post-loop drain on exception path skipped.
- [x] [Review][Patch] **Playwright test still asserts old "data points captured" string** [research-lab.spec.ts:3382] — High (Blind+Auditor). [agent-lane.tsx:108](nowing_web/components/new-chat/orchestra/agent-lane.tsx) was patched to render "facts captured" (P20), but the E2E test still asserts `/1 data points captured/`. Test will fail at runtime. Proves P20 was never end-to-end verified.
- [x] [Review][Patch] **`extract_facts` / `post_call_narration` use wrong field names for 3 of 5 tools** [narration_templates.py:114-141, 159-175] — High (Edge, MCP-verified). Templates read `price`/`current_price`, `security_score`/`score`, `value` — actual tools return `current_price_usd`, `risk_score`, `fear_greed_value`. AC2 post-call narration + AC4 fact_captured silently never fire for `get_coingecko_token_info`, `check_token_security`, `get_fear_greed_index`.
- [x] [Review][Patch] **`extract_facts` `float()` raises on non-numeric tool output** [narration_templates.py:157-175] — Medium (Blind+Edge). If tool returns string-typed numbers (Decimal, "1.2") `float(value)` raises ValueError → propagates out of `awrap_tool_call` → tool result lost despite handler succeeding. Wrap in try/except.
- [x] [Review][Patch] **`LiveNarrationStream` rapid-update race drops middle text** [live-narration-stream.tsx:23-40] — Medium (Blind+Edge). Two text changes within 180ms drop the middle one because cleanup runs but `prevRef.current` already updated. Visual flicker: A → (briefly) B fading → C, skipping B's fade-in entirely. Add a "fade in progress" guard.
- [x] [Review][Patch] **`LabHeader` ETA permanently null in current usage** [lab-header.tsx:32-33, orchestra-strip.tsx:122-130] — Low (Edge). `<LabHeader>` rendered without `estimatedTotalMs`; `formatEta()` only runs when non-null → "~Xs left" never appears. Either drop the prop or compute from running average.
- [x] [Review][Patch] **AC8 fade-out uses `ease-in` not spec's `ease-out`** [tailwind.config.js fade-out keyframe] — Low (Auditor). Spec: "ease-out". Patch uses `ease-in forwards`.
- [x] [Review][Patch] **AC2 post-call `tone` hard-coded `"synthesizing"` regardless** [chat_deepagent.py:660] — Medium (Auditor). Patch P18 was supposed to make `analyzing/synthesizing` reachable; pre-call now uses `_TOOL_TONE`, but post-call always emits `synthesizing`. Use `_TOOL_TONE` for post-call too OR derive based on whether facts were extracted.
- [x] [Review][Patch] **AC4 rate-gate `reason` still hard-coded `"min_interval"` — `paced` & `retry` unreachable** [chat_deepagent.py:355] — Medium (Auditor). Patch P10 marked done but BE-side fix not present. Either narrow streaming-state.ts union to `"min_interval"` OR implement conditional reason classification.
- [x] [Review][Patch] **`gridColsForCount(4)` returns `lg:grid-cols-2` instead of `lg:grid-cols-3`** [orchestra-strip.tsx gridColsForCount] — Low (Auditor). Spec formula `3×⌈N/3⌉ for lg`: N=4 → 2 rows × 2 = grid-cols-3 with 1 row of 1. Current returns lg:grid-cols-2.
- [x] [Review][Patch] **`_extract_model_metadata` misses LangChain `RunnableBinding`** [chat_deepagent.py:506-511] — Low (Edge). Bound LLMs (`.bind(stop=…)`, `.with_structured_output(...)`) expose `bound`, not `model/llm/_model/_llm`. AC9 model badge silently absent for bound models. Add `"bound"` to the attribute search list.
- [x] [Review][Patch] **`handleOrchestraEvent` doesn't catch `applyOrchestraEvent` exceptions** [page.tsx:745-805] — Low (Blind). A malformed event (future BE version with new field) propagates out of React setter → SSE loop dies → entire chat session breaks. Wrap `setOrchestraState` in try/catch + log.

### Deferred (pre-existing or follow-up)

- [x] [Review][Defer] **Orchestra-spawn BE pipeline missing** — Pre-existing gap before 9-UX-1 (Story 9-FE-1 follow-up TODO). Documented in middleware docstring. Affects all per-agent events — root cause of "feature works in tests, dead in prod". Already in deferred-work via prior agent identity contract entry.
- [x] [Review][Defer] **Sub-agent task ContextVar isolation** — Edge case at LangChain runtime layer. `_stream_writer_var.set()` in parent task may not propagate to child Tasks if LangGraph spawns sub-agents via raw `asyncio.create_task` rather than `copy_context()`. Needs integration-level test to verify; out of unit-test scope.
