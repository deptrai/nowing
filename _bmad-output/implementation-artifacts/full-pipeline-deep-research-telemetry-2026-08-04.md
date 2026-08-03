# Full-Pipeline Deep-Research Telemetry

## What changed

The `deep_research` `TokenUsage` row now captures the full pipeline cost and latency, not just the ChainLens engine cost.

## New `ResearchOutput` fields (`nowing_backend/app/capabilities/chainlens/research/schemas.py`)

- `kb_fallback_duration_ms`
- `kb_fallback_embedding_tokens`
- `kb_fallback_embedding_cost_micros`
- `kb_fallback_embedding_cost_basis` (`api` | `local` | `n/a`)
- `kb_fallback_search_cost_micros`

## Executor instrumentation (`nowing_backend/app/capabilities/chainlens/research/executor.py`)

- `_embedding_token_count(query)` uses the configured embedding model's `count_tokens` when available; falls back to `None` with `cost_basis="n/a"`.
- `execute_with_context` now times the KB fallback `search_chunks` call and records the embedding token count and duration on the `ResearchOutput`.
- KB fallback cost is recorded as `0` micros for local sentence-transformer models, with `cost_basis="local"`.

## Billing/telemetry aggregation (`nowing_backend/app/capabilities/core/billing.py`)

`_charge_chainlens` now builds a `call_details` breakdown:

```json
{
  "resolved_mode": "...",
  "mode_requested": "...",
  "cost_basis": "actual|estimated|fallback",
  "tokens_total": 1234,
  "e2e_ms": 12345,
  "ttfb_ms": 2345,
  "cost_dollars": 0.0123,
  "chainlens_cost_micros": 12300,
  "chainlens_cost_basis": "actual",
  "kb_fallback_cost_micros": 0,
  "kb_fallback_duration_ms": 12,
  "kb_fallback_embedding_tokens": 3,
  "kb_fallback_embedding_cost_micros": 0,
  "kb_fallback_embedding_cost_basis": "local",
  "kb_fallback_search_cost_micros": 0,
  "total_cost_micros": 12300,
  "fallback_hit_count": 0,
  "degradation_reason": "...",
  "final_status": "..."
}
```

The `total_cost_micros` is the sum of `chainlens_cost_micros` and `kb_fallback_cost_micros`. Today the KB fallback cost is zero (local embedding + DB search), but the structure is ready for cloud embedding or metered search costs. The `TokenUsage.cost_micros` and the wallet debit now use `total_cost_micros`.

## Verification

- `ruff check app/capabilities/chainlens/research/executor.py app/capabilities/chainlens/research/schemas.py app/capabilities/core/billing.py` — passed.
- `pytest tests/unit/capabilities/test_billing.py tests/unit/capabilities/chainlens/research/test_mutation_killers.py tests/unit/capabilities/chainlens/research/test_degradation.py tests/unit/capabilities/chainlens/research/test_mutation_killers_extra.py -q` — 231 passed.
- `pytest tests/integration/capabilities/chainlens/research/test_research_fallback.py -q` — 9 passed, 1 pre-existing failure (`test_rest_sync_records_degraded_run_output_text` expects sync 200 but State A forces async 202; unrelated to this change).

## Files touched

- `nowing_backend/app/capabilities/chainlens/research/schemas.py`
- `nowing_backend/app/capabilities/chainlens/research/executor.py`
- `nowing_backend/app/capabilities/core/billing.py`
- `_bmad-output/implementation-artifacts/full-pipeline-deep-research-telemetry-2026-08-04.md` (this artifact)
