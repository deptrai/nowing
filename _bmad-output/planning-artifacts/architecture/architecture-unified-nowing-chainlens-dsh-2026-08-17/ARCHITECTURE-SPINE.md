---
name: Nowing + ChainLens + Harness Unified Agentic Architecture
type: architecture-spine
purpose: build-substrate
altitude: platform
paradigm: 4-Tier Hybrid Reactive Architecture with Decoupled Autonomous Mission Workers
scope: Full Platform (Nowing Core, ChainLens Engine, DSH Agent Orchestration Sidecar, DeepSeek V4 + Gemini Flash + Qwen)
status: final
created: '2026-08-17'
updated: '2026-08-23T04:06'
approvedBy: Luisphan
binds:
  - AD-101
  - AD-102
  - AD-103
  - AD-104
  - AD-105
  - AD-106
  - AD-107
  - AD-108
  - AD-109
  - AD-110
  - AD-111
  - AD-112
  - AD-113
  - AD-114
  - AD-115
  - AD-116
  - AD-117
  - AD-118
  - AD-119
---

# Architecture Spine — Nowing + ChainLens + DSH Unified Platform

> Canonical architecture contract governing the integration of Nowing (Product & Memory), ChainLens (JIT Research Engine), DSH (Domain-Specific Sidecar Harness — an internal agent orchestration sidecar), and Hybrid Model Routing (Gemini Flash Free Tier + DeepSeek V4 + Qwen 3.8).
>
> **Note:** `DSH` / `Harness` in this document refers to the in-house Python sidecar worker and its agent-team design patterns. It is **not** a dependency on the open-source `github.com/deepseek-ai/deepseek-harness` repository, which may be evaluated for a future self-host pilot. See `dsh-self-host-pilot-plan-2026-08-19.md`.

---

## 1. Design Paradigm & System Topology

The platform operates as a **4-Tier Hybrid Reactive Architecture with Decoupled Autonomous Mission Workers**:

1. **Client & Experience Plane:** Next.js 16 + React 19 web app with Zero-Client reactive optimistic state, Split Canvas, Glass Box Mission Control Widget, and Telegram 3-Second Glanceable Checkpoints.
2. **Product & Control Plane (Nowing Core):** FastAPI backend, PostgreSQL 16 + pgvector, Zero-Cache CDC sync, and authenticated REST/MCP Tool Gateway. Single source of truth for all persistent entities.
3. **Agent Orchestration Plane (DSH Sidecar):** Long-running autonomous worker containers executing multi-step mission trees with DSH Agent-Team Hierarchical Delegation & Multi-Tier Model Routing. The sidecar is implemented as an internal Python worker (`dsh-worker`) and is an approved exception to parent AD-1 (monolith process).
4. **Specialist Research & Ingestion Plane (ChainLens + Scrapers):** Stateless multi-source web crawlers, SERP extractors, and portal adapters streaming chunks back into Nowing.

```mermaid
flowchart TB
    subgraph ClientPlane ["1. Client & Experience Plane"]
        WebUI["Nowing Web (Next.js 16 + React 19)"]
        ZeroClient["Zero-Client (Realtime Canvas & Matrix)"]
        TeleBot["Telegram Checkpoint Bot (Interactive)"]
    end

    subgraph ControlPlane ["2. Product & Control Plane (Nowing Core)"]
        API["FastAPI Core Backend (:8000)"]
        FastMCP["FastMCP/REST Tool Gateway (batch_ingest_leads)"]
        ZeroCache["Zero-Cache Server (:4848)"]
        DB[("PostgreSQL 16 + pgvector (Single Source of Truth)")]
        RedisBroker[("Redis 7 (Streams: nowing:dsh:tasks)")]
    end

    subgraph SidecarPlane ["3. Autonomous Orchestration Plane (dsh Sidecar)"]
        DSHWorker["dsh Sidecar Worker (Supervisor Loop)"]
        HybridRouter["Hybrid LLM Router"]
        GeminiFlash["Tier 1: Google Gemini Flash (Free Tier / rate-limited; do NOT use for PII)"]
        LocalQwen["Tier 1b: Local vLLM (Qwen/Qwen3.8-27B or AWQ; GPU infra overhead)"]
        DeepSeekV4Flash["Tier 2: deepseek-v4-flash (peak/off-peak; see §5)"]
        DeepSeekV4Pro["Tier 3: deepseek-v4-pro (peak/off-peak; see §5)"]
    end

    subgraph EnginePlane ["4. Stateless Ingestion & Scraper Plane"]
        ChainLensEngine["ChainLens Research Engine (/api/v1/search)"]
        PortalScrapers["Vietnam Scrapers (Batdongsan, Chợ Tốt, TopCV)"]
    end

    WebUI <-->|REST / SSE / Auth| API
    ZeroClient <-->|WebSocket CDC < 10ms| ZeroCache
    TeleBot <-->|Webhooks / Callbacks| API

    API <-->|SQL / HNSW Vector Search| DB
    API -->|XADD Mission Tasks| RedisBroker
    DB -.->|Logical WAL Replication: zero_publication| ZeroCache

    RedisBroker -->|XREADGROUP + XAUTOCLAIM| DSHWorker
    DSHWorker <-->|Inference| HybridRouter
    HybridRouter <-->|Fast Parsing & Ingest ($0)| GeminiFlash
    HybridRouter <-->|Local Offline Backup ($0)| LocalQwen
    HybridRouter -.->|High-Volume Extraction| DeepSeekV4Flash
    HybridRouter -.->|Deep CoT Reasoning| DeepSeekV4Pro

    DSHWorker -->|Tool Call: chainlens.research| ChainLensEngine
    ChainLensEngine -->|POST /v1/chainlens/ingest (Idempotent)| API
    DSHWorker -->|Tool Call: portal.scrape| PortalScrapers
    DSHWorker -->|Tool Call: batch_ingest_leads| FastMCP
    FastMCP -->|SQL Bulk Upsert & PII Encrypt| DB
```

---

## 2. Architectural Invariants (AD-101 to AD-110)

### AD-101 — Stateless ChainLens Engine & Unified Ingestion [ADOPTED]
- **Binds:** `ChainLens` service and Nowing `chunks` repository.
- **Prevents:** Split-brain vector database divergence and double-hop RAG latency.
- **Rule:**
  1. ChainLens MUST remain strictly stateless regarding permanent vector storage. It parses HTML, extracts text, computes citations, and streams structured chunks to Nowing via `POST /v1/chainlens/ingest` using a service-to-service API key (see OQ-7 / Story 39-1).
  2. The existing `NowingIngestService` (Nowing → ChainLens `POST /v1/ingest/scraper`) is the legacy scraper feed contract (AD-34) and MUST be retired or repointed once `POST /v1/chainlens/ingest` is live. The two directions MUST NOT coexist in production.
  3. Nowing stores chunks in its own `chunks` table with deterministic `UUIDv5` IDs. `chunks.id` MUST be a UUID column (not the legacy integer primary key).

### AD-102 — Decoupled Sidecar Worker & FastMCP/REST Gateway [ADOPTED]
- **Binds:** `dsh-worker` sidecar container (internal Python worker, not `github.com/deepseek-ai/deepseek-harness`) and Nowing FastAPI core.
- **Prevents:** Long-running agent loops (1–8 hours) blocking Celery fast-path queues or FastAPI web threads.
- **Rule:**
  1. Autonomous missions MUST be dispatched via Redis Streams (`nowing:dsh:tasks`) with a centralized stream name registry (see `app/config/__init__.py`).
  2. The sidecar interacts with Nowing data exclusively through authenticated interfaces: `batch_ingest_leads` via `POST /api/v1/workspaces/:workspace_id/leads/batch-ingest` or an equivalent MCP tool (not a raw FastAPI route inside the MCP server). It MUST NOT access the database directly.
  3. Worker crash recovery MUST use `XAUTOCLAIM` and DLQ after 3 delivery attempts (`nowing:dsh:dlq`).
  4. This sidecar is an approved exception to parent AD-1 (monolith). It is a stateless worker, not a business-domain microservice.

### AD-103 — Multi-Tier Hybrid LLM Router with Free-Tier Priority [ADOPTED]
- **Binds:** `HybridLLMRouter` and inference backends.
- **Prevents:** Unnecessary token spend, `<think>` token JSON parse failures, and provider lock-in.
- **Rule:**
  1. **Tier 1 Primary (Free Workhorse):** High-volume text parsing, intent categorization, and tool dispatch route to **Google Gemini Flash (Free Tier)**. [ASSUMPTION] Free tier is rate-limited (1,500 RPD, 15 RPM, 1M TPM) and MUST NOT process PII, proprietary business data, or customer content per Google's data-usage terms. When quota is exceeded or data is sensitive, the router MUST fall back to Tier 2/3.
  2. **Tier 1b Secondary (Local GPU):** Offline and high-privacy parsing routes to **local vLLM** with a Qwen model (e.g., `Qwen/Qwen3.8-27B` or an AWQ community quantization such as `barrydeen/Qwen3.8-27B-AWQ-4bit`). [ASSUMPTION] Local vLLM has zero marginal token cost but incurs GPU infrastructure overhead (~$50–$150/month per 1,000 leads at 10–30% utilization on an RTX 4090 / A10G-class GPU). CPU-only hosts route 100% to Tier 1/3.
  3. **Tier 2 (High-Volume Burst):** Large-scale batch extraction falls over to **`deepseek-v4-flash`** when Tier 1 is unavailable or data is sensitive. Use peak/off-peak pricing (off-peak ~$0.22/$0.66, peak ~$0.44/$1.32 per 1M tokens as of 2026-08-16) and prefer off-peak windows when workload is elastic.
  4. **Tier 3 (Deep Strategy & CoT):** Complex valuation, reverse ICP scoring, and Telegram checkpoint generation route to **`deepseek-v4-pro`** using peak/off-peak pricing (off-peak ~$0.66/$1.98, peak ~$1.32/$3.96 per 1M tokens as of 2026-08-16 with Thinking: High).

### AD-104 — Zero-Cache CDC Reactivity [ADOPTED]
- **Binds:** PostgreSQL replication configuration and frontend state management.
- **Prevents:** Custom WebSocket sync boilerplate, cache-invalidation bugs, and PII leakage through CDC.
- **Rule:**
  1. All realtime UI updates for leads, signal events, and mission progress MUST be driven by PostgreSQL Logical WAL Replication (`zero_publication`) streaming to `zero-cache` (< 10ms latency).
  2. The `zero_publication` column list for the `leads` table MUST include only: `id`, `workspace_id`, `title`, `company_name`, `domain`, `source_url`, `fit_score`, `status`, `enriched`, `created_at`, `updated_at`. It MUST NOT include `value_hmac`, `is_blacklisted`, or any PII-derived columns.
  3. The heavy `chunks` table is explicitly EXCLUDED from `zero_publication`.
  4. [ASSUMPTION] Next.js 16 Cache Components remove implicit fetch caching; the frontend Zero client code is audited and uses explicit `'use cache'` directives where needed.

### AD-105 — PII Vault, Unlock Billing & Decree 13/2023/ND-CP Compliance [ADOPTED]
- **Binds:** `verified_contacts`, `leads`, `pii_blacklists`/`dnc_records`, credit wallet, and audit logs.
- **Prevents:** Regulatory PII violations, data leakage, customer disputes over invalid contacts, and unbilled PII access.
- **Rule:**
  1. Phone numbers and emails MUST be stored encrypted at rest in the `verified_contacts` vault using the canonical encryption service `VerifiedContactEncryption` (Fernet/TokenEncryption) as defined in `app/services/pii/verified_contact_encryption.py`.
  2. Contact deduplication MUST use blind HMAC-SHA256 hashes (`value_hmac`). The HMAC input is a single normalized contact string in the form `HMAC_SHA256("phone=<normalized_phone>|email=<normalized_email>|domain=<domain>", HMAC_SECRET)`. `value_hmac` MUST be `NOT NULL` and part of a `UNIQUE(workspace_id, value_hmac)` constraint.
  3. Frontend displays masked strings (`0908 *** 456`) until the user unlocks the contact.
  4. Contact unlock debits **1.5 credits** (1,500 `credit_micros`) from the workspace owner wallet AFTER successful PII decryption.
     - The endpoint is `POST /api/v1/workspaces/:workspace_id/leads/:lead_id/contacts/:contact_id/unlock`.
     - It checks `verified_contacts.is_unlocked = FALSE` and `User.credit_micros_balance >= 1,500` for the attributed owner.
     - In a single transaction: decrypt phone/email, set `is_unlocked = TRUE`, call `wallet_credit.apply_debit(user_id, 1_500, event_type='contact_unlock')`, and write a `BillingEvent` with `event_type='contact_unlock'`, `event_entity_type='verified_contact'`, `cost_micros=1_500`, and `reason='contact_unlock'`.
     - If decryption fails, the wallet is not debited.
  5. `verified_contacts` MUST contain `is_unlocked` (boolean) and `pii_access_audit_logs` (JSONB or reference to `AuditEvent`) recording every access: `user_id`, `workspace_id`, `lead_id`, `access_type`, `timestamp`, `ip_address`.
  6. PII opt-out requests MUST be honored within 24h: add HMAC to the blacklist/DNC table, mark `verified_contacts.is_unlocked = FALSE`, return credits, and schedule PII deletion or irreversible anonymization per Decree 13/PDPD.
  7. Nowing's Terms of Service (ToS) legally structures Nowing as a *Data Processor on behalf of user*.

### AD-106 — DSH Agent-Team Hierarchical Delegation & Specialist Team Pattern [ADOPTED]
- **Binds:** Agent task tree dispatch within the internal `dsh-worker` sidecar.
- **Prevents:** Monolithic prompt bloat and uncontrolled subagent recursion.
- **Rule:** The Mission Supervisor delegates sub-tasks to an Expert Pool (Research Specialist, Scraper Specialist, Valuation Specialist, PII Auditor) using Producer-Reviewer and Fan-out/Fan-in patterns inspired by agent-harness design literature. This is a design pattern; it does not require the `deepseek-harness` runtime.

### AD-107 — Hermetic Testability & $0 API Cost Gate [ADOPTED]
- **Binds:** `nowing_evals`, CI/CD pipelines, and local unit/integration tests.
- **Prevents:** Flaky external API dependencies and costly token burn during automated test runs.
- **Rule:** All CI/CD test suites and regression evals MUST execute in hermetic mode using Golden Streaming Cassettes (`.sse.jsonl`) and in-memory Fake FastMCP transport. Automated Quality Gates enforce: F1 Phone $\ge 98.0\%$, Hallucination $\le 0.1\%$, and MST Modulo 11 $\ge 99.5\%$.

### AD-108 — Container Lifecycle, Zombie Guard & WAL Protection [ADOPTED]
- **Binds:** Dockerfiles, Celery beat schedulers, and PostgreSQL server configuration.
- **Prevents:** Chromium zombie process accumulation on Dokploy and PostgreSQL WAL disk exhaustion.
- **Rule:**
  1. Scraper and Sidecar Dockerfiles MUST use `tini` as PID 1 with hard session context timeout of 60s.
  2. PostgreSQL configuration MUST enforce `max_slot_wal_keep_size = 4096MB` and `wal_keep_size = 1024MB` to protect host disk from replication slot backlogs.

### AD-109 — Batch Ingestion & Concurrency Deadlock Prevention [ADOPTED]
- **Binds:** `batch_ingest_leads` service/route and database repositories.
- **Prevents:** High HTTP roundtrip latency, distributed PostgreSQL row-lock deadlocks, and duplicate nullable rows.
- **Rule:**
  1. `batch_ingest_leads` is exposed as an authenticated **REST endpoint** at `POST /api/v1/workspaces/:workspace_id/leads/batch-ingest` (50–100 items per batch, `min_length=1`). A named MCP tool in `nowing_mcp` is **not in scope** for this epic; if the internal DSH sidecar later uses MCP transport, it will be covered by a separate story. Evaluation of the `deepseek-harness` repo as an optional self-host runtime is deferred to a post-beta pilot.
  2. All incoming items MUST produce a deterministic `value_hmac` using the canonical HMAC input (AD-105, Rule 2). Items with no phone/email/domain MUST be rejected as degenerate before persistence.
  3. The `leads.value_hmac` and `verified_contacts.value_hmac` columns MUST be `NOT NULL` and guarded by a `UNIQUE(workspace_id, value_hmac)` constraint.
  4. All SQL bulk upserts on `leads` and `verified_contacts` MUST deterministically sort records by `value_hmac ASC` before executing `INSERT ... ON CONFLICT DO UPDATE`.
  5. The endpoint MUST enforce a per-workspace rate limit (e.g., 30 batches/minute) and return `ingested_count`, `skipped_blacklisted_count`, `failed_count`, `execution_time_ms`, and `lead_ids`.

### AD-110 — PII Opt-Out Blacklist, Anti-Fraud Refund & Two-Tier Unlock UX [ADOPTED]
- **Binds:** `pii_blacklists` / DNC tables, credit refund engine, and Next.js Lead Matrix component.
- **Prevents:** Failure to honor Right-to-be-Forgotten requests, refund arbitrage abuse, and user click fatigue.
- **Rule:**
  1. The canonical opt-out/blacklist vault is the **existing DNC infrastructure** (`workspace_dnc_records` and `global_dnc_records`) keyed by HMAC-SHA256. A new `pii_blacklists` table MUST NOT be created unless an explicit migration merges DNC data into it. Story 26.1 uses the existing DNC tables for blacklist checks.
  2. Crawlers, batch ingest, and contact unlocks MUST bypass HMACs present in the active DNC/blacklist table.
  3. Opt-out workflow:
     - Users submit an opt-out request via an authenticated endpoint (`POST /api/v1/workspaces/:workspace_id/pii-opt-out`).
     - The HMAC of the contact is inserted into the active DNC table with `is_active = TRUE` and a `reason`.
     - Any already-unlocked `verified_contacts` for that HMAC are marked `is_unlocked = FALSE` and credits are returned to the workspace owner wallet within 24h.
     - PII is deleted or irreversibly anonymized per Decree 13/PDPD and the operation is logged to `pii_access_audit_logs`/`AuditEvent`.
  4. **Anti-Fraud Refund Cap:** Auto-Refund SLA 24h is capped at a maximum of **15% of total unlocked leads** per billing cycle per workspace. Refunded credits are non-withdrawable. The billing cycle is the workspace's subscription billing cycle or a fixed 30-day window if no cycle is set.
  5. **Two-Tier Unlock UX:** On first contact unlock in a session, the UI displays a Smart Confirmation Popover showing the masked contact preview, the 1.5 credit cost, and a session-level "1-Click Fast Unlock" toggle. If enabled, subsequent unlocks in the same session skip the popover. The toggle resets on session end or 30 minutes of inactivity.

---

## 3. Data Plane & Unified PostgreSQL 16 Schema

```
  ┌─────────────────────────────────┐               ┌─────────────────────────────────┐
  │  chunks (pgvector + GIN)        │               │  leads (Zero-Cache CDC)         │
  │  - id: UUID (Deterministic v5)  │               │  - id: UUID (PK)                │
  │  - workspace_id: Int (FK, RLS)  │               │  - workspace_id: Int (FK, RLS)  │
  │  - document_id: UUID (FK)       │◄──────────────┤  - title / company: Text        │
  │  - content: Text                │ (Citations &  │  - source_url: Text             │
  │  - metadata: JSONB              │  Evidence)    │  - fit_score: Int (0-100)       │
  │  - embedding: Vector(1536)      │               │  - value_hmac: String NOT NULL  │
  │  - HNSW Index (m=16, ef_c=64)   │               │    (UNIQUE per workspace)       │
  └─────────────────────────────────┘               └────────────────┬────────────────┘
                                                                     │
                                                                     ▼
  ┌─────────────────────────────────┐               ┌─────────────────────────────────┐
  │  DNC records (workspace_dnc_    │               │  verified_contacts (PII Vault)  │
  │  records / global_dnc_records)  │               │  - lead_id: UUID (FK)           │
  │  (Opt-out Vault)                │               │  - phone: Encrypted (Fernet/   │
  │  - value_hmac: String (PK)      │               │    TokenEncryption)             │
  │  - record_type: String          │               │  - email: Encrypted             │
  │  - reason: String               │               │  - is_unlocked: Boolean         │
  │  - requested_at: Timestamp      │               │  - pii_access_audit_logs: JSONB │
  │  - is_active: Boolean           │               │                                 │
  └─────────────────────────────────┘               └─────────────────────────────────┘
```

---

## 4. API & Protocol Contracts

### 4.1 ChainLens Ingestion Contract (`POST /v1/chainlens/ingest`)
```typescript
interface ChainLensIngestPayload {
  workspace_id: number;
  scraper_id: string; // e.g. "batdongsan.scrape" | "web.deep_research"
  run_id: string;
  chunks: Array<{
    chunk_id?: string; // UUIDv5 for idempotency
    source_url: string;
    title: string;
    content: string;
    published_at?: string;
    metadata: {
      author?: string;
      citations: string[];
      domain_pack?: string;
      confidence_score: number;
    };
  }>;
}
```

### 4.2 Batch Ingestion Contract (`POST /api/v1/workspaces/:workspace_id/leads/batch-ingest`)
```python
class LeadItemPayload(BaseModel):
    source_url: str
    title: str
    contact_name: str | None = None
    phone: str | None = None          # Encrypted at rest in verified_contacts
    email: str | None = None
    fit_score: int = Field(ge=0, le=100)
    intent_signals: list[str] = Field(default_factory=list)
    extracted_metadata: dict[str, Any] = Field(default_factory=dict)

class BatchLeadIngestPayload(BaseModel):
    task_id: str
    leads: list[LeadItemPayload] = Field(min_length=1, max_length=100)

class BatchLeadIngestResponse(BaseModel):
    ingested_count: int
    skipped_blacklisted_count: int
    failed_count: int
    execution_time_ms: float
    lead_ids: list[UUID]
```

A named MCP tool in `nowing_mcp` is **not in scope** for this epic; if the internal DSH sidecar later uses MCP transport, it will be covered by a separate story. Evaluation of the `deepseek-harness` repo as an optional self-host runtime is deferred to a post-beta pilot.

---

## 5. Tokenomics & Unit Economics

Unit economics is a **business hypothesis**, not an architecture invariant. It is maintained separately in `UNIT-ECONOMICS-HYPOTHESIS.md` and must be validated before any pricing or subscription commitments.

The architecture only requires that:
- `TokenUsage.cost_micros` records actual spend per call/ingest job.
- `wallet_credit.py` debits the workspace owner wallet for billable events.
- `HybridLLMRouter` logs model usage so the business hypothesis can be recalibrated with real data.

---

## 6. Assumptions & Reviewable Items

- `[ASSUMPTION]` Google AI Studio / Gemini API Key with active Free Tier quota is configured via `GEMINI_API_KEY` in `.env`.
- `[ASSUMPTION]` Gemini Flash Free Tier data is **not** used for PII, proprietary, or customer content. Sensitive routes fall back to Tier 2/3 or local vLLM.
- `[ASSUMPTION]` Host on Dokploy has optional 1 dedicated GPU (e.g. RTX 4090 / A10G) for local vLLM Qwen 3.8. If CPU-only, the `HybridLLMRouter` routes 100% to Gemini Flash + DeepSeek V4 Cloud.
- `[ASSUMPTION]` Local vLLM has zero marginal token cost but GPU infrastructure overhead of ~$50–$150/month per 1,000 leads at 10–30% utilization.
- `[ASSUMPTION]` DeepSeek peak/off-peak pricing from 2026-08-16 is current; the `HybridLLMRouter` schedules elastic workloads off-peak when possible.
- `[ASSUMPTION]` Residential proxy, CAPTCHA, and HLR/Zalo costs in `UNIT-ECONOMICS-HYPOTHESIS.md` are unverified and must be replaced with live vendor quotes.
- `[ASSUMPTION]` Telegram Bot Webhook endpoint `/api/v1/gateway/telegram/webhook` is configured with SSL for interactive inline callbacks.
- `[ASSUMPTION]` Logical replication slot `zero_publication` is pre-created on PostgreSQL for instant Zero-Cache synchronization.
- `[DECISION]` PII encryption method: canonical service is `VerifiedContactEncryption` (Fernet/TokenEncryption).

---

## 7. Deferred Decisions
- **DEF-101:** Dynamic GPU autoscaling for vLLM based on spot instance prices (deferred to Q4 2026).
- **DEF-102:** Direct Zalo OA Outbound messaging automation (deferred to Sprint 3 post-Closed Beta).

---

## 8. The Manus-Killer Autonomous Workstation Evolution (AD-111 to AD-115)

> Canonical contract (2026-08-20, approved): Quy định vai trò của `nowing` là Autonomous Workstation sở hữu 25 phân hệ tính năng Manus.im.

### AD-111 — Browser Operator Chrome Extension CDP Bridge [ADOPTED]
- **Binds:** `nowing` Chrome Extension (Manifest V3) và FastAPI mission supervisor.
- **Rule:**
  - Backend → Extension dùng **SSE** trên endpoint `GET /api/v1/dsh/cdp/stream`. Extension mở một `fetch` SSE reader và xác thực bằng PAT/Bearer token (hỗ trợ `@plasmohq/storage` và `chrome.storage.local` fallback).
  - Lệnh CDP được publish qua Redis channel `cdp_stream:{user_id}` dưới dạng JSON với `action`, `mission_id`, `command_id`, `url`, `selector`, `text`, `direction`, `px`, `format`.
  - Extension thực thi qua `chrome.debugger` API (`navigate`, `click`, `fill`, `scroll`, `extract`, `take_screenshot`, `detect_challenge`) trên tab phù hợp (tìm theo hostname, tạo mới nếu cần), tự động kiểm tra signature CAPTCHA/2FA, rồi trả kết quả qua REST `POST /api/v1/dsh/cdp/result`.
  - `POST /api/v1/dsh/cdp/result` nhận `result`, `error`, `requires_human`, `challenge`, lưu vào `cdp_result:{user_id}:{mission_id}` (pipeline `rpush` + `expire` + `ltrim`).
  - Capability `browser_operator.execute` (đăng ký trong `app.capabilities.browser_operator`) là giao diện chính thức; `web_crawler` subagent được prompt sử dụng khi user yêu cầu điều khiển trình duyệt.
  - Thao tác trực tiếp trên các tab đã đăng nhập sẵn cookies (LinkedIn, Facebook Ads, Jira, Shopee). Hỗ trợ Human Live Takeover tức thì khi `requires_human=true`.

### AD-112 — In-Sandbox Linux Shell & Python Data Science Studio [ADOPTED]
- **Binds:** `nowing` Execution Sandbox container.
- **Rule:** Docker ephemeral container chạy non-root với PID 1 `tini`, RAM cap 512MB, timeout 60s. Tích hợp sẵn `pandas`, `numpy`, `matplotlib`, `openpyxl` để làm sạch dữ liệu lớn và xuất file Excel `.xlsx` chuyên nghiệp.

### AD-113 — Full-Stack Web App Builder & Traefik/Caddy Instant Hosting [ADOPTED]
- **Binds:** `nowing` Web Builder và Traefik (production/Dokploy) / Caddy (self-host/dev) reverse proxy.
- **Rule:** Agent sinh project Next.js/React trong `/workspace/web-app`. Deploy 1-click tự động lên `https://[app-name].apps.nowing.net` có HTTPS và dynamic routing.
- **Production (Traefik):** web app containers được khởi chạy với Docker labels hoặc file provider để Traefik đăng ký route theo `Host`/`HostRegexp`. Caddy file-provider là fallback cho self-host / local dev.

### AD-114 — Design View Visual "Mark Tool" Canvas AST Mutator [ADOPTED]
- **Binds:** Nowing Canvas Web Preview và React code generator.
- **Rule:** Iframe preview inject Bounding Box Selector. Khi user khoanh vùng phần tử UI, agent bóc DOM XPath/CSS và AST-mutate chính xác component JSX.

### AD-115 — Inbound Mail Gateway (`task@nowing.ai`) & Scheduled Tasks 2.0 [ADOPTED]
- **Binds:** Inbound email webhook và Celery scheduler.
- **Rule:** Inbound email forward kích hoạt task ngầm và trả kết quả qua SMTP kèm deliverables. Scheduled tasks lưu snapshot lần chạy trước và thực hiện Delta Analysis trước khi gửi báo cáo Telegram/Slack.



---

## 9. Readiness Gap ADs (AD-116 to AD-118)

Các AD sau được bổ sung sau Implementation Readiness Assessment 2026-08-20 để đóng gap giữa PRD và architecture spine.

### AD-116 — Bounded Memory Injection & Recall Performance (NFR-1b) [ADOPTED]
- **Binds:** Memory retrieval / injection path, `nowing_recall`, `MemoryExtractionService`.
- **Rule:** Memory injection vào prompt phải có bound: tối đa **8.000 ký tự** context, retrieval phải là **O(top-k)** trên index đã materialized (không scan toàn bộ `Memory` table). `MemoryExtractionService` kiểm tra bound trước khi append; nếu vượt, cắt theo relevance score và log `memory_injection_truncated`.

### AD-117 — Vertical Client Tenancy & `client_id` RLS (FR-56, NFR-MULTI-1) [ADOPTED]
- **Binds:** Public agent-chat API, `Memory`, `TokenUsage`, `Run`, `ResearchThread`.
- **Rule:** Mọi query từ public API **bắt buộc** lọc theo `client_id` (hard filter). PostgreSQL RLS context `SET LOCAL app.current_client_id` được set qua middleware sau PAT validation. `client_id = NULL` chỉ dùng cho Nowing-internal queries. Composite RLS (`workspace_id` + `client_id`) là cách triển khai mặc định; `workspace_id-only` queries tự động thêm `client_id IS NULL`.

### AD-118 — Agent Registry & `agent_configs` Persistence (FR-57) [ADOPTED]
- **Binds:** `AgentConfig` model, chat orchestrator, `NewChatRequest`, `agent_chat_routes`.
- **Rule:** Tồn tại bảng `agent_configs` với schema: `id`, `client_id` (nullable), `name`, `system_instructions`, `enabled_tools` (text[]), `disabled_tools` (text[]), `model_name`, `citations_enabled` (bool), `is_active` (bool). `AgentConfig` là global (không workspace-scoped). Chat orchestrator load config theo `agent_id`, prepend `system_instructions`, filter tool allowlist. Nếu `agent_id` không tồn tại hoặc disabled → 404 và fallback về default agent.

---

## 10. Data Engineering Invariant (AD-119)

> Bổ sung 2026-08-23 để đóng gap giữa code thực tế (đã có multi-layer rule-based parsing) và tài liệu kiến trúc (chưa quy định tường minh chuẩn Deterministic-First Extraction).

### AD-119 — Deterministic-First Parsing & Selective Micro-LLM Fallback [ADOPTED]
- **Binds:** Toàn bộ Scraper Adapters (`app/proprietary/platforms/*`), `app/capabilities/*/scrape/executor.py`, `app/services/bds_aggregator/`, `app/lead_intelligence/adapters/`, và mọi module cào/bóc tách dữ liệu từ nguồn ngoài.
- **Prevents:** (a) Lãng phí token LLM vào việc parse dữ liệu có cấu trúc đã biết trước (giá, SĐT, diện tích, địa chỉ). (b) Latency tăng vô ích do round-trip tới LLM cho text đã match 100% regex/schema. (c) Developer tạo scraper mới rồi ném raw HTML/JSON vào Agent context thay vì viết parser chuẩn.
- **Rule:**
  1. **Pass 1 — Pure Deterministic Parsing (0 token LLM, bắt buộc):** Mọi scraper adapter BẮT BUỘC thực hiện bước đầu tiên bằng Pure Deterministic Parsers — Regex, BeautifulSoup/lxml, Unicode normalizer, và Pydantic schema validation — với chi phí $0 token LLM. Đây là tầng bóc tách chính, không phải bước chuẩn bị cho LLM.
     - **Chuẩn hóa giá:** Regex `_parse_price()` / `_extract_number_and_unit()` xử lý chuỗi `"3.5 tỷ"`, `"500 triệu"`, `"72-75 m²"` thành giá trị số chuẩn.
     - **Chuẩn hóa SĐT:** Regex `extract_phone_from_title()` / `normalize_vietnamese_phone()` bóc SĐT từ title, description, và contact button HTML.
     - **Tách địa chỉ:** `_split_address()` phân tách chuỗi comma-delimited thành Phường/Xã, Quận/Huyện, Tỉnh/Thành phố dựa trên tiền tố địa lý Việt Nam.
     - **Schema mapping:** `parse_listing()` / `normalize_lead()` ánh xạ raw dict sang typed Pydantic model (`BatdongsanListing`, `NormalizedLead`, `VnBdsAggregatedListing`).
  2. **Confidence Gate — Schema Completeness Check:** Sau Pass 1, mỗi record được chấm `confidence_score` dựa trên tỷ lệ trường bắt buộc đã match:
     - **confidence ≥ 0.85:** Record đi thẳng vào Data Plane (Deduplication → Scoring → Persistence) mà KHÔNG qua bất kỳ LLM nào.
     - **confidence < 0.70 hoặc thiếu trường quan trọng** (SĐT, Giá, Địa chỉ cấp Quận): Record đủ điều kiện cho Pass 2.
     - **0.70 ≤ confidence < 0.85:** Record đi vào Data Plane nhưng được đánh dấu `needs_enrichment = true` cho batch enrichment sau (không block luồng chính).
  3. **Pass 2 — Selective Micro-LLM Fallback (chỉ khi cần):** Khi record không match 100%, CHỈ những trường bị thiếu/mơ hồ mới được đưa cho LLM xử lý. Rule:
     - Sử dụng Model Tier 1 (Gemini Flash Free / Local Qwen) theo AD-103 — KHÔNG dùng Tier 2/3 cho việc bóc tách cơ bản.
     - Prompt CHỈ chứa đoạn text liên quan tới trường cần trích xuất (ví dụ: chỉ gửi `description` để tìm SĐT viết bằng chữ), KHÔNG gửi toàn bộ listing.
     - Kết quả LLM phải qua validation lại bằng Regex/Schema trước khi merge vào record — LLM không được là nguồn chân lý cuối cùng cho structured data.
     - Budget: tối đa **200 input tokens** mỗi lần gọi micro-extraction. Vượt ngưỡng → bỏ qua và giữ `confidence` thấp.
  4. **Post-Extraction Pipeline (không dùng LLM):** Các bước sau PHẢI hoàn toàn deterministic, 0 token:
     - **Deduplication:** Union-Find trên phone_key, address_key, image_hash (xem `bds_aggregator/dedupe.py`).
     - **Price Conflict Detection:** So sánh giá cross-source, gắn `ConflictFlag` khi chênh lệch > 20%.
     - **Rule-Based Scoring:** Tính `confidence_score` từ Source Trust, Overlap, Freshness, Price Consistency (xem `bds_aggregator/scoring.py`).
     - **DNC/Blacklist Suppression:** Loại bỏ record theo HMAC blacklist trước khi persist (AD-105/AD-110).
  5. **Token Budget Guard cho Agent Context:** Khi dữ liệu đã qua pipeline trên được trả về Agent chính trong Chat:
     - Output ≤ `RUN_OUTPUT_CHAR_CAP` (40.000 chars, ~10k tokens): trả inline.
     - Output > cap: lưu vào `runs` table, Agent nhận preview + `run_<uuid>` reference để phân trang qua `read_run`/`search_run`.
     - Context cũ tự động spill ra DB khi tổng token vượt 100k (xem `SpillingContextEditingMiddleware`).
  6. **Quy tắc khi tạo Scraper mới:** Mọi scraper adapter mới (trong `app/proprietary/platforms/` hoặc `app/capabilities/*/scrape/`) BẮT BUỘC:
     - Có file `parsers.py` riêng chứa toàn bộ logic bóc tách deterministic, I/O-free, unit-testable.
     - Có Pydantic schema typed output (file `schemas.py`).
     - Pass 1 phải cover ≥ 90% record trong test fixture mà không cần LLM.
     - Nếu cần Pass 2, phải justify trong PR description tại sao regex/heuristic không đủ.
- **Existing compliance (verified 2026-08-23):**
  - `app/proprietary/platforms/batdongsan/parsers.py` — pure regex/BS4, 0 LLM calls ✅
  - `app/proprietary/platforms/muaban_bds/` — pure HTML parsing ✅
  - `app/services/bds_aggregator/` — normalize → dedupe → score, 0 LLM calls ✅
  - `app/lead_intelligence/adapters/batdongsan.py` — normalize_lead() pure rule-based ✅
  - `app/lead_intelligence/services/deduplication_service.py` — entity dedup, 0 LLM calls ✅
  - `app/lead_intelligence/scoring/service.py` — fit/intent scoring chủ yếu rule-based (LLM chỉ cho converted_similarity RAG fallback) ✅
- **Gap cần đóng (post-adoption):**
  - Chưa có Pass 2 Micro-LLM worker riêng — hiện tại record thiếu trường chỉ có `confidence` thấp và chờ Agent chính xử lý khi user hỏi.
  - Story cần tạo: `XX.Y — Micro-Extraction Worker for Low-Confidence Scraper Records` để implement Pass 2 với Tier 1 model routing.
