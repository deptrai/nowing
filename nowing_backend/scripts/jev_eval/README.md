# Jev Vietnamese Evaluation Harness

**Purpose**: Determine if Jev (TypeSafe's System One model) performs well enough on Vietnamese text to justify integration into Nowing.

## Quick start

```bash
# 1. Validate harness (no API keys needed)
uv run scripts/jev_eval/runner.py

# 2. Run LLM baseline only (needs ANTHROPIC_API_KEY or OPENAI_API_KEY)
uv run scripts/jev_eval/runner.py --backend llm_json

# 3. Run Jev only (needs TYPESAFE_API_KEY)
uv run scripts/jev_eval/runner.py --backend jev

# 4. Full comparison (all backends)
uv run scripts/jev_eval/runner.py --live

# 5. One task type only
uv run scripts/jev_eval/runner.py --backend jev --task SUBAGENT_ROUTING

# 6. Quick smoke test (first 5 cases)
uv run scripts/jev_eval/runner.py --live --limit 5

# 7. Explicit dry-run (CI harness check — alias for --backend mock)
uv run scripts/jev_eval/runner.py --dry-run

# 8. Gated live run — exit 1 if any task drops below the floor (default 90%)
uv run scripts/jev_eval/runner.py --backend jev --gate
uv run scripts/jev_eval/runner.py --backend jev --gate --floor 0.95

# 9. Evaluate a specific Jev model version (recorded per row in results.jsonl)
uv run scripts/jev_eval/runner.py --backend jev --gate --model jev-1.14.0
```

## Flags

| Flag | Behavior |
|---|---|
| `--dry-run` | Explicit alias for `--backend mock`; mutually exclusive with `--backend`/`--live`. No API keys needed. |
| `--gate` | Exit 0 when every evaluated (task, backend) group ≥ `--floor`; exit 1 on any group below floor or zero evaluable results. Applies to whatever ran — a gated dry-run legitimately fails because the mock stub is not a real eval. **Note:** `--live --gate` and `--backend all --gate` include the mock backend and fail by design — use `--backend jev --gate` for real gates. |
| `--floor` | Per-task accuracy floor for `--gate` (default `0.90`). |
| `--model` | Jev model override — passed to `client.system_one(model=...)` and recorded in `EvalResult.model` / `results.jsonl`. |
| `--backend` | `jev` \| `llm_json` \| `decision_llm_json` \| `mock` \| `all` (default: mock). |
| `--task`, `--limit`, `--live` | Filter cases / cap case count / run all live backends. |

When `--gate` is set, the report (logged + appended to `summary.md` as
`## Gate`) shows per-task pass/fail and delta vs `baseline.json`.

## Baseline (`baseline.json`)

`baseline.json` is the ratified accuracy reference — checked in, not
regenerated. Current values come from the 2026-09-21 `jev-1.13.0` run
(overall 96.3%: ROUTING 100%, ENTITY 90%, CONTENT 100%, INTENT 95%).

Baseline deltas are **informational**; the hard gate criterion is the
`--floor`. To ratify a new baseline after a model/question-set change:

1. Run a full live eval: `uv run scripts/jev_eval/runner.py --backend jev --gate --model <version>`
2. Review the `## Gate` deltas in `summary.md`.
3. Update `baseline.json` (`model`, `overall`, per-task accuracies) and commit it with the change.
4. Missing/invalid `baseline.json` → warning logged, floor still enforced, comparison skipped.

## CI (`.github/workflows/jev-eval-gate.yml`)

- **`harness-check`** (PR, no secrets): runs `uv run scripts/jev_eval/runner.py --dry-run`
  when eval/decision code changes — validates the harness end-to-end without `--gate`.
- **`live-gate`** (`workflow_dispatch`, paid): runs `--backend jev --gate` with
  `TYPESAFE_API_KEY` from repo secrets. Inputs: `model` (default `jev-1.13.0`),
  `task`, `limit`, `floor` (default `0.90`). Artifacts (`results.jsonl`,
  `summary.md`) are uploaded per run.

## What's evaluated

| Task | Type | Cases | What it measures |
|---|---|---|---|
| `SUBAGENT_ROUTING` | Choice | 20 | Route Vietnamese user request → correct Nowing subagent |
| `ENTITY_MATCH` | Score | 20 | Are two scraped entities the same? (real estate, businesses) |
| `CONTENT_FILTER` | Noul | 20 | RAG passage relevance, prompt injection, PII detection |
| `INTENT_CLASSIFY` | Choice | 20 | Classify Vietnamese user intent into 8 categories |

## Files

- `cases.py` — 80 eval cases with ground-truth labels
- `runner.py` — eval executor (Jev / LLM / mock backends) + `--gate` floor check
- `baseline.json` — ratified per-task accuracies (checked in)
- `results.jsonl` — raw per-case results (generated)
- `summary.md` — aggregated report (generated)

## Scoring

| Task | Correctness |
|---|---|
| Choice (routing, intent) | Exact match on option key |
| Noul (content filter) | `predicted >= 0.5` matches `expected` |
| Score (entity match) | `|predicted - expected| <= tolerance` (default 0.6) |

## Decision criteria

- **Jev accuracy >= LLM baseline** on Vietnamese → proceed with integration (R2: subagent routing)
- **Jev accuracy < LLM baseline** → use Jev for English-content features only, revisit later
- **Jev accuracy >= 90%** → green light for autonomous use (confidence-gated)
- **Jev accuracy 70-90%** → use with human-review fallback
- **Jev accuracy < 70%** → not viable for Vietnamese, revisit when multilingual support lands

## Verdict / failure analysis

> From the ratified 2026-09-21 `jev-1.13.0` run (see `baseline.json`). Moved
> here from `summary.md` — that file is regenerated on every run and is
> disposable.

**Jev handles Vietnamese text excellently** — 77/80 (96.3%) correct across 4 task types, median latency ~308ms, zero API errors.

| Task | Accuracy | Notes |
|---|---|---|
| SUBAGENT_ROUTING | **100%** | All 20 Vietnamese routing decisions correct |
| CONTENT_FILTER | **100%** | All relevance/injection/PII checks correct, incl. Vietnamese injection attempts |
| INTENT_CLASSIFY | **95%** | 19/20 — 1 miss is a borderline label (search vs recommendation) |
| ENTITY_MATCH | **90%** | 18/20 — 2 misses are borderline uncertain scores on genuinely ambiguous pairs |

### Failure analysis

All 3 remaining misses are **borderline/defensible**, not wrong:
- `entity_04` (1.37 vs 2): same person+phone but different role → Jev says "probably same" at 1% confidence
- `entity_15` (1.02 vs 0): same project different blocks → Jev says "uncertain" (arguably correct)
- `intent_01` ("recommendation" vs "search"): "Tìm quán phở ngon" → both labels defensible

### Decision

✅ **Green light for Vietnamese deployment.** Jev's Vietnamese comprehension is production-quality for decision tasks. The eval confirms:

1. **Subagent routing** is the highest-impact first integration — 100% accuracy on Vietnamese routing
2. **Content filtering** works reliably — detects Vietnamese prompt injection
3. **Entity resolution** works but needs confidence-gated human review for edge cases
4. **Intent classification** works well for Vietnamese user messages

**Cost**: ~$0.0018 for 80 eval calls (~540 tokens/call avg). At production scale (10K decisions/day): ~$0.23/day ≈ $7/month.

**Recommendation**: Proceed to R2 — subagent routing integration. Use confidence-gated fallback to LLM for `confidence < 0.6`.

## Prerequisites

```bash
uv add typesafe-sdk    # Jev SDK (already installed)
uv add litellm         # LLM baseline (already installed)
```

Set env vars in `.env.local` or shell:
- `TYPESAFE_API_KEY` — from console.typesafe.ai
- `ANTHROPIC_API_KEY` — for LLM baseline comparison
- `OPENAI_API_KEY` — alternative LLM baseline
