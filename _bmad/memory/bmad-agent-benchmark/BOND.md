# Bond

## Basics
- **Name:** Luisphan
- **Role:** Founder & Lead Developer of Nowing
- **Language:** Việt Nam

## Working Preferences
- Present benchmark results as concise tables with clear deltas ($\Delta$) against baseline.
- Highlight pass/fail status and root causes of regressions clearly.
- Run benchmarks using the existing `nowing_evals` harness without inventing redundant custom scripts.

## Things to Remember
- Benchmark harness location: `nowing_evals/` (invoked via `python -m nowing_evals run <suite>`).
- DSH / Lead Extraction benchmark uses `--mode replay` for $0 cost CI testing.
- Chat regression benchmarks test across `speed`, `balanced`, `quality`, `auto` modes.

## Things to Avoid
- Declaring a benchmark pass when sample sizes are statistically under-sampled.
- Silently skipping failed test cases.
- Overwriting historical memory without recording dates and commit references.
