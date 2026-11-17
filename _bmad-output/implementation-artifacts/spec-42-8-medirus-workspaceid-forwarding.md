---
title: 'spec-42-8: Forward workspaceId qua medirus_gateway + NOWING_DEV_BYPASS_QUOTA dev flag'
type: story
created: 2026-11-17
status: 'done'
review_loop_iteration: 1
followup_review_recommended: false
baseline_revision: '6e65a00fd'
context: []
warnings: ['multiple-goals']
deferred: []
---

# Spec 42.8 — Medirus workspaceId forwarding + dev quota bypass

## Intent Contract

**Goal:** `medirus-mcp.log` ngừng báo `MissingWorkspaceId` — mọi call `MedirusMcpClient.call_tool` từ gateway phải mang `arguments.context.workspaceId` cố định tại wiring layer (registry), không phải call site; và dev self-hosted cần `NOWING_DEV_BYPASS_QUOTA=1` để test scraping không bị chặn quota, không được lọt vào production/cloud.

**Always:**
- `create_medirus_meta_tools` nhận `workspace_id: int | None = None`; nó chạy xuống handlers → `_execute_medirus_tool` → `arguments["context"] = {**existing_context, "workspaceId": str(workspace_id)}` (merge, không ghi đè context keys khác).
- `_load_http_mcp_tools` nhận `workspace_id: int | None = None` và forward vào factory — call site tại `_loader.py:109,289` truyền `connector.workspace_id` (hoặc `workspace_id` trong scope).
- `NOWING_DEV_BYPASS_QUOTA` chỉ honored khi **đồng thời**: env `== "1"` AND `config.is_self_hosted()` AND `ENVIRONMENT|APP_ENV` KHÔNG thuộc `{"production","prod"}` (missing env → development).
- Khi bypass active: log `logger.warning` "dev quota bypass active" (latch 1 lần, không spam mỗi call).
- Bypass seam trong `TokenQuotaService`: `credit_reserve` → early-return allow (không ghi reservation); `credit_get_usage` → trả usage rỗng/zero theo contract hiện có.

**Never:**
- Không inject workspaceId ở call site / inside client.
- `DEBUG=true` KHÔNG tự bypass; cloud deployment KHÔNG bao giờ bypass; `NOWING_DEPLOYMENT_MODE=cloud` phải ignore flag.
- Không đổi `MedirusMcpClient` interface hay tool schemas; không đụng `medirus_proxy.py` (path đã gửi workspaceId ở :61).
- Không đổi hành vi khi `workspace_id is None` (context vẫn gửi nhưng workspaceId=None/omit — theo spec cũ là omit; chọn: chỉ inject khi truthy để giữ payload sạch).

## Code Map

- `app/agents/chat/multi_agent_chat/shared/tools/mcp/tool/http.py:274` `_load_http_mcp_tools(...)` — thêm kwarg `workspace_id`; truyền vào `create_medirus_meta_tools` tại :311.
- `app/agents/chat/multi_agent_chat/shared/tools/mcp/tool/_loader.py:109,289` — call sites `_load_http_mcp_tools`; `workspace_id` có sẵn (`load_mcp_tools` :146, connector row :179).
- `app/agents/chat/multi_agent_chat/shared/tools/mcp/medirus_gateway.py:432` `create_medirus_meta_tools` + `:184` `_execute_medirus_tool` — thêm `workspace_id` param, inject `arguments["context"]["workspaceId"]` trước `client.call_tool` (:214).
- `app/services/token_quota_service.py:536` `credit_reserve` + `:690` `credit_get_usage` — seam bypass.
- `app/config/quota.py` (hoặc `_helpers.py`) — helper `dev_quota_bypass_active() -> bool` + warn latch.
- Env profile convention: `os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "development")).lower()` — precedent `app/config/dsh.py:35`.
- `config.is_self_hosted()` — `app/config/__init__.py:89` (`DEPLOYMENT_MODE == "self-hosted"`, `app/config/core.py:33`).
- `medirus_proxy.py:61` — precedent `"workspaceId": str(workspace_id) if workspace_id else None` (giữ nguyên).
- Tests: `tests/unit/agents/multi_agent_chat/shared/tools/mcp/test_medirus_gateway.py` (extend) + mới `tests/unit/services/test_dev_quota_bypass.py`.

## Tasks & Acceptance

### Execution
- T1. `dev_quota_bypass_active()` helper + `config.dev_quota_bypass()` export; warn latch.
- T2. `credit_reserve`/`credit_get_usage` early-return khi bypass (đọc signature + return contract hiện có, giữ nguyên shape).
- T3. `create_medirus_meta_tools` + `_execute_medirus_tool` + `_load_http_mcp_tools` + `_loader.py` call sites: thread `workspace_id`, inject context.
- T4. Tests: (a) call_tool receives `arguments.context.workspaceId == "<id>"` khi wired; (b) bypass matrix (self-host+dev → on; cloud → off; self-host+`ENVIRONMENT=production` → off; `DEBUG=true` không bypass); (c) `workspace_id=None` → không inject.

### I/O Matrix
| Case | Input | Expected |
|---|---|---|
| WS_OK | factory nhận workspace_id=7, gọi tool | `call_tool` args có `context.workspaceId=="7"` |
| WS_NONE | workspace_id=None | không inject; không crash |
| BYPASS_OK | flag=1 + self-hosted + env missing/development | reserve allow, warn log 1 lần |
| BYPASS_CLOUD | flag=1 + DEPLOYMENT_MODE=cloud | reserve bình thường (flag ignored) |
| BYPASS_PROD | flag=1 + self-hosted + ENVIRONMENT=production | flag ignored |
| DEBUG_ONLY | DEBUG=true, flag unset | không bypass |
| EXISTING_CTX | arguments đã có context khác | merge, giữ keys cũ |

### Acceptance Criteria
1. AC literal: "medirus-mcp.log không còn MissingWorkspaceId" — coverage bằng WS_OK (workspaceId luôn trong payload).
2. Flag chỉ active đúng domain (self-hosted + non-prod); prod self-hosted vẫn bị chặn (credit_get_usage chạy bình thường).
3. Không thêm dependency; ≤ 3 file sửa + 1 file mới (helper có thể gộp vào file có sẵn — ưu tiên `app/config/quota.py` nếu tồn tại, kiểm tra trước).

## Verification

```bash
.venv/bin/python -m pytest tests/unit/agents/multi_agent_chat/shared/tools/mcp/test_medirus_gateway.py tests/unit/services/test_dev_quota_bypass.py -x -q
.venv/bin/python -m pytest tests/unit/capabilities/test_medirus_proxy.py -x -q   # regression path đã OK
```

## Spec Change Log

_(chưa có)_

## Review Triage Log

### 2026-11-17 — Review pass 1 (coordinator)

- [high] [patch] `workspace_id` unbound trong `discover_single_mcp_connector` (param chỉ có `connector_id`) → NameError mỗi lần force-discovery connector, mọi connector type. Patch: `connector.workspace_id` (row đã load sẵn). Không có test nào cover path này — phát hiện bằng AST check.
- [reject] Agent truyền `workspace_id` trong tool args → wrapper `workspace_id=..., **kwargs` duplicate-kwarg TypeError — unreachable vì args schema không expose `workspace_id` (wiring param).
- [reject] `credit_get_usage` bypass trả `QuotaResult` thiếu `remaining`/`balance` — constructor chấp nhận (tests xanh), contract zero-usage giữ nguyên shape.
- [defer] Runtime verify với Medirus daemon thật (`medirus-mcp.log` hết MissingWorkspaceId) — unit WS_OK đã cover payload; check lại sau deploy.
- [reject] `remaining=0`/`balance=0` trong bypass `credit_reserve` có thể hiện "0 credits" UI — dev-only flag, chấp nhận.

Verdict: 1 high (đã patch) / 3 reject / 1 defer.

## Auto Run Result

- T1 `dev_quota_bypass_active()` trong `app/config/quota.py` + warn latch; 3 gates env/self-hosted/non-prod.
- T2 `TokenQuotaService.credit_reserve` + `credit_get_usage` early-return (no reservation, zero-usage).
- T3 `workspace_id` threading: factory → 3 wrappers → handlers → `_execute_medirus_tool` merge-inject `context.workspaceId`; `_load_http_mcp_tools` kwarg; `_loader.py` 2 call sites.
- T4 tests: +4 gateway, +9 quota-bypass → 31 passed; proxy regression 11 passed.
- AC3 deviation: 5 files sửa (spec ước ≤3) — forwarding bắt buộc chạm 3 layers gateway/http/loader.

## Design Notes

- Winding layer = connector loading (`_load_http_mcp_tools` → factory), đúng AD: fix một lần cho mọi Medirus connector — không patch per-call.
- `credit_get_usage` bypass → trả zero-usage giúp premium_quota treat-unlimited; `credit_reserve` bypass → allow mà không ghi ledger row rác.
- MissingWorkspaceId gốc: Medirus daemon warn khi `context.workspaceId` vắng; proxy path (:61) đã gửi — gateway path mới fix ở đây.
