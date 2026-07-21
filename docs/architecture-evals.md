# Kiến trúc - Nowing Evals

**Ngày tạo:** 2026-07-21 16:59:34

## Tóm tắt

Evaluation harness domain-agnostic để benchmark Nowing. Các benchmark tự đăng ký qua registry.

## Tech Stack

| Thành phần | Công nghệ |
|---|---|
| Runtime | Python 3.12 |
| CLI | `nowing-evals` (entry `nowing_evals.core.cli:main`) |
| Libraries | datasets, huggingface_hub, scikit-learn, scipy, pydantic, rich, httpx |
| Test | pytest |

## Cấu trúc

| Thư mục | Mục đích |
|---|---|
| `src/nowing_evals/core/` | CLI, registry, HTTP clients, arms, parsers, metrics, report writer |
| `src/nowing_evals/suites/` | Benchmark suites (medical/, multimodal_doc/) |
| `data/` | Datasets, rendered PDFs, run outputs |
| `reports/` | Báo cáo tổng hợp |
| `scripts/` | Phân tích và hỗ trợ |

## Entry point

`python -m nowing_evals` hoặc `nowing-evals`.

## Các benchmark hiện có

- `medical/medxpertqa` – Native PDF vs Nowing head-to-head MCQ (vision)
- `medical/mirage` – Nowing single-arm MCQ
- `medical/cure` – Nowing single-arm retrieval (Recall/MRR/nDCG)
- `multimodal_doc/mmlongbench` – Long PDFs với hình ảnh, charts, tables

---

_Tài liệu được tạo bởi BMAD Method `document-project` workflow_
