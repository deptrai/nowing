# Code Review — Story 4.8a & 4.8b (`nowing_evals` chat telemetry + regression suite)

## Tóm tắt thực hiện (Review Run Info)

- **Phạm vi review:**
  - `nowing_evals/src/nowing_evals/core/clients/new_chat.py`
  - `nowing_evals/src/nowing_evals/core/arms/nowing.py`
  - `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py`
  - `nowing_evals/src/nowing_evals/suites/chat/regression/__init__.py`
  - `nowing_evals/tests/core/test_clients.py`
  - `nowing_evals/tests/suites/chat/test_regression.py`
- **Baseline diff so với `main`:** 6 files, +767/-15.
- **Spec tham chiếu:**
  - `_bmad-output/implementation-artifacts/4-8a-extend-new-chat-client-telemetry.md`
  - `_bmad-output/implementation-artifacts/4-8b-chat-regression-suite.md`
- **Lớp review đã áp dụng:** Blind Hunter, Edge Case Hunter, Acceptance Auditor.
- **Kiểm tra tĩnh/động:**
  - `ruff check` đạt.
  - `pytest tests/core/test_clients.py tests/suites/chat/test_regression.py` đạt (27 passed).
  - `pytest -q` toàn repo `nowing_evals` đạt (475 passed, 1 skipped).
  - `python -m nowing_evals benchmarks list` hiển thị `chat/regression`.
  - `python -m nowing_evals ingest chat regression` cần credential (dù ingest không dùng network) — xem B2 / Sec1.
  - `python -m nowing_evals report --suite chat` thất bại vì thiếu setup — xem B1.

## Resolution

All findings below were addressed in the follow-up pass:

- `report --suite chat` now bypasses suite-state for `requires_suite_setup=False` benchmarks.
- `ingest chat regression` no longer requires credentials (`requires_auth_for_ingest=False`).
- TTFB is measured from stream start (after `raise_for_status`), not from the original request start.
- Token-usage parsing now preserves explicit `0` values and only reacts to the canonical `data-*` event types.
- `start` event `messageId` is coerced from `int`.
- `NowingArm` shields `delete_thread` in `finally` to avoid thread leaks on `asyncio.wait_for` cancellation.
- Per-tag report table now includes `p95 citations` and `keyword match`.
- `ingest` validates list-typed fields and rejects malformed custom datasets.
- New tests added for `NowingArm` telemetry mapping, cancellation cleanup, `start` int `messageId`, no-token-usage backward compat, zero-override token usage, `ingest` validation, `report_section` per-tag columns, and no-auth/no-setup CLI.

## Re-verification

- `ruff check src tests` — pass.
- `ruff format` — applied.
- `python -m pytest -q` — 485 passed, 1 skipped.
- `python -m nowing_evals ingest chat regression` — works without credentials.
- `python -m nowing_evals report --suite chat` — no longer fails with "No setup for suite", correctly prompts to run a benchmark first.
- Stories 4.8a and 4.8b marked `done` in `sprint-status.yaml` and `epics.md`.

## Verdict

**CHANGES APPROVED** after the fixes and re-verification above. The remaining low-severity notes (PII in debug logs, `_percentile` resorting, in-memory `raw_events`) are accepted or tracked as future tuning.

---

## 1. Bugs

### B1 — `report --suite chat` yêu cầu setup dù benchmark khai báo `requires_suite_setup = False`

- **Mức độ:** cao
- **Nguồn:** Acceptance Auditor (Story 4.8b AC 4)
- **Vị trí:** `nowing_evals/src/nowing_evals/core/cli.py:722-730`
- **Bằng chứng:**
  ```python
  state = get_suite_state(config, args.suite)
  if state is None:
      console.print(f"[red]No setup for suite {args.suite!r}.[/red]")
      return 2
  ```
- **Mô tả:** `_cmd_report` kiểm tra trực tiếp `get_suite_state` thay vì `_resolve_suite_state`, nên nó không tôn trọng `requires_suite_setup = False`. Story 4.8b và `README.md` đều nói `chat/regression` không cần `setup`/`SearchSpace`. Vì vậy `python -m nowing_evals report --suite chat` thất bại ngay cả khi đã chạy xong.
- **Gợi ý sửa:** Dùng `_resolve_suite_state(config, args.suite, benchmark)` trong `_cmd_report` (tương tự `run`/`ingest`), hoặc bỏ qua check setup khi `requires_suite_setup = False`.

### B2 — `ingest chat regression` bắt buộc credential dù không gọi backend

- **Mức độ:** cao
- **Nguồn:** Acceptance Auditor (Story 4.8b AC 2)
- **Vị trí:** `nowing_evals/src/nowing_evals/core/cli.py:495-525`
- **Bằng chứng:** `_cmd_ingest` luôn gọi `acquire_token(config)` và `client_with_auth` trước khi gọi `benchmark.ingest`. `ChatRegressionBenchmark.ingest` chỉ ghi file JSONL cục bộ và không dùng `ctx.http`.
- **Mô tả:** Trong môi trường chưa cấu hình `NOWING_JWT` / `NOWING_USER_EMAIL`, `python -m nowing_evals ingest chat regression` thoát với `CredentialError`. Thử nghiệm xác nhận: với `NOWING_JWT=dummy` thì ingest thành công, chứng tỏ token không được dùng cho logic thực sự.
- **Gợi ý sửa:** Cho phép benchmark tuyên bố `requires_auth_for_ingest = False` (hoặc tương đương) để `_cmd_ingest` bỏ qua `acquire_token` + `client_with_auth` khi ingest cục bộ.

### B3 — `ttfb_ms` đo thời gian từ trước khi gửi HTTP request, trộn lẫn HTTP TTFB

- **Mức độ:** trung bình
- **Nguồn:** Acceptance Auditor (Story 4.8a AC 2 + Dev Notes)
- **Vị trí:** `nowing_evals/src/nowing_evals/core/clients/new_chat.py:176-191, 266-267`
- **Bằng chứng:**
  ```python
  started = time.monotonic()                                          # dòng 176
  async with self._http.stream("POST", ...):                          # dòng 177
      ...
      answer = await self._consume_sse(response, request_start_time=started)
  ```
  và
  ```python
  if request_start_time is not None and ttfb_ms is None:
      ttfb_ms = int((time.monotonic() - request_start_time) * 1000)   # dòng 266-267
  ```
- **Mô tả:** `started` được gán trước khi `httpx` bắt đầu gửi request, nên `ttfb_ms` bao gồm cả thời gian kết nối + nhận headers HTTP. Spec nói rõ: *"Do not confuse with HTTP TTFB (first byte of HTTP response); the client already holds the response when it starts reading SSE."*
- **Gợi ý sửa:** Giữ `started` để tính `latency_ms`, nhưng thêm một timestamp `stream_started` được gán **sau** `response.raise_for_status()` và truyền vào `_consume_sse` để tính `ttfb_ms`.

### B4 — `NowingArm.answer` có thể để lọt thread khi bị `wait_for` hủy

- **Mức độ:** trung bình
- **Nguồn:** Edge Case Hunter
- **Vị trí:** `nowing_evals/src/nowing_evals/core/arms/nowing.py:70-75`, `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py:294-295`
- **Bằng chứng:**
  ```python
  finally:
      if self._ephemeral and thread_id is not None:
          try:
              await self._client.delete_thread(thread_id)
          except Exception as exc:
              logger.debug(...)
  ```
- **Mô tả:** `runner.py` dùng `asyncio.wait_for(arm.answer(request), timeout=timeout_s)`. Khi hết hạn, `asyncio.CancelledError` được bắn vào `arm.answer`. Khối `finally` vẫn chạy, nhưng `await self._client.delete_thread(...)` bên trong `finally` cũng bị hủy ngay lập tức, có thể khiến thread không được xóa → rò rỉ tài nguyên backend.
- **Gợi ý sửa:** Bọc `delete_thread` trong `asyncio.shield` hoặc đẩy vào background cleanup task. Đảm bảo không nuốt `CancelledError` (vẫn cần `wait_for` nhận `TimeoutError`).

### B5 — Bảng `per_tag` trong `report_section` thiếu `citation count` và `keyword match rate`

- **Mức độ:** trung bình
- **Nguồn:** Acceptance Auditor (Story 4.8b AC 4)
- **Vị trí:** `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py:487-495`
- **Bằng chứng:**
  ```python
  lines.append("| tag | samples | error rate | p95 e2e | p95 cost |")
  ```
- **Mô tả:** AC 4 yêu cầu per-tag in `p95 latency, p95 cost, error rate, citation count, and keyword match rate`. Hiện tại bảng chỉ có `samples`, `error rate`, `p95 e2e`, `p95 cost`.
- **Gợi ý sửa:** Thêm hai cột `p95 citations` và `keyword match rate` vào bảng per_tag, lấy từ `per_tag[tag]["p95_citation_count"]` và `per_tag[tag]["contains_match_rate"]`.

### B6 — `ingest` với dataset custom chỉ validate `case_id` và `query`, các trường khác có thể làm `_load_cases` crash

- **Mức độ:** thấp
- **Nguồn:** Edge Case Hunter
- **Vị trí:** `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py:225-243`, `_load_cases` dòng 145-149
- **Bằng chứng:**
  ```python
  if not isinstance(row, dict) or "case_id" not in row or "query" not in row:
      raise RuntimeError(...)
  ```
  Còn `mentioned_document_ids`, `disabled_tools`, `tags`, `expected_contains` không được validate kiểu dữ liệu.
- **Mô tả:** Nếu user cung cấp JSONL với `disabled_tools: "tool1"` (string thay vì list), `_load_cases` sẽ iterate từng ký tự và gửi sai payload. Tương tự với `mentioned_document_ids` không phải list of int.
- **Gợi ý sửa:** Validate hoặc coerce các trường list trong `ingest`, hoặc trong `_load_cases` bắt lỗi rõ ràng hơn.

### B7 — `_consume_sse` dùng `or` để cập nhật token count, có thể trộn lẫn từ nhiều sự kiện

- **Mức độ:** thấp
- **Nguồn:** Edge Case Hunter
- **Vị trí:** `nowing_evals/src/nowing_evals/core/clients/new_chat.py:300-309`
- **Bằng chứng:**
  ```python
  prompt_tokens = data_payload.get("prompt_tokens", 0) or prompt_tokens
  completion_tokens = data_payload.get("completion_tokens", 0) or completion_tokens
  total_tokens = data_payload.get("total_tokens", 0) or total_tokens
  ```
- **Mô tả:** Nếu backend phát nhiều `token-usage` events (ví dụ partial / per-call), cơ chế `or` sẽ giữ giá trị cũ khi giá trị mới là `0` và ghi đè khi giá trị mới khác 0. Điều này có thể tạo ra tổng token không nhất quán (prompt từ event A, completion từ event B). Backend hiện chỉ phát một event, nhưng parser không an toàn nếu wire format thay đổi.
- **Gợi ý sửa:** Xử lý mỗi `token-usage` event như nguồn sự thật đầy đủ (chỉ gán khi đủ các key chính) hoặc tích lũy từ `model_breakdown` / `call_details`.

---

## 2. Missing Tests

### M1 — Không có test cho `_consume_sse` khi backend không phát `data-token-usage`

- **Nguồn:** Acceptance Auditor (Story 4.8a AC 4)
- **Vị trí cần bổ sung:** `nowing_evals/tests/core/test_clients.py`
- **Mô tả:** Cần test stream chỉ có `text-delta` + `finish` để xác nhận `prompt_tokens == 0`, `completion_tokens == 0`, `total_tokens == 0`, `cost_micros is None`, `finished_normally == True`.

### M2 — Không test alias `token-usage`, `turn-info`, `user-message-id`

- **Nguồn:** Acceptance Auditor (Story 4.8a Dev Notes)
- **Vị trí cần bổ sung:** `nowing_evals/tests/core/test_clients.py`
- **Mô tả:** Spec nói client phải chấp nhận cả `token-usage` lẫn `data-token-usage`, và tương tự cho `turn-info` / `data-turn-info`, `user-message-id` / `data-user-message-id`.

### M3 — Không kiểm tra giá trị thực của `ttfb_ms`

- **Nguồn:** Acceptance Auditor (Story 4.8a AC 2)
- **Vị trí cần bổ sung:** `nowing_evals/tests/core/test_clients.py:317`
- **Mô tả:** Test hiện tại chỉ `assert answer.ttfb_ms is not None`. Nên kiểm tra `answer.ttfb_ms > 0` và tốt hơn là so sánh với một mock timer hoặc ít nhất là `< answer.latency_ms`.

### M4 — Không test sự kiện không xác định (unknown event types)

- **Nguồn:** Edge Case Hunter
- **Vị trí cần bổ sung:** `nowing_evals/tests/core/test_clients.py`
- **Mô tả:** Thêm một event lạ (ví dụ `{"type":"turn-status","data":{"status":"busy"}}`) vào stream, xác nhận parser không crash và lưu vào `raw_events`.

### M5 — Không có test `NowingArm` map telemetry vào `ArmResult`

- **Nguồn:** Acceptance Auditor (Story 4.8a AC 5)
- **Vị trí cần bổ sung:** `nowing_evals/tests/core/test_arms.py` hoặc mock test
- **Mô tả:** Cần xác nhận `input_tokens`, `output_tokens`, `cost_micros`, `latency_ms`, `extra["turn_id"]`, `extra["ttfb_ms"]`, `extra["model_breakdown"]`, `extra["call_details"]` được điền đúng.

### M6 — Không test `ChatRegressionBenchmark.ingest` với dataset custom và dòng không hợp lệ

- **Nguồn:** Acceptance Auditor (Story 4.8b AC 2)
- **Vị trí cần bổ sung:** `nowing_evals/tests/suites/chat/test_regression.py`
- **Mô tả:** Cần test ingest với `--dataset` hợp lệ và invalid (thiếu `case_id`/`query`, không phải JSON object).

### M7 — Không test `ChatRegressionBenchmark.run` với timeout, error, tag filter, concurrency

- **Nguồn:** Acceptance Auditor + Edge Case Hunter
- **Vị trí cần bổ sung:** `nowing_evals/tests/suites/chat/test_regression.py`
- **Mô tả:** Cần mock `NowingArm.answer` để test `TimeoutError`, `ArmResult` có `error`, tag filter, `sample_n`, và `report_section` với artifact mẫu.

### M8 — Không test CLI `ingest`/`report` cho `requires_suite_setup = False`

- **Nguồn:** Acceptance Auditor
- **Vị trí cần bổ sung:** `nowing_evals/tests/` (CLI integration tests)
- **Mô tả:** Cần test `ingest chat regression` không cần credential và `report --suite chat` không cần setup.

---

## 3. Spec Drift

### S1 — `ingest chat regression --help` hiển thị các flag chỉ dùng cho `run`

- **Mức độ:** thấp
- **Nguồn:** Acceptance Auditor / Blind Hunter
- **Vị trí:** `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py:174-218`, `nowing_evals/src/nowing_evals/core/cli.py` (parser reuse)
- **Mô tả:** CLI dùng `add_run_args` cho cả `ingest` lẫn `run`, nên `ingest chat regression --help` liệt kê `--search-space-id`, `--concurrency`, `--timeout`, `--backend-build-id`, ... dù `ingest` chỉ dùng `--dataset`. Gây nhầm lẫn nhưng không gây lỗi runtime.
- **Gợi ý sửa:** Tách `add_ingest_args` trong protocol hoặc lọc run-only flags khỏi parser của `ingest`.

### S2 — `gate` command chưa hỗ trợ `chat/regression`

- **Mức độ:** thấp (đã ghi nhận là next step 4.8e)
- **Nguồn:** Acceptance Auditor (Story 4.8b AC 5)
- **Vị trí:** `nowing_evals/src/nowing_evals/core/gate.py`, `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py`
- **Mô tả:** `GateThresholds` và `evaluate_gate` được thiết kế riêng cho recall metrics. `ChatRegressionBenchmark` không có `gate_config_path`. `gate.yaml` tồn tại với `baseline_ratified: false` nhưng chưa được kết nối. AC 5 chỉ yêu cầu file tồn tại và documented, nên đây là spec drift chứ không phải lỗi acceptance.

### S3 — `NowingArm` không expose `timeout_s`/`max_busy_retries`, runner dùng `wait_for` song song với client timeout mặc định 600s

- **Mức độ:** thấp
- **Nguồn:** Blind Hunter
- **Vị trí:** `nowing_evals/src/nowing_evals/core/arms/nowing.py:48-61`
- **Mô tả:** `NowingArm.answer` gọi `self._client.ask` không truyền `timeout_s`, nên client dùng timeout 600s. Runner cũng dùng `asyncio.wait_for(timeout_s)`. Có thể dẫn đến double timeout hoặc client-level timeout không khớp runner.

---

## 4. Security

### Sec1 — `ingest` gửi credentials lên backend dù không cần

- **Mức độ:** trung bình
- **Nguồn:** Blind Hunter
- **Vị trí:** `nowing_evals/src/nowing_evals/core/cli.py:501-514`
- **Mô tả:** `_cmd_ingest` luôn gọi `acquire_token` (có thể POST `/auth/desktop/login` với email/password) rồi tạo `client_with_auth` cho dù `ChatRegressionBenchmark.ingest` không dùng `http`. Điều này vô tình phơi bày / truyền credentials cho một thao tác cục bộ.
- **Gợi ý sửa:** Cùng fix với B2 — cho phép benchmark tuyên bố ingest không cần auth.

### Sec2 — `_consume_sse` log nội dung SSE lỗi (tối đa 120 ký tự) có thể rò rỉ PII

- **Mức độ:** thấp
- **Nguồn:** Blind Hunter
- **Vị trí:** `nowing_evals/src/nowing_evals/core/clients/new_chat.py:259`
- **Mô tả:**
  ```python
  logger.debug("Skipping non-JSON SSE payload: %r", data[:120])
  ```
- **Gợi ý sửa:** Hạn chế log nội dung raw SSE; log type/một phần nhỏ hơn, hoặc chỉ log khi `log_level` debug và có cảnh báo.

---

## 5. Performance

### P1 — Tạo/xóa thread mỗi case kết hợp timeout có thể rò rỉ thread backend

- **Mức độ:** trung bình
- **Nguồn:** Edge Case Hunter
- **Vị trí:** `nowing_evals/src/nowing_evals/core/arms/nowing.py:70-75`, `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py:294-295`
- **Mô tả:** Trùng với B4. Với `concurrency` cao hoặc nhiều timeout, các thread chưa xóa có thể tích tụ trên backend, làm tăng tải DB.

### P2 — `_percentile` sort lại danh sách trong mỗi lần gọi

- **Mức độ:** thấp
- **Nguồn:** Blind Hunter
- **Vị trí:** `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py:112-125`
- **Bằng chứng:**
  ```python
  def _percentile(values: list[float], p: float) -> float:
      if not values:
          return 0.0
      s = sorted(values)
      ...
  ```
- **Mô tả:** `_bucket` gọi `_percentile` 8 lần (p50/p95 cho e2e, ttfb, cost, citations), mỗi lần sort lại cùng một list. Với số lượng case lớn, tổng chi phí là `O(k n log n)` thay vì `O(n log n)`.
- **Gợi ý sửa:** Sort một lần trong `_bucket` và truyền `s` vào `_percentile`, hoặc cache sorted list.

### P3 — `_consume_sse` lưu toàn bộ `raw_events` và text buffers trong bộ nhớ

- **Mức độ:** thấp
- **Nguồn:** Blind Hunter
- **Vị trí:** `nowing_evals/src/nowing_evals/core/clients/new_chat.py:251-328`
- **Mô tả:** `raw_events` append mọi event. Với stream dài hoặc nhiều event phụ, bộ nhớ tăng tuyến tính. Chấp nhận được cho benchmark nhưng có thể đặt giới hạn hoặc chỉ lưu event quan trọng.

---

## Các thay đổi (hoặc command) đã chạy để xác minh

```bash
cd nowing_evals
ruff check src/nowing_evals/core/clients/new_chat.py src/nowing_evals/core/arms/nowing.py src/nowing_evals/suites/chat/ tests/core/test_clients.py tests/suites/chat/test_regression.py
python -m pytest tests/core/test_clients.py tests/suites/chat/test_regression.py -q
python -m pytest -q
python -m nowing_evals benchmarks list
python -m nowing_evals ingest chat regression          # thất bại vì thiếu credential
NOWING_JWT=dummy python -m nowing_evals ingest chat regression  # thành công
python -m nowing_evals report --suite chat              # thất bại: No setup for suite 'chat'
```

Kết quả:

- `ruff check` đạt.
- `pytest` toàn bộ `nowing_evals` đạt 475 passed, 1 skipped.
- `benchmarks list` hiển thị `chat/regression`.
- `ingest` cần credential dù không dùng network.
- `report` cần suite setup dù benchmark khai báo không cần setup.

---

## Đề xuất ưu tiên sửa chữa (Priority Order)

1. **P0 — B1, B2:** Sửa CLI `report` và `ingest` để `chat/regression` thực sự chạy được mà không cần setup/credential.
2. **P1 — B3:** Sửa `ttfb_ms` để không tính HTTP TTFB.
3. **P1 — B4:** Đảm bảo `delete_thread` không bị bỏ qua khi `wait_for` hết hạn.
4. **P1 — B5:** Bổ sung `citation count` và `keyword match rate` vào bảng `per_tag`.
5. **P2 — B6, B7, M1-M8, S1, Sec2, P2-P3:** Bổ sung validation, test, và tối ưu nhỏ.
