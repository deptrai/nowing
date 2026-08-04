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

- `nowing_evals/src/nowing_evals/suites/chat/__init__.py`
- `nowing_evals/src/nowing_evals/suites/chat/regression/__init__.py`
- `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py`
- `nowing_evals/src/nowing_evals/suites/chat/regression/gate.yaml`

### Runner features

- `ChatRegressionBenchmark` registered with `suite="chat"`, `name="regression"`.
- `requires_suite_setup = False`; requires `--search-space-id` at run time.
- `add_run_args`: `--search-space-id`, `--workspace-id`, `--dataset`, `--n`, `--concurrency`, `--tags`, `--timeout`, `--backend-build-id`.
- `ingest()`: validates dataset rows have `case_id` and `query`; writes `cases.jsonl`.
- `run()`: loads cases, filters by `--tags`, runs via `NowingArm`, handles `TimeoutError`, writes `raw.jsonl` and `run_artifact.json`.
- `report_section()`: markdown table per tag + overall summary.

### Metrics

- `overall`: samples, n_failed, error_rate, p50/p95 e2e, p50/p95 ttfb, p50/p95 cost, total cost, p50/p95 citation count, mean total tokens, keyword match rate.
- `per_tag`: same metrics grouped by `tags`.

### Dataset

- Default sample 5 cases covering `memory`, `document`, `deep-research`, `multi-tool`, `creative`.
- JSONL schema: `case_id`, `query`, `tags`, `mentioned_document_ids`, `disabled_tools`, `expected_contains`.

### Docs

- `nowing_evals/README.md` updated with benchmark table and usage section.

## Verification

```bash
cd nowing_evals
python -m nowing_evals benchmarks list
python -m nowing_evals ingest chat regression --help
python -m nowing_evals run chat regression --help
ruff check src/nowing_evals/suites/chat/
ruff format src/nowing_evals/suites/chat/
python -m pytest tests/core/test_clients.py -q
```

To run against a real backend:

```bash
python -m nowing_evals ingest chat regression
python -m nowing_evals run chat regression --search-space-id <SEARCH_SPACE_ID> --concurrency 1
```

## Known limitations / next steps

- `chat/regression` uses a **synthetic default dataset** (no PII risk). Story `4-8c` will add the production query sampler + anonymizer.
- Keyword matching (`expected_contains`) is a cheap proxy, not an LLM judge. Story `4-8d` will add `chat/quality` with LLM-as-judge.
- No CI integration yet. Story `4-8e` adds the deploy gate step.
- `NowingArm` only supports `mentioned_document_ids`; folder/connector/thread mentions are follow-up.

## References

- `_bmad-output/implementation-artifacts/4-8a-extend-new-chat-client-telemetry.md`
- `_bmad-output/planning-artifacts/sprint-change-proposal-2026-08-04-chat-response-benchmark.md`
- `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py`
- `nowing_evals/src/nowing_evals/suites/research/chainlens_latency/runner.py` (pattern reference)
