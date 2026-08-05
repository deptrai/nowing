---
baseline_commit: 412200504
baseline_branch: develop
story_key: 4-8g-benchmark-mode-tier-matrix-local-prod
status: review
---

# Story 4.8g: Benchmark mode/tier matrix and local vs production parity

**Status:** review  
**Epic:** 4 — Chat & Agents  
**Priority:** MEDIUM  
**Requirements:** FR-42, NFR-9, NFR-10  
**Architecture:** `nowing_evals` harness, `AD-15`

## Story

As a release engineer,
I want `nowing_evals` to run queries across all Nowing/ChainLens modes and query tiers, and to compare local dev results against production,
So that small changes and big updates are validated on the right surface area before deploy.

## Context

- `4-8b` đã tạo `chat/regression` nhưng chỉ chạy một mode mặc định.
- `4-8f` sẽ thêm stability metrics.
- **Gap:** benchmark chưa:
  - Chạy matrix `speed` × `balanced` × `quality` × `auto` trên cùng query.
  - Phân tier theo độ phức tạp query (short/long context, single/multi-tool).
  - So sánh local dev (có thể crawl mock) với production (real engine/crawl).
  - Phân biệt gate cho small changes (nhanh, ít case) vs big updates (đầy đủ matrix, nhiều case).

`4-8g` tập trung vào test matrix và environment parity.

## Acceptance Criteria

### AC1 — Mode matrix

- **Given** a dataset case,
  **When** `python -m nowing_evals run chat regression --modes speed,balanced,quality,auto` runs,
  **Then** it replays the same query for each mode and records per-mode latency, TTFB, cost, citation count, and finish status.

### AC2 — Tier tagging

- **Given** a dataset with `tier` field (e.g., `short`, `long_context`, `multi_tool`),
  **When** the run finishes,
  **Then** the report shows `per_mode × per_tier` p50/p95 latency, cost, citation count, and error rate.

### AC3 — Local vs production parity

- **Given** `--environment local` or `--environment production`,
  **When** the run finishes,
  **Then** `run_artifact.json` tags each case with `environment`, and the report can surface `local_prod_delta` for latency/cost/citations if both environments have run artifacts.

### AC4 — Small-change vs big-update modes

- **Given** the CLI flag `--profile quick`,
  **When** it runs,
  **Then** it uses a small subset (e.g., 1 case per tag, 1 mode) for fast local validation.
- **Given** the CLI flag `--profile full`,
  **When** it runs,
  **Then** it runs the full mode × tier matrix across production-like concurrency.

### AC5 — Research latency mode matrix

- **Given** `python -m nowing_evals run research chainlens_latency --modes speed,balanced,quality`,
  **When** it runs,
  **Then** it records p50/p95 e2e and TTFB per mode and compares against `gate.yaml` thresholds.

### AC6 — Gate per mode/tier

- **Given** `gate.yaml` with thresholds under `per_mode` and `per_tier`,
  **When** any mode/tier violates its threshold,
  **Then** the run exits non-zero and the report highlights the failing mode/tier.

### AC7 — Docs benchmark

- **Given** the story is done,
  **When** a release engineer reads `docs/benchmark.md`,
  **Then** they understand how to pick mode/tier matrix, run `--profile quick` for PR validation and `--profile full` for pre-release, and compare local vs production.

## Tasks / Subtasks

### Runner changes

- [x] Add `--modes` and `--tier` flags to `chat/regression` and `research/chainlens_latency` runners.
- [x] Extend dataset schema to accept `tier` and `modes` (optional override per case).
- [x] For each case, run once per requested mode; thread is created per (case, mode).
- [x] Aggregate metrics by `(mode, tier, tag)` in addition to `(tag)`.
- [x] Add `--environment` flag; write `environment` into `run_artifact.json`.
- [x] Add `--profile quick|full` presets:
  - `quick`: 1 mode, 1 case/tag, concurrency 1.
  - `full`: all modes, all tiers, configured concurrency.
- [x] Extend `report_section` to render mode × tier tables and local/prod delta.
- [x] Extend `gate.yaml` schema to support `per_mode` and `per_tier` thresholds.

### Tests

- [x] Unit tests for mode matrix aggregation.
- [x] Unit tests for tier tagging.
- [x] Unit tests for `--profile quick`/`--profile full` preset expansion.
- [x] Respx-mocked test for multi-mode run.

### Docs

- [x] Create/update `docs/benchmark.md` with:
  - Benchmark suite inventory (`chat/regression`, `chat/quality`, `research/chainlens_latency`, medical, multimodal_doc, memory).
  - Mode/tier matrix guide.
  - Local vs production usage.
  - `--profile quick` vs `--profile full`.
  - Gate thresholds and how to ratify baseline.

## Verification

```bash
cd nowing_evals
python -m nowing_evals benchmarks list
python -m nowing_evals run chat regression --search-space-id 42 --modes speed,balanced --profile quick --environment local --concurrency 1 --timeout 600
python -m nowing_evals run chat regression --search-space-id 42 --modes speed,balanced,quality,auto --profile full --environment local --concurrency 4 --timeout 600
python -m nowing_evals run research chainlens_latency --modes speed,balanced,quality --workspace-id <WORKSPACE_ID> --n 3
python -m nowing_evals report --suite chat
python -m nowing_evals report --suite research --benchmark chainlens_latency
ruff check src/nowing_evals/suites/chat/regression/ src/nowing_evals/suites/research/chainlens_latency/ tests/suites/chat/test_regression.py tests/suites/chat/test_operational.py
python -m pytest tests/suites/chat/test_regression.py tests/suites/chat/test_operational.py -q
```

## Gate thresholds (provisional)

Current `src/nowing_evals/suites/chat/regression/gate.yaml`:

```yaml
per_mode:
  speed:
    max_p95_e2e_ms: 15000
    max_p95_cost_micros: 50000
  balanced:
    max_p95_e2e_ms: 30000
    max_p95_cost_micros: 100000
  quality:
    max_p95_e2e_ms: 60000
    max_p95_cost_micros: 200000
  auto:
    max_p95_e2e_ms: 30000
    max_p95_cost_micros: 100000
per_tier:
  short:
    max_p95_e2e_ms: 15000
  long_context:
    max_p95_e2e_ms: 45000
  multi_tool:
    max_p95_e2e_ms: 60000
```

`baseline_ratified: false` until measured.

## Code status note

Implemented and merged. `chat/regression` (`runner.py`) and `research/chainlens_latency` (`runner.py`) both accept `--modes`, `--tier`, `--environment`, and `--profile quick|full`. The `chat/regression` runner passes each requested `mode` into `NewChatRequest.mode` (`arms/nowing.py:68`) and uses a 600s per-turn timeout (`new_chat.py:132`, `runner.py:583`). For each (case, mode) pair a fresh thread is created; multi-turn `turns` reuse the same thread. Metrics are aggregated into `per_tag`, `per_mode`, `per_tier`, and `per_mode_tier` buckets, and the report renders a `local vs production parity` delta table when both environments have run artifacts. `chat/regression/gate.yaml` and `research/chainlens_latency/gate.yaml` contain provisional `per_mode` thresholds. `docs/benchmark.md` documents the matrix and parity features. `chat/quality` is listed as a planned suite but is not implemented (Story 4-8d is `ready-for-dev`).

## References

- `_bmad-output/implementation-artifacts/4-8b-chat-regression-suite.md`
- `_bmad-output/implementation-artifacts/4-8f-benchmark-stability-scrape-captcha-rate-limit.md`
- `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py`
- `nowing_evals/src/nowing_evals/suites/chat/regression/gate.yaml`
- `nowing_evals/src/nowing_evals/suites/research/chainlens_latency/runner.py`
- `nowing_evals/src/nowing_evals/suites/research/chainlens_latency/gate.yaml`
- `_bmad-output/implementation-artifacts/9-3-latency-budget-state-a-b-gate.md`
