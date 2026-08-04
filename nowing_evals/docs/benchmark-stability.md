# Benchmark stability metrics

This doc explains the stability/operational metrics added in Story 4.8f to `chat/regression` and `research/chainlens_latency`.

## `chat/regression`

The benchmark still reports latency, TTFB, tokens, cost, citations, and keyword match rate. It now also parses the raw SSE stream from `POST /api/v1/new_chat` to expose tool-call health.

### Operational metrics

| Metric | Meaning |
|--------|---------|
| `scrape_success_rate` | `web_search` + `web_scrape` outputs that did not report an error, divided by attempts. |
| `tool_drop_rate` | Tool calls that started (`tool-input-start`/`tool-input-available`) but never received a `tool-output-available`, divided by attempts. |
| `captcha_rate` | Failure rate classified as `captcha` from SSE `error` frames, terminal info errors, or tool output messages. |
| `rate_limited_rate` | Failure rate classified as `rate_limit` / `quota` / `throttle`. |
| `timeout_rate` | Failure rate classified as `timeout`. |
| `server_error_rate` | Failure rate classified as `5xx` / `server error`. |
| `parse_error_rate` | Failure rate classified as `parse` / `json` error. |
| `engine_unavailable_rate` | Failure rate classified as `engine_unavailable`. |
| `fallback_kb_hits` | Total workspace KB fallback chunks used when deep-research / ChainLens degraded. |
| `degradation_reasons` | Distribution of `degradation_reason` strings seen in tool output / terminal info. |

### Multi-turn cases

Add a `turns` array to the JSONL case. The first turn uses the top-level `query`; each subsequent turn sends the next query in the same thread. Per-turn snapshots are recorded in `operational.turns`:

```jsonl
{"case_id": "multi", "query": "What is the budget?", "tags": ["memory"], "turns": [{"query": "What is the budget?", "expected_contains": ["Q3"]}, {"query": "And the forecast?", "expected_contains": ["forecast"]}]}
```

| Per-turn field | Meaning |
|----------------|---------|
| `latency_ms` | Time for this turn. |
| `ttfb_ms` | Time to first token for this turn. |
| `citation_count` | Citations in the turn answer. |
| `contains_hits` | Keyword matches against that turn's `expected_contains`. |
| `error` | Error text if the turn failed. |

`n_turns`, `n_failed_turns`, `turn_error_rate`, and `context_drift_score` are also reported. `context_drift_score` is `first_turn_contains_ratio - last_turn_contains_ratio`; a positive value suggests later turns are matching fewer expected keywords relative to the first turn.

### High-intensity / stress mode

Use `--concurrency N` (parallel cases) and/or `--threads M` (parallel chat threads per case) to stress the backend. When `N > 1` or `M > 1`, the report adds under-load metrics:

| Under-load metric | Meaning |
|-------------------|---------|
| `p95_latency_under_load_ms` | p95 e2e latency observed under the configured load. |
| `error_rate_under_load` | Error rate observed under load. |
| `rate_limited_rate_under_load` | Rate-limit/captcha/throttle failure rate under load. |
| `engine_unavailable_rate_under_load` | Engine unavailable rate under load. |

Example:

```bash
python -m nowing_evals run chat regression --search-space-id 42 --concurrency 4 --threads 2
```

## `research/chainlens_latency`

For each requested mode the benchmark now also reports:

| Metric | Meaning |
|--------|---------|
| `sources_partial_rate` | Runs with `status == "partial"` divided by total runs for that mode. |
| `engine_unavailable_rate` | Runs with `status == "engine_unavailable"` divided by total runs. |
| `degraded_rate` | Runs with `degraded == true` divided by total runs. |
| `degradation_reason_counts` | Distribution of `degradation_reason` values. |
| `fallback_kb_hits` | Total workspace KB fallback citations used. |
| `mean_cost_micros` | Mean `cost_micros` reported by the engine. |

These metrics detect when the ChainLens engine is failing over to KB fallback, returning partial results, or becoming unreachable before users feel it in production.
