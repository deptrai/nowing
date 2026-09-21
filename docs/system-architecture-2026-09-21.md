# Nowing Ecosystem System Architecture — September 2026

**Updated:** 2026-09-21 | **Verified against:** `nowing/nowing_backend/app/`, `chainlens-research/apps/`, `XActions/src/`

> Tất cả diagram dùng hướng trái-phải (LR) để đọc ngang, không bị nén dọc như dạng TB.

## 1. Ecosystem Overview — 3 repos, 1 platform

```mermaid
flowchart LR
    subgraph Clients["Clients"]
        Web["nowing_web<br/>Next.js 16"]
        Desktop["nowing_desktop<br/>Electron"]
        Ext["Browser Extension"]
        Obsidian["nowing_obsidian"]
        TeleBot["Telegram Bot"]
    end

    subgraph Nowing["nowing/ backend"]
        API["FastAPI :8000<br/>121 routes"]
        subgraph Agents["Agent Layer"]
            MainAgent["Main Agent<br/>LangGraph + 26 mw"]
            JevRouter["Jev Pre-Router ⭐<br/>~300ms"]
            SubAgents["21 Subagents"]
            VoiceW["Voice Workers<br/>LiveKit + Silero"]
        end
        subgraph Decision["Decision Layer (Epic 39)"]
            DS["DecisionService"]
            JevBE["JevBackend"]
            LLMBE["LLMJsonBackend"]
            QR["QuestionRegistry"]
            CG["ConfidenceGate"]
        end
        subgraph Data["Data"]
            PG[("PostgreSQL<br/>pgvector")]
            Redis[("Redis 8<br/>Streams + Celery")]
        end
        subgraph Svc["Key Services"]
            Dedup["dedup/<br/>entity match"]
            PII["pii/<br/>redact"]
            BDS["bds_aggregator/<br/>merge"]
            LIS["lead_intelligence/<br/>score + signals"]
            Seq["sequencer/<br/>outreach"]
        end
    end

    subgraph CL["chainlens-research/"]
        CLAPI["NestJS API<br/>/api/v1/search"]
        CLMCP["MCP Server<br/>ask + search + contents"]
        CLWorker["Worker<br/>async jobs"]
        CLNow["nowing/<br/>auth + private-data"]
    end

    subgraph XA["XActions/"]
        XMCP["MCP :3001<br/>x_scrape"]
        XCore["core/<br/>base-crawler<br/>dispatcher"]
        XScrapers["scrapers/<br/>10 categories"]
        XStream["streaming/<br/>Redis Stream"]
        XProxy["proxy/<br/>SOCKS5 pool"]
    end

    subgraph Ext["External"]
        JevAPI["Jev API<br/>typesafe.ai"]
        LLM["LLM Providers"]
        Telco["Telco / SIP"]
        OAuthP["OAuth"]
        Pay["Stripe + VietQR"]
    end

    Web <-->|"REST + SSE"| API
    Desktop --> Web
    TeleBot <--> API
    API --> MainAgent
    MainAgent --> JevRouter
    MainAgent -->|"task()"| SubAgents
    JevRouter --> DS
    DS --> JevBE --> JevAPI
    DS --> LLMBE --> LLM
    DS --> QR
    DS --> CG
    API --> PG
    API --> Redis
    MainAgent --> PG

    SubAgents -->|"research"| CLAPI
    API -->|"ingest"| CLAPI
    CLNow -->|"private-data"| API
    CLAPI --> CLWorker

    SubAgents -->|"x_scrape"| XMCP
    XMCP --> XCore --> XScrapers
    XScrapers -->|"XADD"| XStream
    XStream -->|"XREADGROUP"| API
    XCore --> XProxy

    VoiceW --> Telco
    API --> OAuthP
    API --> Pay
```

## 2. Middleware Stack — Main Agent (26 layers)

```mermaid
flowchart LR
    MSG["User Message<br/>VN/EN"] --> M1["busy_mutex"] --> M2["otel_span"] --> M3["todos"] --> M4["memory<br/>inject"] --> M5["anonymous_doc"] --> M6["knowledge_tree"] --> M7["kb_persistence"] --> M8["skills"] --> M9["checkpointed_subagent<br/>task() tool"] --> M10["jev_router ⭐<br/>~300ms hint"] --> M11["mode_budget"] --> M12["model_call_limit"] --> M13["tool_call_limit"] --> M14["context_editing"] --> M15["compaction"] --> M16["noop_injection"] --> M17["retry"] --> M18["fallback"] --> M19["tool_call_repair"] --> M20["permission"] --> M21["doom_loop"] --> M22["action_log"] --> M23["patch_tool_calls"] --> M24["dedup_hitl"] --> M25["plugins"] --> M26["anthropic_cache"] --> LLM["LLM Call<br/>Claude/GPT/Auto"]
```

## 3. ChainLens Internal Architecture

```mermaid
flowchart LR
    subgraph Input["Input"]
        NW["nowing backend"]
        EXT["External users<br/>MCP/API"]
    end

    subgraph CLAPI["apps/api (NestJS)"]
        Search["search/<br/>POST /api/v1/search"]
        Research["research/<br/>deep research"]
        Ask["answer/<br/>Q&A synthesis"]
        Contents["contents/<br/>page extraction"]
        Ingest["ingest/<br/>scraper + chainlens"]
        GapFill["gap-fill/<br/>self-healing KB"]
        Embed["embeddings/<br/>vector index"]
        Chunk["chunk/<br/>chunking"]
        Discover["discover/<br/>source discovery"]
        Crawl["crawl/<br/>web crawl"]
        Extract["extract/<br/>content extraction"]
        Nowing2["nowing/<br/>auth + private-data"]
        Media["media/<br/>audio transcription"]
        Swarm["swarm/<br/>parallel research"]
        Evidence["evidence-pack/<br/>citations"]
    end

    subgraph MCP4["apps/mcp"]
        MCPTools["tools/<br/>ask, search, contents,<br/>wideResearch, monitors,<br/>chats, codeSearch, blocks"]
    end

    subgraph W["apps/worker"]
        Jobs["async job processing"]
    end

    DB2[("PostgreSQL")]
    Redis2[("Redis")]

    NW -->|"POST /api/v1/search"| Search
    NW -->|"POST /v1/chainlens/ingest"| Ingest
    NW -->|"POST /v1/private-data/search"| Nowing2
    Nowing2 -->|"query docs"| NW
    EXT --> MCPTools
    MCPTools -->|"calls"| CLAPI
    CLAPI --> DB2
    CLAPI --> Redis2
    Redis2 --> Jobs
    Jobs --> DB2
```

## 4. XActions Internal Architecture

```mermaid
flowchart LR
    subgraph Input2["Input"]
        NW2["nowing backend"]
        CLI2["CLI / scripts"]
    end

    subgraph MCP3["src/mcp/"]
        Server["server.js<br/>MCP :3001<br/>stdio + http"]
        Envelope["envelope.js<br/>3-layer response"]
        Ctx["consumer-context.js<br/>multi-tenant"]
        PLUGINS["plugins/<br/>extensible tools"]
    end

    subgraph Core3["src/core/"]
        BaseCrawl["base-crawler.js"]
        Dispatch["action-registry.js<br/>scrape() dispatcher"]
        Session["session-manager.js"]
        Governor["adaptive-governor.js<br/>rate limit"]
        TLS["tls-profile-provider.js"]
        Challenge["challenge-signature-detector.js"]
        SchemaGuard["schema-drift-guard.js"]
        HealthOrch["session-health-orchestrator.js"]
    end

    subgraph Scrapers3["src/scrapers/"]
        Social3["social/<br/>11 platforms"]
        RE3["realestate/<br/>batdongsan, chotot"]
        Ecom3["ecom/<br/>shopee, tiktok-shop"]
        Recruit3["recruitment/"]
        Procure3["procurement/"]
        Legal3["legal/"]
        Health3["healthcare/"]
        Vehicle3["vehicles/"]
        Fnb3["fnb/"]
        Identity3["identity/"]
    end

    subgraph Store3["src/store/"]
        Checkpoint["checkpoint-manager.js"]
    end

    subgraph Stream3["src/streaming/"]
        RedisOut["Redis Stream<br/>stream:social:raw_posts"]
    end

    subgraph Agents3["src/agents/"]
        LLMBrain["llmBrain.js"]
        Persona["persona.js"]
        AntiDetect["antiDetection.js"]
        Engagement["engagementNetwork.js"]
    end

    subgraph Proxy3["src/proxy/"]
        Pool["proxy-pool.js<br/>SOCKS5"]
    end

    NW2 -->|"x_scrape(...)"| Server
    Server --> Dispatch
    Dispatch --> BaseCrawl
    BaseCrawl --> Scrapers3
    BaseCrawl --> Checkpoint
    BaseCrawl --> RedisOut
    RedisOut -->|"XREADGROUP"| NW2
    Dispatch --> Governor
    Dispatch --> Proxy
    Proxy --> Pool
    Dispatch --> TLS
    Dispatch --> Challenge
    Dispatch --> Session
    CLI2 --> Server
    PLUGINS --> Server
```

## 5. Nowing ↔ ChainLens Data Flow

```mermaid
sequenceDiagram
    participant U as User
    participant NA as Nowing Agent
    participant DS as DecisionService
    participant JEV as Jev API
    participant CL as ChainLens API
    participant XA as XActions MCP
    participant DB as PostgreSQL

    U->>NA: "Nghiên cứu thị trường BĐS Q7"
    NA->>DS: decide(subagent_routing)
    DS->>JEV: POST /v1/systemone {state, questions}
    JEV-->>DS: {subagent: "chainlens", confidence: 0.95}
    DS-->>NA: DecisionResult (300ms)
    NA->>CL: task("chainlens", query)
    CL->>CL: search → crawl → extract → synthesize
    CL-->>NA: SSE stream (sources + answer)
    NA->>DB: Store chunks + citations
    NA-->>U: Research answer with citations

    Note over NA,XA: For scraper tasks
    NA->>XA: x_scrape("realestate", "search_listings", {province: "Q7"})
    XA->>XA: dispatcher → crawler → store
    XA-->>NA: envelope {preview, stream_ref}
    XA->>DB: via Redis Stream → nowing consumer
```

## 6. Nowing ↔ XActions Contract (target state)

```mermaid
sequenceDiagram
    participant NW as Nowing
    participant XA as XActions MCP :3001
    participant CR as BaseCrawler
    participant RS as Redis Stream
    participant CONS as social_stream_worker
    participant DB as PostgreSQL

    NW->>XA: x_scrape(platform, action, args, context)
    XA->>CR: dispatch → scrape()
    CR-->>XA: envelope {success, data:preview[], meta}
    XA-->>NW: preview (≤30 records)
    CR->>RS: XADD thin event per record
    Note over RS: stream:social:raw_posts<br/>{platform, external_post_id,<br/>content_snippet, target_id, ...}
    RS->>CONS: XREADGROUP consumer
    CONS->>DB: UPSERT social_posts + leads
    CONS->>RS: XACK
```

## 7. Decision Points Map

```mermaid
flowchart LR
    subgraph Existing["Current Decision Points (rule-based)"]
        direction LR
        D1["Subagent routing<br/>jev_router.py ✅"]
        D2["PII redaction<br/>pii/redact.py"]
        D3["Intent classify<br/>auto_reply_agent.py"]
        D4["Entity dedup<br/>dedup/"]
        D5["BĐS merge<br/>bds_aggregator/"]
        D6["Corp verify<br/>corporate_verification"]
        D7["Lead scoring<br/>lead_intelligence/"]
        D8["Confidence gate<br/>confidence/gate.py"]
        D9["LLM tier select<br/>hybrid_llm_router.py"]
        D10["Signal detect<br/>signals/service.py"]
        D11["Sequence conditions<br/>sequencer/"]
        D12["Voice post-STT<br/>voice/agent_worker.py"]
    end

    subgraph JevP["Jev primitives"]
        direction LR
        P1["Choice<br/>pick 1 of N"]
        P2["Score<br/>0-N ordinal"]
        P3["Noul<br/>yes/no prob"]
    end

    D1 -->|100% eval| P1
    D2 -->|"Noul: has_pii?"| P3
    D3 -->|95% eval| P1
    D4 -->|90% eval| P2
    D5 -->|"Score: merge?"| P2
    D6 -->|"Score: same?"| P2
    D7 -->|"Score: quality"| P2
    D8 -->|"Noul: real lead?"| P3
    D9 -->|"Choice: tier"| P1
    D10 -->|"Noul: signal?"| P3
    D11 -->|"Noul: met?"| P3
    D12 -->|"Noul+Score"| P3
```

## 8. Voice Pipeline

```mermaid
sequenceDiagram
    participant Callee
    participant SIP as SIP/Telco
    participant LK as LiveKit Room
    participant VW as Voice Worker
    participant VAD as Silero VAD
    participant STT as Deepgram STT
    participant JEV as Jev (future)
    participant LLM2 as Claude/GPT
    participant TTS as OpenAI TTS

    SIP->>LK: SIP 180 Ringing
    VW->>LK: Join + prewarm STT/TTS
    Callee->>LK: Picks up (audio)
    LK->>VAD: Audio frames 30ms
    VAD->>VW: End-of-utterance 180-220ms
    LK->>STT: Audio buffer
    STT->>VW: Transcript (Vietnamese)
    Note over JEV: Future: transfer_to_human?<br/>frustration_score?
    VW->>LLM2: Transcript + context
    LLM2->>VW: Streaming tokens
    VW->>TTS: Micro-clause chunks
    TTS->>LK: Audio frames
    LK->>Callee: Voice response
```

## 9. Data Flow — Scraper → Lead Pipeline

```mermaid
flowchart LR
    subgraph Sources["Scraper Sources"]
        BDS2["batdongsan"]
        CT2["chotot"]
        MB2["muaban"]
        TC2["topcv"]
        VW3["vietnamworks"]
        ITV2["itviec"]
        XA2["XActions<br/>11 social platforms"]
    end

    subgraph Pipe["Ingestion Pipeline"]
        Scrape["Proprietary Scrapers<br/>app/proprietary/platforms/"]
        Norm["Normalize<br/>canonical schema"]
        Dedup2["Dedup<br/>Jaccard + spatial"]
        Conf2["ConfidenceGate<br/>schema completeness"]
        PII2["PII Redact<br/>regex → Jev Noul"]
        Store2["Store<br/>Lead + VerifiedContact"]
    end

    subgraph Enrich["Enrichment"]
        Score2["LeadScoring<br/>fit + intent"]
        Signal2["SignalDetect<br/>funding/hiring"]
        Phone["PhoneWaterfall<br/>3-tier"]
        Corp["CorpVerify<br/>MST"]
    end

    Sources --> Scrape --> Norm --> Dedup2 --> Conf2 --> PII2 --> Store2
    Store2 --> Score2
    Store2 --> Signal2
    Store2 --> Phone
    Store2 --> Corp
```

## Files Verified

| Repo | Path | What |
|------|------|------|
| nowing | `app/agents/.../middleware/stack.py` | 26-middleware stack, jev_router at position 10 |
| nowing | `app/agents/.../middleware/jev_router.py` | JevRouterMiddleware — calls typesafe_sdk directly |
| nowing | `app/agents/.../shared/feature_flags.py` | `enable_jev_router` flag, default OFF |
| nowing | `app/agents/.../subagents/builtins/` | 21 subagent directories |
| nowing | `app/services/` | 120+ service files |
| nowing | `app/proprietary/platforms/` | 22 platform scraper adapters |
| chainlens | `apps/api/src/` | 40+ NestJS modules |
| chainlens | `apps/mcp/src/tools/` | 7+ MCP tools |
| chainlens | `apps/worker/src/` | Async job worker |
| XActions | `src/mcp/server.js` | MCP server :3001 |
| XActions | `src/scrapers/` | 10 categories |
| XActions | `src/core/` | base-crawler, dispatcher, governor |
| XActions | `src/streaming/` | Redis Stream output |
