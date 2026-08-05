# ChainLens Research — Adjustment Proposal from Nowing

**Date:** 2026-08-05  
**From:** Nowing Benchmark / Integration Team  
**To:** ChainLens Research Team  
**Subject:** Third-party blockers observed in Nowing `chat/quality` and `chat/regression` benchmarks — requested changes before Nowing can ratify baselines

## TL;DR

Nowing benchmark (real `ag/` models against local backend) shows `chat/quality` **passes** its quality gate, but `chat/regression` with a multi-chunk document **fails latency/cost gates**. The failures are rooted in ChainLens-side behavior that Nowing cannot remediate unilaterally:

1. `costDollars` in the terminal SSE `done` frame is **writer-only**, not full-pipeline, and there is no `estimated` flag — Nowing under-meters users.
2. Deep-research latency remains **NFR6 FAIL** on both the current `ag/` Gemini stack and the DeepSeek-direct kill-test; Nowing needs validated latency/cost targets per mode or an async deliverable contract.
3. `deepseek-v4-pro` in `quality` mode produces **systematically empty outputs** and must not be used.
4. Full-pipeline cost telemetry (Epic 34.1) is still `backlog` in ChainLens, blocking Nowing from building accurate spend budgets.

## 1. Evidence from Nowing benchmark

### 1.1 `chat/quality` (LLM-as-judge) — passes quality gate

Run: `2026-08-05T07-53-20Z/quality`

| Metric | Result | `gate.yaml` threshold | Status |
|---|---|---|---|
| Mean correctness | 4.88 | ≥ 3.5 | PASS |
| Mean citation_faithfulness | 4.81 | ≥ 3.0 | PASS |
| Mean completeness | 5.00 | ≥ 3.0 | PASS |
| Mean harmfulness | 1.00 | ≤ 2.0 | PASS |
| Answer error rate | 0% | ≤ 10% | PASS |

These numbers were achieved **only after** two Nowing-side fixes:

- Source text is now fetched from `mentioned_document_ids` and numbered `[1]`, `[2]`, ... so the judge can verify bare `[n]` citations.
- `_JUDGE_SYSTEM` is finally passed as the judge `system_prompt` (it was previously `None`).

The judge model was `agy/gemini-3.1-pro-high` because `agy/claude-sonnet-4-6` and `no-think/windsurf/claude-sonnet-4.6` both returned `1.0` for obviously correct answers, indicating that model reliability is itself a risk.

### 1.2 `chat/regression` with a 21-chunk document — fails latency/cost

Run: `2026-08-05T08-11-20Z/regression`

| Metric | Result | `gate.yaml` threshold | Status |
|---|---|---|---|
| p95 e2e | 43,165 ms | ≤ 30,000 ms | **FAIL** |
| p95 TTFB | 33,286 ms | ≤ 5,000 ms | **FAIL** |
| p95 cost | 259,193 micros | ≤ 200,000 micros | **FAIL** |
| Keyword match rate | 95% | ≥ 70% | PASS |
| Error rate | 0% | ≤ 5% | PASS |

Per-mode:

| mode | p95 e2e | p95 cost | keyword match | Notes |
|---|---|---|---|---|
| speed | 41,098 ms | 228,891 micros | 80% | over-cites, slow |
| balanced | 27,892 ms | 185,201 micros | 100% | cost over per-mode `100k` |
| quality | 33,782 ms | 178,654 micros | 100% | e2e OK for quality tier |
| auto | 55,071 ms | **463,185 micros** | 100% | **21 citations** for a 1-sentence question |

The document used (`benchmark_doc_large.md`, 8 sections, 21 chunks, 51) is not extreme; it is a realistic internal tech memo. `auto` mode blew up both cost and citation count, which is a ChainLens behavior Nowing cannot fix.

## 2. Issues that must be fixed on the ChainLens side

### 2.1 `costDollars` is writer-only, not full-pipeline

**Nowing requirement (FR-37, Story 9.2):** cost must cover the **full pipeline**: classifier + researcher + writer + reflection.

**Current ChainLens implementation (Story 42-1):**

```typescript
// apps/api/src/search/api.ts:2205-2224
// Story 42-1: attach actual dollar cost when the writer usage can be priced.
// Current pipeline only surfaces the writer usage; cost is computed from that
// single source and omitted when pricing data is missing.
const writerCostDollars = modelCostAnalyzer.calculateCostDollars(answerUsage);
const finalUsage = withPhases(
  {
    ...answerUsage,
    ...modeMeta,
    ...claimVerificationMeta,
    ...(writerCostDollars !== null ? { costDollars: writerCostDollars } : {}),
  },
  phaseTracker,
);
recordPhaseTimings(finalUsage.phases);
session.emit('end', { ...modeMeta, usage: finalUsage });
```

`modelCostAnalyzer.calculateCostDollars()` takes a single `LLMUsage` record and computes cost from `promptTokens`/`completionTokens`/`totalTokens` (`apps/api/src/models/model-cost.service.ts:215-260`). It is called with `answerUsage` only — the writer's usage.

**Impact on Nowing:**

- The cost Nowing meters to end-users is **partial** (writer only).
- Nowing's wallet/credit model will under-charge and lose margin.
- Story 42-1 AC6 explicitly marks full-pipeline aggregation as "LATER" and deferred.

**Requested change:**

1. ChainLens must either:
   - Aggregate token counts from **all pipeline LLM calls** (classifier, researcher loops, rerank, deep extract, writer, reflection, citation guard) and emit a single `costDollars` covering the whole pipeline; OR
   - Emit `done.usage.costDollars` on the **writer only** and add `done.usage.estimated: true` plus a per-phase `costDollars` breakdown so Nowing can decide to use a fallback or add a surcharge.
2. The contract agreed in `42-3` says `costDollars` is "full pipeline" and `estimated` is required to distinguish measured vs estimated. The current implementation does not honor that contract.

### 2.2 No full-pipeline cost telemetry (Epic 34.1)

`34-1-cost-tracking-for-searchcontentanswer` is in `backlog` in `chainlens-research/_bmad-output/sprint-status.yaml`.

**Impact on Nowing:**

- Story 29-5 DeepSeek kill-test reported **G2 cost = INCONCLUSIVE** because the harness emits `usage = null`.
- Without per-call token usage for the full pipeline, Nowing cannot build a spend budget, cannot ratify `NFR-9` State A→B, and cannot expose a believable "cost per mode" to users.

**Requested change:**

Promote Epic 34.1 to in-progress or deliver a minimal version that exposes full-pipeline token usage and cost, at least through the `/api/v1/search` SSE `done` frame.

### 2.3 Deep-research latency is NFR6 FAIL and not improving

**Evidence:**

- `nfr6-final-20-8-v2-postfix.md` verdict: **FAIL**.
  - Ask avg 57–136s (target ≤ 8s)
  - Reason 50–160s (target ≤ 35s)
  - Research quality 198s (target ≤ 180s)
- Story 29-5 DeepSeek-direct kill-test: **G3 latency = FAIL** (9/18 mode×tier cells over revised NFR6 targets).
  - `deepseek-v3.2`: ask/quality 114s, reason/speed 99s, reason/quality 199s.
  - `deepseek-v4-pro`: ask/speed 108–125s.
  - Verdict: "DeepSeek-direct does NOT solve latency".

**Impact on Nowing:**

- Nowing cannot expose a synchronous `quality` or `auto` chat mode that calls ChainLens without violating `NFR-9`.
- The only viable product design is **async deliverable (State A)**, but that requires a ChainLens contract for:
  - `requestId` + `webUrl` for progress polling.
  - Terminal `done` with `resolvedMode` and `estimated`.
  - Clear per-mode latency promise so Nowing can gate State B sync behind a feature flag.

**Requested change:**

1. Provide **validated p50/p95 latency per mode** measured from ChainLens's own benchmark harness, not just one-word probes.
2. Either meet NFR6 revised targets (ask ≤ 60s, reason ≤ 90s, research ≤ 120s) or formally declare them unachievable and agree on an **async-only contract** for Nowing.
3. Re-run Story 29-4 latency deep-dive and share the report before Nowing enables ChainLens in production `quality`/`auto`.

### 2.4 `deepseek-v4-pro` in quality mode is broken

**Evidence from Story 29-5:**

- `deepseek-v4-pro` quality mode → **34w/0 cites empty outputs across all 3 tiers**.
- Verdict: "EXCLUDE `deepseek-v4-pro`".

**Impact on Nowing:**

- If ChainLens model policy ever routes Nowing's `quality` mode to `deepseek-v4-pro`, the user gets an empty answer.
- This model must be removed from the allow-list or explicitly marked non-production.

**Requested change:**

1. Remove `deepseek-v4-pro` from the default `quality` allow-list.
2. Provide a published "model allow-list per mode" contract that Nowing can depend on.

### 2.5 `ag/` Gemini is far above PRD cost targets

**Evidence:**

- ChainLens PRD §7.1 targets: speed $0.0018, ask $0.0048, reason $0.0061, research $0.0105.
- Nowing measured 2026-08-02: **speed $0.0353, balanced $0.0482, quality $0.0671**.
- Gap: **7.3× speed, 10× balanced, 6.4× quality** vs. target.

**Root cause:** `DEFAULT_MODEL_POLICY` is 100% `ag/` Gemini because DeepSeek is not production-viable (NFR6 FAIL and `v4-pro` broken).

**Impact on Nowing:**

- Nowing cannot price deep-research competitively or even cover cost at the current ChainLens pricing.
- The cost-moat thesis is unprovable until ChainLens lands a cheaper, working model stack.

**Requested change:**

1. Finish Epic 34.1 cost telemetry so both teams can measure true blended cost.
2. Either fix DeepSeek latency/quality (Story 29-4 + model policy) or provide ChainLens-side pricing/credits that absorb the `ag/` cost until a cheaper stack is ready.

## 3. Recommended acceptance criteria for ChainLens v4 integration

Before Nowing can move `4-8d` and `9.x` stories to `done`, ChainLens must:

| # | Criterion | Evidence required |
|---|---|---|
| A1 | Full-pipeline `costDollars` in `done.usage` or explicit `estimated` flag + per-phase breakdown | Unit test in `search-contract.spec.ts`; live probe with at least 10 calls |
| A2 | Full-pipeline token usage telemetry (prompt/completion/total for each phase) | Epic 34.1 `done`; `usage` in `done` frame non-null for happy path |
| A3 | Validated per-mode p50/p95 latency from ChainLens harness | `nfr6` or equivalent report showing ≤ revised NFR6 targets for the modes Nowing uses |
| A4 | `deepseek-v4-pro` removed from `quality` allow-list or contractually excluded | `model-policy.ts` diff + unit test |
| A5 | Cost per mode within 2× of PRD §7.1 targets OR async-only contract documented | Kill-test report or pricing commitment |
| A6 | `resolvedMode` and `estimated` flags in terminal `done` frame, per contract 42-3 | `search-contract.spec.ts` test + fixture |

## 4. Nowing-side actions we will take

These are independent but gated by the ChainLens items above:

1. **Keep `4-8d` `ready-for-dev` / `in-review`** until `chat/regression` cost/latency gates can be ratified with real ChainLens numbers.
2. **Implement Story 9.2 (cost parser)** in Nowing only after ChainLens A1/A2 are stable; fallback `60k` micros remains acceptable for partial/failure paths.
3. **Keep `NFR-9` in State A** (async deliverable required) until ChainLens A3 is proven.
4. **Do not enable ChainLens `quality`/`auto` in production** until A3, A4, and A5 are satisfied.

## 5. Attachments / references

- `chainlens-research/apps/api/src/search/api.ts:2205-2224` — writer-only `costDollars` emission.
- `chainlens-research/apps/api/src/models/model-cost.service.ts:215-260` — `calculateCostDollars` on single `LLMUsage`.
- `chainlens-research/packages/types/src/llm.ts:183-217` — `LLMUsage` type with optional `costDollars`.
- `chainlens-research/_bmad-output/implementation-artifacts/stories/42-1-costdollars-in-sse.md` — AC6 deferred full-pipeline aggregation.
- `chainlens-research/_bmad-output/implementation-artifacts/stories/42-3-verify-nowing-endpoint-needs.md` — contract Q4/Q5.
- `chainlens-research/_bmad-output/implementation-artifacts/stories/29-5-deepseek-direct-routing-cost-latency-killtest.md` — G2/G3/G4 verdicts.
- `chainlens-research/_bmad-output/sprint-status.yaml` — `34-1` in `backlog`.
- `nowing/_bmad-output/implementation-artifacts/sprint-status.yaml` — `4-8d` returned to `ready-for-dev`.
- `/private/tmp/nowing_evals_real/reports/chat/2026-08-05T08-12-02Z/summary.md` — Nowing `chat/regression` large-doc report.

---

**Next step requested:** ChainLens team to review and either commit to the six acceptance criteria or propose a bounded alternative with a PO sign-off.
