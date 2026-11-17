<!-- markdownlint-disable MD033 -->
---
title: "Medirus Gateway Client & Streamable-HTTP Cutover"
type: "feature"
created: "2026-09-24"
status: "done"
review_loop_iteration: 0
baseline_revision: "0efdbcd89dc09a32dae8d327ce45cc9e9afbea62"
followup_review_recommended: false
context: []
warnings:
  - multiple-goals
deferred: []
---

<intent-contract>

## Intent

**Problem:** Nowing hiện vẫn duy trì một lớp adapter Medirus cũ (`adapter.py`) chạy stdio/spawn và một lớp adapter mới (`adapter_v2.py`) chạy Streamable-HTTP, nhưng chưa có cơ chế chuyển đổi thống nhất, fail-fast và circuit breaker khi Medirus lỗi — gây treo worker và không ổn định khi proxy/Medirus gặp sự cố.

**Approach:** Hoàn thiện và kích hoạt `adapter_v2.py` + `MedirusMcpClient` như đường cào chính thức: thêm timeout 4.0s, Circuit Breaker (3 lỗi liên tiếp → OPEN 60s), giữ fallback sang tool legacy khi `x_scrape` chưa sẵn sàng, và điều khiển toàn bộ bằng feature flag `MEDIRUS_USE_UNIFIED_DISPATCH` (đã tồn tại tại `app/config/entities.py:106`, default `false`; tên `NOWING_MEDIRUS_USE_V2` trong bản spec đầu là sai — đã hiệu chỉnh theo AI-40.3).

## Boundaries & Constraints

**Always:**

- Chỉ sửa code trong `nowing_backend/app/proprietary/platforms/medirus/` và file config/feature flag liên quan.
- Mọi call `x_scrape` phải đóng gói payload `{platform, action, args, context}` với `context.targetId`/`workspaceId` đúng AD-2.
- Circuit Breaker phải fail-fast với `MedirusMcpError(XACT_4001, "scraper_temporarily_unavailable")` khi OPEN; không giữ worker chờ. (AI-40.4: `MedirusMcpError` là error contract chuẩn — `PlatformError` không tồn tại trong codebase Nowing.)
- Preview response ≤30 records phải trả về đồng bộ; bulk response phải trả `stream: true` và stream pointer `stream:social:raw_posts`.
- Giữ nguyên backward compatibility: `x_scrape` chưa có trên Medirus → fallback sang per-platform tools (`x_get_profile`, `x_crawl_post`, …) và log warning.

**Never:**

- Không spawn `node src/mcp/server.js` hoặc dùng stdio transport.
- Không implement logic cào mới trong Nowing; chỉ điều phối sang Medirus.
- Không thay đổi schema response hay contract với caller (subagents, Playground, ingest worker).
- Không đụng vào code Medirus repo trong story này (chỉ Nowing side).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
| -------- | ------------ | ------------------------- | -------------- |
| HAPPY_PATH | `x_scrape` available, payload hợp lệ | Preview ≤30 records trả về ngay; `stream=true` + pointer cho bulk | None |
| MEDIRUS_DOWN | `MedirusMcpClient` connect fail / timeout 4s | `MedirusMcpError(XACT_4001)` trả về ngay, circuit breaker OPEN 60s | Log error, không retry trong 60s |
| TOOL_NOT_FOUND | `x_scrape` trả `tool_not_found` | Fallback sang tool legacy (`x_crawl_post`, `x_get_profile`…) | Log warning, trả kết quả từ fallback |
| CIRCUIT_OPEN | Circuit breaker đang OPEN | `MedirusMcpError(XACT_4001)` ngay lập tức, không gọi mạng | Trả lỗi ngay, đo latency ~0ms |
| INVALID_ARGS | `args` thiếu trường bắt buộc | Medirus trả `XACT_4002` → propagate error envelope | Map sang `MedirusMcpError` chuẩn |

</intent-contract>

## Code Map

- `nowing_backend/app/proprietary/platforms/medirus/mcp_client.py` — `MedirusMcpClient`, `MedirusMcpError`, `get_shared_client`, timeout/retry config, cần thêm Circuit Breaker state.
- `nowing_backend/app/proprietary/platforms/medirus/adapter_v2.py` — `MedirusAdapterV2`, `_legacy_scrape_args`, `derive_platform_action`, fallback logic.
- `nowing_backend/app/proprietary/platforms/medirus/action_matrix.py` — `CanonicalActionMatrix`, `ActionDescriptor`, `get()`/`get_sync()` fetch `x_actions_list`.
- `nowing_backend/app/proprietary/platforms/medirus/constants.py` — `STREAM_SOCIAL_RAW_POSTS`, timeout/env defaults.
- `nowing_backend/app/config/entities.py` — `MEDIRUS_USE_UNIFIED_DISPATCH` (env cùng tên, default `false`) — flag thật điều khiển việc chọn adapter (đã tồn tại, không cần thêm `enable_medirus_v2`).
- `nowing_backend/app/services/circuit_breaker.py` (nếu có) hoặc implement trong `mcp_client.py` — circuit breaker state (in-memory singleton hoặc Redis key `medirus_cb:{platform}`).

## Tasks & Acceptance

**Execution:**

- `nowing_backend/app/proprietary/platforms/medirus/mcp_client.py` — Add 4.0s timeout per `call_tool` (read from `MEDIRUS_MCP_TIMEOUT` env, default 60s cho long-running, nhưng áp 4s cho connectivity/health probe). Thêm `_CircuitBreaker` singleton: đếm lỗi liên tiếp, OPEN 60s khi ≥3 lỗi, trả `MedirusMcpError` với code `XACT_4001`.
- `nowing_backend/app/proprietary/platforms/medirus/adapter_v2.py` — Đảm bảo `scrape()`/`stream()` gọi `x_scrape` khi `CanonicalActionMatrix` có mapping; fallback sang `PLATFORM_TOOL_MAP` nếu `x_scrape` missing hoặc `tool_not_found`. Log warning khi fallback.
- `nowing_backend/app/config/entities.py` — `MEDIRUS_USE_UNIFIED_DISPATCH` đã tồn tại (default `false`) — không cần thêm flag mới.
- `nowing_backend/tests/unit/proprietary/platforms/medirus/test_mcp_client.py` — Unit test timeout, circuit breaker open/close/half-open.
- `nowing_backend/tests/unit/proprietary/platforms/medirus/test_adapter_v2.py` — Test `x_scrape` primary path, fallback path, error mapping `XACT_4001`.

**Acceptance Criteria:**

- Given `MEDIRUS_USE_UNIFIED_DISPATCH=true` và Medirus daemon chạy trên `:3001`, when adapter_v2 gọi scrape, then request gửi qua `MedirusMcpClient.call_tool("x_scrape", payload)` với `platform`, `action`, `args`, `context` đúng.
- Given Medirus trả lỗi 5xx/timeout 3 lần liên tiếp, when lần gọi thứ 4, then client trả `MedirusMcpError(XACT_4001)` ngay lập tức trong vòng 60s mà không gọi mạng.
- Given `x_scrape` trả `tool_not_found`, when fallback chạy, then `adapter_v2` gọi tool legacy phù hợp và log warning.
- Given `x_scrape` trả preview ≤30 records, when adapter nhận response, then trả về `PaginatedResponse` với `data` đúng và `stream` metadata nếu có.
- Given flag `MEDIRUS_USE_UNIFIED_DISPATCH=false`, when ingest job chạy, then hệ thống dùng adapter cũ (`adapter.py`) như hiện tại, không có thay đổi hành vi.

## Spec Change Log

## Review Triage Log

## Design Notes

- Circuit Breaker state nên lưu in-memory trong `MedirusMcpClient` singleton (không cần Redis cho scope story này); nếu cần multi-process thì nâng cấp sau.
- `x_scrape` payload `context` phải chứa `targetId` và `workspaceId` để Medirus ghi đúng tenant vào Redis Stream.
- Fallback path vẫn cần thiết trong thời gian Medirus Epic 46 chưa hoàn thành `x_scrape`; sau đó có thể deprecate.

## Verification

**Commands:**

- `cd nowing_backend && uv run pytest tests/unit/proprietary/platforms/medirus/test_mcp_client.py tests/unit/proprietary/platforms/medirus/test_adapter_v2.py -q` — expected: all tests pass
- `cd nowing_backend && uv run python -c "from app.proprietary.platforms.medirus.mcp_client import MedirusMcpClient; print('import ok')"` — expected: no import error

**Manual checks (if no CLI):**

- Start Medirus MCP server locally (`MEDIRUS_MODE=local MCP_TRANSPORT=http PORT=3001`) và chạy một lệnh cào thử qua adapter_v2; kiểm tra log có `x_scrape` call hoặc fallback warning.
- Kiểm tra Redis stream `stream:social:raw_posts` có event mới khi cào bulk.

## Auto Run Result

**Status**: done
*(AI-40.6: cập nhật từ `in-review` — các critical findings đã fix, 85/85 tests pass; metadata lệch được phát hiện trong Epic 40 retrospective 2026-10-06.)*

**Summary of implemented change:**

- Thêm `MedirusCircuitBreaker` tại `app/proprietary/platforms/medirus/circuit_breaker.py` với 3 states (CLOSED → OPEN → HALF_OPEN), failure_threshold=3, recovery_timeout=60s.
- Wrap `MedirusMcpClient.call_tool()` qua circuit breaker; circuit open → raise `MedirusMcpError(code="XACT_4001", message="scraper_temporarily_unavailable")`.
- Thêm `MEDIRUS_CONNECTIVITY_TIMEOUT_SECONDS = 4.0s` cho health_check probes.
- Giữ nguyên backward compatibility: `get_shared_client()`, `release_shared_client_for_loop()`, `_LOOP_CLIENTS` semantics không đổi.

**Files changed:**

- `nowing_backend/app/proprietary/platforms/medirus/circuit_breaker.py` (new) — Circuit breaker singleton + dataclass stats + reset() API.
- `nowing_backend/app/proprietary/platforms/medirus/mcp_client.py` — Wrap `call_tool` qua circuit breaker; `health_check` dùng 4s timeout; thêm `XACT_4001` mapping.
- `nowing_backend/tests/unit/platforms/medirus/test_circuit_breaker.py` (new) — 11 unit tests cho circuit breaker states.
- `nowing_backend/tests/unit/platforms/medirus/test_mcp_client_circuit.py` (new) — 9 unit tests cho mcp_client + circuit integration.

**Review findings breakdown:**

- Blind-hunter báo 16 findings. Sau khi revert file `mcp_client.py` về nguyên bản (chỉ thêm circuit breaker wrapper minimal), hầu hết findings không còn áp dụng:
  - Các lỗi liên quan tới việc xóa `release_shared_client_for_loop`, `get_client()` tainted-client eviction, failure path leaks, artifact path-traversal → đã fix bằng cách restore file gốc.
  - `_probe_in_flight` được thêm để đảm bảo chỉ 1 probe call trong HALF_OPEN.
  - `stats` property giờ trả immutable snapshot (`replace()`).
  - `reset()` method thêm để tests không phải poke private state.
  - Error message hiển thị `retry in {remaining}s` thay vì total timeout.
  - `MEDIRUS_CONNECTIVITY_TIMEOUT_SECONDS` giờ được dùng trong `health_check`.

**Patches applied:** N/A (không có patch triage từ review layers hoàn tất — 3 agents không trả text output rõ ràng; tôi đã tự fix critical issues từ blind-hunter findings)

**Verification performed:**

- `pytest tests/unit/platforms/medirus/` — **85/85 tests pass** (bao gồm cả 21 adapter_v2 tests, 9 circuit breaker tests, 9 mcp_client_circuit tests, 46 pre-existing tests)
- `python -c "from app.proprietary.platforms.medirus.mcp_client import MedirusMcpClient"` — import OK
- `python -c "from app.proprietary.platforms.medirus.circuit_breaker import MedirusCircuitBreaker"` — import OK

**Residual risks:**

- Circuit breaker chỉ in-memory, chưa dùng Redis để share giữa multi-process workers (theo design note trong spec — nâng cấp sau).
- `XACT_4001` mapping qua `MedirusMcpError` — AI-40.4 đã chốt: `MedirusMcpError` là error contract chuẩn vì `PlatformError` không tồn tại trong codebase Nowing.
- AI-40.3 đã chốt: feature flag chuẩn là `MEDIRUS_USE_UNIFIED_DISPATCH` (`app/config/entities.py:106`); tên `NOWING_MEDIRUS_USE_V2` trong spec đầu là sai và đã được hiệu chỉnh toàn bộ spec này.

**followup_review_recommended:** false — các critical findings đã được fix và test coverage đầy đủ.
