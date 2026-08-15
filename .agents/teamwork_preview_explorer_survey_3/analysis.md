# Epic 21 (Lead Gen Intelligence) Architecture & Codebase Survey Report

**Survey Explorer 3**: Outbound Prospecting, Multi-Channel Delivery, CRM Sync, ROI & Metering, and Testing Architecture  
**Working Directory**: `/Users/luisphan/Documents/GitHub/nowing/.agents/teamwork_preview_explorer_survey_3`  
**Timestamp**: 2026-08-15T06:33:30Z  

---

## 1. Executive Summary

Nowing platform đã xây dựng sẵn một nền tảng kiến trúc rất vững chắc và module hóa cao cho:
1. **Automation & Sequence Execution**: Meta-scheduler Celery Beat, declarative plan execution (`app/automations/runtime/executor.py`), step templating, retry backoffs, và rate limiting qua Redis token bucket (`app/gateway/ratelimit.py`).
2. **Channel & Gateway Adapters**: Multi-platform messaging gateway (`app/gateway/`) hỗ trợ Telegram, Slack, Discord, WhatsApp (Cloud & Baileys), cùng cơ chế action write-back (`app/automations/actions/builtin/`).
3. **CRM & MCP Integration**: MCP write-back architecture (`app/automations/actions/builtin/write_back/shared.py`), Composio SDK (`app/services/composio_service.py`), và native connectors (`app/connectors/`).
4. **Billing, Metering & Workspace Limits**: Phân lớp rõ ràng giữa Workspace Limits (`app/services/workspace_limits.py`), Token Tracking / LLM usage (`app/services/token_tracking_service.py`), non-LLM Business Event Ledger (`app/services/billing_event_service.py`), và Capability Billing (`app/capabilities/core/billing.py`).
5. **API & Test Conventions**: FastAPI routers chuẩn hóa trong `app/routes/`, RBAC permission checks, Tenancy (AD-31) qua Postgres RLS, Provenance (AD-44/AD-47) qua `source_uuid`/`source_entity_type`, cùng bộ test unit/integration chuẩn (`tests/unit/` & `tests/integration/`).

---

## 2. Outbound Prospecting Sequencer & Multi-Channel Delivery (Stories 21.4, 21.6)

### 2.1. Celery Task Architecture & Scheduling
* **Celery Configuration (`nowing_backend/app/celery_app.py`)**:
  - `celery_app`: Đầy đủ middleware đo queue latency, telemetry span enrichment (`@task_prerun`, `@task_postrun`), worker process initialization (`init_worker` khởi tạo LiteLLM Router, Pricing Registration, OTel).
  - Dedicated Queues:
    - `CELERY_TASK_DEFAULT_QUEUE`: Fast user-facing operations (chat, file upload, reports).
    - `CONNECTORS_QUEUE`: Dedicated slow/long-running queue (`index_notion_pages`, `index_github_repos`, `index_google_gmail_messages`, v.v.).
    - `GATEWAY_QUEUE`: Dedicated messaging inbox queue (`gateway.reconcile_inbox`, `gateway.health_check`, `gateway.retention_sweep`).
  - Meta-Scheduler (`celery_app.conf.beat_schedule`):
    - `check-periodic-connector-schedules`: Chạy định kỳ quét DB tìm connectors cần crawl.
    - `alert-engine-tick` (`app.alerts.engine.tick`): Ticks every minute cho saved search alerts.
    - `automation-schedule-select` (`app.automations.triggers.builtin.schedule.source:BEAT_SCHEDULE`): Ticks every minute cho automation triggers.

### 2.2. Sequencer & Step Runtime
* **Schedule Trigger Selector (`app/automations/triggers/builtin/schedule/selector.py`)**:
  - Ticks mỗi phút (`automation_schedule_select`).
  - **Self-healing**: Tự động tính `next_fire_at` cho các row mới có `next_fire_at IS NULL` dựa trên cron expression + timezone.
  - **Concurrency-safe claiming**: Dùng `with_for_update(skip_locked=True)` với batch size 200, cập nhật `last_fired_at` và advance `next_fire_at` trước khi gọi `launch_run()`.
* **Execution Engine (`app/automations/runtime/executor.py` & `step.py`)**:
  - `execute_run(session, run_id)`:
    1. Load snapshot `AutomationDefinition` từ DB.
    2. Thiết lập origin context `automation_run_origin(run.id)` (đây là **loop-guard** quan trọng ngăn memory change trigger tự kích hoạt lại chính nó khi automation ghi memory).
    3. Duyệt tuần tự qua `definition.plan` (danh sách `PlanStep`):
       - Đánh giá điều kiện rẽ nhánh `step.when` qua `evaluate_predicate`.
       - Render dynamic parameters qua Jinja context `build_run_context` (`{{ inputs.company_name }}`, `{{ step_outputs.step_1.result }}`).
       - Validate schema parameter Pydantic model (`action.params_model.model_validate`).
       - Thực thi handler qua `with_retries` (hỗ trợ max_retries, exponential backoff, timeout).
       - Append structured step result vào `run.step_results` JSONB column.
    4. Nếu bước thất bại, kích hoạt `definition.execution.on_failure` steps và đánh dấu `RunStatus.FAILED`.
    5. Khi hoàn tất, enqueue asynchronous notification qua Celery task `notify_telegram_run_complete`.

### 2.3. Rate Limiting & Flow Control
* **Redis Token Bucket (`app/gateway/ratelimit.py`)**:
  - Sử dụng Lua script nguyên tử (`_TOKEN_BUCKET_LUA`) với capacity, refill rate, và expire TTL (3600s).
  - Tự động fallback sang in-memory token bucket (`_memory_fallback_acquire`) khi Redis gặp sự cố ngắn hạn để không làm sập gateway outbound traffic.
  - Cung cấp 2 hàm cốt lõi:
    - `acquire_token(scope, capacity, refill_per_sec, consume)`: Trả về số mili-giây cần chờ (0 nếu được phép gửi ngay).
    - `wait_for_token(scope, capacity, refill_per_sec, consume)`: Tự động `asyncio.sleep` đúng thời gian chờ trước khi gửi.

### 2.4. Multi-Channel Adapters & Delivery Matrix
* **Gateway Platform Adapters (`app/gateway/`)**:
  - `BasePlatformAdapter` (`app/gateway/base/adapter.py`): Định nghĩa interface chuẩn `parse_inbound`, `send_message`, `edit_message`, `validate_credentials`.
  - Các adapter hiện có:
    - `TelegramAdapter` (`app/gateway/telegram/adapter.py`): Gửi qua Telegram Bot API (hỗ trợ MarkdownV2, inline keyboards, reply markups).
    - `SlackAdapter` (`app/gateway/slack/adapter.py`): Gửi qua Slack Bot Token Web API.
    - `DiscordAdapter` (`app/gateway/discord/adapter.py`): Gửi qua Discord REST API.
    - `WhatsAppCloudAdapter` & `WhatsAppBaileysAdapter` (`app/gateway/whatsapp/`): Gửi qua Meta Cloud API hoặc self-hosted Baileys gateway.
* **Write-Back Action Plugins (`app/automations/actions/builtin/`)**:
  - `write_back_telegram`: Đã tích hợp sẵn, giải quyết account ID (workspace account hoặc system bot) và peer ID qua `ExternalChatBinding`.
  - `write_back_slack`: Tích hợp qua Slack MCP tool hoặc SlackAdapter.
  - `write_back_linear`, `write_back_jira`, `write_back_notion`: Ghi dữ liệu trực tiếp vào hệ thống ngoài qua MCP tool pipeline (`write_back/shared.py`).
* **Email, SMS, Webhook Extension for Outbound (Stories 21.4, 21.6)**:
  - Email: Đã có prompt template & skill drafting (`email-drafting/SKILL.md`), cùng Gmail connector. Khi triển khai delivery trực tiếp, có thể thêm action `write_back_email` hoặc channel adapter kết nối SMTP/SES/Resend/Gmail API.
  - SMS & Webhook: Tương tự, xây dựng action `write_back_sms` (Twilio/Infobip) và `write_back_webhook` (Generic HTTP POST with signing key) tuân thủ `PlanStep` handler pattern.

---

## 3. CRM Integration & Write-Back Architecture (Story 21.5)

### 3.1. MCP Write-Back Pattern (`app/automations/actions/builtin/write_back/shared.py`)
Kiến trúc write-back trong Nowing được thiết kế theo generic pipeline chuẩn:
1. **Connector Resolution (`resolve_connector`)**:
   - Truy vấn `SearchSourceConnector` theo `workspace_id` và `provider` (ví dụ `notion`, `linear`, `jira`, `hubspot`, `salesforce`).
   - Kiểm tra trạng thái xác thực `auth_expired`.
2. **Tool Discovery (`load_tools_for_connector`)**:
   - Gọi `load_mcp_tools` với cờ `bypass_internal_hitl=True` để cho phép background automation thực thi mà không bị nghẽn human approval nội bộ.
3. **Write Tool Selection (`select_write_tool`)**:
   - Phân biệt công cụ tạo mới (`create_tools`: `createJiraIssue`, `notion-create-pages`, `save_issue`) và cập nhật (`update_tools`: `editJiraIssue`, `notion-update-page`).
   - Ngăn chặn lỗi vô tình tạo duplicate nếu caller yêu cầu update (`object_id` tồn tại) nhưng connector chỉ hỗ trợ create tool.
4. **Parameter Schema Translation (`build_tool_args`)**:
   - Trích xuất `input_schema.properties` của MCP tool và ánh xạ các trường từ Pydantic model (`title`, `description`, `properties`, `additional_fields`).
5. **Execution & Response Normalization (`parse_mcp_result`)**:
   - Parse kết quả JSON/string, trích xuất `object_id`, `url` (permalink) và `raw` payload để lưu vào step results.

### 3.2. CRM & External System Integrations
* **Composio Toolkit Platform (`app/services/composio_service.py`)**:
  - Hỗ trợ OAuth initiation (`initiate_connection`), token management (`get_access_token`, `refresh_connected_account`), và tool execution (`execute_tool`).
  - Hỗ trợ delta sync / change tracking (e.g. `get_drive_start_page_token`, `list_drive_changes`).
* **MCP OAuth 2.1 Router (`app/routes/mcp_oauth_route.py`)**:
  - Quản lý OAuth handshake cho Linear, Jira, Slack, Notion, Airtable, ClickUp.
* **Field Mapping & Conflict Resolution**:
  - Dynamic mapping được cấu hình trong template context của Automation Playbook.
  - Conflict resolution dựa trên composite unique constraints (ví dụ: `uq_leads_workspace_company` trên bảng `leads`, `(workspace_id, client_id, company_name)`) và update timestamps (`updated_at`).
* **Audit & Sync Logs**:
  - Lưu chi tiết trong `automation_runs.step_results`, `billing_events`, và `TokenUsage.call_details`.

---

## 4. Outcome-Based Pricing & ROI Tracking (Story 21.7)

### 4.1. Workspace Limits & Plan Gating (`app/services/workspace_limits.py`)
* **WorkspaceLimitService**:
  - Quản lý hạn mức tập trung cho toàn bộ workspace: documents, members, runs, storage.
  - **Resolution Precedence**:
    1. `config.is_self_hosted()` -> Unlimited (tất cả limit trả về `None`).
    2. Per-workspace override row trong bảng `workspace_limits` (`workspace_id == id` và `plan_tier IS NULL`).
    3. Plan tier default row trong `workspace_limits` (`plan_tier == workspace.plan_tier`).
    4. Env override cấu hình trong `config.WORKSPACE_PLAN_LIMITS`.
    5. Fallback về plan `free` nếu workspace tier không xác định.
  - **Concurrency Safety**: Dùng Postgres advisory transaction lock:
    ```sql
    SELECT pg_advisory_xact_lock(hashtext('workspace_limits'), :workspace_id)
    ```
  - **Gating Methods**: `check_document_limit`, `check_member_limit`, `check_run_limit` — raise `HTTPException(403, detail={"error_code": "limit_exceeded", "limit_type": ..., "used": ..., "limit": ...})`.

### 4.2. Business Event Ledger (`app/services/billing_event_service.py`)
* **Bảng `billing_events` (`alembic/versions/198_add_signal_tables.py`)**:
  - Quản lý chi phí cho các sự kiện kinh doanh phi-LLM (non-LLM business events) như:
    - `signal_scan` (`event_entity_type = 'signal_event'`)
    - `lead_scoring` (`event_entity_type = 'lead_score'`)
    - `outcome_event` / `conversion` (`event_entity_type = 'outcome_event'`)
  - **Trường dữ liệu**:
    - `workspace_id` (int, FK workspaces.id)
    - `client_id` (CITEXT, tenant context)
    - `user_id` (UUID, FK user.id)
    - `event_entity_type`, `event_type`, `event_id` (UUID)
    - `cost_micros` (BigInteger, micro-USD: $1.00 = 1,000,000 micros)
    - `currency` (mặc định "USD")
    - `cost_basis` ("estimated" hoặc "actual")
  - **Idempotency**:
    - Index duy nhất có điều kiện (partial unique index):
      ```sql
      CREATE UNIQUE INDEX ix_billing_events_signal_unique ON billing_events (event_id)
      WHERE event_entity_type = 'signal_event' AND event_type = 'signal_scan';

      CREATE UNIQUE INDEX ix_billing_events_outcome_unique ON billing_events (event_id)
      WHERE event_entity_type = 'outcome_event' AND event_type = 'outcome';
      ```
    - Check session uncommitted objects trước khi insert để tránh race condition trong cùng 1 request session.
  - **Wallet Integration**: Tích hợp trực tiếp với `wallet_credit.check_balance(session, user_id, cost_micros)` và `wallet_credit.apply_debit(session, user_id, cost_micros)`.

### 4.3. LLM Token Tracking & Metering (`app/services/token_tracking_service.py`)
* **TurnTokenAccumulator & TokenTrackingCallback**:
  - LiteLLM callback tự động capture usage (prompt tokens, completion tokens, cached tokens, cost USD) sau mỗi LLM invocation.
  - Scoped turn helper `scoped_turn()` quản lý ContextVar an toàn, tránh leak chi phí giữa các concurrent/sub-agent calls.
  - `record_token_usage()` lưu thông tin vào bảng `token_usage`:
    - `usage_type` (`UsageType.LEAD_SCORING_LLM`, `UsageType.DEEP_RESEARCH`, v.v.)
    - `cost_micros`, `prompt_tokens`, `completion_tokens`, `total_tokens`
    - `call_details` (JSONB: breakdown theo model, latency e2e_ms, ttfb_ms, degradation_reason)
    - `run_id`, `client_id`, `workspace_id`, `user_id`

### 4.4. Capability Executor Billing (`app/capabilities/core/billing.py`)
* Pre-flight Gate (`gate_capability`): Tính toán worst-case units (`estimated_units`), kiểm tra số dư ví `wallet_credit.check_balance` trước khi chạy executor.
* Post-execution Charge (`charge_capability`): Tính toán chính xác số lượng items/pages/queries thành công, trừ tiền ví `wallet_credit.apply_debit`, và ghi record vào `token_usage` / `billing_events`.
* **ROI & Conversion Attribution Metrics (Story 21.7)**:
  - Toàn bộ chi phí cấu thành cho 1 Lead (Intent Signal Scan + Contact Enrichment + Lead Scoring LLM + Outbound Delivery) đều được lưu với `workspace_id`, `client_id`, `lead_id`, `cost_micros`.
  - Khi Lead chuyển đổi sang trạng thái `converted` (hoặc deal won ghi nhận qua CRM write-back/webhook), hệ thống có thể tính toán chính xác:
    - **Cost Per Lead (CPL)** = $\sum \text{cost\_micros}(\text{signal} + \text{enrichment} + \text{scoring}) / N_{\text{leads}}$
    - **Cost Per Conversion (CPC)** = $\sum \text{total\_prospecting\_cost} / N_{\text{converted\_leads}}$
    - **ROI** = $(\text{Deal Value} - \text{Total Lead Gen Cost}) / \text{Total Lead Gen Cost} \times 100\%$

---

## 5. API Routes Structure & Testing Patterns

### 5.1. REST API Routing Architecture
* **Tổ chức Module**:
  - Toàn bộ router được đặt trong `app/routes/` và mount tập trung vào `crud_router` trong `app/routes/__init__.py`.
  - `app/app.py` include `crud_router` với tiền tố `/api/v1`.
* **Standard Route Signature & Pattern**:
  ```python
  @router.post("/workspaces/{workspace_id}/leads/score", response_model=LeadScoreOutput)
  async def score_leads(
      workspace_id: int,
      body: LeadScoreInput,
      session: AsyncSession = Depends(get_async_session),
      auth: AuthContext = Depends(get_auth_context),
  ) -> LeadScoreOutput:
      # 1. RBAC check
      await check_permission(session, auth, workspace_id, Permission.LEADS_SCORE.value)
      
      # 2. Tenancy Context (AD-31)
      client_id = auth.pat.client_id if auth.pat is not None else None
      ctx = SimpleNamespace(
          session=session,
          workspace_id=workspace_id,
          run_id=None,
          client_id=client_id,
          user_id=auth.user.id,
      )
      
      # 3. Service Call
      service = LeadScoringService()
      return await service.score(session, ctx, body)
  ```

### 5.2. Tenancy (AD-31) & Provenance (AD-44 / AD-47)
* **Tenancy (AD-31)**:
  - Cột `workspace_id` (bắt buộc) + `client_id` (CITEXT, tùy chọn).
  - Postgres Row-Level Security (RLS) được thiết lập tự động trong migrations:
    - Read policy: `workspace_id IS NOT DISTINCT FROM current_setting('app.workspace_id', true)::int`
    - Write policy: `workspace_id ... AND client_id IS NOT DISTINCT FROM current_setting('app.current_client_id', true)`
  - Thiết lập context qua `set_request_tenant_context(session, workspace_id, client_id, user_id)`.
* **Provenance (AD-44 / AD-47)**:
  - Mọi Memory sinh ra từ lead scoring hoặc intent signals đều liên kết qua `Memory.source_uuid` (ID của LeadScore/SignalEvent) và `Memory.source_entity_type` (`"lead_score"`, `"signal_event"`).
  - PII Redaction (`app/services/pii.redact.redact_pii`) được áp dụng trước khi ghi nội dung memory.

### 5.3. Testing Strategy & Quality Gates
* **Unit Testing (`tests/unit/`)**:
  - Đánh dấu `@pytest.mark.unit`.
  - Mọi dependency bên ngoài (DB session, HTTP client, LiteLLM) đều được mock bằng `AsyncMock` / `MagicMock` hoặc `monkeypatch`.
  - Kiểm tra logic thuần túy: công thức scoring (`app/lead_intelligence/scoring/rubric.py`), rate limiter arithmetic, schema validators.
  - Lệnh chạy: `pytest tests/unit/lead_intelligence/ -q`
* **Integration Testing (`tests/integration/`)**:
  - Đánh dấu `pytestmark = [pytest.mark.integration, pytest.mark.asyncio]`.
  - Chạy trên real PostgreSQL DB + pgvector.
  - Sử dụng fixtures từ `conftest.py`:
    - `db_session`: AsyncSession thực kết nối test database với rollback tự động.
    - `db_workspace`, `db_user`: Workspace và User đã seed sẵn.
    - `client`: `httpx.AsyncClient` với `ASGITransport(app=app)` và `dependency_overrides` trên `get_async_session` và `get_auth_context`.
  - Lệnh chạy: `pytest tests/integration/lead_intelligence/ -q`
* **Code Quality & Linting Gates**:
  - `ruff check app/ routes/ tests/`
  - `ruff format --check app/ routes/ tests/`

---

## 6. Synthesis & Architecture Matrix

| Component | Current Implementation in Codebase | Recommended Extension for Epic 21 (21.4 - 21.7) |
|---|---|---|
| **Prospecting Sequencer** | `app/automations/runtime/executor.py`, `step.py`, `triggers/builtin/schedule/` | Sử dụng nguyên vẹn `AutomationDefinition` & `PlanStep` engine. Thêm prospecting action types (`prospect_outreach_step`, `enrich_lead_step`). |
| **Delivery Channels** | `app/gateway/` (Telegram, Slack, Discord, WhatsApp) | Thêm Email Channel Adapter (SMTP/SES/Resend) và SMS/Webhook Action handlers theo chuẩn `BasePlatformAdapter` / `ActionContext`. |
| **CRM Integration** | `write_back/shared.py` (MCP tools), `composio_service.py` | Tạo `write_back_hubspot` & `write_back_salesforce` actions tận dụng MCP discovery pipeline có sẵn. |
| **Rate Limiting** | `app/gateway/ratelimit.py` (Redis token bucket + in-memory fallback) | Sử dụng trực tiếp `acquire_token` / `wait_for_token` theo recipient domain và sender account. |
| **Billing & Metering** | `app/services/billing_event_service.py`, `workspace_limits.py`, `token_tracking_service.py` | Ghi nhận `BillingEvent` cho `signal_scan`, `lead_scoring`, `enrichment_call`, `outreach_send`, `outcome_event`. |
| **ROI / CPL Tracking** | `TokenUsage` + `BillingEvent` ledger | Tạo analytics query tổng hợp CPL và ROI theo `lead_id` và `workspace_id`. |
| **API & RBAC** | `app/routes/`, `app/utils/rbac.py`, `check_permission` | Đăng ký route mới vào `app/routes/__init__.py`, dùng permission enum `Permission.LEADS_*`. |
| **Database & Tenancy** | Alembic migrations 198 & 199, RLS helpers | Tuân thủ `workspace_id` + `client_id` composite index và RLS policies. |
| **Testing** | `tests/unit/lead_intelligence/`, `tests/integration/lead_intelligence/` | Mở rộng test suite cho sequence step execution, CRM write-back mock, và ROI computation. |

---

## 7. Next Steps for Implementation

1. **Sequencer & Outreach Actions (Story 21.4 & 21.6)**:
   - Xây dựng built-in actions: `write_back_email`, `write_back_webhook`, `outbound_sequence_step`.
   - Kết nối Redis rate limiter cho outbound channels.
2. **CRM Integration (Story 21.5)**:
   - Xây dựng MCP write-back adapters cho HubSpot & Salesforce theo template `write_back/shared.py`.
   - Thiết lập bi-directional webhook handler cập nhật lead status khi có phản hồi từ CRM.
3. **Pricing & ROI Analytics (Story 21.7)**:
   - Viết API endpoint `/workspaces/{workspace_id}/leads/roi` tổng hợp chi phí từ `billing_events` và `token_usage` đối chiếu với conversion outcomes.
4. **Test & Verification**:
   - Viết trọn bộ unit & integration tests trong `tests/unit/lead_intelligence/` và `tests/integration/lead_intelligence/`.
