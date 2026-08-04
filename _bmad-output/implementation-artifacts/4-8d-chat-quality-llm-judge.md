---
baseline_commit: e3de8a948
baseline_branch: develop
story_key: 4-8d-chat-quality-llm-judge
status: ready-for-dev
---

# Story 4.8d: Chat quality benchmark with LLM-as-judge

**Status:** ready-for-dev  
**Epic:** 4 — Chat & Agents  
**Priority:** MEDIUM  
**Requirements:** FR-42  

## Story

As an ML/QA engineer,
I want a `chat/quality` benchmark that scores each answer against a reference/rubric using a strong judge model,
So that we can measure answer correctness, citation faithfulness, and completeness beyond simple regression signals.

## Context

- `chat/regression` (4.8b) detects **regression** (latency, cost, error rate, citations, keyword match).
- It cannot detect **quality drift** such as answers becoming less accurate, more hallucinated, or missing citations.
- `chat/quality` (Phase 2) is a labeled, reference-based benchmark run weekly or pre-release, not every deploy.
- The Nowing harness already has `OpenRouterPdfProvider`, `BareLlmArm`, and `NativePdfArm` for OpenRouter calls.

## Acceptance Criteria

1. **Dataset with reference/rubric**
   - **Given** a JSONL dataset of curated cases,  
     **When** `python -m nowing_evals ingest chat quality` runs,  
     **Then** it validates every row has `case_id`, `query`, `reference_answer`, `rubric`, and optional `tags`.

2. **Judge model call**
   - **Given** a Nowing answer and a reference,  
     **When** `chat/quality` runs,  
     **Then** it calls an OpenRouter judge model with a structured prompt and parses `correctness`, `citation_faithfulness`, `completeness`, and `harmfulness` scores (1–5).

3. **Cost and latency tracking**
   - **Given** a judge call,  
     **When** it returns,  
     **Then** `chat/quality` records the judge's `cost_micros` and `latency_ms` in the run artifact.

4. **Per-tag aggregation**
   - **Given** the scored cases,  
     **When** the run finishes,  
     **Then** metrics are aggregated by `tags` and overall.

5. **Gate**
   - **Given** `gate.yaml` with `min_mean_correctness`,  
     **When** overall `mean_correctness` is below the threshold,  
     **Then** the run exits non-zero (or the report highlights failure).

## Tasks / Subtasks

### New suite `chat/quality`

- [ ] Create `nowing_evals/src/nowing_evals/suites/chat/quality/__init__.py` and `runner.py`.
- [ ] Register `ChatQualityBenchmark` with `suite="chat"`, `name="quality"`.
- [ ] Dataset schema:
   ```jsonl
   {"case_id": "q-001", "query": "...", "reference_answer": "...", "rubric": "...", "tags": ["memory"], "mentioned_document_ids": [123]}
   ```
- [ ] `ingest` validates JSONL and copies to `data/chat/quality/cases.jsonl`.
- [ ] `run`:
   - Load cases.
   - For each case, call `NowingArm` to get the Nowing answer (reuse `NewChatClient` from 4.8a).
   - Build a judge prompt with query, reference, rubric, and answer.
   - Call OpenRouter judge model (configurable via `--judge-model`, default `anthropic/claude-sonnet-4.5`).
   - Parse JSON response for `correctness`, `citation_faithfulness`, `completeness`, `harmfulness` (1–5 or 0–1).
   - Record raw, scores, cost, latency.
- [ ] `report_section` shows overall + per-tag mean scores, judge model, cost.
- [ ] `gate.yaml` with `min_mean_correctness: 3.5`, `min_citation_faithfulness: 3.0`, etc.

### Judge prompt & parser

- [ ] Create `nowing_evals/src/nowing_evals/suites/chat/quality/prompt.py` with a structured prompt template.
- [ ] Use `response_format: { "type": "json_object" }` if the model supports it; otherwise fallback to regex JSON extraction.
- [ ] Validate parsed fields and default to `0` on parse failure.

### Metrics

- [ ] `mean_correctness`, `mean_citation_faithfulness`, `mean_completeness`, `mean_harmfulness`.
- [ ] `p50_judge_latency_ms`, `p95_judge_latency_ms`.
- [ ] `total_judge_cost_micros`.

### Tests

- [ ] Unit tests for judge prompt rendering and JSON parsing.
- [ ] Unit tests for metric aggregation.
- [ ] Respx-mocked test for the judge API call.

## Verification

```bash
cd nowing_evals
python -m nowing_evals benchmarks list | grep chat
ruff check src/nowing_evals/suites/chat/quality/ tests/suites/chat/test_quality.py
ruff format src/nowing_evals/suites/chat/quality/ tests/suites/chat/test_quality.py
python -m pytest tests/suites/chat/test_quality.py -q
```

## References

- `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py`
- `nowing_evals/src/nowing_evals/core/providers/openrouter.py` (if exists) or `OpenRouterPdfProvider`
- `nowing_evals/src/nowing_evals/core/arms/nowing.py`
- `_bmad-output/implementation-artifacts/4-8b-chat-regression-suite.md`
