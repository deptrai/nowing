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
```

## What's evaluated

| Task | Type | Cases | What it measures |
|---|---|---|---|
| `SUBAGENT_ROUTING` | Choice | 20 | Route Vietnamese user request → correct Nowing subagent |
| `ENTITY_MATCH` | Score | 20 | Are two scraped entities the same? (real estate, businesses) |
| `CONTENT_FILTER` | Noul | 20 | RAG passage relevance, prompt injection, PII detection |
| `INTENT_CLASSIFY` | Choice | 20 | Classify Vietnamese user intent into 8 categories |

## Files

- `cases.py` — 80 eval cases with ground-truth labels
- `runner.py` — eval executor (Jev / LLM / mock backends)
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

## Prerequisites

```bash
uv add typesafe-sdk    # Jev SDK (already installed)
uv add litellm         # LLM baseline (already installed)
```

Set env vars in `.env.local` or shell:
- `TYPESAFE_API_KEY` — from console.typesafe.ai
- `ANTHROPIC_API_KEY` — for LLM baseline comparison
- `OPENAI_API_KEY` — alternative LLM baseline
