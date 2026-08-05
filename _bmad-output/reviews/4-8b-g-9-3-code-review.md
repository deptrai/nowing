# Code Review — Stories 4.8b–4.8g & 9.3 (benchmark round 2)

## Tóm tắt thực hiện (Review Run Info)

- **Phạm vi review:**
  - `nowing_evals/src/nowing_evals/suites/research/chainlens_latency/runner.py`
  - `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py`
  - `nowing_evals/src/nowing_evals/suites/chat/regression/operational.py`
  - `nowing_evals/src/nowing_evals/core/clients/new_chat.py`
  - `nowing_evals/src/nowing_evals/core/arms/nowing.py`
  - `nowing_evals/src/nowing_evals/core/notifications.py`
  - `nowing_evals/src/nowing_evals/core/cli.py`
  - `nowing_backend/app/capabilities/chainlens/research/executor.py`
  - `nowing_backend/app/capabilities/chainlens/research/schemas.py`
  - `nowing_backend/app/capabilities/core/access/agent.py`
  - `nowing_backend/app/capabilities/core/access/rate_limit.py`
  - `nowing_backend/app/services/token_tracking_service.py`
  - `nowing_backend/app/schemas/new_chat.py`
  - `nowing_backend/app/routes/new_chat_routes.py`
  - `nowing_backend/app/gateway/agent_invoke.py`
- **Lớp review đã áp dụng:** Blind Hunter, Edge Case Hunter, Acceptance Auditor.
- **Baseline diff so với `main`:** Các thay đổi liên quan `NewChatRequest.mode`, `mode` propagation, deep-research cost/timeout, benchmark harness, telemetry client, và notification.
- **Kiểm tra tĩnh/động:**
  - `ruff check` trên `nowing_evals` và `nowing_backend` (các file trong scope) — pass.
  - `pytest tests/suites/chat/test_regression.py tests/suites/chat/test_operational.py` — 21 passed.
  - `pytest nowing_backend/tests/unit/capabilities/chainlens/research/test_chainlens_fixture_drift.py` — 2 passed, 1 skipped.

## Verdict

**CHANGES NOT APPROVED — cần sửa P0 trước khi mark `done`.**

Tổng hợp: **8 high**, **18 medium**, **23 low (patch)**, **2 decision-needed**, **5 defer**.
Các lỗi high phân bố đều ở cả `nowing_evals` benchmark harness và `nowing_backend` research executor, đặc biệt làm sai lệch TTFB, mode aggregation, và multi-turn. Nhiều medium/low về validation, telemetry coercion, gate wiring, và report completeness.

## Ảnh hưởng đến trạng thái story

| Story | Trạng thái cũ | Trạng thái mới | Lý do |
|---|---|---|---|
| 4-8b | `done` | `review` | Multi-turn, aggregate `turn_error_rate`, scrape drop/failure mismatch, token coercion, tag/tier filter, `_one_case_per_tag`. |
| 4-8d | `ready-for-dev` | `ready-for-dev` | Không có code mới để review (harness tồn tại, LLM-judge suite chưa implement). |
| 4-8e | `done` | `review` | Gate check thiếu `max_error_rate`, `max_p95_ttfb_ms`; thiếu warning khi `baseline_ratified: false`; `chainlens_latency` thiếu cost cap / `fail-on-unratified`. |
| 4-8f | `done` | `review` | Multi-turn bị xóa thread sau lượt đầu, operational metrics chưa aggregate đúng, scrape metric hardcoded. |
| 4-8g | `done` | `review` | Mode resolved bị đổ bucket, thiếu per-tier aggregation, report thiếu p50, `_one_case_per_tag` break sớm. |
| 9-3 | `done` (sprint-status) / `in-progress` (spec) | `in-progress` | `_parse_engine_ts` không parse epoch-ms, làm sai TTFB; mode chưa propagate qua regenerate/resume/gateway; sync path thiếu rate limit. |

*Các thay đổi trạng thái được phản ánh trong `sprint-status.yaml` và header của spec file.*

---

## 1. Bugs — P0 (High)

### H1 — `chainlens_latency` runner abort toàn bộ matrix khi một query lỗi

- **Mức độ:** cao
- **Nguồn:** Blind Hunter
- **Vị trí:** `nowing_evals/src/nowing_evals/suites/research/chainlens_latency/runner.py:253`, `:_call_research ~474-475`
- **Bằng chứng:**
  ```python
  results = await asyncio.gather(*(_run_one(q, m) for m in modes for q in queries))
  ```
  và `_call_research` `raise RuntimeError` khi `resp.status_code >= 400`.
- **Mô tả:** Một lỗi 429/500 hoặc JSON decode ở một ô `(query, mode)` sẽ dừng toàn bộ các ô còn lại. Benchmark mất dữ liệu partial và không sinh artifact.
- **Gợi ý sửa:** Dùng `return_exceptions=True` trong `asyncio.gather`, chuyển exception thành error row, tiếp tục các ô còn lại.

### H2 — `resolved_mode` divergence tạo bucket rỗng, gate có thể pass với `p95 = 0.0`

- **Mức độ:** cao
- **Nguồn:** Blind + Edge + Acceptance Auditor
- **Vị trí:** `nowing_evals/src/nowing_evals/suites/research/chainlens_latency/runner.py:236`, `:258-270`, `:_percentile ~118-131`, `:_evaluate_chainlens_gate ~88-115`
- **Bằng chứng:**
  ```python
  by_mode: dict[str, _ModeStats] = {m: _ModeStats() for m in modes}
  ...
  mode = resolved_mode or mode_requested
  ```
  `_percentile([])` trả về `0.0`.
- **Mô tả:** Nếu `speed` resolve thành `balanced`, bucket `speed` rỗng nhưng vẫn được đưa vào metrics; `_evaluate_chainlens_gate` không skip bucket rỗng, nên `speed` pass ngưỡng 15s với `p95 = 0.0`. `resolved_mode` cũng không validate với enum.
- **Gợi ý sửa:** Skip bucket rỗng hoặc fail; `_percentile([])` trả về `None`; validate `resolved_mode` thuộc allowed set.

### H3 — Multi-turn chat bị xóa thread ngay sau lượt đầu

- **Mức độ:** cao
- **Nguồn:** Blind + Acceptance Auditor
- **Vị trí:** `nowing_evals/src/nowing_evals/core/arms/nowing.py:79-86` và `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py:760-821`
- **Bằng chứng:**
  ```python
  should_delete = self._ephemeral and reused is None
  ```
  Lượt đầu `reused is None` -> xóa thread. Runner đọc `thread_id` từ `result.extra` rồi dùng cho lượt sau nhưng thread đã bị xóa.
- **Mô tả:** Vi phạm 4.8f AC3 (“creates one thread and sends `turns` sequential messages”). Multi-turn case hiện fail ở lượt 2.
- **Gợi ý sửa:** Trong vòng lặp multi-turn, runner set `options["delete_thread"] = False` và gọi `arm.delete_thread(thread_id)` sau khi tất cả lượt xong; hoặc dùng `ephemeral_threads=False` và quản lý lifecycle thủ công.

### H4 — `workspace_id` bị hardcode bằng `search_space_id`, flag `--workspace-id` không dùng

- **Mức độ:** cao
- **Nguồn:** Blind
- **Vị trí:** `nowing_evals/src/nowing_evals/core/clients/new_chat.py:97,145` và `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py:528-532,636,933`
- **Bằng chứng:**
  ```python
  "workspace_id": search_space_id,
  "search_space_id": search_space_id,
  ```
  Runner lưu `--workspace-id` vào `extra` nhưng không truyền xuống `NowingArm`/`NewChatClient`.
- **Mô tả:** Nếu `workspace_id` và `search_space_id` khác nhau (thường là khác), benchmark tạo/ask nhầm workspace hoặc 404/permission error.
- **Gợi ý sửa:** Cho `NewChatClient.create_thread` và `ask` nhận `workspace_id` riêng, ưu tiên `--workspace-id` từ runner.
- **Bucket:** `decision_needed` — cần xác nhận liệu eval harness có bắt buộc `workspace_id == search_space_id` hay hỗ trợ tách.

### H5 — Aggregate `operational` thiếu `turn_error_rate`, gate `max_turn_error_rate` bị vô hiệu

- **Mức độ:** cao
- **Nguồn:** Blind + Acceptance Auditor
- **Vị trí:** `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py:138-247,444-456,502-507`
- **Bằng chứng:** `_per_turn_metrics` tính `turn_error_rate` và `summarize_operational` merge vào per-case, nhưng `_aggregate_operational` không cộng dồn `n_turns`/`n_failed_turns`/`turn_error_rate`. `_evaluate_chat_gate` gọi `operational.get("turn_error_rate")` -> `None`, `_check` bỏ qua.
- **Mô tả:** `max_turn_error_rate` trong `gate.yaml` không bao giờ trigger. Tương tự `context_drift_score` không aggregate.
- **Gợi ý sửa:** Aggregate `turn_error_rate`, `n_turns`, `n_failed_turns`, `context_drift_score` trong `_aggregate_operational`.

### H6 — `max_scrape_drop_rate` gate đang check sai metric (`scrape_failure_rate` thay vì drop rate)

- **Mức độ:** cao
- **Nguồn:** Blind + Acceptance Auditor
- **Vị trí:** `nowing_evals/src/nowing_evals/suites/chat/regression/operational.py:200-216` và `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py:504`
- **Bằng chứng:** `scrape_failures` chỉ đếm tool output báo lỗi, không đếm tool bị drop (input mà không có output). Drop được tính trong `total_tool_drops`/`tool_drop_rate`.
- **Mô tả:** Web search bị attempt rồi drop sẽ không tăng `scrape_failure_rate`, nên gate có thể pass trong khi thực tế có dropouts.
- **Gợi ý sửa:** Gate `max_scrape_drop_rate` nên dùng metric drop dành riêng cho scrape (ví dụ tổng `drops` của các tool tìm kiếm/scrape) hoặc đổi tên threshold cho rõ ràng.

### H7 — Scrape metric chỉ hardcoded `web_search`/`web_scrape`, lệch với backend

- **Mức độ:** cao
- **Nguồn:** Blind + Acceptance Auditor
- **Vị trí:** `nowing_evals/src/nowing_evals/suites/chat/regression/operational.py:200-202`
- **Bằng chứng:** Backend đã retire `web_search` khỏi main agent, chuyển sang `google_search` subagent; capabilities vẫn emit `web_scrape` và `web_discover`.
- **Mô tả:** `scrape_attempts`/`scrape_successes`/`scrape_failures` undercount hoạt động tìm kiếm/thu thập thực, gate sai.
- **Gợi ý sửa:** Cập nhật danh sách tool được coi là scrape/search theo contract hiện tại (`google_search`, `web_scrape`, `web_discover`) hoặc dùng capability/topic classification thay vì tên tool.
- **Bucket:** `decision_needed` — cần xác nhận danh sách tool chính xác với backend team.

### H8 — `_parse_engine_ts` chỉ chấp nhận ISO string, bỏ qua epoch-ms theo spec 9.3

- **Mức độ:** cao
- **Nguồn:** Blind + Edge + Acceptance Auditor
- **Vị trí:** `nowing_backend/app/capabilities/chainlens/research/executor.py:107-119`, `:186-222`
- **Bằng chứng:** `_parse_engine_ts` trả `None` nếu input không phải `str`. Spec 9.3 và `tests/e2e/mock_chainlens.py` gửi `requestAcceptedAt`/`firstFactualChunkAt` dạng integer epoch-ms.
- **Mô tả:** Khi parser fail, `_record_first_token` fallback sang `time.perf_counter() - self.start_time`, đo TTFB bằng wall-clock Nowing thay vì `firstFactualChunkAt - requestAcceptedAt`. Vi phạm 9.3 AC1/8 và 4.8g AC5.
- **Gợi ý sửa:** `_parse_engine_ts` nhận cả ISO string và int/float epoch-ms.

---

## 2. Bugs — P1 (Medium)

### M1 — `gate.yaml` khai báo `max_error_rate` và `max_p95_ttfb_ms` nhưng evaluator không check

- **Mức độ:** trung bình
- **Nguồn:** Acceptance Auditor
- **Vị trí:** `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py:470-510` và `gate.yaml:5,7`
- **Mô tả:** `_evaluate_chat_gate` không so sánh `overall["error_rate"]`/`overall["p95_ttfb_ms"]` với threshold. Run có error/TTFB cao có thể pass.
- **Gợi ý sửa:** Thêm `_check` cho hai metric này.

### M2 — `chainlens_latency` chưa aggregate/gate theo tier

- **Mức độ:** trung bình
- **Nguồn:** Acceptance Auditor
- **Vị trí:** `nowing_evals/src/nowing_evals/suites/research/chainlens_latency/runner.py:163-167,215-256,565-634` và `gate.yaml`
- **Mô tả:** `--tier` chỉ là nhãn phẳng, không group, compute, gate per-tier. 4.8g AC2/AC6 yêu cầu `per_mode × per_tier`.
- **Gợi ý sửa:** Group metrics theo `(mode, tier)`, thêm `per_tier`/`per_mode_tier` block vào `gate.yaml` và `report_section`.

### M3 — `chainlens_latency` thiếu `--max-total-cost-micros` và `--fail-on-unratified`

- **Mức độ:** trung bình
- **Nguồn:** Acceptance Auditor
- **Vị trí:** `nowing_evals/src/nowing_evals/suites/research/chainlens_latency/runner.py:143-199,337-344`
- **Mô tả:** 4.8e AC4/AC5 yêu cầu cost cap và exit non-zero khi `baseline_ratified: false`. `chat/regression` đã có, `chainlens_latency` chưa.
- **Gợi ý sửa:** Thêm hai flag vào `add_run_args` và logic gate.

### M4 — `chainlens_latency` gate failure không gửi Slack/Telegram

- **Mức độ:** trung bình
- **Nguồn:** Acceptance Auditor
- **Vị trí:** `nowing_evals/src/nowing_evals/suites/research/chainlens_latency/runner.py:337-344`
- **Mô tả:** `core/notifications.py` và `chat/regression` đã gọi `notify_gate_failure`, nhưng `chainlens_latency` chỉ raise `RuntimeError` khi ratified.
- **Gợi ý sửa:** Gọi `notify_gate_failure` trước khi raise.

### M5 — `chainlens_latency` dùng `poll_timeout` cho cả sync call và poll timeout

- **Mức độ:** trung bình
- **Nguồn:** Blind
- **Vị trí:** `nowing_evals/src/nowing_evals/suites/research/chainlens_latency/runner.py:455-460`
- **Mô tả:** `httpx.Timeout(poll_timeout, connect=10.0)` dùng cho POST `?mode=sync`. Nếu State B bật và `quality` mất >300s, client abort trước khi backend xong.
- **Gợi ý sửa:** Tách `sync_timeout` riêng (ví dụ 600s hoặc vô hạn + poll cap), hoặc dùng `timeout=None` cho sync khi cần.

### M6 — `chainlens_latency` async path poll `GET /runs/{id}` thay vì SSE `/events`

- **Mức độ:** trung bình
- **Nguồn:** Acceptance Auditor
- **Vị trí:** `nowing_evals/src/nowing_evals/suites/research/chainlens_latency/runner.py:455-472,497-525`
- **Mô tả:** 9.3 AC2 mô tả tail `GET .../runs/{id}/events` SSE. Benchmark poll summary endpoint, parse `output_text` sau finalization. Không exercise real-time SSE path và bỏ qua `X-Run-Id`.
- **Gợi ý sửa:** Dùng SSE endpoint khi `mode=async`, hoặc ít nhất hỗ trợ cả hai.

### M7 — Telegram notification không escape Markdown metacharacters

- **Mức độ:** trung bình
- **Nguồn:** Blind
- **Vị trí:** `nowing_evals/src/nowing_evals/core/notifications.py:29-44,70-97`
- **Mô tả:** Tên threshold (`mode_speed_p95_e2e_ms`) và đường dẫn artifact chứa `_`, `*`, `[`. Telegram `parse_mode="Markdown"` sẽ 400 khi parse fail.
- **Gợi ý sửa:** Escape `_`, `*`, `[`, `]`, `` ` `` trong `text`; hoặc dùng `parse_mode="MarkdownV2"` với escaping đúng.

### M8 — `_one_case_per_tag` break sớm, có thể bỏ sót tag

- **Mức độ:** trung bình
- **Nguồn:** Edge Case Hunter
- **Vị trí:** `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py:411-422`
- **Mô tả:** Vòng trong `break` ngay sau tag đầu tiên dù nó đã seen; ví dụ `[a,x]` rồi `[a,b]` sẽ không chọn case chứa tag `b`. Vi phạm 4.8g AC4.
- **Gợi ý sửa:** `break` chỉ khi tìm thấy tag mới; hoặc xử lý tất cả tag rồi quyết định append.

### M9 — `--tags`/`--tier` với giá trị rỗng hoặc chỉ dấu phẩy silently chọn 0 case

- **Mức độ:** trung bình
- **Nguồn:** Edge Case Hunter
- **Vị trí:** `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py:664-673`
- **Mô tả:** `tags.split(",")` lọc empty segment, `wanted` rỗng, `wanted.intersection(c.tags)` luôn falsy -> không case nào được chọn.
- **Gợi ý sửa:** Coi empty list hoặc `","` như “no filter”.

### M10 — HTTP-level failures và `asyncio.wait_for` timeouts không được classify vào `error_reason_counts`

- **Mức độ:** trung bình
- **Nguồn:** Blind
- **Vị trí:** `nowing_evals/src/nowing_evals/core/arms/nowing.py:70-76`, `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py:718-818`, `operational.py:85-90`
- **Mô tả:** `NowingArm.answer` catch HTTP exception, trả `ArmResult.error` không có `error_code`. Runner catch `TimeoutError` nhưng không thêm vào `error_reason_counts`. `timeout_rate`, `server_error_rate`, v.v. undercount client-side failures.
- **Gợi ý sửa:** Map exception type/code vào `error_code` trong `ArmResult.extra`; runner ghi nhận timeout/network errors vào `error_reason_counts`.

### M11 — Report chat regression thiếu bảng Operational / Stability per tag

- **Mức độ:** trung bình
- **Nguồn:** Acceptance Auditor
- **Vị trí:** `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py:1102-1281`
- **Mô tả:** Metrics có `per_tag_operational`, `per_mode_operational`, nhưng `report_section` chỉ render 1 overall operational block. Các bảng per-tag/per-mode/per-tier chỉ có latency, cost, citation, keyword-match. 4.8f AC7 yêu cầu operational/stability per tag.
- **Gợi ý sửa:** Thêm bảng per-tag operational với `scrape_success_rate`, `tool_drop_rate`, `engine_unavailable_rate`, `error_reason_counts`.

### M12 — Token/cost từ `data-token-usage` không coerce về kiểu số

- **Mức độ:** trung bình
- **Nguồn:** Blind
- **Vị trí:** `nowing_evals/src/nowing_evals/core/clients/new_chat.py:310-325` và `nowing_evals/src/nowing_evals/core/arms/nowing.py:98-100`
- **Mô tả:** `_consume_sse` gán `data_payload["prompt_tokens"]` trực tiếp; nếu backend gửi string/None/float, downstream `sum()` hoặc `ArmResult` int fields fail. `NowingArm` chỉ `or 0`, vẫn giữ string truthy.
- **Gợi ý sửa:** Coerce `int()` và validate, xử lý `None`/float.

### M13 — `mode` research-depth không propagate qua regenerate/resume/gateway chat

- **Mức độ:** trung bình
- **Nguồn:** Blind + Acceptance Auditor
- **Vị trí:** `nowing_backend/app/schemas/new_chat.py:314-393,434-443`, `nowing_backend/app/routes/new_chat_routes.py:2284-2306`, `nowing_backend/app/gateway/agent_invoke.py:76-87`
- **Mô tả:** `NewChatRequest` có `mode` nhưng `RegenerateRequest`/`ResumeRequest` thiếu; regenerate/resume gọi `stream_new_chat` không truyền `mode`; `agent_invoke` cũng không. Các flow quay về `DEFAULT_RESEARCH_MODE`, phá vỡ repeatability của 4.8g.
- **Gợi ý sửa:** Thêm `mode` vào `RegenerateRequest`/`ResumeRequest`; propagate qua các call site; lưu `mode` vào `NewChatMessage`/checkpoint.
- **Bucket:** `decision_needed` — cần xác nhận scope (regenerate/resume/gateway) có bắt buộc preserve mode hay không.

### M14 — Sync research path (State B) không enforce per-workspace capability rate limit

- **Mức độ:** trung bình
- **Nguồn:** Blind
- **Vị trí:** `nowing_backend/app/capabilities/core/access/agent.py:175-278`
- **Mô tả:** `_check_rate_limit` chỉ gọi ở async branch. Sync branch gọi `gate_capability` nhưng không `_check_rate_limit`. Khi `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED=true`, deep-research vượt cap.
- **Gợi ý sửa:** Gọi `_check_rate_limit` trước khi thực hiện sync research.

### M15 — KB fallback `execute_with_context` catch exception hẹp, để lọt `asyncio.TimeoutError`/`ValueError`

- **Mức độ:** trung bình
- **Nguồn:** Blind + Edge
- **Vị trí:** `nowing_backend/app/capabilities/chainlens/research/executor.py:754-854`
- **Mô tả:** Except tuple chỉ gồm `SQLAlchemyError, RuntimeError, OSError, httpx.RequestError`. `search_chunks`/`_embedding_token_count` có thể raise `asyncio.TimeoutError`, `ValueError`, v.v., crash turn thay vì degrade.
- **Gợi ý sửa:** Mở rộng tuple hoặc dùng `Exception` base với re-raise nếu không phải fallback-eligible.

### M16 — `_extract_cost` giữ `costDollars` đầu tiên, bỏ qua terminal `done.usage.costDollars`

- **Mức độ:** trung bình
- **Nguồn:** Blind
- **Vị trí:** `nowing_backend/app/capabilities/chainlens/research/executor.py:434-493`
- **Mô tả:** `_extract_cost` return early khi `self.cost_dollars is not None`. Nếu event `usage` non-terminal đến trước `done.usage`, cost bị stale.
- **Gợi ý sửa:** Chỉ ghi nhận `costDollars` từ terminal event (`done` hoặc final `usage`); hoặc cho phép overwrite bởi terminal.

### M17 — `_capability_tool` async path chỉ catch `InsufficientCreditsError`

- **Mức độ:** trung bình
- **Nguồn:** Blind
- **Vị trí:** `nowing_backend/app/capabilities/core/access/agent.py:175-206`
- **Mô tả:** `_verify_workspace_access` raise `ForbiddenError`, `gate_capability` raise wallet/DB errors, `start_async_run` raise `ExternalServiceError`; chúng bubble lên thay vì trả error string có kiểm soát.
- **Gợi ý sửa:** Catch base `NowingError` hoặc các class cụ thể, trả error message.

### M18 — `_percentile` trả `0.0` cho list rỗng, che dấu missing data

- **Mức độ:** trung bình
- **Nguồn:** Edge Case Hunter
- **Vị trí:** `nowing_evals/src/nowing_evals/suites/research/chainlens_latency/runner.py:118-131`
- **Mô tả:** `_percentile([]) = 0.0`. Kết hợp với H2, mode chưa chạy có thể pass threshold. Cả chat regression `_percentile` cũng trả `0.0` cho rỗng.
- **Gợi ý sửa:** Trả `None` khi list rỗng, để caller skip/fail.

---

## 3. Bugs — P2 (Low / Patch)

### L1 — `report_section` chat regression coi `0.0` p95 TTFB là "n/a"

- **Vị trí:** `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py:1118`
- **Mô tả:** `overall.get('p95_ttfb_ms') or 'n/a'` làm `0.0` thành "n/a". `_bucket_row` đã dùng `is not None` đúng.
- **Gợi ý sửa:** Dùng `x if x is not None else 'n/a'`.

### L2 — `report_section` per-mode/tier thiếu p50

- **Vị trí:** `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py:1160-1216`
- **Mô tả:** `_bucket` tính p50, `_bucket_row` chỉ render p95. 4.8g AC2 yêu cầu p50/p95.
- **Gợi ý sửa:** Thêm cột p50 vào `_bucket_row`/headers.

### L3 — `raw.jsonl` không persist `raw_events`/`call_details`

- **Vị trí:** `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py:888-919`
- **Mô tả:** `_CaseResult` lưu full frames nhưng JSONL chỉ ghi `n_raw_events` và operational summary, mất dữ liệu debug.
- **Gợi ý sửa:** Ghi `raw_events` và `call_details` vào JSONL (có thể chunk/large-object).

### L4 — `chainlens_latency` `ingest` vẫn đòi auth

- **Vị trí:** `nowing_evals/src/nowing_evals/suites/research/chainlens_latency/runner.py:134-141` và `core/cli.py:500-508`
- **Mô tả:** `requires_auth_for_ingest` mặc định `True`, mặc dù `ingest()` no-op.
- **Gợi ý sửa:** Thêm `requires_auth_for_ingest: bool = False`.

### L5 — `_cmd_report` bypass suite-setup check nhầm khi benchmark filtered

- **Vị trí:** `nowing_evals/src/nowing_evals/core/cli.py:742-748`
- **Mô tả:** `any(not requires_suite_setup)` chạy trước khi filter `--benchmark`; mixed suite có thể cho qua setup-required benchmark.
- **Gợi ý sửa:** Filter benchmark trước, rồi check `any`.

### L6 — CLI error message vẫn nói đường dẫn global-model-connections cũ

- **Vị trí:** `nowing_evals/src/nowing_evals/core/cli.py:130`
- **Mô tả:** Endpoint là `/global-model-connections`, lỗi vẫn ghi `/model-connections/global`.
- **Gợi ý sửa:** Sửa message.

### L7 — `chainlens_latency` `--n`, `--concurrency`, `--poll-interval`, `--poll-timeout`, `--quality-latency-budget-ms` không validate giá trị vô lý

- **Vị trí:** `nowing_evals/src/nowing_evals/suites/research/chainlens_latency/runner.py:209-217`
- **Mô tả:** `--n 0` -> empty query list; `--n -1` slice ngược; `--poll-interval 0` busy loop; `--poll-timeout 0` timeout ngay; `--quality-latency-budget-ms 0` reject quality.
- **Gợi ý sửa:** Validate lower bound, đặc biệt `n >= 1`, `poll-interval > 0`, `poll-timeout > 0`.

### L8 — `chainlens_latency` `_poll_run` thoát với mọi status khác "running"

- **Vị trí:** `nowing_evals/src/nowing_evals/suites/research/chainlens_latency/runner.py:513-514`
- **Mô tả:** `if data.get("status") not in ("running",): return data` thoát ngay với status lạ/missing (e.g. `"pending"`).
- **Gợi ý sửa:** Chỉ thoát trên terminal status set (`completed`, `failed`, `timeout`, `cancelled`).

### L9 — `chainlens_latency` `--references` path lỗi crash run

- **Vị trí:** `nowing_evals/src/nowing_evals/suites/research/chainlens_latency/runner.py:391-418`
- **Mô tả:** `path.read_text()` không check tồn tại, không catch `OSError`.
- **Gợi ý sửa:** `path.exists()` check, wrap `OSError`.

### L10 — `chainlens_latency` quality reference lookup exact trên query string

- **Vị trí:** `nowing_evals/src/nowing_evals/suites/research/chainlens_latency/runner.py:420-440`
- **Mô tả:** `references.get(row["query"])` yêu cầu khớp chính xác; backend strip whitespace, khác case/space dẫn đến no match.
- **Gợi ý sửa:** Normalize key (strip, lower) khi load và lookup.

### L11 — `chainlens_latency` `gate.yaml` chỉ gate p95 e2e, thiếu TTFB/cost

- **Vị trí:** `nowing_evals/src/nowing_evals/suites/research/chainlens_latency/gate.yaml` và `runner.py:88-115`
- **Mô tả:** Runner ghi p50/p95 TTFB, mean_cost_micros, sources_partial_rate, degraded_rate, engine_unavailable_rate; `gate.yaml` chỉ có `max_p95_e2e_ms` và degraded/engine-unavailable global.
- **Gợi ý sửa:** Bổ sung `per_mode` thresholds cho TTFB và cost; hoặc ghi rõ scope NFR-9.
- **Bucket:** `decision_needed` — cần PO quyết định ngưỡng.

### L12 — Negative/zero `--n` và `--timeout` trong chat regression không validate

- **Vị trí:** `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py:640-650,674-675`
- **Mô tả:** `cases[:sample_n]` với negative slice ngược; `timeout` falsy (`0`) thay bằng 300s, không cho disable.
- **Gợi ý sửa:** Validate `sample_n >= 1`; tách `timeout is None` vs `timeout == 0`.

### L13 — `_load_cases` và `ingest` không catch malformed JSONL

- **Vị trí:** `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py:363,619`
- **Mô tả:** `json.loads(line)` raise raw `JSONDecodeError`, khó debug.
- **Gợi ý sửa:** Wrap `JSONDecodeError`, raise `RuntimeError` với context line number.

### L14 — `asyncio.gather` trong chat regression có thể mất partial results

- **Vị trí:** `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py:883`
- **Mô tả:** Không `return_exceptions=True`; unexpected exception trong `_make_error_result`/`summarize_operational` abort cả run.
- **Gợi ý sửa:** Dùng `return_exceptions=True` và xử lý exception row.

### L15 — `--modes` chat regression không validate với backend literal

- **Vị trí:** `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py:554-558,647-649`
- **Mô tả:** `NewChatRequest.mode` là `Literal["speed", "balanced", "quality", "auto"]`. Typo `--modes fast` gây 422 toàn bộ run.
- **Gợi ý sửa:** Validate sớm, in lỗi rõ ràng.

### L16 — TTFB chat client đo từ stream start thay vì request start

- **Vị trí:** `nowing_evals/src/nowing_evals/core/clients/new_chat.py:185-201,278-279`
- **Mô tả:** `stream_started` gán sau `raise_for_status`, TTFB không bao gồm HTTP connection/header latency. Có thể bias local-vs-prod.
- **Gợi ý sửa:** Cân nhắc đo từ `started` nếu spec yêu cầu true HTTP TTFB.
- **Bucket:** `patch` nhưng ghi chú: spec 4.8a ghi rõ TTFB là first token *after stream starts*, không phải HTTP TTFB; cần PO confirm trước khi đổi.

### L17 — `tool-output-available` không có input tạo fake `unknown` attempt

- **Vị trí:** `nowing_evals/src/nowing_evals/suites/chat/regression/operational.py:135-152`
- **Mô tả:** Output event cho toolCallId chưa thấy input -> tăng `tool_attempts["unknown"]`, làm drop_rate/success_rate sai.
- **Gợi ý sửa:** Không tăng attempts khi input bị drop; hoặc ghi riêng orphan outputs.

### L18 — `contains_hits` dùng substring match, dễ false-positive

- **Vị trí:** `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py:380-382`
- **Mô tả:** `"Apple"` match "pineapple". Spec 4.8b ghi nhận là known limitation.
- **Gợi ý sửa:** Cải thiện bằng word-boundary hoặc LLM-judge (4-8d).
- **Bucket:** `defer` — đang chờ LLM-judge suite.

### L19 — `chainlens_latency` Slack/Telegram artifact link có thể không clickable

- **Vị trí:** `nowing_evals/src/nowing_evals/core/notifications.py:19-44`
- **Mô tả:** Khi `NOWING_EVALS_ARTIFACT_URL_PREFIX` không set, link là local path; Slack cần `<url|text>` để auto-link.
- **Gợi ý sửa:** Dùng `<url|text>` cho Slack; validate prefix hoặc đổi phrasing.
- **Bucket:** `defer` — 4.8e AC3 yêu cầu link, nhưng có thể giải quyết bằng env var CI.

### L20 — Chat regression không log warning khi `baseline_ratified: false` và threshold bị vi phạm

- **Vị trí:** `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py:959-982`
- **Mô tả:** 4.8e AC5 yêu cầu warn nhưng không block khi baseline chưa ratified. Code chỉ ghi `metrics["gate_violations"]` mà không log.
- **Gợi ý sửa:** Thêm `logger.warning` liệt kê violations.
- **Bucket:** `defer` — không gây sai kết quả, chỉ thiếu observability.

---

## 4. Backend executor — low/patch (bổ sung từ Blind/Edge/Auditor)

### B1 — `_record_first_token` có thể emit `first_token` progress event hai lần

- **Vị trí:** `nowing_backend/app/capabilities/chainlens/research/executor.py:186-222`
- **Mô tả:** Local-fallback set `saw_first_token=True`, engine branch check `saw_engine_first_token`. Nếu text token trước rồi `progress` event có `firstFactualChunkAt`, sẽ emit duplicate.
- **Gợi ý sửa:** Dùng một cờ chung `saw_first_token` cho cả hai nhánh.

### B2 — Standalone `usage` event không được coi là terminal, bị classify timeout

- **Vị trí:** `nowing_backend/app/capabilities/chainlens/research/executor.py:266-272,521-527`
- **Mô tả:** `feed_line` xử lý `event_type in {"done", "usage"}` nhưng chỉ set `saw_done` cho `done`. Stream kết thúc bằng `usage` bị `finalize` coi là timeout.
- **Gợi ý sửa:** Terminal `usage` cũng set `saw_done=True`, hoặc bỏ `usage` khỏi terminal type.

### B3 — `_extract_cost` override explicit `tokens.total = 0` với `usage.totalTokens`

- **Vị trí:** `nowing_backend/app/capabilities/chainlens/research/executor.py:481-488`
- **Mô tả:** `total = total or usage.get("totalTokens")` coi `0` là missing.
- **Gợi ý sửa:** Dùng `None` check, chỉ fallback khi `total is None`.

### B4 — `_extract_cost` không guard `+inf`/`-inf` `costDollars`

- **Vị trí:** `nowing_backend/app/capabilities/chainlens/research/executor.py:458-467,495-502`
- **Mô tả:** `+inf` vượt qua NaN/negative check, `Decimal('Infinity') * 1_000_000` raise `OverflowError`.
- **Gợi ý sửa:** Reject `+inf`/`-inf`.

### B5 — `_to_int` chấp nhận `bool` vì `bool` là subclass `int`

- **Vị trí:** `nowing_backend/app/capabilities/chainlens/research/executor.py:96-104`
- **Mô tả:** `isinstance(True, int)` đúng -> `1`; `False` -> `0`.
- **Gợi ý sửa:** Loại `bool` bằng `isinstance(value, bool)` guard.

### B6 — `_parse_engine_ts` và `_to_int` silently drop malformed values, không log

- **Vị trí:** `nowing_backend/app/capabilities/chainlens/research/executor.py:96-119`
- **Mô tả:** Trả `None` nhưng không log, khó phát hiện contract drift.
- **Gợi ý sửa:** `logger.warning` khi parse fail.

### B7 — `ResearchInput.mode` description thiếu `auto`

- **Vị trí:** `nowing_backend/app/capabilities/chainlens/research/schemas.py:77-80`
- **Mô tả:** Literal gồm `auto` nhưng description không liệt kê.
- **Gợi ý sửa:** Cập nhật description.

### B8 — `_call_chainlens` hardcode `tier: "research"`, `ResearchInput` thiếu engine-tier

- **Vị trí:** `nowing_backend/app/capabilities/chainlens/research/executor.py:612-613` và `schemas.py:69-100`
- **Mô tả:** ChainLens contract hỗ trợ `ask`/`reason`/`research`; benchmark/eval chưa expose.
- **Gợi ý sửa:** Thêm `tier` vào `ResearchInput` và request body.
- **Bucket:** `decision_needed` — cần xác nhận có cần tier matrix cho 4.8g/9.3.

### B9 — `_check_rate_limit` gọi sync Redis/`threading.Lock` trong async agent tool

- **Vị trí:** `nowing_backend/app/capabilities/core/access/agent.py:109-119` và `rate_limit.py:45-54`
- **Mô tả:** `_incr` sync có thể block streaming event loop.
- **Gợi ý sửa:** Dùng async Redis client hoặc executor cho `_incr`.
- **Bucket:** `defer` — cần benchmark production để đo impact.

### B10 — `record_token_usage` signature extend nhưng billing wiring chưa chắc populate đủ field

- **Vị trí:** `nowing_backend/app/services/token_tracking_service.py:545-604`; callers trong `app/capabilities/core/billing.py:329-420`
- **Mô tả:** 9.3 AC1 yêu cầu `resolved_mode`, `mode_requested`, `e2e_ms`, `ttfb_ms` trong `TokenUsage.call_details`. Billing call site cần verify vẫn truyền đủ.
- **Gợi ý sửa:** Kiểm tra call site đã cập nhật theo signature mới.
- **Bucket:** `defer` — chủ yếu là chunk-boundary note; billing file cần cross-check.

---

## 5. Story 4-8d — LLM judge quality benchmark

- **Trạng thái:** `ready-for-dev`.
- **Nhận xét:** Harness đã có chỗ (`nowing_evals/suites/chat/quality_llm_judge/`), nhưng suite chưa implement. Không có code mới trong diff để review.
- **Khuyến nghị:** Tạo story implementation; khi dev xong chạy lại `bmad-code-review` cho 4-8d.

---

## 6. Missing Tests / Gaps

### T1 — `chainlens_latency` thiếu unit tests toàn bộ

- Không có test cho `_call_research`, `_poll_run`, `_parse_run`, `_evaluate_chainlens_gate`, `report_section`.

### T2 — Chat regression tests không cover high findings

- `tests/suites/chat/test_regression.py` pass 21 tests nhưng không test:
  - multi-turn thread deletion,
  - `_one_case_per_tag` edge cases,
  - `--tags`/`--tier` empty,
  - token/cost coercion,
  - `error_reason_counts` với client timeout,
  - `_aggregate_operational` includes `turn_error_rate`.

### T3 — Backend research executor tests bị skip/drift

- `test_chainlens_fixture_drift.py` cần `CHAINLENS_REPO_PATH`; không chạy tự động trong CI.
- Không có test cho `_parse_engine_ts`, `_extract_cost`, `_record_first_token`, sync rate limit.

### T4 — NFR-9 / State B ratification

- `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED=false`; `gate.yaml` `baseline_ratified: false`. Story 9.3 vẫn `in-progress`.

---

## 7. Spec / Sprint Status Changes

Các story sau cần được đặt lại trạng thái trong `sprint-status.yaml` và header spec file:

| Story | New Status | Lý do chính |
|---|---|---|
| 4-8b | `review` | Multi-turn broken, operational aggregation, tag/tier filters, token coercion. |
| 4-8e | `review` | Gate checks missing, unratified warning, chainlens cost cap/fail flag missing. |
| 4-8f | `review` | Multi-turn thread deletion, scrape metric mismatch, error classification. |
| 4-8g | `review` | Resolved-mode bucket divergence, per-tier missing, report p50, one_case_per_tag. |
| 9-3 | `in-progress` | `_parse_engine_ts` epoch-ms bug, mode propagation, sync rate limit. |

`4-8c` giữ `done` (production query sampler không có finding mới). `4-8d` giữ `ready-for-dev`.

---

## 8. Recommended Priority Order

1. **P0 — H8, H2, H1, H3:** Sửa TTFB parser, mode bucket, matrix abort, multi-turn thread deletion.
2. **P0 — H4, H5, H6, H7:** Workspace wiring, `turn_error_rate` aggregation, scrape drop/gate, scrape tool set.
3. **P1 — M1, M2, M3, M4, M5, M6:** Hoàn thiện chat gate, chainlens tier/cap/notification/SSE.
4. **P1 — M8, M9, M10, M11, M12:** Chat runner filtering, error classification, token coercion, report tables.
5. **P2 — L1-L20, B1-B10:** Validation, edge cases, backend executor guards, docs/status update.

---

## 9. Re-verification Checklist (after fixes)

- [ ] `ruff check src/nowing_evals/suites/research/chainlens_latency/ src/nowing_evals/suites/chat/regression/ src/nowing_evals/core/ tests/suites/chat/`
- [ ] `ruff format` applied.
- [ ] `pytest tests/suites/chat/test_regression.py tests/suites/chat/test_operational.py` pass.
- [ ] Thêm tests mới cho P0/P1 findings (multi-turn, mode bucket, `_parse_engine_ts`, scrape rate).
- [ ] `python -m nowing_evals run research chainlens_latency --workspace-id ... --modes speed,balanced,quality` chạy và sinh artifact.
- [ ] `python -m nowing_evals run chat regression --search-space-id ... --profile quick` cover all tags.
- [ ] Confirm `sprint-status.yaml` updated to `review`/`in-progress` for affected stories.
