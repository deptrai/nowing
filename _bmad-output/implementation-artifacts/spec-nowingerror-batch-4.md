---
title: NowingError & Exception Narrowing — Batch 4 (Health, Web Builder, Memory & Telemetry Services)
type: refactor
created: '2026-09-13'
status: done
baseline_commit: 9d5535311e9a263fa7db316ce40498b898be2bc1
review_loop_iteration: 0
context:
  - nowing_backend/app/exceptions.py
  - nowing_backend/app/services/health/
  - nowing_backend/app/services/web_builder/
  - nowing_backend/app/services/memory/
  - nowing_backend/app/services/admin_telemetry/
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Có 101 vị trí `except Exception` trong các dịch vụ hệ thống cốt lõi: Health probes & monitoring (38 sites), Web Builder generation & deployment (31 sites), Team & Workspace Memory management (20 sites), và Admin Telemetry (12 sites). Các lỗi kiểm tra probe, build container, hay memory encryption cần được bắt đúng kiểu hoặc phân loại rõ ràng giữa monitoring failure vs production disruption.

**Approach:** Refactor Batch 4 gồm 101 call-sites `except Exception` trên 32 files:
1. Với Health probes (`health/probes/` và `alert_engine.py`): bắt lỗi probe execution, ghi nhận trạng thái probe FAIL / DEGRADED an toàn, không để 1 probe crash toàn bộ scheduler.
2. Với Web Builder (`web_builder/`): bắt lỗi code generation, validation AST, Docker/container deployment, trả về kết quả lỗi có cấu trúc thay vì crash build loop.
3. Với Memory (`memory/`): bảo vệ extraction budget gates, revalidation pipelines, encryption decryption fallbacks.
4. Với Admin Telemetry (`admin_telemetry/`): bảo đảm metric/queue collection fail-safe, trả về 0 / degraded metrics khi Redis hoặc Celery broker unready.

## Boundaries & Constraints

**Always:**
- Giữ nguyên logic health checks và probes status transitions.
- Với probes: không bao giờ để unhandled exception thoát ra khỏi probe `run()` method (probes phải return `ProbeResult(status=UNHEALTHY)`).
- Với Web Builder: rollback và cleanup temporary build directories khi deploy fail.
- Chạy tests liên quan sau khi sửa.

**Never:**
- Không làm gián đoạn pipeline build của Web Builder hay scheduler của Health.
- Không nuốt lỗi mã hóa PII / Memory mà không có ghi log / fallback an toàn.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Health probe network timeout | Upstream down | ProbeResult(status=UNHEALTHY, message=...) | Ghi log debug/warning, không crash scheduler |
| Web builder AST syntax error | Invalid generated JSX | ValidationResult(valid=False, errors=[...]) | Parse error bắt cụ thể, trả về lỗi chi tiết |
| Memory budget check fail | DB error | GateResult(allowed=False, reason="error") | Fail-closed bảo vệ quota ví |
| Telemetry queue read fail | Celery broker down | Metric count = 0 | Best-effort monitoring |

</frozen-after-approval>

## Code Map

- `app/exceptions.py` — NowingError hierarchy.
- `app/services/health/` (38 sites across 12 files):
  - `alert_engine.py` (7), `scheduler.py` (4), `registry.py` (1), `result_store.py` (1)
  - Probes: `xactions_probe.py` (5), `messaging_probe.py` (4), `infrastructure_probe.py` (3), `chainlens_probe.py` (3), `scraper_probe.py` (2), `storage_probe.py` (2), `payment_probe.py` (2), `connector_probe.py` (2), `proxy_probe.py` (1), `model_probe.py` (1)
- `app/services/web_builder/` (31 sites across 6 files):
  - `generator.py` (6), `deploy/deploy_app.py` (6), `validator.py` (5), `deploy/service.py` (5), `builder.py` (4), `mark_tool.py` (3), `deploy/custom_domain.py` (2)
- `app/services/memory/` (20 sites across 8 files):
  - `extract_budget.py` (8), `revalidation_service.py` (5), `repository.py` (2), `run_enqueue.py` (1), `encryption.py` (1), `extraction.py` (1), `pipeline.py` (1), `rewrite.py` (1)
- `app/services/admin_telemetry/` (12 sites across 3 files):
  - `_helpers.py` (7), `queues.py` (4), `health.py` (1)

## Tasks & Acceptance

**Execution:**
- [ ] `app/services/health/` (38 sites across 12 files)
- [ ] `app/services/web_builder/` (31 sites across 6 files)
- [ ] `app/services/memory/` (20 sites across 8 files)
- [ ] `app/services/admin_telemetry/` (12 sites across 3 files)
- [ ] Verify tests & ruff check

**Acceptance Criteria:**
- 100% các call-sites `except Exception` được narrow hoặc annotate rationale chuẩn.
- Các bài test unit và integration liên quan pass 100%.
- `ruff check` pass không có lỗi.
