# Epic 21 — Lead Intelligence Architecture Update

> **Status:** REVIEWED and MERGED into `ARCHITECTURE-SPINE.md` as AD-36..AD-42 `[ADOPTED 2026-08-10]`.
>
> ADs below are the pre-merge source; the canonical versions live in `ARCHITECTURE-SPINE.md`. Assumptions that still require validation before implementation are marked `[VALIDATION REQUIRED]` and tracked in `implementation-readiness/implementation-readiness-report-final-2026-08-10.md`.

---

## Tóm tắt thay đổi

| AD | Title | Source | Status |
|----|-------|--------|--------|
| AD-36 | Waterfall enrichment: buy via API | Origami analysis | `[ADOPTED 2026-08-10 — validation: vendor contract/POC]` |
| AD-37 | Signal detection: hybrid build + buy | Market research | `[ADOPTED 2026-08-10 — validation: Crunchbase/LinkedIn ToS + feed feasibility]` |
| AD-38 | Lead scoring: composite fit + intent | Technical research | `[ADOPTED 2026-08-10 — validation: benchmark on pilot workspaces]` |
| AD-39 | Sequencer: multi-channel outreach | Origami analysis | `[ADOPTED 2026-08-10 — validation: email-first legal/ToS]` |
| AD-40 | CRM integration: bidirectional sync | Origami analysis | `[ADOPTED 2026-08-10 — FR-67 aligned to phased read-first]` |
| AD-41 | Zalo integration: Vietnam market | Market research | `[ADOPTED 2026-08-10 — validation: Zalo OA business verification]` |
| AD-42 | Outcome-based pricing support | Market research | `[ADOPTED 2026-08-10 — validation: first-touch attribution model]` |

---

## New Architecture Decisions

### AD-36 — Waterfall enrichment: buy via API, không build 14+ provider integrations

- **Binds:** FR-65 (Enriched Contact Data), Epic 21
- **Prevents:** Build và maintain 14+ email/phone provider integrations trong `app/proprietary/`
- **Rule:**
  - Enrichment requests gọi external waterfall API (Cleanlist/BetterContact) qua Celery async tasks
  - Pay-per-result pricing: chỉ trả khi verified data returned
  - Cache verification results (TTL: 30 days) trong Redis để tránh re-query
  - Fallback: nếu primary API down, dùng basic verification (MX check + pattern matching) `[ASSUMPTION: cần fallback không?]`
- **Data flow:**
  ```
  Lead discovered → Celery task → Waterfall API → Verified? → Cache + Store in Memory
                                                      ↓ No
                                                 Next provider → ... → Exhausted → Flag low confidence
  ```
- **New models:**
  - `EnrichmentRequest` (id, lead_id, status, provider_results, cost_micros)
  - `VerifiedContact` (id, lead_id, email, phone, verification_status, confidence, source_provider)
- **TokenUsage.usage_type mở rộng:** thêm `contact_enrichment`
- **Ghi chú:** Đây là build-vs-buy decision. Mua nhanh hơn, build cheaper ở scale lớn. `[ASSUMPTION: mua trước, build sau nếu scale > X leads/tháng]`

---

### AD-37 — Signal detection framework: hybrid build + buy data feeds

- **Binds:** FR-63 (Intent Signal Detection), Epic 21
- **Prevents:** Build 8+ independent scheduler/notification paths (giống AD-33 Anti-Pattern)
- **Rule:**
  - **Signal Engine là một AlertRule template type** (governed by AD-33), không phải service mới
  - **Signal types:**
    - `funding` — Crunchbase/TechCrunch feeds (buy) + web scraping (build)
    - `hiring` — Job board monitoring (build on existing scrapers)
    - `tech_stack` — Website change detection (build)
    - `executive_move` — LinkedIn monitoring (build on existing scrapers)
    - `news` — News API (buy) + RSS feeds (build)
  - **Signal storage:** `SignalEvent` (id, workspace_id, company_name, signal_type, source_url, confidence, detected_at, processed)
  - **Signal → Lead Score:** High-confidence signals boost lead scoring (governed by AD-38)
  - **Notification:** Reuse AD-33 notification dispatch (in-app + Telegram)
- **Monitoring frequency:** `[ASSUMPTION: daily扫描, real-time qua webhooks cho funding events]`
- **New models:**
  - `SignalEvent` (id, workspace_id, company_name, signal_type, source_url, confidence, detected_at, processed)
  - `SignalSubscription` (id, workspace_id, signal_types, notification_channels)
- **Ghi chú:** Reuse AD-33 Alert Engine infrastructure — không build scheduler riêng

---

### AD-38 — Lead scoring engine: composite fit + intent scoring

- **Binds:** FR-64 (Lead Scoring & Prioritization), Epic 21
- **Prevents:** Rule-based scoring không capture non-obvious signals
- **Rule:**
  - **Composite score = Fit (50%) + Intent (50%)** `[ASSUMPTION: weights configurable per workspace]`
  - **Fit score:** Firmographics (company size, industry, location, tech stack) + ICP match
  - **Intent score:** Signal strength (funding, hiring, tech stack changes) + recency
  - **Scoring method:**
    - Weighted scoring system (configurable per workspace)
    - RAG-based similarity matching against converted leads `[ASSUMPTION: cần historical conversion data]`
    - AI reasoning + rule fallback
  - **Output:** Hot / Warm / Cold classification + numeric score (0-100)
  - **Storage:** `LeadScore` (id, workspace_id, company_name, score, fit_score, intent_score, factors_json, computed_at)
- **Integration with Memory:** Lead scores stored as `Memory` rows with type `semantic` + tags `lead_score` `[ASSUMPTION: dùng Memory table hay separate table?]`
- **TokenUsage.usage_type mở rộng:** thêm `lead_scoring`

---

### AD-39 — Sequencer: multi-channel outreach (email, LinkedIn, Zalo)

- **Binds:** FR-66 (Outbound Prospecting Automation), Epic 21
- **Prevents:** Build separate outreach tools per channel
- **Rule:**
  - **Sequence builder:** Multi-step sequences (trigger → wait → action → condition → action)
  - **Channels:**
    - Email (SMTP/SES) — `[ASSUMPTION: dùng existing email infrastructure]`
    - LinkedIn (via API or automation) — `[ASSUMPTION: LinkedIn API hay browser automation?]`
    - Zalo (Zalo OA API) — Vietnam market
  - **Personalization:** AI-generated messages using lead context + ICP + intent signals
  - **Tracking:** Delivery, open, reply, meeting booked → feedback loop to lead scoring
  - **Compliance:** Unsubscribe handling, rate limiting, Decree 356 compliance
- **New models:**
  - `Sequence` (id, workspace_id, name, trigger_type, status)
  - `SequenceStep` (id, sequence_id, step_order, channel, template, wait_duration, condition)
  - `SequenceEnrollment` (id, sequence_id, lead_id, status, current_step, enrolled_at)
  - `SequenceEvent` (id, enrollment_id, event_type, channel, metadata, created_at)
- **Ghi chú:** Đây là complex feature — nên start với email-only, sau đó add LinkedIn + Zalo

---

### AD-40 — CRM integration: bidirectional sync, read-first pattern

- **Binds:** FR-67 (CRM Integration & Write-Back), Epic 21
- **Prevents:** CRM sync failures gây data inconsistency
- **Rule:**
  - **Phase 1: Read-only dedup** (giống Origami)
    - Match incoming leads against existing CRM contacts by email, domain
    - Flag duplicates before they reach CRM
    - Generate CRM context document for agent understanding
  - **Phase 2: Write-back**
    - Push verified leads to CRM (Salesforce, HubSpot)
    - Map Nowing fields to CRM properties (configurable)
    - Support lead assignment rules
  - **Phase 3: Bidirectional sync**
    - CRM updates → Nowing (contact changes, deal stages)
    - Nowing updates → CRM (lead scores, signals, enrichment)
  - **Conflict resolution:** Last-write-wins with audit log `[ASSUMPTION: conflict strategy]`
- **Integration pattern:** OAuth 2.0 + webhooks for real-time sync
- **New models:**
  - `CrmConnection` (id, workspace_id, provider, credentials_encrypted, sync_config, last_sync_at)
  - `CrmSyncLog` (id, connection_id, direction, entity_type, entity_id, status, error_message, synced_at)
- **Ghi chú:** Reuse existing OAuth connector infrastructure (AD-3, FR-7)

---

### AD-41 — Zalo integration: Vietnam market via Zalo OA

- **Binds:** FR-68 (Zalo Integration), Epic 21
- **Prevents:** Miss Vietnam market opportunity (81% professionals use Zalo)
- **Rule:**
  - **Zalo OA (Official Account) là primary channel** cho Vietnam market
  - **Capabilities:**
    - Send personalized Zalo messages to leads
    - Receive replies → log in lead activity timeline
    - Zalo OA authentication (OAuth flow)
  - **Compliance:** Zalo business messaging policies + Decree 356
  - **Fallback:** Nếu lead không có Zalo → dùng email hoặc LinkedIn
- **New models:**
  - `ZaloConnection` (id, workspace_id, oa_id, access_token_encrypted, refresh_token_encrypted)
  - `ZaloMessage` (id, lead_id, direction, content, status, sent_at, delivered_at, read_at)
- **Ghi chú:** Zalo OA API cần business verification — `[ASSUMPTION: team đã có Zalo OA chưa?]`

---

### AD-42 — Outcome-based pricing: pay per meeting/lead support

- **Binds:** FR-69 (Outcome-Based Pricing Option), Epic 21
- **Prevents:** Pricing model không align với customer value
- **Rule:**
  - **Dual pricing model:**
    - Seat-based (existing): $29/mo (Starter), $99/mo (Pro), Custom (Enterprise)
    - Outcome-based (new): $50/meeting booked, $0.50/lead enriched
  - **Tracking:**
    - Meeting booked = calendar event created from Nowing outreach
    - Lead enriched = verified contact data delivered
  - **Billing:** Reuse existing credit wallet (AD-8) + Stripe integration
  - **Attribution:** Sequence → lead → meeting (multi-touch attribution) `[ASSUMPTION: first-touch hay last-touch?]`
- **New models:**
  - `OutcomeEvent` (id, workspace_id, event_type, lead_id, sequence_id, attribution, cost_micros, created_at)
  - `PricingPlan` (id, workspace_id, plan_type, seat_price, outcome_rates_json, billing_period)
- **Ghi chú:** Đây là pricing strategy, không phải technical architecture — nhưng cần infrastructure support

---

## Architecture Diagram (Updated)

```mermaid
flowchart TB
    subgraph Client["Client Layer"]
        Web["nowing_web<br/>Next.js"]
        Desktop["nowing_desktop<br/>Electron"]
        MCP["MCP Client"]
        Ext["Browser Extension"]
    end

    subgraph APIGW["API / Gateway"]
        NJS["Next.js Server Proxy"]
        API["FastAPI Monolith<br/>nowing_backend"]
    end

    subgraph Core["Nowing Core Modules"]
        Chat["Chat & Agents"]
        Mem["Memory Service<br/>HNSW + GIN"]
        Scrapers["Domain Scrapers<br/>app/proprietary/platforms/"]
        CapReg["Capability Registry"]
        Auto["Automations"]
        Bill["Billing / Usage"]
        Conn["Connectors / OAuth"]
        Admin["Admin / RBAC"]
        PDP["NowingPrivateProvider"]
    end

    subgraph LeadIntelligence["Epic 21 — Lead Intelligence"]
        Enrich["Waterfall Enrichment<br/>External API"]
        Signals["Signal Detection<br/>AlertRule templates"]
        Scoring["Lead Scoring<br/>Fit + Intent"]
        Sequencer["Sequencer<br/>Email + LinkedIn + Zalo"]
        CRM["CRM Sync<br/>Salesforce + HubSpot"]
        Zalo["Zalo OA<br/>Vietnam"]
    end

    subgraph Data["Data Layer"]
        PG["(PostgreSQL<br/>pgvector + Alembic)"]
        Redis["(Redis<br/>Celery + events)"]
        S3["(S3 / MinIO<br/>screenshots)"]
    end

    subgraph External["External"]
        CL["chainlens-research<br/>POST /api/v1/search SSE"]
        LLM["LLM Providers"]
        Stripe["Stripe"]
        OAuth["OAuth Providers"]
        Cleanlist["Cleanlist API<br/>Waterfall Enrichment"]
        CrmAPI["CRM APIs<br/>Salesforce + HubSpot"]
        ZaloAPI["Zalo OA API"]
    end

    Web -->|/api/*| NJS
    MCP -->|MCP over stdio/sse| API
    Ext -->|native| Desktop --> Web
    NJS -->|HTTP| API

    API --> Chat
    Chat --> Mem
    Chat --> CapReg
    Chat -->|deep research| CL
    CapReg --> Scrapers
    CapReg --> Auto
    Scrapers -->|to_chunks()| PG
    Scrapers -->|POST /v1/ingest/scraper| CL
    Chat -->|POST /v1/gap-fill| CL
    CL -->|POST /v1/private-data/search| PDP
    PDP --> PG
    PDP --> Conn
    CapReg -->|async jobs| Redis
    API --> Bill
    Bill -->|charge| Stripe
    API -->|auth| OAuth
    API --> Admin
    Admin --> PG
    Mem --> PG
    Auto --> Redis
    Conn -->|tokens| PG
    Chat -->|screenshot on anti-bot| S3

    %% Epic 21 connections
    Chat --> Enrich
    Enrich -->|async| Cleanlist
    Enrich -->|cache| Redis
    Enrich -->|store| Mem

    Chat --> Signals
    Signals -->|AlertRule| Auto
    Signals -->|events| Redis

    Chat --> Scoring
    Scoring -->|read signals| Signals
    Scoring -->|store| Mem

    Chat --> Sequencer
    Sequencer -->|email| External
    Sequencer -->|LinkedIn| External
    Sequencer --> Zalo
    Zalo -->|OAuth + send| ZaloAPI

    Chat --> CRM
    CRM -->|OAuth + sync| CrmAPI
    CRM -->|dedup| Mem

    Scoring -->|boost| Sequencer
    Signals -->|trigger| Sequencer
```

---

## Implementation Readiness

**Status:** ⛔ Implementation blocked until validation workstream closes (vendor contracts, legal/ToS for Zalo/LinkedIn/Crunchbase, Zalo OA business verification, PII/consent pipeline).

| # | Gate | State | Story / Artifact |
|---|------|-------|------------------|
| 1 | AD-36 — Waterfall enrichment API selection | `[ADOPTED — vendor contract/POC required]` | `Story 21.3` |
| 2 | AD-37 — Signal detection data feeds | `[ADOPTED — Crunchbase/LinkedIn ToS + feed feasibility]` | `Story 21.1` |
| 3 | AD-38 — Lead scoring weights | `[ADOPTED — benchmark on pilot workspaces]` | `Story 21.2` |
| 4 | AD-39 — Sequencer channel priority | `[ADOPTED — email-first, legal/ToS for LinkedIn/Zalo]` | `Story 21.4` |
| 5 | AD-40 — CRM integration order | `[ADOPTED — read-first per FR-67 update]` | `Story 21.5` |
| 6 | AD-41 — Zalo OA availability | `[ADOPTED — business verification required]` | `Story 21.6` |
| 7 | AD-42 — Outcome pricing attribution | `[ADOPTED — first-touch, audit model required]` | `Story 21.7` |

**Recommended start order:**
1. `Story 21.1` (Signal Detection) — foundation, reuse AD-33
2. `Story 21.2` (Lead Scoring) — depends on signals
3. `Story 21.3` (Waterfall Enrichment) — independent, buy via API
4. `Story 21.4` (Sequencer) — depends on scoring + enrichment
5. `Story 21.5` (CRM Sync) — independent
6. `Story 21.6` (Zalo) — Vietnam market, independent
7. `Story 21.7` (Outcome Pricing) — depends on sequencer tracking

---

## Key Assumptions to Confirm

| # | Assumption | Impact if Wrong | How to Validate |
|---|------------|-----------------|-----------------|
| 1 | Dùng Cleanlist/BetterContact API cho waterfall | Wrong vendor = rework | Test both APIs with sample data |
| 2 | Signal monitoring frequency = daily | Too frequent = cost, too rare = miss signals | Interview sales teams |
| 3 | Lead scoring weights: 50% fit + 50% intent | Wrong weights = poor scoring | A/B test with historical data |
| 4 | Sequencer: email-first, then LinkedIn + Zalo | Wrong channel priority = low adoption | Survey target users |
| 5 | CRM: read-first, then write-back | Write-first = data quality issues | Follow Origami pattern |
| 6 | Zalo OA: chưa có, cần setup | Delay Vietnam market | Check with team |
| 7 | Outcome pricing: first-touch attribution | Wrong attribution = pricing disputes | Review industry standard |

---

## Lessons from Origami (Applied to Nowing)

1. **Conversational UX wins** — Origami's chat-first approach is easier than Clay's workflow builder
2. **Waterfall verification = table stakes** — Nowing needs FR-65 for competitive parity
3. **Memory is the differentiator** — Origami has no memory; Nowing's provenance = moat
4. **Signal-first > database-first** — monitoring buying signals beats static filtering
5. **Outcome pricing aligns incentives** — pay per meeting booked > per seat

---

**Draft Date:** 2026-08-10
**Merged Date:** 2026-08-10
**Author:** Mary (Business Analyst) + Winston (Architect)
**Status:** MERGED into `ARCHITECTURE-SPINE.md` (AD-36..AD-42). Validation workstream tracked in `implementation-readiness/implementation-readiness-report-final-2026-08-10.md`.
**Next Step:** Review assumptions, confirm vendor choices, merge into Architecture Spine
