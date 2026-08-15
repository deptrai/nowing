# Handoff Report — Survey Explorer 3 (Epic 21)

**Agent**: Survey Explorer 3  
**Target Recipient**: Orchestrator (Conversation ID: `50a7ac8d-3de4-4fdf-bf6c-27623b1509b7`)  
**Timestamp**: 2026-08-15T06:34:00Z  
**Type**: Hard Handoff (Investigation Complete)  

---

## 1. Observation

Khảo sát trực tiếp trên codebase `nowing_backend/` và `nowing_web/` thu được các quan sát thực tế (paths, lines, code references):

1. **Celery Scheduling & Queues**:
   - `nowing_backend/app/celery_app.py:180-209`: Khởi tạo `Celery` app bao gồm các include `app.automations.tasks.execute_run`, `app.automations.tasks.notify_run_complete`, `app.automations.triggers.builtin.schedule.selector`, `app.alerts.engine.tick`.
   - `nowing_backend/app/celery_app.py:278-361`: Cấu hình Celery Beat với `automation-schedule-select` (`minute="*"`) và `alert-engine-tick` (`minute="*"`).
   - `nowing_backend/app/celery_app.py:247-266`: Tách các queue riêng biệt: `CONNECTORS_QUEUE` (`nowing_task_queue.connectors`) cho tasks indexing dài hạn, `gateway` queue cho inbox reconciliation.

2. **Automation Execution Engine**:
   - `nowing_backend/app/automations/runtime/executor.py:36-102`: `execute_run` nạp `AutomationDefinition`, bọc context trong `with automation_run_origin(run.id):` (loop guard ngăn memory loop trigger), duyệt tuần tự `definition.plan` qua `execute_step()`.
   - `nowing_backend/app/automations/runtime/step.py:19-91`: `execute_step` kiểm tra `evaluate_predicate(step.when, ...)`, render template qua `render_value`, validate Pydantic parameters, và thực thi action handler bọc trong retry decorator `with_retries(max_retries, backoff, timeout)`.
   - `nowing_backend/app/automations/actions/builtin/write_back_telegram/invoke.py:102-130`: Gửi tin nhắn Telegram qua `TelegramAdapter(token).send_message()`, tự động tra cứu `ExternalChatBinding` theo workspace và creator user ID.

3. **Gateway Adapters & Rate Limiting**:
   - `nowing_backend/app/gateway/base/adapter.py:32-71`: `BasePlatformAdapter` định nghĩa `parse_inbound`, `send_message`, `edit_message`, `validate_credentials`.
   - `nowing_backend/app/gateway/ratelimit.py:88-136`: `acquire_token` và `wait_for_token` thực thi Lua script `_TOKEN_BUCKET_LUA` trên Redis, tự động fallback sang `_memory_fallback_acquire` khi Redis unavailable.

4. **MCP Write-Back Pipeline & Integrations**:
   - `nowing_backend/app/automations/actions/builtin/write_back/shared.py:75-138`: `resolve_connector` kiểm tra `SearchSourceConnector` và `auth_expired` flag.
   - `nowing_backend/app/automations/actions/builtin/write_back/shared.py:183-237`: `select_write_tool` phân biệt công cụ create vs update dựa trên tên tool MCP và ngăn chặn duplicate create khi có `object_id`.
   - `nowing_backend/app/automations/actions/builtin/write_back/shared.py:260-349`: `build_tool_args` ánh xạ Pydantic params sang schema của Notion, Linear, Jira, Slack.
   - `nowing_backend/app/services/composio_service.py:155-207`: `initiate_connection` và `execute_tool` hỗ trợ OAuth và tool execution cho các bộ toolkit ngoài.

5. **Workspace Limits, Billing Events & Token Metering**:
   - `nowing_backend/app/services/workspace_limits.py:105-206`: `WorkspaceLimitService.get_effective_limits` ưu tiên self-hosted (unlimited) -> workspace override -> plan default -> env override.
   - `nowing_backend/app/services/workspace_limits.py:87-100`: Advisory lock `SELECT pg_advisory_xact_lock(hashtext('workspace_limits'), :wid)`.
   - `nowing_backend/app/services/billing_event_service.py:91-156`: `_record_business_event` ghi `BillingEvent` phi-LLM với partial unique indexes (`ix_billing_events_signal_unique`, `ix_billing_events_outcome_unique`) và trừ tiền ví qua `wallet_credit.apply_debit`.
   - `nowing_backend/app/services/token_tracking_service.py:566-649`: `record_token_usage` ghi nhận chi phí LLM, prompt/completion tokens, model breakdown và correlation metadata (`run_id`, `client_id`).

6. **Lead Intelligence Database Models & Routes**:
   - `nowing_backend/alembic/versions/198_add_signal_tables.py:38-234`: Bảng `signal_events`, `signal_subscriptions`, `billing_events` kèm RLS policies.
   - `nowing_backend/alembic/versions/199_add_lead_score_tables.py:41-174`: Bảng `leads`, `lead_scores`, cột `workspaces.icp_criteria` kèm RLS policies.
   - `nowing_backend/app/routes/lead_scoring_routes.py:33-233`: REST routes `POST /workspaces/{id}/leads/score`, `GET /workspaces/{id}/leads/scores`, `PUT /workspaces/{id}/icp`.
   - `nowing_backend/tests/integration/lead_intelligence/test_lead_scoring.py:86-132`: Test integration xác nhận `LeadScore` liên kết `Memory` qua `source_uuid` và `source_entity_type = 'lead_score'`.

---

## 2. Logic Chain

1. **Khả năng tái sử dụng Sequencer cho Outbound Prospecting (Story 21.4)**:
   - *Căn cứ*: `app/automations/runtime/executor.py` và `step.py` đã cung cấp sẵn runtime duyệt plan, render templated parameters, retry with backoff, và error handling.
   - *Suy luận*: Không cần xây dựng một sequencer engine mới từ đầu. Ta có thể biểu diễn Outbound Sequences dưới dạng các `AutomationDefinition` gồm các `PlanStep` liên tiếp (VD: Bước 1: Generate Email Draft -> Bước 2: Wait/Delay -> Bước 3: Send Outreach -> Bước 4: Check Reply / Follow-up).
2. **Khả năng mở rộng Multi-Channel Delivery (Story 21.6)**:
   - *Căn cứ*: `app/gateway/` đã có interface `BasePlatformAdapter` và `app/gateway/ratelimit.py` cung cấp Redis token bucket rate limiter.
   - *Suy luận*: Để bổ sung Email và SMS/Webhook delivery, chỉ cần triển khai adapter tương ứng tuân thủ `BasePlatformAdapter` hoặc action plugins trong `app/automations/actions/builtin/` và bọc qua `wait_for_token(scope="email_outbound:domain", capacity=..., refill_per_sec=...)`.
3. **Mô hình CRM Write-Back (Story 21.5)**:
   - *Căn cứ*: `write_back/shared.py` đã chuẩn hóa flow discovery MCP tools, parameter mapping, và response normalization cho Linear, Jira, Notion.
   - *Suy luận*: Việc tích hợp HubSpot / Salesforce có thể áp dụng trực tiếp mô hình này: định nghĩa action `write_back_hubspot` và `write_back_salesforce`, sử dụng `resolve_connector` và `build_tool_args` để push lead data vào CRM.
4. **Mô hình Metering & ROI Tracking (Story 21.7)**:
   - *Căn cứ*: Hệ thống đã phân định rạch ròi 2 ledger: `TokenUsage` (LLM prompt/completion/cost) và `BillingEvent` (non-LLM business event cost, idempotent qua partial unique indexes).
   - *Suy luận*: Chi phí tạo lead và chăm sóc lead (Signal detection scan + Enrichment + LLM scoring + Outbound messaging) được ghi nhận chi tiết theo `lead_id` và `workspace_id`. Khi có `outcome_event` (Lead convert / Deal won), hệ thống tính toán chính xác Cost Per Lead (CPL) và ROI.

---

## 3. Caveats

- **Email Delivery Provider**: Hiện tại codebase chưa cấu hình SMTP/SES client trực tiếp cho outbound prospecting mà mới có skill `email-drafting` và connector đọc Gmail. Khi triển khai Story 21.6, cần xác định provider cụ thể (Resend, SendGrid, AWS SES, hoặc Gmail API).
- **CRM Webhook Inbound**: Đã có webhook routes cho Circleback và Gateway WhatsApp, nhưng chưa có webhook listener riêng cho HubSpot/Salesforce lifecycle events. Cần đăng ký webhook route trong `app/routes/` khi triển khai 21.5 bi-directional sync.
- **Frontend Lead Gen UI**: Frontend `nowing_web/` hiện có trang automations, saved searches, connectors, nhưng các trang chuyên biệt cho Lead Intelligence UI (Lead table, score details, ICP settings) sẽ cần kết nối các contract types tương ứng từ backend schemas.

---

## 4. Conclusion

Kiến trúc backend của Nowing hoàn toàn sẵn sàng cho việc hoàn thiện trọn bộ Epic 21 (Lead Gen Intelligence — Stories 21.1 đến 21.7):
- **Sequencer (21.4)**: Tái sử dụng `app/automations/` runtime.
- **CRM Sync (21.5)**: Mở rộng `app/automations/actions/builtin/write_back/` và MCP/Composio connectors.
- **Multi-Channel Delivery (21.6)**: Tận dụng `app/gateway/` adapters và `app/gateway/ratelimit.py`.
- **Outcome-Based Pricing & ROI (21.7)**: Sử dụng `BillingEventService` kết hợp `TokenUsage` ledger và `WorkspaceLimitService`.
- **Tuân thủ Tenancy (AD-31) & Provenance (AD-44/AD-47)**: Đảm bảo composite index `(workspace_id, client_id)` và liên kết `Memory.source_uuid`.

---

## 5. Verification Method

Các lệnh độc lập để kiểm chứng kiến trúc và chất lượng code:

1. **Chạy Unit Tests của Lead Intelligence & Billing**:
   ```bash
   cd nowing_backend
   uv run pytest tests/unit/lead_intelligence/ -q
   uv run pytest tests/unit/capabilities/test_billing.py -q
   ```
2. **Chạy Integration Tests (Yêu cầu Postgres + Redis qua Docker)**:
   ```bash
   # Khởi động dependency containers
   docker compose -f docker/docker-compose.deps-only.yml up -d db redis
   
   cd nowing_backend
   uv run alembic upgrade head
   uv run pytest tests/integration/lead_intelligence/ -q
   uv run pytest tests/integration/automations/ -q
   uv run pytest tests/integration/gateway/ -q
   ```
3. **Kiểm tra Linting & Formatting**:
   ```bash
   cd nowing_backend
   ruff check app/lead_intelligence/ app/automations/ app/gateway/ app/services/ app/routes/
   ruff format --check app/lead_intelligence/ app/automations/ app/gateway/ app/services/ app/routes/
   ```
4. **Kiểm tra FastAPI App Initialization**:
   ```bash
   uv run python -c "from app.app import app; print('Nowing App Import & Routing OK')"
   ```
