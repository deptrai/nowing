---
reviewer: Winston (System Architect)
date: 2026-04-25
scope: Epic 9 Phase 2 UX Overhaul — 4 stories (9-UX-1 through 9-UX-4)
project: Nowing
stepsCompleted: [1, 2, 3, 4, 5, 6]
verdict: 🟡 AMBER — ship-ready after 6 addressable gaps closed
---

# Implementation Readiness Report — Epic 9 Phase 2 UX Overhaul

**Reviewed by:** Winston, Senior System Architect
**Date:** 2026-04-25
**Scope:** 4 UX stories (9-UX-1 Live Research Lab, 9-UX-2 Crypto Report Layout, 9-UX-3 Interactive Analysis, 9-UX-4 Additional Data Sources)
**Cross-checked against:** epics.md Epic 9, Story 0.6b (shipped 2026-04-25), architecture-backend.md, product-brief-epic9-crypto-orchestra.md, PRD, chat_deepagent.py production code

---

## 🎯 Verdict

**🟡 AMBER — ready for dev after closing 6 addressable gaps.**

The 4 stories have strong vision alignment with product brief (Messari × Perplexity × Nansen target) and correctly extend the existing middleware stack. However, **three architectural assumptions are subtly wrong** and **three acceptance criteria are missing** that would cause 2-5 day debugging sessions if not addressed upfront. All gaps are closeable by amending story ACs — no architecture redesign required.

**GO decision**: after patch-6 (listed below) merged into the story files, 9-UX-1 can start Week 1.

---

## 📋 Document Inventory

| Document | Status | Notes |
|----------|--------|-------|
| PRD ([prd.md](prd.md)) | ✅ Loaded | Epic 9 in scope, no UX section |
| Product Brief ([briefs/product-brief-epic9-crypto-orchestra.md](briefs/product-brief-epic9-crypto-orchestra.md)) | ✅ Loaded | Includes Messari × Perplexity aspiration |
| Epics ([epics.md](epics.md)) | ✅ Loaded | Epic 9 has 6 sub-agents listed; no UX sub-epics yet |
| Architecture ([architecture.md](architecture.md)) | ✅ Loaded | Backend-heavy; FE component architecture section thin |
| Architecture Backend ([docs/architecture-backend.md](../../docs/architecture-backend.md)) | ✅ Loaded | Rate-limit ladder Layers 1-5 documented post-Story 0.6b |
| UX Design Specification ([ux-design-specification.md](ux-design-specification.md)) | ✅ Loaded | Pre-Phase-2, mostly onboarding flow |
| UX Handoff ([ux-crypto-orchestra-handoff.md](ux-crypto-orchestra-handoff.md)) | ✅ Loaded | OrchestraStrip v1 spec |
| Story 9-UX-1 | ✅ Loaded | 12 ACs, 16 tasks |
| Story 9-UX-2 | ✅ Loaded | 13 ACs, 16 tasks |
| Story 9-UX-3 | ✅ Loaded | 14 ACs, 15 tasks |
| Story 9-UX-4 | ✅ Loaded | 14 ACs, 14 tasks |
| Story 0.6b (shipped 2026-04-25) | ✅ Loaded | AC8-AC11 defines current state SubAgentResilienceMiddleware + synthesis mode |
| Plan file (.claude/plans/harmonic-cuddling-glacier.md) | ✅ Loaded | Sally's full UX spec |

**No duplicates. No missing docs.** Clean inventory.

---

## 🔬 Analysis — 5 Focus Areas

### 1. SSE Event Contract Completeness

✅ **Mostly complete.** 9-UX-1 AC1 adds 5 events. BUT — critical omission:

> **🔴 GAP-1**: No SSE event for **tool-call-in-progress** intermediate state. Current events are spawn → update → done/fail. For the LiveNarrationStream to show "Đang gọi DeFiLlama…" between narration bursts, we need either:
>
> - (a) Emit `orchestra-narration` with `tone: 'fetching'` BEFORE tool executes (requires sub-agent pre-hook), OR
> - (b) New event `orchestra-tool-start` + `orchestra-tool-end` so FE can render generic "Fetching…" fallback when narration text hasn't arrived.
>
> **Recommendation**: adopt (a) — narration events already in contract, just need BE to emit pre-call narration in addition to post-call narration. Update 9-UX-1 AC2 to explicitly state "Pre-tool-call narration emission is mandatory, not optional."

> **🔴 GAP-2**: `orchestra-rate-gate-wait` event (9-UX-1 AC1) isn't connected to any backend emit point. The `_GlobalRateBucket.acquire()` method in `chat_deepagent.py` is shared by main + sub-agent + KB planner via monkey-patch, but the patched function doesn't know which SSE stream to write to.
>
> **Blocker severity**: Medium. Fix: either (i) pass `stream_writer` via `contextvars.ContextVar` in Python, or (ii) emit via a shared Redis pub/sub that `stream_new_chat.py` subscribes to.
>
> **Recommendation**: Use pattern (i) — contextvar is already used in `chat_deepagent.py` (`_prl_step_start` at line 201). Pattern is proven. Add AC to 9-UX-1 T4 explicitly: "Add `contextvars.ContextVar[StreamWriter | None]` to `chat_deepagent.py`; set/reset in `stream_new_chat.py` around `agent.astream_events`."

### 2. Citation Metadata Flow

🟡 **Partial. The happy-path is solid; edge cases under-specified.**

The flow defined in 9-UX-2 AC10:
```
Sub-agent tool → dict with citation_id → aggregated citation_map → message metadata → FE
```

But **who generates citation_ids**? AC10 says "update each sub-agent system prompt to return `citation_id`". That's asking the LLM to invent unique IDs — **unreliable.** LLMs will either:
- Generate duplicate IDs across turns (collisions)
- Forget to include `citation_id` for some numbers
- Invent new IDs for the same data point in different sentences

> **🔴 GAP-3**: Citation IDs should be generated **deterministically by a post-processor**, not the LLM.
>
> **Recommendation**: Add new middleware `CitationHarvesterMiddleware` that runs AFTER each sub-agent tool, inspects the ToolMessage content for numeric values + their units, and emits a canonical citation object:
>
> ```
> citation_id = hash(f"{metric_name}:{provider}:{value}:{date}")
> ```
>
> Then the main agent's synthesis prompt references IDs via a simple lookup table: "Here are the available citation IDs and their values: [table]. When citing a value, use `[[cite:id]]value[[/cite]]`." Much more reliable than asking LLM to invent IDs.
>
> **Impact**: New AC for 9-UX-2 (AC14 — CitationHarvesterMiddleware) + dependency bump: story requires additional 2-3 days BE.

> **🟡 GAP-4**: Conflict detection ([schema.ts](../../nowing_web/components/tool-ui/citation/schema.ts) has `detectConflict()` + `CONFLICT_NUMERIC_DELTA`) is frontend-only. But whether 2 sources report the same metric happens on **backend** (CitationHarvester sees GoPlus audit=20 and CertiK audit=45).
>
> **Recommendation**: Move conflict detection to backend — `CitationHarvesterMiddleware` groups citations by `(metric_name)` and emits `conflict: {detected, variants, delta}` in the CryptoDataCitation object. Frontend just renders the variant. Keeps logic in one place.

### 3. Sub-Agent Extension Pattern Coherence

✅ **Good** — 9-UX-4 follows the Story 0.1 pattern for adding new tools. BUT:

> **🔴 GAP-5**: Both 9-UX-1 `SourceAttributionMiddleware` and 9-UX-2 `CitationHarvesterMiddleware` need to be registered in **TWO places**:
>
> 1. Main agent's `deepagent_middleware` list
> 2. Each sub-agent's `_build_gp_middleware()` list
>
> Reason: Tool execution happens INSIDE sub-agents. Main agent's `awrap_tool_call` only sees the outer `task()` invocation, not the inner `get_defillama_protocol()` calls. This is the same lesson learned in Story 0.6b where `ProviderRateLimitMiddleware` had to be registered on both main AND sub-agent middleware lists.
>
> **Recommendation**: Add explicit AC to 9-UX-1 (T2): "Register `SourceAttributionMiddleware` in BOTH main agent chain AND `_build_gp_middleware()` — verify with Playwright that sub-agent tool calls trigger SSE events, not just main orchestrator." Same for 9-UX-2 CitationHarvester.

> **🟡 GAP-6**: 9-UX-4 adds `whale_tracker` as 7th sub-agent. Several places need to match this new count:
>
> - `_COMPREHENSIVE_AGENTS` list in chat_deepagent.py (OK, AC5 covers it)
> - 9-UX-1 Research Lab Grid is "6 lanes 2×3" (AC6) — must become **dynamic grid** based on session agent count, otherwise 7-agent case breaks layout
> - `ParallelSpawnDirectiveMiddleware._COMPREHENSIVE_AGENTS` — should be feature-flag-aware
> - Test `test_comprehensive_query_triggers_parallel_spawn` expects 6 — needs update
> - Quality-gate threshold `FULL_SUITE_DURATION_HISTOGRAM.labels(agents_count="4+")` needs a 7+ bucket
>
> **Recommendation**: 9-UX-1 AC6 should say "Grid adapts to N agents (2×3 for 6, 2×4 for 7-8, 3×3 for 9)". Add 9-UX-4 AC15: "Story 9-UX-1 Research Lab must render correctly with 7 agents when `CRYPTO_ORCHESTRA_ENABLE_WHALE_TRACKER=true`."

### 4. Dependency Ordering Risk

✅ **Correctly ordered.** The dependency chain:

```
9-UX-1 (Lab + SSE events)  ──┐
                              ├──→ 9-UX-2 (Report + Citations) ──┬──→ 9-UX-3 (Interactive)
                              └──→                                │
                                                                   └──→ 9-UX-4 (Data Sources)
```

is logically sound. Parallel tracks for 9-UX-3 and 9-UX-4 after 9-UX-2 is a reasonable optimization.

**BUT**: 9-UX-3 AC7 (scenario re-synthesis) depends on `agent.aget_state(config)` from checkpointer — this works post-Story 0.6b. ✅ Verified.

**BUT**: 9-UX-4 whale_tracker changes `_COMPREHENSIVE_AGENTS` list. If 9-UX-3 is developed in parallel with 9-UX-4, scenario simulator must account for variable agent count. Currently 9-UX-3 assumes 6 agents.

> **🟡 GAP-7 (NON-BLOCKING)**: Minor race between 9-UX-3 and 9-UX-4 dev. Either:
> - Sequence: 9-UX-4 then 9-UX-3, OR
> - Add AC to 9-UX-3 that scenario re-synthesis handles N agents (not hardcoded 6).
>
> **Recommendation**: Go parallel — add 1-line AC to 9-UX-3.

### 5. Missing Acceptance Criteria

Beyond Gaps 1-6 above, the stories are reasonably complete. Additional nitpicks:

- **9-UX-1 missing**: AC for "narration language matches user's communication_language setting (vi/en)" — currently hardcoded Vietnamese in examples
- **9-UX-1 missing**: AC for "narration events batched/throttled to ≤ 5/sec/agent to avoid SSE overflow"
- **9-UX-2 missing**: AC for "graceful degradation when chart data is incomplete (empty array, null values)"
- **9-UX-2 missing**: AC for "Citation Chip v2 backward-compat with existing UrlCitation / InlineCitation so existing web-search citations don't regress"
- **9-UX-3 missing**: AC for "scenario result has its own checkpoint so user can navigate back to Base Case even after session restart"
- **9-UX-4 missing**: AC for "total token cost budget per comprehensive query (prevent runaway with all 10+ sources enabled)"

These are 🟢 LOW priority — can be added during dev-time story grooming.

---

## 📊 Readiness Matrix

| Story | Scope | AC quality | Dep safety | Tech feasibility | Overall |
|-------|-------|------------|-----------|------------------|---------|
| 9-UX-1 | Clear | 11/12 solid | ✅ | Contextvar pattern proven | 🟢 READY (after GAP-2 patch) |
| 9-UX-2 | Clear | 12/13 solid | ✅ depends 9-UX-1 | CitationHarvester needed | 🟡 NEEDS GAP-3,4 patch |
| 9-UX-3 | Clear | 13/14 solid | ✅ depends 9-UX-2 | Scenario flow sound | 🟢 READY (after GAP-7 patch) |
| 9-UX-4 | Clear | 13/14 solid | ✅ depends 9-UX-1,2 | API integration straightforward | 🟡 NEEDS GAP-6 patch |

---

## 🔴 Blocking Gaps (must close before dev starts)

| ID | Story | Gap | Fix effort |
|----|-------|-----|-----------|
| **GAP-1** | 9-UX-1 | Pre-call narration emission not explicit in AC2 | 5 min (amend AC2 copy) |
| **GAP-2** | 9-UX-1 | `orchestra-rate-gate-wait` has no BE emission path | 30 min (add AC for contextvar pattern) |
| **GAP-3** | 9-UX-2 | Citation IDs generated by LLM = unreliable | 2 hours (add CitationHarvesterMiddleware AC14, ~1 day dev) |
| **GAP-4** | 9-UX-2 | Conflict detection split FE/BE | 15 min (amend AC to move to BE) |
| **GAP-5** | 9-UX-1, 9-UX-2 | Middleware needs dual registration (main + sub-agent) | 10 min (amend T2 AC) |
| **GAP-6** | 9-UX-1, 9-UX-4 | Hard-coded 6-agent grid breaks with whale_tracker | 15 min (amend AC6 dynamic grid) |

## 🟡 Non-blocking (can address during sprint)

| ID | Story | Gap |
|----|-------|-----|
| GAP-7 | 9-UX-3 | Scenario count assumption 6 vs 7 agents |
| Minor | 9-UX-1,2,3,4 | ~6 additional ACs for edge cases listed above |

---

## 📝 Recommended Story Amendments (patch-6)

### Amend 9-UX-1 AC2 (GAP-1)

Current: "Pre-tool-call: emit narration `"Đang query {tool_domain} cho {data_type}..."`"
Replace: "Pre-tool-call emission is **mandatory**, emitted from sub-agent's tool-call middleware before `handler(request)` executes. Post-tool-call emission uses actual result data. Missing pre-call narration → story fails AC."

### Add 9-UX-1 AC13 (GAP-2)

> **AC13 — Stream writer contextvar wiring**
>
> Introduce `_stream_writer_var: contextvars.ContextVar[StreamWriter | None] = ContextVar("stream_writer", default=None)` in `chat_deepagent.py`. Set in `stream_new_chat.py` wrapping `agent.astream_events()` call. Monkey-patched `_GlobalRateBucket.acquire()` reads contextvar and emits `orchestra-rate-gate-wait` when wait ≥ 3s. Verify with E2E test: trigger rate gate wait → verify SSE event received.

### Amend 9-UX-1 T2 (GAP-5)

> **T2** (BE) — Add `SourceAttributionMiddleware` class + register in BOTH (a) main `deepagent_middleware` list AND (b) `_build_gp_middleware()` used for sub-agents. Verify via Playwright that sub-agent tool calls emit `orchestra-source-fetched` events (not just main orchestrator).

### Amend 9-UX-1 AC6 (GAP-6)

> "AgentLaneGrid renders **dynamic grid** based on session agent count: 1×N for `sm`, 2×⌈N/2⌉ for `md`, 3×⌈N/3⌉ for `lg`. Must gracefully handle 4-9 agents."

### Add 9-UX-2 AC14 (GAP-3, GAP-4)

> **AC14 — CitationHarvesterMiddleware**
>
> New middleware registered in main + sub-agent chains. Scans each ToolMessage for numeric values (regex `\$[\d.]+[KMB]?` + `\d+(\.\d+)?%` + etc.), creates canonical citation objects:
>
> ```python
> citation = CryptoDataCitation(
>     id=sha256(f"{metric}:{provider}:{value}:{yyyymmdd}"),
>     value=formatted,
>     sources=[{provider, favicon, fetchedAt, rawValue, rawUrl}],
>     conflict=detect_conflict_across_sources(...),
>     agentAttribution=current_agent,
>     confidence=min(3, source_count),
> )
> ```
>
> Aggregates into session-level `citation_map: dict[str, CryptoDataCitation]`. Synthesis prompt gets injected: "Use IDs from this table when citing: [generated table]". LLM picks existing ID, never invents. Conflict detection runs backend-side; FE just renders variant from `citation.conflict` field.

### Amend 9-UX-2 AC10 (GAP-3 simplification)

Old: "update each sub-agent system prompt to return `citation_id` + structured facts"
Replace: "update sub-agent system prompts to return structured JSON with `metric_name`, `value`, `unit`, `source`, `timestamp` for each numeric fact. Citation IDs are generated post-hoc by `CitationHarvesterMiddleware` (AC14) — LLM never generates IDs."

### Add 9-UX-3 AC15 (GAP-7)

> **AC15 — Variable agent count support**
>
> Scenario re-synthesis loads ToolMessages from all available sub-agents in checkpoint state, not a hardcoded 6. Comparison lightweight-agent pair (tokenomics + defillama) may expand to 3 agents (+ whale_tracker) when feature flag enabled — `ComparisonTable` rows render based on available data.

### Add 9-UX-4 AC15 (GAP-6)

> **AC15 — Layout compatibility**
>
> When `CRYPTO_ORCHESTRA_ENABLE_WHALE_TRACKER=true`, verify Story 9-UX-1 Research Lab renders 7 agents correctly in dynamic grid. E2E test: enable flag → send comprehensive query → assert 7 agent lanes visible.

---

## 🚨 Risks Not Flagged in Stories

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Narration token cost explosion** — narration prompts add ~5-10K tokens per query | 🟡 MED | Template-driven (deterministic, no LLM call). Story 9-UX-1 T3 confirms this. |
| **Favicon CDN failures** — if DuckDuckGo favicon proxy goes down, whole Lab looks broken | 🟡 MED | Add AC: fallback to colored-initials SVG on fetch error. Cache aggressive. |
| **TradingView Lightweight bundle conflict** — imports via `<script>` may not SSR cleanly | 🟡 MED | Always `next/dynamic({ ssr: false })`. Already in AC7. |
| **Scenario result caching** — `scenario_results` table could grow unbounded | 🟢 LOW | Add TTL cleanup job. |
| **Nansen API cost** — $150/mo Pro tier, credit burn with queries | 🟠 HIGH | Feature-flag defaults OFF (AC5 covers). Monitor credit usage in Prometheus. |
| **Mobile experience** — 6-7 agent grid very cramped on sm | 🟡 MED | Stack vertical on sm explicitly. Stories cover but needs design review. |
| **Race: scenario re-synthesis vs concurrent user chat** | 🟡 MED | Lock checkpoint for scenario API endpoint. New AC. |

---

## ✅ Strengths to Highlight

1. **Vision coherence** — all 4 stories ladder clearly to product brief's "Messari × Perplexity × Nansen" aspiration
2. **Reuse discipline** — stories explicitly call out existing components (Citation, Sheet, MarkdownText, OrchestraStrip) instead of reinventing
3. **Incremental rollout** — 2+3+2+2 week split avoids big-bang risk; each sub-epic deliverable independently
4. **Backend rate-limit foundations** — built on Story 0.6b's layers (gate, retry, synthesis mode); UX layer doesn't re-architect infra
5. **Accessibility baseline** — all stories include ARIA live, keyboard nav, chart alt-text requirements
6. **Storybook/E2E coverage expectations** stated upfront in DoD

---

## 🏁 Final Recommendation

**Proceed to dev after patch-6 merged into story files.** Estimated patch effort: **4 hours BA + 15 min architect approval**. No architecture redesign required.

**Sequencing:**
1. Patch-6 applied to stories (today/tomorrow)
2. 9-UX-1 Sprint 1 starts Monday (week 1-2)
3. 9-UX-2 + 9-UX-4 parallel tracks after 9-UX-1 done (week 3-5)
4. 9-UX-3 after 9-UX-2 (week 5-6)
5. Integration testing week 7
6. Canary week 8

**Post-implementation gates:**
- Lighthouse ≥ 90 on all 3 axes (Performance / Accessibility / Best Practices)
- Bundle delta < 250KB gzipped
- No regression in Story 0.6b completion-rate metric
- User-test (n=5 crypto-native) scores ≥ 4.2/5 on "feels premium"

**Approval:** Winston ✍️ · 2026-04-25

---

## Appendix A — Architecture Diagram (proposed post-patch)

```
User Query: "phân tích toàn diện UNI"
      ▼
┌──────────────────────────────────────────┐
│ stream_new_chat.py                       │
│ ├─ set _stream_writer_var (contextvar)   │  ← NEW (GAP-2 fix)
│ └─ agent.astream_events()                │
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│ Main Agent middleware chain              │
│ 1. ProviderRateLimitMiddleware           │ (Story 0.6b)
│ 2. SubAgentResilienceMiddleware          │ (Story 0.6b)
│ 3. SourceAttributionMiddleware ← NEW     │ (9-UX-1)
│ 4. CitationHarvesterMiddleware ← NEW     │ (9-UX-2)
│ 5. ParallelSpawnDirectiveMiddleware      │ (existing)
│ 6. ParallelismTelemetryMiddleware        │ (existing)
│ 7. [KB planner, summarization, etc.]     │
└──────────────────┬───────────────────────┘
                   ▼ emits task() × 6-7
┌──────────────────────────────────────────┐
│ Sub-agent (spawned via SubAgentMiddleware)│
│ ├── Sub-agent middleware chain            │
│ │   1. ProviderRateLimitMiddleware       │ ← shared gate
│ │   2. SourceAttributionMiddleware       │ ← NEW (GAP-5)
│ │   3. CitationHarvesterMiddleware       │ ← NEW (GAP-5)
│ │   4. NarrationEmitterMiddleware         │ ← NEW
│ │   5. [existing middlewares]            │
│ └── Calls tools (coingecko, defillama, etc.)
└──────────────────┬───────────────────────┘
                   ▼ SSE events via contextvar
┌──────────────────────────────────────────┐
│ Frontend (Jotai orchestra-atom)          │
│ ├── orchestra-narration                  │
│ ├── orchestra-source-fetched              │
│ ├── orchestra-fact-captured               │
│ ├── orchestra-model-attribution           │
│ ├── orchestra-rate-gate-wait (← GAP-2)   │
│ └── orchestra-done (existing)             │
│                                           │
│ Renders: ResearchLabPanel → report with  │
│   Citation Chip v2 from citation_map     │
└──────────────────────────────────────────┘
```

---

## Appendix B — File references

- Story files: `_bmad-output/planning-artifacts/stories/9-UX-{1,2,3,4}-*.md`
- Plan: `.claude/plans/harmonic-cuddling-glacier.md`
- Architecture: `docs/architecture-backend.md` § 4.4 Crypto Orchestra
- Contextvar pattern precedent: `nowing_backend/app/agents/new_chat/chat_deepagent.py:201` (`_prl_step_start`)
- Middleware dual-registration precedent: `_build_gp_middleware()` at `chat_deepagent.py` (ProviderRateLimitMiddleware registered in both)
- Existing conflict detection: `nowing_web/components/tool-ui/citation/schema.ts:detectConflict()`
