# Benchmark runner reference

This guide covers the `chat/regression` and `research/chainlens_latency` benchmarks, with a focus on the **mode × tier matrix** and **local vs production parity** features added in Story 4.8g.

## Quick reference

| Benchmark | CLI entry | Needs setup? | Needs SearchSpace? |
|---|---|---|---|
| `chat/regression` | `python -m nowing_evals run chat regression` | no | yes (`--search-space-id`) |
| `research/chainlens_latency` | `python -m nowing_evals run research chainlens_latency` | no | no (needs `--workspace-id`) |

## Common flags

Both runners accept:

- `--modes <csv>` — modes to compare (e.g. `speed,balanced,quality,auto`).
- `--environment {local,production}` — tags each row and enables the **local vs production parity** report table.
- `--profile {quick,full}` — `quick` runs one case per tag (chat) or one query (chainlens) with one mode and concurrency 1; `full` runs the full matrix.

`chat/regression` additionally accepts:

- `--tier <csv>` — filter by the dataset `tier` field (e.g. `short,long_context,multi_tool`).
- `--threads N` — open `N` parallel chat threads per case for stress testing.

## Chat regression dataset

Each JSONL row is a case:

```jsonl
{"case_id": "chat-mem-001", "query": "What do we know about AlphaCorp?", "tags": ["memory"], "tier": "short", "expected_contains": ["AlphaCorp"]}
{"case_id": "chat-doc-001", "query": "Summarize the NDA.", "tags": ["document"], "tier": "long_context", "mentioned_document_ids": [123], "expected_contains": ["NDA"]}
{"case_id": "chat-multi-001", "query": "What is the budget?", "tags": ["memory"], "tier": "multi_tool", "turns": [{"query": "What is the budget?", "expected_contains": ["Q3"]}, {"query": "And the forecast?", "expected_contains": ["forecast"]}], "expected_contains": ["forecast"]}
```

- `tier` is a free-form classifier. The default sample dataset uses `short`, `long_context`, and `multi_tool`.
- `modes` is an optional per-case override for the `--modes` flag.
- `turns` supports multi-turn cases that reuse the same thread.

## Mode × tier matrix

When `--modes` contains multiple values, `chat/regression` runs each case once per mode. If a case defines its own `modes`, the per-case value is used. Aggregates are produced for:

- `overall`
- `per_tag`
- `per_mode`
- `per_tier`
- `per_mode_tier`

Each bucket contains: samples, error rate, p50/p95 e2e, p50/p95 TTFB, p50/p95 cost, p50/p95 citation count, mean tokens, and keyword match rate.

## Local vs production parity

Run the same benchmark against the local and production environments, then use `report`:

```bash
python -m nowing_evals run chat regression --search-space-id 42 --environment local  ...
python -m nowing_evals run chat regression --search-space-id 42 --environment production  ...
python -m nowing_evals report --suite chat
```

The report compares the latest `local` and `production` artifacts and shows a delta table for p95 e2e, p95 cost, and p95 citations, both overall and per mode. The same pattern works for `research/chainlens_latency`.

## Gate thresholds

Both benchmarks ship with `gate.yaml` in their package directories:

- `src/nowing_evals/suites/chat/regression/gate.yaml`
- `src/nowing_evals/suites/research/chainlens_latency/gate.yaml`

Thresholds are grouped by **overall**, **per_mode**, and **per_tier**. The runner evaluates them after each run and records any `gate_violations` in the metrics. When `baseline_ratified: true` is set in `gate.yaml`, a violation causes the run to exit with a non-zero status; until then the run completes so the baseline can be measured.

## Operational / stability metrics

`chat/regression` also computes operational summaries: scrape success/drop rates, per-tool attempt/success/failure/drop counts, failure reason counts (captcha, rate-limit, timeout, 5xx, parse, engine unavailable), fallback KB hits, and multi-turn `turn_error_rate` / `context_drift_score`.

## ChainLens research latency

`research/chainlens_latency` calls the Nowing deep-research endpoint and records p50/p95 e2e and TTFB per mode. It also tracks `sources_partial_rate`, `engine_unavailable_rate`, `degraded_rate`, `degradation_reason_counts`, `fallback_kb_hits`, and `mean_cost_micros`. The `quality` mode is the Nowing schema mode that maps to ChainLens `deep`/`deep-reasoning`.

Example:

```bash
python -m nowing_evals run research chainlens_latency \
  --modes speed,balanced,quality \
  --n 3 \
  --environment local
python -m nowing_evals report --suite research --benchmark chainlens_latency
```
