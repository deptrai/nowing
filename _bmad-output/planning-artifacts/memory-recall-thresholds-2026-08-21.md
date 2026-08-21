---
title: "Memory Recall Thresholds"
date: 2026-08-21
status: PROPOSED
owner: QA / Memory Team
oracle_version: 0.1.0
---

# Memory Recall Thresholds

## Baseline measurement

| Metric | Candidate threshold | Baseline measured | Wilson CI (95%) | Verdict |
|---|---|---|---|---|
| `precision@5` | ≥ 0.80 | TBD | TBD | TBD |
| `noise_rate` | ≤ 0.10 | TBD | TBD | TBD |
| `MRR` | ≥ 0.70 | TBD | TBD | TBD |
| `nDCG@5` | ≥ 0.75 | TBD | TBD | TBD |

## Oracle

- Path: `nowing_evals/datasets/memory-recall-oracle/`
- Format: `query, expected_memory_ids[], noise_memory_ids[]`
- Maintenance: human review quarterly or khi model/method thay đổi.

## CI gate wiring

- `nowing_evals run memory recall --profile ci`
- Regression fail nếu bất kỳ metric nào dưới threshold.
- Missing threshold/oracle → `QualityBenchmarkConfigError`.

## Notes

- Candidate thresholds là điểm khởi đầu; phải baseline trước khi ratify.
- Sau khi baseline có số thật, cập nhật bảng trên và đổi `status: RATIFIED`.
