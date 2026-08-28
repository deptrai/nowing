---
title: "Memory Recall Thresholds"
date: 2026-08-21
status: RATIFIED
owner: QA / Memory Team
oracle_version: 0.1.0
baseline_run: "2026-07-28T16-28-54Z"
---

# Memory Recall Thresholds

## Baseline measurement (Ratified 2026-08-28 against run `2026-07-28T16-28-54Z`)

| Metric | Ratified threshold | Baseline measured | Wilson CI (95%) | Verdict |
|---|---|---|---|---|
| `recall@5` | ≥ 0.90 | 0.986 | [0.924, 0.998] | PASS |
| `MRR` | ≥ 0.70 | 1.000 | [0.903, 1.000] | PASS |
| `nDCG@5` | ≥ 0.75 | 0.995 | [0.962, 1.000] | PASS |
| `distractor_noise_rate` | ≤ 0.10 | 0.067 | [0.031, 0.138] | PASS |
| `off_corpus_rate` | ≤ 0.05 | 0.033 | [0.013, 0.083] | PASS |
| `precision@1` | ≥ 0.85 | 1.000 | [0.903, 1.000] | PASS |
| `precision@5` (diagnostic) | N/A (known-item bound ~0.20-0.40) | 0.228 | [0.173, 0.294] | PASS |
| `noise_rate` (diagnostic) | N/A (1 - precision@5) | 0.772 | [0.706, 0.827] | PASS |

## Oracle

- Path: `nowing_evals/src/nowing_evals/suites/memory/recall/dataset/` (`corpus.jsonl`, `queries.jsonl`)
- Format: `query, expected_memory_ids[], distractors[]`
- Maintenance: human review quarterly or khi model/retrieval engine thay đổi.

## CI gate wiring

- Gate config: `nowing_evals/src/nowing_evals/suites/memory/recall/gate.yaml`
- Command: `python -m nowing_evals gate --suite memory --benchmark recall`
- CI workflow: `.github/workflows/eval-memory-recall-gate.yml`
- Regression fail nếu bất kỳ metric nào vi phạm threshold hoặc không đạt số lượng mẫu tối thiểu.
- Missing threshold/oracle → `GateConfigError` (fail-closed, không silently pass).

## Notes

- Ratified against live run artifact `nowing_evals/data/memory/runs/2026-07-28T16-28-54Z/recall/run_artifact.json`.
- Dataset là known-item retrieval (1-2 relevant memories/query trên 36-memory corpus) nên `precision@5` bị chặn trên bởi `|relevant|/5 = 0.20-0.40`. Gate chuyển sang dùng `distractor_noise_rate` (share labeled distractors ≤ 0.10) và `off_corpus_rate` (≤ 0.05) theo quyết định Story 3.9 DEC-1 / DEC-4 & Story 3.18.
