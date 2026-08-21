# Capabilities

## Built-In Suites (Full nowing_evals Surface)

| Code | Name | CLI Command | Spec / Story |
| :--- | :--- | :--- | :--- |
| `run-chat-regression` | Chat Response Regression | `python -m nowing_evals run chat regression --search-space-id <ID>` | **Story 4.8 / 4.8g / 9.2**: Latency (p95/TTFB), cost/turn matrix, finish rate, operational stability |
| `run-lead-extraction` | Lead Extraction (DSH) | `python -m nowing_evals run lead_extraction regression --mode replay` | **Story 26.7 / AD-107**: F1 Phone $\ge 98\%$, Hallucination $\le 0.1\%$, MST Modulo-11 $\ge 99.5\%$ |
| `run-research-latency` | ChainLens Deep Research Latency | `python -m nowing_evals run research chainlens_latency --modes speed,balanced,quality` | **Story 9.3 / NFR-9**: Deep research e2e latency, TTFB, degradation rates |
| `run-memory-recall` | Memory Recall Quality Gate | `python -m nowing_evals run memory recall` | **Story 3.9 / SM-10**: Precision@5 $\ge 0.80$, Noise rate $\le 0.10$, Wilson CI |
| `run-canonical-dedup` | Canonical Entity Deduplication | `python -m nowing_evals run canonical dedup` | **Story 10.4 / 12.4b**: Cross-source listing & job deduplication accuracy |
| `run-vision-rag` | Medical & Multimodal Vision RAG | `python -m nowing_evals run medical medxpertqa` / `mmlongbench` | Ingestion-time Vision extraction vs runtime text LLM cost-arbitrage |
| `generate-report` | Generate Suite Report | `python -m nowing_evals report --suite <suite>` | Compile markdown & JSON reports with percentiles and stability analysis |
| `compare-drift` | Historical Drift Analysis | Compare latest run vs ratified baselines in `MEMORY.md` | Flag latency $>15\%$, cost spikes, or gate breaches |
| `record-result` | Persist Benchmark Result | Append run summary, metrics, and commit SHA to `MEMORY.md` | Immutable quality ledger across sessions |
| `ratify-baseline` | Ratify New Baseline | Overwrite gold-standard baseline upon PO approval | Update target matrix |

## Lifecycle Verbs

1. `setup`: `python -m nowing_evals setup --suite <suite> --provider-model <slug> [--scenario head-to-head|symmetric-cheap|cost-arbitrage]`
2. `ingest`: `python -m nowing_evals ingest <suite> <benchmark> [--use-vision-llm] [--split test|dev]`
3. `run`: `python -m nowing_evals run <suite> <benchmark> [flags]`
4. `report`: `python -m nowing_evals report --suite <suite>`
5. `teardown`: `python -m nowing_evals teardown --suite <suite>`
