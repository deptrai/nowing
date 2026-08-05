---
baseline_commit: e3de8a948
baseline_branch: develop
story_key: 4-8b-chat-regression-suite
status: review
---

# Story 4.8b: Chat Regression Benchmark Suite

**Status:** review  
**Epic:** 4 — Chat & Agents  
**Priority:** HIGH  
**Requirements:** FR-42, NFR-10  
**Architecture:** `nowing_evals` harness, `AD-15` (nếu benchmark gọi ChainLens)

## Story

As a release engineer,
I want a `chat/regression` benchmark in `nowing_evals` that replays a dataset of chat queries and reports latency, cost, citations, and finish status,
So that we can gate production deploys on chat quality drift.

## Context

- `4-8a` đã extend `NewChatClient` để parse `data-token-usage`, `data-turn-info`, TTFB, và trả về `cost_micros`/`prompt_tokens`/... trong `StreamedAnswer`.
- `NowingArm` đã map các telemetry fields này vào `ArmResult`.
- `nowing_evals` harness hỗ trợ `ingest`/`run`/`report` qua registry và auto-discovery.

## Acceptance Criteria

1. **Auto-discovery**
   - **Given** `python -m nowing_evals benchmarks list`,  
     **Then** `chat/regression` appears.

2. **Ingest**
   - **Given** `python -m nowing_evals ingest chat regression`,  
     **Then** a default synthetic dataset is written to `data/chat/regression/cases.jsonl`.
   - **Given** `python -m nowing_evals ingest chat regression --dataset custom.jsonl`,  
     **Then** the custom dataset is validated and copied to `data/chat/regression/cases.jsonl`.

3. **Run**
   - **Given** `python -m nowing_evals run chat regression --search-space-id 42`,  
     **When** it executes,  
     **Then** it creates a fresh thread per case, calls `/api/v1/new_chat`, records latency, TTFB, tokens, cost, citations, and finish status.

4. **Report**
   - **Given** `python -m nowing_evals report --suite chat`,  
     **Then** it prints overall and per-tag p95 latency, p95 cost, error rate, citation count, and keyword match rate.

5. **Gate**
   - **Given** `src/nowing_evals/suites/chat/regression/gate.yaml`,  
     **Then** thresholds are provisional (`baseline_ratified: false`) and documented.

## Tasks / Subtasks

### Files created

- [x] `nowing_evals/src/nowing_evals/suites/chat/__init__.py`
- [x] `nowing_evals/src/nowing_evals/suites/chat/regression/__init__.py`
- [x] `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py`
- [x] `nowing_evals/src/nowing_evals/suites/chat/regression/operational.py`
- [x] `nowing_evals/src/nowing_evals/suites/chat/regression/gate.yaml`

### Runner features

- [x] `ChatRegressionBenchmark` registered with `suite="chat"`, `name="regression"`.
- [x] `requires_suite_setup = False`; requires `--search-space-id` at run time.
- [x] `add_run_args`: `--search-space-id`, `--workspace-id`, `--dataset`, `--n`, `--concurrency`, `--threads`, `--modes`, `--tier`, `--environment`, `--profile`, `--tags`, `--timeout` (default 600s), `--backend-build-id`, `--max-total-cost-micros`, `--fail-on-unratified`.
- [x] `ingest()`: validates dataset rows have `case_id` and `query`; writes `data/chat/regression/cases.jsonl`.
- [x] `run()`: loads cases, filters by `--tags` and `--tier`, expands the `--modes` matrix, calls `NowingArm` with the case `mode` in `NewChatRequest`, handles `TimeoutError`, writes `raw.jsonl` and `run_artifact.json`.
- [x] `report_section()`: markdown tables per tag, mode, tier, and mode×tier, plus overall summary and an "Operational / Stability" section.
- [x] `--environment local|production` is written into `run_artifact.json`; the report can surface a `local vs production` delta when both are present.

### Metrics

- [x] `overall`: samples, n_failed, error_rate, p50/p95 e2e, p50/p95 ttfb, p50/p95 cost, total cost, p50/p95 citation count, mean total tokens, keyword match rate.
- [x] `per_tag`: same metrics grouped by `tags`.
- [x] `per_mode`, `per_tier`, `per_mode_tier`: same metrics grouped by the requested chat `mode` and the case `tier`.
- [x] `operational`: scrape/tool success and drop rates, failure reason counts, fallback KB hits, engine unavailable rate, plus under-load metrics.

### Dataset

- [x] Default sample 5 cases covering `memory`, `document`, `deep-research`, `multi-tool`, `creative`; each case has a `tier` and uses the requested mode matrix.
- [x] JSONL schema: `case_id`, `query`, `tags`, `tier`, `modes`, `turns`, `mentioned_document_ids`, `disabled_tools`, `expected_contains`.

### Docs

- [x] `nowing_evals/README.md` updated with benchmark table and usage section.
- [x] `nowing_evals/docs/benchmark-stability.md` and `nowing_evals/docs/benchmark.md` reference the chat/regression runner.

## Verification

```bash
cd nowing_evals
python -m nowing_evals benchmarks list
python -m nowing_evals ingest chat regression --help
python -m nowing_evals run chat regression --help
ruff check src/nowing_evals/core/clients/new_chat.py src/nowing_evals/core/arms/nowing.py src/nowing_evals/core/notifications.py src/nowing_evals/suites/chat/regression/ tests/suites/chat/test_regression.py tests/suites/chat/test_operational.py
ruff format src/nowing_evals/core/clients/new_chat.py src/nowing_evals/core/arms/nowing.py src/nowing_evals/core/notifications.py src/nowing_evals/suites/chat/regression/ tests/suites/chat/test_regression.py tests/suites/chat/test_operational.py
python -m pytest tests/core/test_clients.py tests/suites/chat/test_regression.py tests/suites/chat/test_operational.py -q
```

To run against a real backend:

```bash
python -m nowing_evals ingest chat regression
python -m nowing_evals run chat regression --search-space-id <SEARCH_SPACE_ID> --profile quick --environment local --concurrency 1
python -m nowing_evals run chat regression --search-space-id <SEARCH_SPACE_ID> --profile full --tags deep-research --modes speed,balanced,quality,auto --timeout 600 --environment local --concurrency 1
python -m nowing_evals report --suite chat
```

## Known limitations / next steps

- `chat/regression` uses a **synthetic default dataset** (no PII risk). The production query sampler from Story `4-8c` exists; it is not yet the default and must be ingested manually with `--dataset`.
- Keyword matching (`expected_contains`) is a cheap proxy, not an LLM judge. Story `4-8d` (`chat/quality`) is still `ready-for-dev` and not present.
- CI integration from Story `4-8e` is implemented (`.github/workflows/chat-regression-gate.yml`); the gate is dry-run until `gate.yaml` has `baseline_ratified: true`.
- `NowingArm` only supports `mentioned_document_ids`; folder/connector/thread mentions are follow-up.

## Code status note

Implemented and merged. `ChatRegressionBenchmark` is registered, the `chat/regression` runner passes `mode` from the requested mode matrix into `NewChatRequest.mode` via `NowingArm` (`nowing_evals/src/nowing_evals/core/arms/nowing.py:68`), and the default per-turn `--timeout` is 600s (`runner.py:583`, `new_chat.py:132`). It records per-turn latency/TTFB, token/cost, citations, finish status, multi-turn `turns`, and operational stability metrics. Gate evaluation, cost-cap, notification, and `--fail-on-unratified` are wired. Unit tests (`tests/suites/chat/test_regression.py`, `tests/suites/chat/test_operational.py`) pass. Gaps: `chat/quality` (Story 4-8d) is not implemented; the default dataset remains synthetic; `baseline_ratified` is still `false`.

## References

- `_bmad-output/implementation-artifacts/4-8a-extend-new-chat-client-telemetry.md`
- `_bmad-output/planning-artifacts/sprint-change-proposal-2026-08-04-chat-response-benchmark.md`
- `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py`
- `nowing_evals/src/nowing_evals/suites/research/chainlens_latency/runner.py` (pattern reference)
