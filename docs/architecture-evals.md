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
| `src/nowing_evals/core/clients/` | HTTP clients (`NewChatClient`, `SearchSpaceClient`, `DocumentsClient`, `MemoriesClient`) |
| `src/nowing_evals/core/arms/` | Arms (`NowingArm`, `NativePdfArm`, `BareLlmArm`) |
| `src/nowing_evals/suites/` | Benchmark suites (medical/, multimodal_doc/, research/, memory/, chat/) |
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
- `research/chainlens_latency` – Deep-research p50/p95 e2e + TTFB
- `memory/recall` – Workspace memory recall quality
- `chat/regression` – Chat response regression (latency, cost, citations, keyword match) [4.8b]
- `chat/quality` (Phase 2) – LLM-as-judge chat quality [4.8d]

## Telemetry flow

`NewChatClient._consume_sse` parses Vercel AI SDK SSE frames (`text-delta`, `data-token-usage`, `data-turn-info`, `data-user/assistant-message-id`) and exposes them in `StreamedAnswer`. `NowingArm` maps them into `ArmResult` so all chat suites can record tokens, cost, TTFB, turn id, and citations.

---

_Tài liệu được tạo bởi BMAD Method `document-project` workflow_
