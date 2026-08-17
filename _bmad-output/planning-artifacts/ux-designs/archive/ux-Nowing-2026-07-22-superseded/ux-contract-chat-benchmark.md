# UX Contract — Chat Response Benchmark

**Ngày:** 2026-08-05
**Phạm vi:** UX cho `nowing_evals` CLI / dashboard hiển thị kết quả benchmark chat (FR-42, NFR-10).
**Bám vào:** FR-42 · NFR-10 · Stories 4.8a–4.8g
**Loại tài liệu:** *contract* — định nghĩa trạng thái UI/CLI phải biểu diễn được.

---

## 1. Bài toán UX

`nowing_evals run chat regression` chạy trên tập query đại diện, đo p50/p95 latency, TTFB, error rate, finish rate, citation count, cost/turn. Kết quả cần dễ đọc và dễ so sánh baseline.

Hệ quả UX:
- CLI không thể hiển thị bảng dài không có màu sắc phân loại drift.
- Dashboard cần thấy rõ tag nào đang regression và chi phí/turn theo mode.

## 2. Contract — các trạng thái UI bắt buộc

| # | Trạng thái | Bắt buộc |
|---|---|---|
| B1 | **Run summary** — tổng số case, pass/fail, drift so với baseline | ✅ |
| B2 | **Per-tag metrics** — memory, document, deep-research, multi-tool, creative; mỗi tag có p95 latency, TTFB, error rate, finish rate, citation count, cost/turn | ✅ |
| B3 | **Per-mode matrix** — speed/balanced/quality/auto với p50/p95/p99 latency + cost | ✅ |
| B4 | **Drift indicator** — màu/threshold khi vượt baseline (ví dụ p95 latency > X% hoặc citation count giảm > Y%) | ✅ |
| B5 | **Local vs prod parity** — so sánh cùng query chạy local và production | ✅ |
| B6 | **Gate status** — `baseline_ratified: true/false`, `--fail-on-unratified` block message | ✅ |
| B7 | **Cost extraction** — hiển thị cost/turn theo model/capability, bao gồm deep-research `costDollars` | ✅ |

## 3. Ràng buộc kỹ thuật UX

- Dữ liệu từ `NewChatClient` telemetry (`StreamedAnswer`: `ttfb_ms`, `turn_id`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_micros`, `model_breakdown`, `call_details`).
- `nowing_evals report --suite chat` render markdown/CLI table.
- CI gate hiển thị fail reason rõ ràng khi `chat/regression` drift.

## 4. Truy vết

- Chặn: stories 4.8a–4.8g
- Phụ thuộc: `nowing_evals/core/clients/new_chat.py`, `nowing_evals/suites/chat/regression/`
