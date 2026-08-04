---
baseline_commit: 412200504
baseline_branch: develop
story_key: 4-8f-benchmark-stability-scrape-captcha-rate-limit
status: done
---

# Story 4.8f: Benchmark stability — scrape, captcha, rate-limit, and multi-turn

**Status:** done  
**Epic:** 4 — Chat & Agents  
**Priority:** HIGH  
**Requirements:** FR-42, NFR-10  
**Architecture:** `nowing_evals` harness, `AD-15` (nếu benchmark gọi ChainLens)

## Story

As a release engineer,
I want `nowing_evals` to measure scrape/search stability, captcha/rate-limit resilience, and multi-turn session health,
So that we can detect when external search, crawl, or tool providers degrade before users feel it in production.

## Context

- `4-8a`/`4-8b` đã xây `chat/regression` với metrics cơ bản: latency, TTFB, tokens, cost, citations, finish status.
- `4-8c` sẽ lấy production queries để dataset thực hơn.
- `4-8d` sẽ đánh giá chất lượng câu trả lời bằng LLM judge.
- `4-8e` sẽ gắn gate vào CI.
- **Gap hiện tại:** `chat/regression` không đo được:
  - Tỷ lệ scrape/search thành công hay thất bại.
  - Lý do thất bại (captcha, rate-limit, timeout, 5xx, parse error).
  - Multi-turn liên tục có bị lỗi tích lũy, context rút ngắn, hay tool call drop.
  - Cường độ cao có làm engine/provider treo hay không.

`4-8f` tập trung vào các stability/operational metrics trên cả `chat/regression` và `research/chainlens_latency`.

## Acceptance Criteria

### AC1 — Scrape / search success rate

- **Given** a benchmark run against a query that triggers web search / crawling,
  **When** the run finishes,
  **Then** the report shows `scrape_success_rate`, `scrape_attempts`, `scrape_failures` per case and per tag.

### AC2 — Failure reason classification

- **Given** a scrape or tool call that fails,
  **When** the error is captcha, rate-limit, timeout, 5xx, or parse error,
  **Then** the runner records the reason and the report shows `captcha_rate`, `rate_limited_rate`, `timeout_rate`, `server_error_rate`, `parse_error_rate`.

### AC3 — Multi-turn stability

- **Given** a benchmark case with `turns > 1` in the dataset,
  **When** the runner executes the case,
  **Then** it creates one thread and sends `turns` sequential messages, recording:
  - per-turn latency and TTFB,
  - per-turn `citation_count`,
  - `turn_error_rate`,
  - `context_drift_score` (keyword match across turns, or later-turn `expected_contains` hit rate vs first turn).

### AC4 — High-intensity stress option

- **Given** a `--concurrency N` flag with `N > 1` and/or `--threads M` with `M > 1`,
  **When** the runner executes,
  **Then** it runs cases/threads in parallel and reports:
  - `p95_latency_under_load_ms`,
  - `error_rate_under_load`,
  - `rate_limited_rate_under_load`,
  - `engine_unavailable_rate`.

### AC5 — Tool drop rate per tool

- **Given** a `done` frame with `call_details` or tool-call events,
  **When** the runner parses the SSE stream,
  **Then** it records `tool_attempts`, `tool_successes`, `tool_drop_rate` per tool name (e.g., `web_search`, `chainlens.research`, `memory`, `document`).

### AC6 — Operational metrics in `run_artifact.json`

- **Given** any benchmark run,
  **When** it finishes,
  **Then** `run_artifact.json` includes a new `operational` section with all metrics above plus `fallback_kb_hits`, `degradation_reason` distribution, and `engine_unavailable_rate`.

### AC7 — Report table

- **Given** `python -m nowing_evals report --suite chat`,
  **When** the report renders,
  **Then** it includes an "Operational / Stability" table per tag with the new metrics.

## Tasks / Subtasks

### Backend / runner changes

- [x] Extend `NowingArm` / `NewChatClient` to capture and surface `call_details` and `raw_events` from `data-token-usage` frames.
- [x] Parse raw SSE events to extract per-tool success/failure, dropouts, and failure reasons.
- [x] Add scrape/search result classification:
  - Detect `captcha` / `rate_limit` / `timeout` / `5xx` / `parse_error` from SSE `error` frames, terminal info, and tool output.
- [x] Update `ChatRegressionBenchmark._aggregate` and `report_section` to compute and render operational metrics (scrape success rate, tool drop rate, failure reason rates, engine unavailable, fallback KB hits).
- [x] Add multi-turn dataset support:
  - JSONL schema field `turns: list[{query, expected_contains}]`.
  - Runner reuses one thread for all turns in a case and records per-turn latency, TTFB, citations, keyword hits, `turn_error_rate`, and `context_drift_score`.
- [x] Add high-intensity flags:
  - `--concurrency` (already exists) documented for stress.
  - `--threads` to create multiple parallel chat threads.
  - Operational "under load" metrics (`p95_latency_under_load_ms`, `error_rate_under_load`, `rate_limited_rate_under_load`, `engine_unavailable_rate`).
- [x] Extend `research/chainlens_latency` runner to record `sources_partial_rate`, `engine_unavailable_rate`, `degraded_rate`, `degradation_reason_counts`, `fallback_kb_hits`, and `mean_cost_micros`.

### Tests

- [x] Unit tests for call_details/fallback extraction with synthetic payloads.
- [x] Unit tests for failure-reason classification.
- [x] Unit tests for tool-attempt/drop aggregation.
- [x] Unit tests for multi-turn case loading / validation.
- [ ] Respx/httpx-mocked test for high-concurrency error rate (deferred — covered by aggregate unit tests and `--threads` arg wiring).

### Docs

- [x] Update `nowing_evals/README.md` "Chat response regression" and "ChainLens research latency" sections with new metrics.
- [x] Add `docs/benchmark-stability.md` explaining stability metrics, how to run multi-turn and stress modes, and how to read the report.
- [x] Add stability thresholds to `chat/regression/gate.yaml` and `research/chainlens_latency/gate.yaml`.

## Verification

```bash
cd nowing_evals
ruff check src/nowing_evals/core/clients/new_chat.py src/nowing_evals/core/arms/nowing.py src/nowing_evals/suites/chat/regression/runner.py
ruff format ...
python -m pytest tests/suites/chat/test_regression.py tests/suites/chat/test_operational_metrics.py -q
python -m nowing_evals run chat regression --search-space-id 42 --concurrency 1 --dataset multi-turn-sample.jsonl
python -m nowing_evals report --suite chat
```

## Gate thresholds (provisional)

Add to `src/nowing_evals/suites/chat/regression/gate.yaml`:

```yaml
max_scrape_drop_rate: 0.10
max_rate_limited_rate: 0.05
max_tool_drop_rate: 0.05
max_turn_error_rate: 0.05
max_engine_unavailable_rate: 0.01
```

`baseline_ratified: false` until measured.

## References

- `_bmad-output/implementation-artifacts/4-8a-extend-new-chat-client-telemetry.md`
- `_bmad-output/implementation-artifacts/4-8b-chat-regression-suite.md`
- `nowing_evals/src/nowing_evals/core/clients/new_chat.py`
- `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py`
- `nowing_evals/src/nowing_evals/suites/chat/regression/gate.yaml`
- `nowing_evals/src/nowing_evals/suites/research/chainlens_latency/runner.py`
