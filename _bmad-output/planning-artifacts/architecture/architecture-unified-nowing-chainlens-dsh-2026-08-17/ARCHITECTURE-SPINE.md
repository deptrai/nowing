---
name: Nowing + ChainLens + Harness Unified Agentic Architecture
type: architecture-spine
purpose: build-substrate
altitude: platform
paradigm: 4-Tier Hybrid Reactive Architecture with Decoupled Autonomous Mission Workers
scope: Full Platform (Nowing Core, ChainLens Engine, Harness Orchestrator, DeepSeek V4 + Gemini Flash + Qwen)
status: review
created: '2026-08-17'
updated: '2026-08-17T05:00'
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
---

# Architecture Spine — Nowing + ChainLens + Harness Unified Platform

> Canonical architecture contract governing the integration of Nowing (Product & Memory), ChainLens (JIT Research Engine), Harness (Agent Team Factory), and Hybrid Model Routing (Gemini Flash Free Tier + DeepSeek V4 + Qwen 3.8).

---

## 1. Design Paradigm & System Topology

The platform operates as a **4-Tier Hybrid Reactive Architecture with Decoupled Autonomous Mission Workers**:

1. **Client & Experience Plane:** Next.js 16 + React 19 web app with Zero-Client reactive optimistic state, Split Canvas, Glass Box Mission Control Widget, and Telegram 3-Second Glanceable Checkpoints.
2. **Product & Control Plane (Nowing Core):** FastAPI backend, PostgreSQL 16 + pgvector, Zero-Cache CDC sync, and authenticated REST/MCP Tool Gateway. Single source of truth for all persistent entities.
3. **Agent Orchestration Plane (Harness + dsh Sidecar):** Long-running autonomous worker containers executing multi-step mission trees with Harness Hierarchical Delegation & Multi-Tier Model Routing. This is an approved exception to parent AD-1 (monolith process); the sidecar is a separate stateless worker, not a business-domain microservice.
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
- **Binds:** `dsh-worker` sidecar container and Nowing FastAPI core.
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
  1. Phone numbers and emails MUST be stored encrypted at rest in the `verified_contacts` vault. The canonical encryption service is the existing `VerifiedContactEncryption` (Fernet/TokenEncryption) as defined in `app/services/pii/verified_contact_encryption.py`. A migration to AES-256-GCM is [DEFERRED] pending an explicit AD amendment and a decrypt/re-encrypt plan (see M12).
  2. Contact deduplication MUST use blind HMAC-SHA256 hashes (`value_hmac`). The HMAC input is a single normalized contact string in the form `HMAC_SHA256("phone=<normalized_phone>|email=<normalized_email>|domain=<domain>", HMAC_SECRET)`. `value_hmac` MUST be `NOT NULL` and part of a `UNIQUE(workspace_id, value_hmac)` constraint.
  3. Frontend displays masked strings (`0908 *** 456`) until the user unlocks the contact.
  4. Contact unlock debits **1.5 credits** (1,500 `credit_micros`) from the workspace owner wallet AFTER successful PII decryption, via a `BillingEvent` with `event_type='contact_unlock'`. Unlock is atomic: decrypt and debit in the same transaction; if decryption fails, no debit.
  5. `verified_contacts` MUST contain `is_unlocked` (boolean) and `pii_access_audit_logs` (JSONB or reference to `AuditEvent`) recording every access: `user_id`, `workspace_id`, `lead_id`, `access_type`, `timestamp`, `ip_address`.
  6. PII opt-out requests MUST be honored within 24h: add HMAC to the blacklist/DNC table, mark `verified_contacts.is_unlocked = FALSE`, return credits, and schedule PII deletion or irreversible anonymization per Decree 13/PDPD.
  7. Nowing's Terms of Service (ToS) legally structures Nowing as a *Data Processor on behalf of user*.

### AD-106 — Harness Hierarchical Delegation & Specialist Team Pattern [ADOPTED]
- **Binds:** Agent task tree dispatch within `dsh-worker`.
- **Prevents:** Monolithic prompt bloat and uncontrolled subagent recursion.
- **Rule:** The Mission Supervisor delegates sub-tasks to an Expert Pool (Research Specialist, Scraper Specialist, Valuation Specialist, PII Auditor) using Harness Producer-Reviewer and Fan-out/Fan-in patterns.

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
  1. `batch_ingest_leads` is exposed as an authenticated **REST endpoint** at `POST /api/v1/workspaces/:workspace_id/leads/batch-ingest` (50–100 items per batch, `min_length=1`). It MAY additionally be registered as a **named MCP tool** in `nowing_mcp` if the DSH sidecar uses MCP transport; the route inside `nowing_backend` is FastAPI, not an MCP server route.
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
  │  dnc_records / pii_blacklists   │               │  verified_contacts (PII Vault)  │
  │  (Opt-out Vault)                │               │  - lead_id: UUID (FK)           │
  │  - value_hmac: String (PK)      │               │  - phone: Encrypted ( Fernet   │
  │  - record_type: String          │               │    or AES-256-GCM ) [DEFERRED]  │
  │  - reason: String               │               │  - email: Encrypted             │
  │  - requested_at: Timestamp      │               │  - is_unlocked: Boolean         │
  │  - is_active: Boolean           │               │  - pii_access_audit_logs: JSONB │
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

A named MCP tool `batch_ingest_leads` MAY also be registered in `nowing_mcp` if the DSH sidecar uses MCP transport; the backend canonical endpoint is the FastAPI route above.

---

## 5. Tokenomics & Unit Economics [ASSUMPTION — PENDING VALIDATION]

> The numbers below are a working hypothesis. DeepSeek pricing changed to peak/off-peak on 2026-08-16; vLLM is not $0 (it has GPU infrastructure cost); and residential-proxy, CAPTCHA, and HLR/Zalo costs have not been verified with vendor contracts. Do not use these figures for pricing or subscription commitments until validated.

| Task Type / Cost Center | Primary Model | COGS / 1,000 Leads (baseline) | Notes |
| :--- | :--- | :--- | :--- |
| **HTML Parsing & Initial Filtering** | **Google Gemini Flash (Free Tier)** | **$0.00–$0.05** | Only for non-PII parsing. PII/sensitive data routes to Tier 2/3. |
| **Local Offline / Fallback** | **Qwen 3.8-27B (vLLM)** | **$50.00–$150.00 GPU infra** | Allocated per 1,000 leads at 10–30% GPU utilization; marginal token cost is $0. |
| **Residential Proxies & CAPTCHA** | VN Residential Pool + Solvers | **$7.80 [UNVERIFIED]** | Cost must come from a live pilot or vendor quote. |
| **High-Volume Burst Extraction** | **deepseek-v4-flash** | **$1.20–$4.00** | Off-peak $0.22/$0.66; peak $0.44/$1.32 per 1M tokens; depends on cache hit rate. |
| **Deep Reasoning & ICP Scoring** | **deepseek-v4-pro** | **$3.50–$10.00** | Off-peak $0.66/$1.98; peak $1.32/$3.96 per 1M tokens with Thinking: High. |
| **Telco HLR / Zalo Lookup** | 15% Verification Sample | **$1.50 [UNVERIFIED]** | Cost must come from a live pilot or vendor contract. |
| **TỔNG GIÁ VỐN (COGS) / 1.000 LEADS** | **Multi-Tier Architecture** | **$17.00–$35.00 (working range)** | **$150.00 revenue (1.5k credits)** is a placeholder until FR-69 pricing is finalized. |

**Gross margin working range: 76.7%–88.7%** (not the previously claimed 89.8%).

---

## 6. Assumptions & Reviewable Items

- `[ASSUMPTION]` Google AI Studio / Gemini API Key with active Free Tier quota is configured via `GEMINI_API_KEY` in `.env`.
- `[ASSUMPTION]` Gemini Flash Free Tier data is **not** used for PII, proprietary, or customer content. Sensitive routes fall back to Tier 2/3 or local vLLM.
- `[ASSUMPTION]` Host on Dokploy has optional 1 dedicated GPU (e.g. RTX 4090 / A10G) for local vLLM Qwen 3.8. If CPU-only, the `HybridLLMRouter` routes 100% to Gemini Flash + DeepSeek V4 Cloud.
- `[ASSUMPTION]` Local vLLM has zero marginal token cost but GPU infrastructure overhead of ~$50–$150/month per 1,000 leads at 10–30% utilization.
- `[ASSUMPTION]` DeepSeek peak/off-peak pricing from 2026-08-16 is current; the `HybridLLMRouter` schedules elastic workloads off-peak when possible.
- `[ASSUMPTION]` Residential proxy, CAPTCHA, and HLR/Zalo costs in §5 are unverified and must be replaced with live vendor quotes.
- `[ASSUMPTION]` Telegram Bot Webhook endpoint `/api/v1/gateway/telegram/webhook` is configured with SSL for interactive inline callbacks.
- `[ASSUMPTION]` Logical replication slot `zero_publication` is pre-created on PostgreSQL for instant Zero-Cache synchronization.
- `[REVIEW]` PII encryption method: final decision is [DEFERRED] between existing Fernet/TokenEncryption and AES-256-GCM migration (see AD-105 Rule 1 and M12).

---

## 7. Deferred Decisions
- **DEF-101:** Dynamic GPU autoscaling for vLLM based on spot instance prices (deferred to Q4 2026).
- **DEF-102:** Direct Zalo OA Outbound messaging automation (deferred to Sprint 3 post-Closed Beta).
