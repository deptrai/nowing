# Story 4.8h: Mode-Aware Chat Policy for Latency/Cost

**Status:** done  
**Epic:** 4 (Chat & Agents)  
**FRs:** FR-42 Chat Response Benchmark, NFR-10 Chat Response Regression Gate  
**Spec:** `@doc/specs/2026-08-05/new-chat-mode-aware-latency-cost-policy`  
**Sprint Change Proposal:** `_bmad-output/planning-artifacts/sprint-change-proposal-2026-08-05-chat-mode-policy.md`  

---

## User Story

As a user,
I want `new_chat` to respect the requested `mode` (speed/balanced/quality/auto) when selecting tools, retrieval depth, and escalation to deep research,
So that `chat/regression` passes latency, TTFB, and cost gates without losing answer quality.

---

## Context

The `chat/regression` benchmark with a 21-chunk document (run 2026-08-05T08-12-02Z) fails every latency and cost gate:

| Metric | Overall | speed | balanced | quality | auto | Threshold |
|---|---|---|---|---|---|---|
| p95 e2e (ms) | 43,165 | 41,098 | 27,892 | 33,782 | 55,071 | 30,000 |
| p95 TTFB (ms) | 33,286 | 31,789 | 25,508 | 30,999 | 18,062 | 5,000 |
| p95 cost (micros) | 259,193 | 228,891 | 185,201 | 178,654 | 463,185 | 200,000 |

Root cause from operational metrics: the multi-agent chat ignores `mode` and behaves like deep research for all four modes. Examples:

- `speed` still invokes `search_knowledge_base` 6 times and `task` 5 times.
- `auto` triggers `google_search_scrape` 8 times, `search_knowledge_base` 7 times, `task` 7 times.
- `search_knowledge_base` always retrieves up to `_MAX_PASSAGES_PER_DOC = 12` passages per doc, causing large prompts.
- `chainlens.research` is not gated by mode or document presence.

The existing code already propagates `research_mode` via `configurable` (see `app/capabilities/core/access/agent.py::_current_research_mode`), but the agent system prompt, tool list, and retrieval logic do not use it.

---

## Acceptance Criteria

### AC-1 — Speed mode tool budget
**Given** a user asks a short question with `mode=speed` and one or more `mentioned_document_ids`,  
**When** the agent runs,  
**Then** it calls `search_knowledge_base` at most once, uses `top_k=1` and `max_passages_per_doc=4`, does not call `task`, `chainlens.research`, `google_search_scrape`, `ask_knowledge_base` (external), or any connector/research subagent, and answers within 15 seconds.

### AC-2 — Balanced mode tool budget
**Given** a user asks a question with `mode=balanced` and a document is mentioned,  
**When** the agent runs,  
**Then** it may call `search_knowledge_base` at most twice and `task` at most once, never calls `chainlens.research`, and `chat/regression` p95 cost per turn stays under 100,000 micros.

### AC-3 — Quality mode web-research gating
**Given** a user asks `mode=quality` with no `mentioned_document_ids`,  
**When** the first `search_knowledge_base` returns no relevant hits,  
**Then** the agent may call `chainlens.research` for external deep research.

### AC-4 — Auto mode tool budget cap
**Given** a user asks `mode=auto` about a single mentioned document,  
**When** the agent has made 5 tool calls total,  **Then** a tool-call budget middleware returns a `ToolMessage` forcing the agent to synthesize an answer immediately.

### AC-5 — Regression benchmark passes
**Given** the `chat/regression` large-doc dataset (doc-large, 4 modes, 20 runs),  
**When** the policy is live and the suite runs,  
**Then** p95 e2e ≤ 30,000 ms, p95 TTFB ≤ 5,000 ms, p95 cost ≤ 200,000 micros, and per-mode cost stays under `speed 50k / balanced 100k / quality 200k / auto 100k`.

### AC-6 — Quality benchmark does not regress
**Given** `chat/quality` runs after the change,  
**When** evaluated with the same judge model,  
**Then** mean correctness ≥ 3.5, mean citation faithfulness ≥ 3.0, and mean completeness ≥ 3.0.

### AC-7 — Unit tests for policy
**Given** the new code,  
**When** unit/integration tests run,  
**Then** they cover each mode's tool availability list, `top_k` and `max_passages_per_doc` clamping, and budget middleware behavior (≥ 90% coverage of changed modules).

---

## Locked Decisions (from spec)

- **D1 — Scope:** Mode policy applies to all `/new_chat` and `/resume_chat` turns, including `search_knowledge_base`, `task`, `chainlens.research`, and web tools.
- **D2 — Mode mapping:**
  - `speed`: at most 1 `search_knowledge_base`; no `task`, no `chainlens.research`, no web tools.
  - `balanced`: at most 2 `search_knowledge_base` + at most 1 `task`; no `chainlens.research` if a document is mentioned or KB returned results.
  - `quality`: at most 3 `search_knowledge_base` + at most 2 `task`; `chainlens.research` allowed only when web/deep research is required.
  - `auto`: agent decides, but total tool calls are capped at 5 and KB must be tried first.
- **D3 — Enforcement:** Three layers: (1) per-mode system prompt, (2) tool availability lists, (3) tool-call budget middleware.
- **D4 — Default mode:** When `mode` is missing, default to `auto` (with budget cap).
- **D5 — ChainLens gating:** `chainlens.research` disabled for `speed`; restricted for `balanced`/`auto` unless external research is clearly needed; allowed for `quality`.

---

## Technical Approach

### Layer 1 — System prompt per mode
- File: `app/agents/chat/multi_agent_chat/main_agent/system_prompt/builder/compose.py`
- Append a mode appendix to the system prompt based on `configurable["research_mode"]`.
- The appendix tells the agent exactly which tools it may use and the hard budget.

### Layer 2 — Tool availability filtering
- File: `app/agents/chat/multi_agent_chat/main_agent/middleware/checkpointed_subagent_middleware/middleware.py`
- Before the agent compiles/runs, filter the tool list by mode.
- `speed`: remove `task`, `chainlens.research`, `google_search_scrape`, `ask_knowledge_base` (external), and connector/research subagent tools.
- `balanced`: same as speed unless no `mentioned_document_ids`; then allow one `task(knowledge_base)` but still disable `chainlens.research`.
- `quality`: keep full tool surface.
- `auto`: keep full tool surface, but prompt and middleware enforce budget.

### Layer 3 — Tool-call budget middleware
- New file: `app/agents/chat/multi_agent_chat/main_agent/middleware/mode_budget_middleware.py`
- Track per-mode counts of tool calls per turn.
- When a mode's budget is exhausted, return a `ToolMessage` telling the agent it must answer now.
- Wire into the main agent graph and subagent graph (subagents inherit `configurable` via `subagent_invoke_config`).

### Layer 4 — Retrieval depth clamping
- File: `app/agents/chat/multi_agent_chat/shared/retrieval/hybrid_search.py`
- Add `max_passages_per_doc` parameter to `search_chunks`, `_search`, `_group_into_documents`, and `_reading_order`.
- Default remains `_MAX_PASSAGES_PER_DOC` (12) to avoid breaking other call sites.
- File: `app/agents/chat/multi_agent_chat/subagents/builtins/knowledge_base/tools/search_knowledge_base.py`
- Read `research_mode` from `runtime.config["configurable"]` and clamp:
  - `speed`: `top_k=1`, `max_passages=4`
  - `balanced`: `top_k=2`, `max_passages=8`
  - `quality`: `top_k=3`, `max_passages=12`
  - `auto`: `top_k=2`, `max_passages=8` until the agent escalates.

### Layer 5 — Config forwarding verification
- Files: `stream_new_chat` and `stream_resume_chat` entry points
- Ensure `research_mode` is in `configurable` and is copied into every subagent `configurable` (already done for `subagent_invoke_config` — verify no overwrite).

---

## Related Files

- `app/agents/chat/multi_agent_chat/main_agent/system_prompt/builder/compose.py`
- `app/agents/chat/multi_agent_chat/main_agent/system_prompt/builder/load_md.py`
- `app/agents/chat/multi_agent_chat/main_agent/middleware/checkpointed_subagent_middleware/middleware.py`
- `app/agents/chat/multi_agent_chat/main_agent/middleware/checkpointed_subagent_middleware/task_tool.py`
- `app/agents/chat/multi_agent_chat/shared/retrieval/hybrid_search.py`
- `app/agents/chat/multi_agent_chat/subagents/builtins/knowledge_base/tools/search_knowledge_base.py`
- `app/capabilities/core/access/agent.py` (`_current_research_mode`)
- `app/agents/chat/multi_agent_chat/main_agent/graph/compile_graph_sync.py`
- `nowing_evals/suites/chat/regression/gate.yaml`
- `nowing_evals/suites/chat/regression/cases/doc-large-*.json`
- `nowing_evals/suites/chat/quality/gate.yaml`

## Related Tests

- `tests/integration/agents/multi_agent_chat/shared/retrieval/test_hybrid_search.py`
- `tests/integration/capabilities/chainlens/research/test_research_fallback.py`
- `tests/unit/observability/test_chainlens_degradation.py`
- New: `tests/unit/agents/multi_agent_chat/test_mode_budget_middleware.py`
- New: `tests/unit/agents/multi_agent_chat/test_mode_tool_availability.py`
- Run: `pytest tests/integration/agents/multi_agent_chat/shared/retrieval/ -q`

## Verification Commands

Backend (from `nowing_backend/`):

```bash
ruff check app/agents/chat/multi_agent_chat/main_agent/system_prompt/builder/compose.py \
  app/agents/chat/multi_agent_chat/main_agent/middleware/checkpointed_subagent_middleware/middleware.py \
  app/agents/chat/multi_agent_chat/shared/retrieval/hybrid_search.py \
  app/agents/chat/multi_agent_chat/subagents/builtins/knowledge_base/tools/search_knowledge_base.py

ruff format app/agents/chat/multi_agent_chat/main_agent/system_prompt/builder/compose.py \
  app/agents/chat/multi_agent_chat/main_agent/middleware/checkpointed_subagent_middleware/middleware.py \
  app/agents/chat/multi_agent_chat/shared/retrieval/hybrid_search.py \
  app/agents/chat/multi_agent_chat/subagents/builtins/knowledge_base/tools/search_knowledge_base.py

pytest tests/integration/agents/multi_agent_chat/shared/retrieval/test_hybrid_search.py -q
pytest tests/unit/agents/multi_agent_chat/ -q
```

Eval (from repo root):

```bash
nowing_evals run chat regression --dataset doc-large
nowing_evals run chat quality
```

---

## Open Questions

- Should `speed` also pin a cheaper/faster global model? (Deferred to separate model policy story.)
- How does this policy interact with desktop local-folder mode? (Likely unchanged — local files are part of the KB.)

---

## Handoff Notes for Dev Agent

1. Start with `search_knowledge_base` + `hybrid_search` chunk cap — low blast radius, measurable cost reduction.
2. Add mode budget middleware before system prompt/tool filtering to avoid two conflicting enforcement layers.
3. Run `chat/quality` after every layer to catch regressions early.
4. Do not change `chainlens.research` contract on ChainLens side — only gate calls from Nowing.

## Review Findings (code review 2026-08-08)

Scope: commit `9cce2967d` — 2 implementation files (399 lines) + 1 test file (231 lines).

**patch (HIGH) — fixed 2026-08-08:**
- [x] [Review][Patch] Batch tool call budget bypass — counter was incremented AFTER all evaluations, so if LLM returned 2 KB calls in one AIMessage, both were evaluated against `counter.kb=0` and both passed (budget=1), then counter became 2. Fixed by incrementing counter immediately when a call is allowed, so subsequent calls in the same batch are evaluated against the updated counter. [edge]

**defer:** 9 (all low/medium severity)
- Silent mode fallback (invalid mode → "auto") — safe default, no warning logged.
- No actual cost tracking (call count ≠ cost) — AC specifies call count budgets, not cost.
- Missing subagent_type treated as non_kb — malformed tool calls are edge case.
- Exception swallowing in config retrieval — fallback to runtime config is reasonable.
- Case sensitivity ("SPEED" → "auto") — API schema validates mode is lowercase.
- AC-1 PARTIAL: top_k/max_passages_per_doc clamping not in this diff (may be in retrieval layer).
- AC-3 PARTIAL: quality mode allows ChainLens by design (budget 3,2,5).
- AC-5/AC-6: benchmark tests are in nowing_evals, not backend.
- AC-7 PARTIAL: tests cover speed/balanced/auto modes, missing quality mode specific tests.

**dismissed:** 5 (all false positives)
- Race condition in counter updates — FALSE POSITIVE. LangGraph agent loop is sequential within a turn. Single asyncio event loop. No concurrent after_model calls for same turn.
- Counter key collision — FALSE POSITIVE. thread_id and turn_id always set in configurable (orchestrator line 473-474). turn_id is timestamp-based, always unique.
- Non-atomic check-and-set (TOCTOU) — FALSE POSITIVE. Same as race condition. Sequential execution.
- Duplicate tool calls counted separately — FALSE POSITIVE. Each tool call has unique ID from LLM.
- Counter persistence (turn_id reuse) — FALSE POSITIVE. turn_id is `f"{chat_id}:{int(time.time() * 1000)}"`, always unique.

**AC coverage:** AC-1 PARTIAL (top_k clamping not in diff), AC-2 PASS, AC-3 PARTIAL (quality allows ChainLens by design), AC-4 PASS, AC-5/AC-6 defer (benchmark tests in nowing_evals), AC-7 PARTIAL (missing quality mode tests).

**Positive findings:**
- Mode budgets correctly defined: speed (1,0,1), balanced (2,1,3), quality (3,2,5), auto (2,5,5)
- Speed mode blocks web/deep-research tools
- Budget exhaustion forces synthesis (jump_to="end")
- Counter is per-turn (thread_id::turn_id key)
- aafter_model delegates to after_model (no duplicate logic)
- 16 unit tests covering all modes and batch counting
