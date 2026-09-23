# Admin Third-Party Health Alerts & Operations Panel — Design

## 1. Tổng quan

Xây dựng một **Admin Operations Center** (`/admin/operations` hoặc mở rộng `/admin/telemetry`) chuyên monitor health của **mọi third-party dependency** mà Nowing sử dụng. Mục tiêu:

- Phát hiện sớm third-party down/degraded trước khi user bị ảnh hưởng.
- Tách biệt từng provider/model/platform một cách chi tiết.
- Có alerting thresholds rõ ràng (green / yellow / red).
- Hỗ trợ drill-down: click một platform để xem logs, runs, errors.
- Cho phép admin nhận notifications (Telegram/Slack/Email) khi third-party quan trọng fail.

---

## 2. Kiến trúc đề xuất

### 2.1 Tổng thể

```
┌─────────────────────────────────────────────────────────────┐
│                    /admin/operations                         │
├─────────────────────────────────────────────────────────────┤
│  Top Alert Banner — Active incidents + Acknowledge button   │
├─────────────────────────────────────────────────────────────┤
│  [Overview] [LLM/AI] [Scrapers] [Connectors] [Infra]       │
├─────────────────────────────────────────────────────────────┤
│  Status Cards Grid (grouped by category)                    │
├─────────────────────────────────────────────────────────────┤
│  Real-time Timeline / Event Feed                            │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Backend components cần xây mới

| Component | File đề xuất | Nhiệm vụ |
|-----------|-------------|----------|
| `HealthProbeScheduler` | `app/services/health/scheduler.py` | Lập lịch chạy probe định kỳ (mỗi 30s-5m) cho tất cả third-party |
| `HealthProbeRegistry` | `app/services/health/registry.py` | Đăng ký probe theo category: model, scraper, connector, proxy, etc. |
| `ThirdPartyHealthService` | `app/services/health/third_party_service.py` | Chạy probe, aggregate kết quả, lưu snapshot Redis/DB |
| `HealthResultStore` | `app/services/health/result_store.py` | Lưu kết quả probe gần nhất + time-series ngắn hạn |
| `AdminHealthAlertEngine` | `app/services/health/alert_engine.py` | Đánh giá thresholds, emit alerts, deduplicate |
| `AdminOperationsRoutes` | `app/routes/admin_operations_routes.py` | `/api/v1/admin/operations/*` endpoints |
| `HealthProbeTask` | `app/tasks/celery_tasks/health_probe_task.py` | Celery task gọi scheduler mỗi 30s |

### 2.3 Data model

```yaml
# Bảng mới: admin_health_status
- id: serial
- category: enum  # model, scraper, connector, proxy, messaging, payment, storage, infra
- service_id: str  # vd "azure/gpt-5.1", "batdongsan", "google_drive"
- service_name: str
- display_group: str  # "LLM/Vision", "Vietnam Real Estate", "Google Workspace"
- status: enum  # healthy, degraded, unavailable, disabled, not_configured
- last_probe_at: timestamp
- next_probe_at: timestamp
- latency_ms: int
- error_rate_15m: float
- success_rate_15m: float
- last_error: text
- metadata: jsonb  # { "provider", "endpoint", "model", "region", "cost_today" }
- alert_threshold: jsonb  # { "degraded_latency_ms", "dead_latency_ms", "error_rate_pct" }
- acknowledged_until: timestamp
- created_at, updated_at

# Bảng mới: admin_health_history
- id, service_id, probe_at, status, latency_ms, error_message

# Bảng mới: admin_health_alert_rules
- id, name, category, service_id_pattern, condition_json, channel (telegram/slack/email), enabled

# Bảng mới: admin_health_alerts
- id, rule_id, service_id, triggered_at, status, message, acknowledged_by, resolved_at
```

---

## 3. Các category cần monitor

### 3.1 Core Infrastructure

| Service | Probe | Metrics | Thresholds |
|---------|-------|---------|------------|
| **PostgreSQL** | `SELECT 1` + `pg_stat_activity` count | pool utilization, slow queries, replication lag | >95% pool red; replication lag >50MB red |
| **Redis** | `PING` + `INFO memory` + `INFO clients` | ping latency, memory %, connected clients, evicted keys | latency >100ms yellow, >500ms red; memory >90% red |
| **Zero Cache** | `GET http://zero:4848/keepalive` | sync status, active WS clients, query latency | keepalive fail red; replication lag >30s yellow |
| **Caddy Proxy** | `GET https://nowing.ai/health` + parse Caddy config | 5xx rate, cert expiry, upstream latency | cert expiry <7d red; 5xx >2% red |
| **Celery Workers** | `celery_app.control.inspect()` | active workers, queue depth, task error rate | 0 workers red; queue >10k red |
| **DSH Worker** | `GET /dsh/health` hoặc internal ping | uptime, event throughput | fail red |

### 3.2 LLM / AI / Vision / Embedding — từng model cụ thể

Có 2 loại:

1. **GLOBAL static models** từ `global_llm_config.yaml` (Azure OpenAI, Gemini, DeepSeek, vLLM, OpenRouter...)
2. **User BYOK models** từ bảng `Connection` + `Model`

Với mỗi model/connection:

| Probe | Kết quả | Metrics |
|-------|---------|---------|
| `verify_connection()` từ `model_connection_service.py` | OK / AUTH_FAILED / NOT_FOUND / RATE_LIMITED / TIMEOUT / UNREACHABLE | latency, status code |
| `test_model()` với `messages=[{"role":"user","content":"Hello"}]` | OK / error | TTFT, latency, token cost |

**Admin panel hiển thị theo dạng bảng:**

| Model / Connection | Provider | Endpoint | Status | Latency | Last Error | 15m Error Rate | Cost Today |
|-------------------|----------|----------|--------|---------|-----------|----------------|------------|
| Azure GPT-5.1 | azure | `https://...azure.com` | 🟢 healthy | 120ms | - | 0.1% | $12.50 |
| Gemini Flash | gemini | `generativelanguage...` | 🟡 degraded | 2.1s | 429 rate limit | 8% | $3.20 |
| Local vLLM Qwen | openai | `http://localhost:8000/v1` | 🔴 dead | timeout | unreachable | 100% | $0 |
| DeepSeek Pro | deepseek | `api.deepseek.com` | 🟢 healthy | 890ms | - | 0% | $45.00 |
| OpenRouter Claude 4 | openrouter | `openrouter.ai` | 🟢 healthy | 1.2s | - | 0.5% | $8.00 |

**Nhóm theo capability:**
- Chat models
- Vision models
- Image generation models
- Embedding models
- Reranker models
- TTS / Voice models

**Embedding model health:**
- Probe: `embed_text("health_check")` qua `config.embedding_model_instance`
- Metrics: latency, dimension, provider (Azure/OpenAI/Ollama/local), error rate

### 3.3 Platform Scrapers — 25 platform + từng cá thể

Với mỗi platform trong `nowing_backend/app/proprietary/platforms/`, chạy probe định kỳ:

| Platform | Probe | Failure Criteria |
|----------|-------|------------------|
| amazon | Search keyword `test` với rotating US proxy | Dog page / 403 / captcha >50% |
| batdongsan | Ping `apimap.batdongsan.com.vn` + test ticker | 403 Cloudflare / token expired |
| cafef | Lấy price history `VNM` | Empty response / ASP.NET throttling |
| chotot | Public ad-listing gateway | 403 HMAC signature / datacenter IP |
| crawler (general) | Fetch safe test URL qua Scrapling | SSRF block / redirect loop |
| google_maps | Query known place ID | Consent cookie / geoblock |
| google_search | Query `"test"` với proxy | CAPTCHA / unusual traffic |
| indeed | Search `developer` | Turnstile / 403 |
| instagram | Query public handle | Login wall / checkpoint |
| itviec | Search IT jobs | Cloudflare challenge |
| linkedin | Jobs guest search `engineer` | 429 / 999 / login wall |
| masothue | Lookup test tax code | 5 req/min rate limit / Cloudflare |
| muaban_bds | Phone unveil test | JWT expiry / account ban |
| muasamcong | Fetch recent tenders | Portal maintenance / TLS failure |
| reddit | `r/all.json` | 429 / geoblock |
| shopee | Search `ao` | Akamai Bot Manager / signature fail |
| spatial_planning | GIS tile service | CRS mismatch / slow WFS |
| telegram | Public channel preview + MTProto ping | FloodWait / DC migration |
| tiktok | Video search probe | Signature rot / IP blacklist |
| topcv | Search recent listings | Bot detection / selector breakage |
| vietnamworks | Job search v1.0 | API deprecation / token expiry |
| vietstock | Ticker `HPG` trading info | Session cookie / RequestVerificationToken |
| walmart | Search UPC/keyword | PerimeterX / 403 |
| xactions | Lead resolver test | Upstream outage / throttling |
| youtube | InnerTube search `Nowing` | Consent wall / IP block |

**UI dạng grid 25 ô, mỗi ô có:**
- Status badge 🟢🟡🔴
- Tên platform + quốc gia/target
- Last success
- 15m success rate
- Last error message (tooltip)
- Button "Test Now" / "View Logs"

**Metrics tổng hợp:**
- Platform success rate (rolling 15m, 1h, 24h)
- Avg latency per platform
- CAPTCHA/403 rate per platform
- Proxy/IP depletion rate

### 3.4 Proxy & Anti-Bot

| Service | Probe | Metrics | Thresholds |
|---------|-------|---------|------------|
| **DataImpulse proxy pool** | HEAD `https://www.google.com` qua proxy | latency, success rate, available IPs, bandwidth | >5s red; error >20% yellow; >50% red |
| **Capsolver** | `getBalance` API | balance, solve success rate, circuit-breaker latch | balance < $5 yellow, < $1 red; `_solver_latched` true red |
| **2Captcha** | `getBalance` API | balance, success rate | balance < $5 yellow, < $1 red |
| **Cloudflare Turnstile** | Sample verify call | pass/fail ratio, avg response time | fail >20% red |

### 3.5 External Research & Search

| Service | Probe | Metrics | Thresholds |
|---------|-------|---------|------------|
| **ChainLens Research** | `GET /api/v1/health` + sample `search` | status, latency, cost per call, degraded rate | `engine_unavailable` / timeout >5% yellow; >15% red |
| **ChainLens Ingest** | Sample `POST /api/v1/ingest` | throughput, retry rate, queue depth | retry >10% red |
| **SearXNG / Web Search** | `GET /search?q=test` | latency, result count, rate limit | fail >20% red |
| **OpenRouter Catalog** | `GET /api/v1/models` | fetch latency, model count, parse errors | fail red |

### 3.6 Document ETL / Parsers

| Service | Probe | Metrics | Thresholds |
|---------|-------|---------|------------|
| **Docling** | Parse small PDF sample | success, RAM usage, time | crash red |
| **Unstructured API** | POST sample | latency, 429 rate | fail red |
| **LlamaParse** | POST sample | quota, queue time | quota exceeded red |
| **Azure Document Intelligence** | POST sample | quota, page count bill shock | quota >80% yellow |
| **Vision LLM parser** | Convert + prompt 1 page | latency, cost, token limit | >60s red |

### 3.7 Storage

| Service | Probe | Metrics | Thresholds |
|---------|-------|---------|------------|
| **Local object store** | stat mount point | disk %, file count | >90% red |
| **Azure Blob Storage** | HEAD container | upload/download latency, 403/404 | fail red |

### 3.8 SaaS Connectors — 20+ connectors

Mỗi connector có 1 row:

| Connector | Probe | Metrics |
|-----------|-------|---------|
| Google Drive | `GET /drive/v3/about` | token valid, last sync, 429 count |
| Gmail | `GET /gmail/v1/users/me/profile` | token valid, scope ok |
| Google Calendar | `GET /calendar/v3/users/me/calendarList` | sync token expired |
| Google Sheets | `GET /v4/spreadsheets/{id}` | read quota |
| OneDrive | `GET /v1.0/me/drive` | tenant consent |
| Teams | `GET /v1.0/me/joinedTeams` | permissions |
| Jira | `JQL search` | cloud ID, token |
| Confluence | `GET /wiki/rest/api/space` | permissions |
| Notion | `POST /v1/search` | rate limit, unshared page |
| Airtable | `GET /v0/meta/bases` | rate limit |
| Linear | GraphQL `viewer` | complexity |
| Slack | `auth.test` | token revoked |
| Discord | `GET /users/@me` | intent, rate limit |
| Dropbox | `users/get_current_account` | quota, token |
| ClickUp | `GET /v2/user` | access |
| GitHub | `GET /user` or repo probe | secondary rate limit |
| Bookstack | `GET /api/shelves` | self-hosted reachable |
| Luma | `GET /public/v1/calendar` | key valid |
| Lark/Feishu | `GET /open-apis/bitable/v1/apps` | IP whitelist |
| Composio | `GET /api/v1/integrations` | timeout |

**Admin panel:** bảng với columns: Connector, Active Accounts, Status, Last Sync, Tokens Expiring 48h, 24h Error Count, Top Error Code.

### 3.9 Omnichannel Messaging Gateways

| Channel | Probe | Metrics | Thresholds |
|---------|-------|---------|------------|
| Telegram Bot | `getMe` / `getWebhookInfo` | webhook SSL, secret, bot blocked | fail red |
| Telegram MTProto (telethon) | `client.is_user_authorized()` | session, DC, FloodWait | fail red |
| WhatsApp Cloud | Graph API `messages` test | app secret, 24h window | fail red |
| WhatsApp Baileys Bridge | `GET http://whatsapp-bridge:9929/health` | QR status, session | fail red |
| Slack Gateway | `auth.test` + inbound HMAC verify | signature, socket | fail red |
| Discord Gateway | `GET /users/@me` | webhook, permissions | fail red |
| SendGrid | `GET /v3/user/credits` | inbound ECDSA, payload size | fail red |
| Mailgun | `GET /v3/domains` | inbound HMAC, domain | fail red |
| SMTP Server | Socket connect + EHLO | auth, relay, port block | fail red |
| Zalo OA | `GET /v2.0/oa/acc/getinfo` | 25h token, template | fail red |

### 3.10 Payments & Banking

| Service | Probe | Metrics | Thresholds |
|---------|-------|---------|------------|
| Stripe | `GET /v1/account` + webhook check | API key, webhook lag, signature fail | webhook lag >60s red |
| VietQR Payout | `GET /v2/health` hoặc balance | merchant balance, NAPAS success rate, webhook reconciliation | balance low red; success <90% red |

### 3.11 Sandboxes & Cloud Services

| Service | Probe | Metrics | Thresholds |
|---------|-------|---------|------------|
| Daytona Sandbox | `GET /api/health` hoặc target ping | active sandboxes, spawn latency, crash rate | spawn >120s red |
| Docker Socket Engine | `docker info` | child containers, dangling volume size | fail red |

### 3.12 Observability

| Service | Probe | Metrics | Thresholds |
|---------|-------|---------|------------|
| OpenTelemetry Collector | `GET :13133/healthz` + gRPC 4317 | buffer drops, trace export errors | export errors >5% red |
| Grafana Cloud | POST sample trace/metric | API key, ingestion lag | key invalid red |

---

## 4. Health Probe Implementation Details

### 4.1 Probe types

```python
class HealthProbe(ABC):
    @property
    @abstractmethod
    def service_id(self) -> str
    
    @abstractmethod
    async def probe(self) -> HealthResult
    
    @property
    def interval(self) -> timedelta:
        return timedelta(seconds=30)
```

Probe cụ thể:
- `ModelHealthProbe`
- `ScraperHealthProbe(platform)`
- `ConnectorHealthProbe(connector_type, connector_id)`
- `ProxyHealthProbe`
- `CaptchaSolverHealthProbe(solver_name)`
- `InfrastructureHealthProbe(service)`
- `ChainLensHealthProbe(endpoint)`
- `MessagingGatewayHealthProbe(channel)`
- `PaymentGatewayHealthProbe(gateway)`

### 4.2 Probe results

```python
@dataclass
class HealthResult:
    service_id: str
    service_name: str
    category: str
    display_group: str
    status: Literal["healthy", "degraded", "unavailable", "disabled", "not_configured"]
    latency_ms: int
    last_error: str | None
    error_rate_15m: float
    success_rate_15m: float
    metadata: dict[str, Any]
    probed_at: datetime
```

### 4.3 Scheduler

- Chạy như 1 Celery beat task mỗi 30s.
- Lấy danh sách probe từ registry.
- Chạy probe song song với `asyncio.gather` + semaphore (max 20 concurrent).
- Lưu kết quả Redis cache 5 phút + DB `admin_health_status`.
- Gửi event vào Redis pub/sub để frontend realtime cập nhật.

### 4.4 Alert Engine

```python
class HealthAlertRule:
    id: int
    name: str
    category: str | None  # None = all
    service_id_pattern: str | None  # regex
    condition: AlertCondition  # e.g. status == red for 2 consecutive probes
    channels: list[AlertChannel]  # telegram, slack, email, in-app
    cooldown_minutes: int
    enabled: bool
```

Mặc định rules:
- Bất kỳ model nào `unavailable` 2 lần liên tiếp → alert
- Scraper success rate < 50% trong 15 phút → alert
- Proxy `dead` → alert
- Redis / PostgreSQL / Celery unavailable → CRITICAL alert
- ChainLens `engine_unavailable` > 15% → alert
- VietQR / Stripe webhook lag > 60s → alert

---

## 5. API Endpoints đề xuất

```
GET  /api/v1/admin/operations/status
     Query: category, group, status, q
     Response: list of HealthResult

GET  /api/v1/admin/operations/status/{service_id}
     Response: HealthResult + history

POST /api/v1/admin/operations/status/{service_id}/probe
     Force re-probe now

GET  /api/v1/admin/operations/categories
     Response: list categories + counts

GET  /api/v1/admin/operations/alerts
     Query: status, category, from, to

POST /api/v1/admin/operations/alerts/{alert_id}/ack

GET  /api/v1/admin/operations/alerts/rules
     Response: list rules

POST /api/v1/admin/operations/alerts/rules
     Create rule

PUT  /api/v1/admin/operations/alerts/rules/{rule_id}

DELETE /api/v1/admin/operations/alerts/rules/{rule_id}

GET  /api/v1/admin/operations/metrics/{service_id}
     Time series: latency, success rate, error rate
```

---

## 6. Frontend Components đề xuất

| Component | File | Chức năng |
|-----------|------|-----------|
| `AdminOperationsPage` | `app/admin/operations/page.tsx` | Trang chính với tabs |
| `HealthOverviewGrid` | `components/admin/operations/HealthOverviewGrid.tsx` | Grid status cards theo category |
| `HealthStatusCard` | `components/admin/operations/HealthStatusCard.tsx` | Card cho 1 service |
| `HealthTable` | `components/admin/operations/HealthTable.tsx` | Bảng chi tiết sort/filter |
| `HealthTimeline` | `components/admin/operations/HealthTimeline.tsx` | Timeline sự kiện |
| `AlertBanner` | `components/admin/operations/AlertBanner.tsx` | Active alerts top banner |
| `AlertRulesPanel` | `components/admin/operations/AlertRulesPanel.tsx` | Quản lý rules |
| `HealthMetricChart` | `components/admin/operations/HealthMetricChart.tsx` | Recharts time series |
| `ModelHealthPanel` | `components/admin/operations/ModelHealthPanel.tsx` | Tab LLM/AI |
| `ScraperHealthGrid` | `components/admin/operations/ScraperHealthGrid.tsx` | Tab Scrapers (25 ô) |
| `ConnectorHealthPanel` | `components/admin/operations/ConnectorHealthPanel.tsx` | Tab Connectors |
| `InfrastructurePanel` | `components/admin/operations/InfrastructurePanel.tsx` | Tab Infra |

---

## 7. Tích hợp với hệ thống hiện tại

Tái sử dụng:
- `model_connection_service.verify_connection()` / `test_model()` cho model probes.
- `admin_telemetry_service.get_proxy_health()` cho proxy.
- `admin_telemetry_service.get_celery_queue_stats()` cho Celery.
- `hybrid_llm_router._vllm_health()` cho vLLM.
- `app/redis_client.py` cho Redis health.
- `app/database/` engine cho DB health.
- Mỗi scraper module có thể expose `health_probe()` method hoặc dùng canonical search query.
- `chainlens/private_provider.py` và schemas cho ChainLens health.

Mở rộng `/admin/telemetry` hoặc tạo `/admin/operations` mới. `/admin/operations` khuyến nghị hơn vì nó rõ ràng hơn "telemetry".

---

## 8. Phạm vi MVP & Phân phối

### Phase 1 (cần làm ngay)
1. Core infrastructure: PostgreSQL, Redis, Zero Cache, Celery, Caddy
2. LLM/AI models: tất cả global models + BYOK (dùng verify/test model)
3. Embedding model
4. Proxy + DataImpulse
5. ChainLens Research + Ingest
6. 25 platform scrapers (probe đơn giản)
7. Alert engine cơ bản + 5 default rules

### Phase 2
1. SaaS connectors health (20+)
2. Messaging gateways (10)
3. Document ETL parsers (5)
4. Payments (Stripe, VietQR)
5. Storage (local, Azure Blob)
6. Sandboxes (Daytona, Docker)
7. Advanced alert channels (Telegram/Slack/Email)

### Phase 3
1. Auto-remediation (rotate proxy, disable failing model, retry scraper)
2. Historical analytics
3. Cost impact correlation
4. Runbook integration

---

## 9. Câu hỏi cần quyết định

1. **Tên trang:** dùng `/admin/operations` hay mở rộng `/admin/telemetry`?
2. **Lưu trữ health data:** chỉ Redis cache hay cần DB tables mới?
3. **Probe frequency:** 30s cho infra, 2m cho models, 5m for scrapers, 1h for connectors?
4. **Alert channels đầu tiên:** in-app notification + Telegram bot hay cả Slack/Email?
5. **Có cần auto-disable** model/platform khi unavailable liên tục không?
6. **Scope ban đầu:** toàn bộ 25 scrapers + 10+ models + infra, hay tập trung theo nhóm ưu tiên?

---

## 10. Files / Stories cần tạo

Backend:
- `nowing_backend/app/services/health/__init__.py`
- `nowing_backend/app/services/health/registry.py`
- `nowing_backend/app/services/health/scheduler.py`
- `nowing_backend/app/services/health/probe_base.py`
- `nowing_backend/app/services/health/probes/model_probe.py`
- `nowing_backend/app/services/health/probes/scraper_probe.py`
- `nowing_backend/app/services/health/probes/connector_probe.py`
- `nowing_backend/app/services/health/probes/infrastructure_probe.py`
- `nowing_backend/app/services/health/probes/chainlens_probe.py`
- `nowing_backend/app/services/health/probes/messaging_probe.py`
- `nowing_backend/app/services/health/probes/payment_probe.py`
- `nowing_backend/app/services/health/result_store.py`
- `nowing_backend/app/services/health/alert_engine.py`
- `nowing_backend/app/routes/admin_operations_routes.py`
- `nowing_backend/app/tasks/celery_tasks/health_probe_task.py`
- Alembic migrations cho `admin_health_status`, `admin_health_history`, `admin_health_alert_rules`, `admin_health_alerts`

Frontend:
- `nowing_web/app/admin/operations/page.tsx`
- `nowing_web/components/admin/operations/*.tsx`
- `nowing_web/lib/apis/admin-operations-api.service.ts`

Tests:
- `nowing_backend/tests/unit/services/health/test_*_probe.py`
- `nowing_backend/tests/integration/routes/test_admin_operations.py`

---

*Design này đủ chi tiết để chuyển thành story/dev plan.*
