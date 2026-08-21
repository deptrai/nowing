---
title: "AD-46 — Recall Precision / Noise Threshold Ratification"
status: ADOPTED
date: 2026-08-21
owner: Architecture / QA
binds: FR-99, AR-15, NFR-8, Story 3.18
---

# AD-46 — Recall Precision / Noise Threshold Ratification

## Context

`nowing_recall` cần trả facts liên quan và không trả hallucination/noise. Story 3.18 chốt ngưỡng precision/noise trên `nowing_evals` trước khi mở rộng auto-extract. Cần một quy trình ratification để threshold có cơ sở dữ liệu.

## Decision

### Metrics

- `precision@k`: tỉ lệ top-k recalled memory được oracle đánh là relevant.
- `noise_rate`: tỉ lệ memory trả về bị oracle đánh là không hỗ trợ câu hỏi hoặc contradictory.
- `MRR`, `nDCG`, `Wilson CI`: giữ nguyên từ `memory-recall` eval suite.

### Oracle dataset

- Tập `nowing_evals/datasets/memory-recall-oracle/` gồm `(query, expected_memory_ids, noise_memory_ids)`.
- Oracle được duy trì như một artifact trong repo `_bmad-output/evals/memory-recall-oracle/`.
- Human review định kỳ để cập nhật oracle khi model/method thay đổi.

### Threshold document

- File `_bmad-output/planning-artifacts/memory-recall-thresholds-2026-08-21.md` là single source of truth.
- Chứa: `precision@5_threshold`, `noise_rate_threshold`, `mrr_threshold`, `ndcg_threshold`, `confidence_level`, `baseline_measured_at`, `oracle_version`.
- Candidate ban đầu: `precision@5 ≥ 0.80`, `noise_rate ≤ 0.10` — chỉ là starting point; baseline measurement sẽ điều chỉnh.

### CI gate

- `nowing_evals` chạy `memory recall` suite trên `pull_request` hoặc `nightly`.
- Nếu metric vượt ngưỡng thì `pass`; regression → `fail` với diff metric deltas và link đến oracle.
- Missing threshold/oracle → raise `QualityBenchmarkConfigError`, không silently pass.

### Noise handling

- Runtime `nowing_recall` có thể dùng threshold như filter: bỏ memory có score < `noise_score_cutoff`.
- `noise_flag` được log để audit.

## Consequences

- **Positive:** Ngăn "AI guessing" xuất hiện trong recall.
- **Positive:** CI gate objective, reproducible.
- **Negative:** Oracle maintenance tốn công.
- **Risk:** Threshold quá cao có thể làm recall trả ít kết quả; cần baseline trước khi chốt.
