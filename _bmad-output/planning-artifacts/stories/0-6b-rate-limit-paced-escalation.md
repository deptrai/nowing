---
storyId: 0.6b
storyTitle: Tier 3 Paced Sequential Escalation (rate-limit guaranteed completion)
epicParent: epic-00-crypto-foundation
dependsOn: [Story 0.6 DONE]
blocks: []
relatedFRs: [FR35 Graceful Degradation]
relatedNFRs: [NFR-Q3 Graceful Degradation > 98%, NFR-CS3 API Rate Awareness]
priority: P1 (scope-in follow-up to 0.6 — discovered during canary-prep E2E)
estimatedEffort: 1-2 hours
status: in-progress
createdAt: 2026-04-24
author: Dev (session-driven follow-up)
---

# Story 0.6b: Tier 3 Paced Sequential Escalation

## User Story

**As a** user running comprehensive crypto queries on a provider with strict RPM limits,
**I want** the system to guarantee completion (slow but correct) when rate-limit pressure is sustained,
**So that** I always receive an answer — instead of `Sorry, there was an error` — even when Tier 2 natural sequential still exceeds the provider's rolling RPM window.

---

## Context

Story 0.6 delivered **Tier 1 (parallel)** and **Tier 2 (natural sequential)** rate-limit degradation. E2E testing against TrollLLM 10 RPM on 2026-04-24 surfaced a limitation: Tier 2's natural LangGraph pacing (~1-3s between sub-agent turns) is still faster than 10 RPM can tolerate once KB planner + main synthesis LLM calls are added.

**Observed failure sequence** (from `/tmp/nowing_backend.log` 2026-04-24):

```
23:33:10 parallel_spawn: 6 agents dispatched
23:33:20 [stream_new_chat] rate_limit caught           ← events=1
23:33:42 rate_limit_degraded: spawning sequentially     ← Tier 2 activated
23:33:45 [stream_new_chat] rate_limit caught            ← Tier 2 ALSO hit 429
23:36:20 parallel_spawn: 6 agents dispatched (retry)
23:36:49 rate_limit_degraded: spawning sequentially
23:36:52 [stream_new_chat] rate_limit caught            ← repeated pattern
```

Even single-agent turns accumulate: KB planner (1 call) + sub-agent internal (1-2 calls) + main orchestrator synthesis (1 call) ≈ 3-4 calls per turn × 6 turns = 18-24 calls in <1 minute → exceeds 10 RPM rolling window.

**Tier 3** solves this by **forcing `asyncio.sleep(7)` between agent emissions** once sustained pressure is detected, buying time for the provider's rolling window to recover.

---

## Acceptance Criteria

### AC1 — Escalation counter

`_RateLimitState.escalation_level()` returns:
- `0` when `(now - last_ts) ≥ cooldown_seconds` (clean)
- `1` when `consecutive_events` in `[1, escalation_threshold - 1]`
- `2` when `consecutive_events ≥ escalation_threshold` (default 3)

Each `mark_rate_limited()` call within the cooldown window increments `consecutive_events`; after cooldown expires it resets to 0.

### AC2 — Tier 3 paced emission

When `escalation_level() == 2` and `pending` agents remain in `ParallelSpawnDirectiveMiddleware.awrap_model_call`:
- Log `rate_limit_paced (Tier 3): sleeping 7.0s before spawning <agent>`
- `await asyncio.sleep(CRYPTO_ORCHESTRA_PACED_DELAY_SECONDS)` before returning the synthetic `task()` AIMessage
- Emit exactly 1 `task()` tool_call (same as Tier 2)
- `GRACEFUL_DEGRADATION_COUNTER{outcome="rate_limit_paced"}` incremented

### AC3 — Protected main synthesis

When `escalation_level() == 2` and `pending == []` (all 6 agents done → synthesis step):
- Wrap `handler(synth_request)` in retry loop (max 3 attempts)
- On `RateLimitError` (or error with "rate limit"/"429"): log `synthesis_paced_retry (Tier 3): attempt N/3`, call `mark_rate_limited()` to keep escalation hot, `asyncio.sleep(PACED_DELAY_SECONDS)`, retry
- On non-rate-limit exception: raise immediately
- On 3rd failure: raise (normal error path)

### AC4 — Regression: Tier 1 / Tier 2 preserved

- `escalation_level() == 0` → 6-parallel spawn unchanged (Phase 1 Quality Gate AC1/AC2)
- `escalation_level() == 1` → 1-per-turn sequential, no forced sleep (previous Tier 2 behavior verified 2026-04-24)

### AC5 — Env-configurable

- `CRYPTO_ORCHESTRA_ESCALATION_THRESHOLD` (default 3) — tune when to escalate
- `CRYPTO_ORCHESTRA_PACED_DELAY_SECONDS` (default 7) — tune delay per provider RPM
- `CRYPTO_ORCHESTRA_RATE_LIMIT_COOLDOWN` (pre-existing, default 60) — how long pressure lingers

### AC6 — Global provider rate gate (Option B)

A new `ProviderRateLimitMiddleware` enforces `PROVIDER_RPM_LIMIT` across **every** LLM call (main orchestrator, sub-agents, KB planner, synthesis) via token-bucket over rolling `PROVIDER_RATE_WINDOW_SECONDS`:
- When bucket full, `awrap_model_call` sleeps until the oldest slot ages out (capped by `PROVIDER_RATE_MAX_WAIT_SECONDS`, default 90s)
- Emits log `provider_rate_gate: N/M slots used — waiting X.Ys`
- Zero-cost when `PROVIDER_RPM_LIMIT == 0` (default — disabled)
- Env: `PROVIDER_RPM_LIMIT` (default 0), `PROVIDER_RATE_WINDOW_SECONDS` (default 60), `PROVIDER_RATE_MAX_WAIT_SECONDS` (default 90)

### AC7 — Reduced-scope analysis at Tier 3 (Option C)

When `escalation_level() == 2` AND no agents yet spawned, the middleware caps `pending = pending[:2]` — running only the top-2 deterministic-API agents (`tokenomics_analyst` + `defillama_analyst`) instead of the full 6. This:
- Guarantees a useful partial answer in ~30-45s under strict RPM providers
- Emits log `rate_limit_reduced_scope (Tier 3): capping analysis to 2/6 agents`
- Increments `GRACEFUL_DEGRADATION_COUNTER{outcome="rate_limit_reduced_scope"}`
- Resumes full 6-agent suite once `escalation_level()` drops back to 0/1

### AC8 — Sub-agent resilience (unbounded retry + error-as-ToolMessage)

A new `SubAgentResilienceMiddleware` wraps every `task()` tool call from the main orchestrator:
- **Unbounded exponential backoff** — retry the sub-agent indefinitely on rate-limit errors, capped only by `SUBAGENT_RETRY_MAX_WALL_SECONDS` (default 900s / 15 min absolute)
- Backoff schedule: 5s → 10s → 20s → 40s → 80s → 120s → 120s → ... (capped at `SUBAGENT_RETRY_MAX_BACKOFF`)
- On wall-clock exhaustion, converts to `ToolMessage(status="error")` so main agent synthesizes with remaining agents
- Non-rate-limit exceptions bubble up unchanged (no retry — real bugs shouldn't be masked)
- Emits logs `subagent_retry: <name> attempt N (elapsed Xs) hit rate_limit, sleeping Ys` and `subagent_exhausted: <name> gave up after N attempts / Xs`
- Metrics: `GRACEFUL_DEGRADATION_COUNTER{outcome="subagent_retry"|"subagent_exhausted"}`

**Philosophy**: rate-limit errors are transient by definition. Given enough spacing they ALWAYS resolve. The only reason to give up is wall-clock timeout, not attempt count. Combined with AC10 min-interval gate, retries should be rare in practice.

### AC9 — Partial synthesis fallback in stream layer

When `stream_new_chat` or `stream_resume_chat` catches a terminal rate-limit error AFTER sub-agents have produced some output (including error ToolMessages from AC8), the new helper `_extract_partial_analysis(agent, config)`:
- Reads current state from checkpointer via `agent.aget_state(config)`
- Scans messages for `ToolMessage` paired with prior `task()` AIMessage tool_calls
- Partitions outputs into ✅ completed and ❌ errored groups
- Yields a markdown-formatted partial analysis (Vercel streaming protocol `text_start` / `text_delta` / `text_end`) + `format_finish` / `format_done`
- **Never** yields `format_error("Sorry, there was an error")` when partial results exist

The user always sees a graceful "⚠️ Phân tích bị giới hạn bởi rate limit..." message with whatever partial work was salvaged — including the list of agents that could not complete — instead of a generic error.

### AC10 — Min-interval gate (no bursts possible)

`_GlobalRateBucket` enforces **strict minimum spacing** = `window_seconds / max_rpm` between any two LLM calls, not merely a count-per-window cap. An `asyncio.Lock` holds across the spacing wait AND timestamp update so parallel callers queue rather than race.

**Why this matters**: the previous token-bucket implementation allowed 8 parallel agents to all pass the "count check" within 10ms (slots filled from 0→8 instantly), sending 8 simultaneous requests to the provider → rolling-window burst triggered 429 on all subsequent calls. Min-interval makes bursts mathematically impossible: at 10 RPM, call N+1 waits at least 6 seconds after call N regardless of concurrency.

**Verified 2026-04-25**: at `PROVIDER_RPM_LIMIT=8 / PROVIDER_RATE_WINDOW_SECONDS=75` (min_interval=9.4s), a 6-agent comprehensive query produced:
- 50+ gate-spacing events (`provider_rate_gate: spacing 9.4s before next call`)
- 0 stream-fatal 429 errors
- 3 transient retries (handled by AC8 middleware, converted to successful calls)
- Stream stayed alive for 17+ minutes while sub-agents completed their work

### AC11 — Synthesis Mode (no re-spawn loop, always produce final text)

After AC8–AC10 stabilized the pacing layer, E2E revealed a separate failure: main orchestrator would keep re-emitting 6 `task()` calls each turn instead of synthesizing, because the LLM saw (possibly errored) sub-agent outputs and decided to retry them — hitting `recursion_limit` with **zero final text output**.

Resolution — 3 complementary fixes in `ParallelSpawnDirectiveMiddleware.awrap_model_call`:

1. **Strip `task` tool** when `pending == []`: `request.override(tools=[t for t in request.tools if name(t) != 'task'], tool_choice='none')`. LLM cannot mechanically emit a task() tool_call.
2. **Replace** (not append) the parallel-spawn directive with a dedicated `_SYNTHESIS_DIRECTIVE` that explicitly overrides prior instructions: "IMPORTANT: Any previous instructions telling you to 'call task() for all 6 sub-agents' are now OBSOLETE. That phase is COMPLETE." → avoids LLM hallucinating tool calls from contradictory prompt context.
3. **Respawn-loop detection** (Fix 3c): track last-emitted batch signature; if 2 consecutive turns emit the same set of agents, force the synthesis path regardless of `pending` state.

Env tunable: `AGENT_RECURSION_LIMIT` (default bumped 80 → 200) for pacing mode where each step may take 10-60s.

**Verified 2026-04-25 02:27-02:30 (chat_id=30)**:
- LDO token query completed successfully with `synthesis_mode: stripped task tool (tools 30→29), forcing final text` log entry
- Final AIMessage rendered full markdown analysis with 10+ sections (market data, tokenomics, DeFi, security, yield, sentiment, risks, conclusion)
- `Copy to clipboard` + `Download as Markdown` buttons enabled on UI — user has extractable result

---

## Implementation

### File changed
- [nowing_backend/app/agents/new_chat/chat_deepagent.py](../../../nowing_backend/app/agents/new_chat/chat_deepagent.py)
  - `_RateLimitState`: +`_consecutive_events`, +`_escalation_threshold`, +`escalation_level()`, +`refresh_pressure()`
  - Module: +`_PACED_DELAY_SECONDS`, +`_PROVIDER_RPM_LIMIT`, +`_PROVIDER_RATE_WINDOW_SECONDS`, +`_PROVIDER_RATE_MAX_WAIT_SECONDS` constants
  - **New class** `ProviderRateLimitMiddleware` (AgentMiddleware): global token-bucket gating every LLM call
  - Registered at top of `deepagent_middleware` chain — runs before all downstream middlewares
  - `ParallelSpawnDirectiveMiddleware.awrap_model_call`: branch on `escalation_level()` instead of bool `is_under_pressure()`; wrap synthesis fallthrough with retry loop; **cap pending to 2 agents** at escalation_level ≥ 2 when run is fresh (no prior spawns)

### Not changed
- `stream_new_chat.py` — existing `mark_rate_limited()` hook from Story 0.6 is sufficient
- KB planner (`knowledge_search.py`) — already has "use raw query" fallback on 429
- Frontend — OrchestraStrip renders agent rows as tool_calls stream in, unaffected by pacing

---

## Tasks

- [x] **T1** Upgrade `_RateLimitState` with consecutive-event counter + `escalation_level()`
- [x] **T2** Add paced branch in `awrap_model_call` pending path
- [x] **T3** Add retry-with-sleep loop in `awrap_model_call` synthesis fallthrough
- [ ] **T4** E2E verify — simulate 3×429 against TrollLLM, confirm log pattern `rate_limit_paced (Tier 3)` + agent completes
- [ ] **T5** Optional: unit test `tests/integration/agents/test_rate_limit_escalation.py`
  - `TestRateLimitEscalation.test_consecutive_events_promote_level`
  - `TestRateLimitEscalation.test_paced_emission_sleeps`
  - `TestRateLimitEscalation.test_synthesis_retries_on_rate_limit`

---

## Verification

```bash
# Terminal 1: restart backend with short cooldown for fast iteration
CRYPTO_ORCHESTRA_RATE_LIMIT_COOLDOWN=60 \
CRYPTO_ORCHESTRA_ESCALATION_THRESHOLD=3 \
CRYPTO_ORCHESTRA_PACED_DELAY_SECONDS=7 \
uv run python main.py

# Terminal 2: monitor log
tail -f /tmp/nowing_backend.log | grep -E "rate_limit|parallel_spawn|paced|synthesis"
```

Send 4 "Phân tích toàn diện X token" queries in rapid succession. Expected progression:
- Query 1 → Tier 1 (parallel) → 429 → events=1
- Query 2 → Tier 2 (sequential) → 429 → events=2
- Query 3 → Tier 2 (sequential) → 429 → events=3
- Query 4 → **Tier 3 (paced)** → `sleeping 7.0s before spawning tokenomics_analyst` → agent runs to completion (LiteLLM retry + 7s spacing absorb transient 429s)
- Final UI response appears after ~42-50s total

---

## Risk & Rollback

- **Risk**: Thấp. Tier 1/2 behavior preserved. Added code path only activates at `escalation_level == 2`.
- **Rollback**: 1 git revert — toàn bộ thay đổi gói gọn trong `chat_deepagent.py`.
- **Observability**: new metric label `rate_limit_paced` must appear in Grafana dashboard for canary.

---

## References

- Parent story: [0-6-error-handling-fallback.md](0-6-error-handling-fallback.md)
- Parallel validation: [0-5-parallel-execution-validation.md](0-5-parallel-execution-validation.md)
- Quality gate: [phase-1-quality-gate-review.md](../../implementation-artifacts/quality-gates/phase-1-quality-gate-review.md)
- Architecture: [docs/architecture-backend.md](../../../docs/architecture-backend.md) §Rate-limit degradation ladder
- Runbook: [docs/runbooks/crypto-orchestra-degradation.md](../../../docs/runbooks/crypto-orchestra-degradation.md) §Step D
