# Innovation Strategy: Nowing

**Date:** 2026-08-04
**Strategist:** Luisphan
**Strategic Focus:** Business model, pricing, and GTM execution for open-source research memory

---

## 🎯 Strategic Context

### Current Situation

Nowing is an open-source **research memory** platform for AI agents and research teams. Its positioning is anchored in a single sentence: *“Nowing is open-source research memory for AI agents — it remembers what it went and found, not just what you told it.”* (brief §1, lines 43-55). The product differentiates from existing memory layers (Mem0, Zep, Cognee, Supermemory) and research workspaces (Onyx, OpenWebUI, LibreChat, Perplexity) by combining four rarely co-existing capabilities:

1. **Live web / UGC ingestion into long-term memory** — Reddit, YouTube, TikTok, Instagram, Google Search/Maps, Amazon, and generic web crawl.
2. **Provenance-aware memory** — facts carry citations and source links.
3. **Self-hostability** — Apache-2.0 core with an optional BSL 1.1 crawler engine, keeping research data inside the user’s infrastructure.
4. **Integration depth** — connectors → citations → memory → chat → deliverables → multi-client surfaces (web, desktop, extension, Obsidian, MCP) in one closed loop.

The architecture is a deliberate **three-tier license model**: the `nowing_backend` core is Apache-2.0, the crawler engine in `app/proprietary/**` is Business Source License 1.1 (not OSS but free for self-host production use), and the deep-research engine is closed-source, hosted cloud-only in Phase 1, with a metered Phase 2 endpoint (brief §5.1, lines 180-215; PRD §1.1, lines 39-65).

The beachhead is the **AI agent builder + research team** segment. Distribution is intentionally OSS + MCP registry + self-host, with no push-GTM or sales team. The team is dev-strong and GTM-thin, so the strategy must leverage product-led growth rather than outbound muscle (baseline §5, lines 85-93; PRD §1.1, lines 37-38).

### Strategic Challenge

The challenge is to convert this open-source, engineering-first foundation into a **sustainable cloud revenue model** while:

- Avoiding the red-ocean consumer search trap that Perplexity, OpenWebUI, and others dominate.
- Not building a costly owned web index or selling raw research data — both are explicit non-goals.
- Maintaining the authenticity and trust of the open-source community, especially around the Apache-2.0 / BSL 1.1 boundary.
- Pricing the deep-research capability using real cost data and a defensible margin model.
- Passing hard quality gates (recall evaluation, research degradation, cost metering, spend caps) before public launch.

In short, Nowing must prove that **open-source research memory can become a paid cloud workspace** without becoming either a free memory utility or a thin wrapper around an LLM.

> **Tóm tắt tiếng Việt:** Nowing là bộ nhớ nghiên cứu mã nguồn mở, khác biệt ở việc đưa dữ liệu web sống (Reddit, YouTube, Maps, Amazon…) vào bộ nhớ có nguồn (citations), hỗ trợ self-host, và tích hợp sâu qua nhiều client. Thách thức là chuyển đổi từ mô hình OSS sang doanh thu cloud mà không rơi vào cạnh tranh với Perplexity, không bán dữ liệu, không xây owned index, và giữ niềm tin cộng đồng.

---

## 📊 Market Analysis

### Frameworks Applied

- **TAM / SAM / SOM Analysis** (`innovation-frameworks.csv` line 12) — for sizing the opportunity in AI agent memory and research workspaces.
- **Five Forces Analysis** (`innovation-frameworks.csv` line 13) — for understanding competitive pressure, supplier power, and substitution threats.
- **Market Timing Assessment** (`innovation-frameworks.csv` line 15) — for evaluating whether the market is ready for an open-source research-memory workspace.
- **Competitive Positioning Map** (`innovation-frameworks.csv` line 16) — for identifying the whitespace between memory APIs, consumer research, and self-host enterprise search.

### Market Landscape

The category is fragmenting into two layers that do not fully overlap:

| Layer | What it does | Revenue evidence | Incumbents / threats |
|---|---|---|---|
| **Memory layer** | Stores conversation / document / business-data context for agents; often bundled free. | Weak as a standalone business. No public ARR from Mem0, Zep, Cognee, or Supermemory. Memory is being bundled free by OpenAI, Anthropic, Google, AWS, Oracle, Databricks. | Mem0, Zep, Cognee, Supermemory, and every major AI platform. |
| **Research workspace** | Connectors, search, citations, deliverables, team collaboration. | Strong. Glean ~$300M ARR, Exa ~$10M ARR, Onyx 1,000+ enterprise. | Onyx, OpenWebUI, LibreChat, Perplexity, Gemini Notebook. |

Nowing sits at the **intersection** of these layers: a research workspace with long-term, provenance-aware memory and live-web data. This is the whitespace (brief §11, lines 354-358; baseline §9, lines 139-144).

Using a TAM/SAM/SOM lens:

- **TAM — AI agent infrastructure and enterprise knowledge/research automation.** Broad, growing rapidly as agent builders and research teams adopt agentic tooling.
- **SAM — Agent builders and SMB/mid-market research teams who prefer or require open/self-hostable tools, and who need live web evidence in their workflows.** Excludes pure consumer search users and enterprise buyers requiring deep SLA/compliance.
- **SOM — The initial beachhead of AI agent builders and privacy-sensitive research teams reached via OSS, MCP, and GitHub/HN communities.** This is the segment most likely to install, self-host, and convert to cloud for deep-research usage.

> *Note: quantitative sizing is intentionally left to the `bmad-market-research` skill; the baseline explicitly asks for TAM/SAM/SOM of AI agent memory / research workspace (baseline §11, lines 152-164).*

### Competitive Dynamics

A Five Forces view:

1. **Rivalry — High.** Many well-funded memory-layer startups and VC-backed research tools exist. Large platforms are bundling memory for free, and consumer search is a red ocean.
2. **Buyer Power — Moderate-to-High.** OSS users can switch to another self-hostable tool or build a thin wrapper. Cloud buyers are sensitive to price, latency, and output quality.
3. **Supplier Power — Moderate.** LLM/embedding providers, web-search aggregators (Brave, Jina, Exa, Tavily, SearXNG), and proxies are critical. Nowing’s deep-research engine (ChainLens) is internal but represents a strategic dependency.
4. **Threat of Substitutes — High.** ChatGPT/Claude memory, Claude Code `CLAUDE.md` files, Perplexity, NotebookLM, and internal wikis all compete for the same research-and-context job.
5. **Threat of New Entrants — High.** Open-source + LLM APIs lower barriers. However, the full loop (live-web ingest, anti-bot, memory, provenance, multi-client, deliverables) takes time to replicate and operate.

The key insight is that **citation and basic memory are now table stakes**. In ~90 days before 2026-07-25, OpenAI, Zep, Oracle, AgentPrizm, and an OSS library (`memcite`) all shipped provenance/citation features. The remaining differentiator is **live source data with re-validation**, not just “memory with citations” (brief §4, lines 93-113).

### Market Opportunities

1. **Privacy-sensitive and regulated teams** that cannot push research data into closed AI vendor clouds.
2. **Agent builders** using Claude Code, Cursor, OpenCode who need persistent memory across sessions via MCP.
3. **Research teams** that need shared project memory of live UGC and web evidence.
4. **Conversion to cloud** via deep open-web research — the only cloud-only capability in Phase 1.
5. **MCP-native distribution** as the protocol for agent-tool discovery.
6. **Research deliverables** (reports, podcasts, video, automations) as premium, shareable outputs built on top of memory.

### Critical Insights

- Revenue in this category is at the **workspace layer**, not the memory-API layer (brief §11, lines 354-358).
- “Memory with citations” has become table stakes; the fight is now about **memory with live, re-validatable sources** (brief §4, lines 93-113).
- The provenance chain from `Memory` back to a `Run` is currently **blocked by schema mismatches** (`Run.id` is UUID, `Memory.source_id` is Integer; no writer for `SCRAPER_RUN`; `Run` retention is 30 days). This is not a missing feature, it is a schema defect that must be fixed before the live-source story can be marketed (brief §4, lines 115-127; PRD §4.9, lines 670-702).
- Do not call the whole product “open source.” The crawler engine is BSL 1.1 and is *not* OSS. Honest messaging is a trust asset, not a liability (brief §5.1, lines 181-205).
- Deep research must be **cloud-only in Phase 1 and metered for self-host in Phase 2**. Degradation is a business-model requirement, not only a reliability feature (PRD §4.9, lines 632-669; baseline §3, lines 67-72).

---

## 💼 Business Model Analysis

### Frameworks Applied

- **Business Model Canvas** (`innovation-frameworks.csv` line 7) — for mapping the full create/deliver/capture value chain.
- **Value Proposition Canvas** (`innovation-frameworks.csv` line 8) — for matching customer jobs, pains, and gains.
- **Revenue Model Innovation** (`innovation-frameworks.csv` line 10) — for designing pay-as-you-go and optional tiered pricing.
- **Cost Structure Innovation** (`innovation-frameworks.csv` line 11) — for improving margin around LLM/embedding/deep-research costs.

### Current Business Model

Nowing operates an **open-core, product-led-growth (PLG)** business model with a clear three-tier license boundary:

| Tier | Scope | License | Self-host |
|---|---|---|---|
| **Core** | Everything outside `app/proprietary/` | Apache-2.0 (OSS) | Free, full production use |
| **Crawler engine** | `nowing_backend/app/proprietary/**` fetchers, YouTube InnerTube, CAPTCHA, stealth testbench, proxy registry | BSL 1.1 (not OSS) | Free for self-host production; cannot resell as hosted service |
| **Deep-research engine** | Not in repo | Closed-source, hosted | Phase 1: unavailable; Phase 2: metered via Nowing Cloud API |

*(baseline §3, lines 57-71; PRD §1.1, lines 43-49; brief §5.1, lines 180-189).*

**Customer segments:**
- AI agent builders (primary beachhead).
- Research/analyst teams.
- Self-hosters / data-sensitive teams.

**Channels:** GitHub, Hacker News, MCP registry, community OSS, word-of-mouth among agent builders.

**Revenue model (cloud):** Pay-as-you-go credit wallet (`credit_micros_balance`) for:
- LLM token usage.
- Embedding token usage.
- Storage.
- Deep-research calls.

Top-ups are purchased via Stripe; auto-reload is supported (PRD §4.8, lines 515-535; baseline §3, lines 57-60).

### Value Proposition Assessment

The three reasons to pay are well validated:

1. **Memory with provenance** — long-term memory that includes citations and live web data.
2. **Self-host / privacy** — data-sensitive teams keep research data on their own infrastructure.
3. **Integration depth** — connectors → citations → memory → deliverables → multi-client in one loop.

These are *not* “cheaper than Perplexity” or “selling research data” — both are explicit non-goals (baseline §1, lines 31-36; brief §2, lines 63-69).

The customer jobs are also clear:

| Customer | Job to be done |
|---|---|
| AI agent builder | Persistent memory across sessions so agents don’t lose context; reduce context-window stuffing. |
| Researcher / analyst | Gather real-world opinions from Reddit/YouTube/Amazon/Maps without writing one-off scrapers; continue research across sessions. |
| Team | Share a workspace, see what teammates found, avoid duplicate research, correct facts once. |
| Self-hoster | Run an open platform on own infra with own LLM/embedding model, data never leaves. |

*(baseline §2, lines 43-48; brief §3, lines 75-84; PRD §2.1, lines 68-75).*

### Revenue and Cost Structure

**Revenue streams:**
1. Cloud credit purchases (Stripe).
2. Auto-reload of credit wallets.
3. Future: metered deep-research calls for self-host (Phase 2).
4. Future: optional team/enterprise subscription tiers (post-MVP).

**Cost basis (deep-research engine, 2026-08-02):**

| Mode | Avg cost per call (tier=research) | Notes |
|---|---|---|
| speed | $0.0353 | Lowest quality, fastest |
| balanced | $0.0482 | Default mode (D3, 2026-07-25) |
| quality | $0.0671 | Higher quality, more expensive |

*Fallback flat-rate:* `CHAINLENS_QUERY_MICROS_PER_CALL` updated to 60,000 micros ≈ **$0.06** when `costDollars` is not emitted (PRD §4.9, lines 602-618; baseline §4, lines 77-83).

**Cost structure (full pipeline):**
- LLM / embedding provider costs (pass-through or margin-touched).
- Deep-research engine costs (pass-through, marked up).
- Storage (Postgres, object storage, vector index).
- Compute (FastAPI backend, Next.js, Celery workers, Zero sync).
- Payment processing, fraud, support.

**Target margin:** 1.5–2.5× full-pipeline cost aggregation (baseline §4, line 82). This means the *effective cloud price* must be a multiplier over the fully-loaded cost of a request, not a flat fee unrelated to reality.

### Business Model Weaknesses

1. **Conversion risk.** Self-host is free and rich; the only cloud-only feature is deep research. If self-hosters can live without it, cloud revenue stalls.
2. **Usage-based revenue only.** No recurring subscription cushion; revenue is volatile and tied to active usage.
3. **Cost and margin volatility.** Deep-research cost varies by mode and by provider reliability (SearXNG CAPTCHA, rate limits, proxy costs). Pricing must be tolerant of spikes.
4. **Trust / license messaging risk.** If public messaging overstates “open source,” the HN/Reddit community will react negatively.
5. **Legal exposure for long-term scrape data.** Reddit/YouTube/Amazon/Maps data retained as memory raises ToS, copyright, and PII questions; retention and right-to-delete are not fully defined (PRD OQ-3, lines 963-966).
6. **Recall quality is existential.** If `nowing_recall` returns noise, the entire positioning collapses. This is a ship gate, not a nice-to-have (PRD NFR-8, lines 787-795; brief §11, lines 348-352).
7. **GTM-thin.** No sales team, no marketing budget. Growth depends on OSS virality, MCP adoption, and product quality.

---

## ⚡ Disruption Opportunities

### Frameworks Applied

- **Disruptive Innovation Theory** (`innovation-frameworks.csv` line 2) — for serving overlooked segments with a simpler, self-hostable alternative.
- **Jobs to be Done** (`innovation-frameworks.csv` line 3) — for unmet research-and-memory jobs.
- **Blue Ocean Strategy** (`innovation-frameworks.csv` line 4) — for creating uncontested space between consumer search and enterprise knowledge platforms.
- **Platform Revolution** (`innovation-frameworks.csv` line 6) — for evaluating MCP and connector ecosystem network effects.

### Disruption Vectors

1. **Open-source + self-host as a wedge into privacy-sensitive and regulated teams** that closed SaaS (Perplexity, OpenAI, Google) cannot serve.
2. **MCP as a new distribution channel.** Coding agents (Claude Code, Cursor, OpenCode) need persistent memory; Nowing can become the default memory layer via `nowing_mcp`.
3. **Live web data into memory at low cost** by orchestrating search providers instead of building an owned index. This is hard to copy because the cost is operational, not architectural.
4. **Async deep research as a deliverable**, not a chat turn. This lowers latency expectations and opens new use cases: scheduled reports, competitor monitoring, research podcasts, automations.
5. **“Good enough” for agent builders and small research teams** before they need enterprise Glean/Onyx.

### Unmet Customer Jobs

| Job | Current pain | Nowing’s answer |
|---|---|---|
| Agent builder: keep context across sessions | Stuffing files into context, losing decisions | `nowing_remember` / `nowing_recall` via MCP |
| Research team: avoid duplicate research | Each person in their own chat, no shared memory | Workspace with `ResearchThread` and shared memory |
| Analyst: capture real user opinions | Write one-off scrapers, results in a JSON file | Built-in scrapers + automatic memory extraction |
| Data-sensitive user: keep data in-house | Cloud AI vendors cannot be used | Self-host Apache-2.0 core + BSL crawler |
| Researcher: continue a line of inquiry | Search history lost in chat logs | `nowing_continue_research` and research threads |

*(brief §3, lines 75-84; baseline §2, lines 43-48; PRD §2.1, lines 68-75).*

### Technology Enablers

- **MCP ecosystem** — coding agents are the beachhead and Nowing has four memory tools exposed via MCP.
- **Postgres + pgvector** — hybrid search, HNSW, and full-text are sufficient; no graph DB required.
- **ChainLens deep-research engine** — multi-step open-web research without an owned index.
- **Open-source distribution** — Docker Compose self-host, GitHub, and community reduce CAC.
- **Async run infrastructure** — `?mode=async` + SSE run events + ring buffer replay already exists (PRD NFR-9, lines 797-867).

### Strategic White Space

The intersection of **open-source core + self-host + BSL crawler + live-web ingestion + provenance + persistent memory + multi-client workspace** is not currently occupied by any single competitor. The closest shapes:

- **Onyx** — MIT, 40+ connectors, citations, 29K★, 1,000+ enterprise — but **no memory** (brief §4, lines 130-144).
- **Zep / Mem0** — memory, but **no live web/UGC connectors** (brief §4, lines 93-97).
- **Perplexity** — live web + citations, but **no self-host or OSS**, and consumer-focused.
- **Supermemory** — generic web crawler, but not the specific UGC connectors or self-host breadth.

This whitespace is defensible by **integration depth and operational data-acquisition capability**, not by a single proprietary algorithm (brief §4, lines 145-160).

---

## 🚀 Innovation Opportunities

### Frameworks Applied

- **Three Horizons Framework** (`innovation-frameworks.csv` line 17) — for balancing core, adjacent, and transformational initiatives.
- **Value Chain Analysis** (`innovation-frameworks.csv` line 22) — for deciding what to own (ingest, index, memory, deliverables) vs. what to partner (search providers, LLMs).
- **Partnership Strategy** (`innovation-frameworks.csv` line 26) — for MCP registry, connector ecosystem, and model-provider relationships.
- **Innovation Ambition Matrix** (`innovation-frameworks.csv` line 19) — for portfolio balance across core improvements, adjacent expansions, and transformational plays.

### Innovation Initiatives

| # | Initiative | Horizon | Type | Rationale |
|---|---|---|---|---|
| 1 | **Usage-based cloud pricing with real-cost markup** | H1 — Core | Business model | Convert cloud usage into revenue at 1.5–2.5× fully-loaded cost. |
| 2 | **Metered deep-research endpoint for self-host (Phase 2)** | H1 — Core | Business model | Capture revenue from self-hosters without exposing the engine directly. |
| 3 | **Optional team workspace subscription tier** | H1–H2 — Adjacent | Business model | Add recurring revenue and unlock collaboration/admin features. |
| 4 | **MCP registry + template marketplace** | H1 — Adjacent | Ecosystem / Partnership | Drive OSS distribution and make Nowing the default agent memory. |
| 5 | **Provenance and source re-validation (FR-39)** | H1 — Core | Technology | Make “live source memory” real and defensible. |
| 6 | **Auto-extract + spend-cap guardrails** | H1 — Core | Technology | Ship first-run value safely; prevent cost bleed. |
| 7 | **Usage & credit dashboard (NFR-7 / FR-31)** | H1 — Core | Technology | Build trust and transparency for pay-as-you-go users. |
| 8 | **Research deliverables as premium outputs** | H2 — Adjacent | Value chain | Monetize reports, podcasts, video, and scheduled automations. |
| 9 | **Enterprise managed self-host / support tier** | H2 — Adjacent | Business model | Sell deployment support and BSL compliance to regulated teams. |
| 10 | **Cost-routing and provider diversity for deep research** | H1 — Core | Value chain | Improve reliability, reduce cost, and avoid single-provider lock-in. |

### Business Model Innovation

The core innovation is a **two-sided metered model**:

- **Self-host side:** free, Apache-2.0 core + BSL crawler. User brings their own LLM/embedding keys and infrastructure. Deep research is **unavailable in Phase 1** and **metered via Nowing Cloud API in Phase 2**.
- **Cloud side:** pay-as-you-go credits for the full pipeline. Deep research is the **primary conversion lever** because it is the most expensive capability and the only one cloud-only in Phase 1.
- **Future subscription anchor:** optional team/enterprise tier adds a per-seat recurring fee plus a usage credit allowance, reducing revenue volatility.

This model treats OSS not as a cost center but as a **lead-generation and trust-building layer**, while the cloud captures the high-cost, high-value deep-research workload.

### Value Chain Opportunities

Nowing should **own** the layers that create differentiation and **partner/orchestrate** the layers that are commoditized:

- **Own:** workspace, memory, provenance, citation UI, research threads, deliverables, multi-client surfaces, MCP server, billing/metering.
- **Partner/orchestrate:** LLM/embedding providers, web search aggregators (Brave, Jina, Exa, Tavily, SearXNG, Perplexity Sonar), proxies/CAPTCHA services.
- **Not build:** owned web index (NG-1), separate ChainLens product (NG-3), consumer Perplexity clone (NG-2).

Cost-routing across search providers (ChainLens `29-5`) is a key value-chain optimization that can improve margin without building a commodity index (PRD §4.9, lines 803-805).

### Partnership and Ecosystem Plays

1. **MCP registry listing** — be the memory category in the official MCP registry and aggregators.
2. **Claude Code / Cursor / OpenCode compatibility** — templates, tutorials, and example agent prompts.
3. **Connector ecosystem** — OAuth connectors for Notion, Slack, Linear, Jira, Google Drive, Confluence, etc.; encourage community PRs.
4. **Search provider relationships** — negotiated rates or preferential routing with Brave, Jina, Exa, Tavily; keep multiple providers for resilience.
5. **OSS community** — transparent roadmap, clear license boundaries, contributor credits, and honest README.
6. **Obsidian / Zotero / academic workflows** — plugins that make research memory a first-class citizen in existing researcher toolchains.

---

## 🎲 Strategic Options

### Option A: Open-Core PLG with Usage-Based Cloud

**Description:** Continue the current direction. Self-host is free and fully functional except deep research (cloud-only in Phase 1; metered Phase 2 via Nowing Cloud API). Cloud users pay for LLM, embedding, storage, and deep-research usage through a credit wallet. Distribution is OSS + MCP + community. Add a lightweight team subscription tier once cost data and baseline usage are stable.

**Pros:**
- Matches the team’s dev-strong / GTM-thin reality.
- Low customer acquisition cost via PLG and OSS virality.
- Authentic open-source positioning builds trust.
- BSL 1.1 protects against SaaS resellers while allowing self-host production use.
- Deep research is a clean, honest cloud-only conversion lever.
- Scalable without a sales team.

**Cons:**
- Conversion from self-host to cloud may be slow; deep research must be genuinely compelling.
- Revenue is usage-dependent and lumpy.
- Requires strong engineering execution on recall quality, degradation, and cost metering before public launch.
- Self-hosters could remain on free tier indefinitely.
- Legal/retention questions for long-term scrape data must be resolved before GA cloud.

### Option B: Cloud-First Team Workspace with Freemium Trial

**Description:** Launch cloud-first with a free tier limited by credits. Self-host open-source release happens later or is de-prioritized. Pricing is subscription-based per seat plus overage for deep research. Marketing targets research teams directly with a Perplexity-like workspace narrative, but avoids consumer parity.

**Pros:**
- Faster path to recurring revenue.
- Easier to set prices because all users run on Nowing’s infrastructure.
- Full control over the engine and latency.
- Can sell team collaboration, RBAC, and deliverables as value-adds.

**Cons:**
- Contradicts the existing three-tier license architecture and OSS-first positioning.
- Requires GTM muscle (marketing, sales, onboarding) the team does not have.
- Higher CAC and competitive pressure from Onyx, Glean, and OpenWebUI.
- Alienates the developer/agent-builder community that is the intended beachhead.
- Loses the privacy/self-host differentiator.

### Option C: MCP-First Ecosystem + Premium Research Marketplace

**Description:** Position Nowing as the default memory layer for MCP agents. Monetize through premium MCP connectors, managed research packs, and licensed research *deliverables* for verticals (e.g., competitive intelligence, market research, due diligence). Avoid selling raw data (NG-1). Heavy investment in ecosystem, partner marketplace, and template library.

**Pros:**
- Potential network effects as more agents and connectors join.
- Diversified revenue beyond usage.
- Aligns with the MCP distribution channel and developer beachhead.

**Cons:**
- Requires ecosystem scale before revenue materializes.
- Governance and quality control of third-party connectors add complexity.
- Non-goals limit one major revenue stream (raw data-as-a-product).
- Could distract from the core research-memory value proposition.
- Marketplace and vertical deliverables are post-MVP, not a near-term primary model.

---

## 🏆 Recommended Strategy

### Strategic Direction

**Adopt Option A — Open-Core PLG with Usage-Based Cloud — with three refinements:**

1. **Add a small team/enterprise subscription anchor** once the cost basis is ratified. The subscription includes a per-seat fee plus a usage credit allowance, with overage charged at usage rates. This stabilizes revenue without abandoning the OSS/PLG motion.
2. **Make provenance and source re-validation a P0 narrative project** (FR-39). This is the only durable differentiator after “citations” became table stakes.
3. **Execute a strict gate-based launch sequence**: recall eval → degradation → cost metering → spend cap → public repo → cloud soft launch → Phase 2 metered self-host.

This direction is recommended because it is the only one that simultaneously:

- Leverages the team’s actual capabilities (engineering, OSS, MCP).
- Preserves the self-host/privacy differentiator.
- Avoids the red-ocean consumer search market.
- Uses deep research as a clean, honest conversion lever.
- Can scale without a sales team.

### Key Hypotheses to Validate

1. **Agent builders and research teams will install and self-host Nowing if the first-run value is ≤ 15 minutes.** (M1 from brief §9, lines 308-313)
2. **Deep open-web research is compelling enough to convert a meaningful share of self-hosters to cloud usage.** (baseline §3, lines 67-72)
3. **The `balanced` deep-research mode is “good enough” for most queries at a lower cost than `quality`.** (PRD §4.9, lines 585-588)
4. **Recall quality (precision@k and noise rate) is good enough that users trust `nowing_recall` for research continuation.** (PRD NFR-8, lines 787-795)
5. **Legal retention and right-to-delete can be implemented for memory before GA cloud without breaking the product.** (PRD OQ-3, lines 963-966)

### Critical Success Factors

- **Recall quality gate must close before any public launch.**
- **FR-38 degradation must make self-host usable without the engine.**
- **FR-37 cost metering and 8.7 spend cap must give real cost data before pricing is finalized.**
- **License messaging must be honest and consistent everywhere (README, landing, docs, HN).**
- **MCP distribution must land in Claude Code / Cursor / OpenCode example workflows.**
- **A usage/credit dashboard must be live before cloud pricing is public.**
- **Provenance re-validation (FR-39) must ship before the “live source” story is marketed aggressively.**

> **Tóm tắt đề xuất:** Chọn mô hình open-core PLG + cloud trả theo dùng, bổ sung gói subscription cho team khi có số cost ổn định. Cửa hàng conversion chính là deep-research — năng lực duy nhất self-host không có ở Phase 1, và trả tiền theo call ở Phase 2. Mọi quyết định giá phải dựa trên `costDollars` thật và mục tiêu margin 1.5–2.5×. Không launch ồn ào trước khi eval recall, degradation, và cost metering đóng.

---

## 📋 Execution Roadmap

The roadmap is **gate-driven**, not calendar-driven. Each phase advances only when its hard gates close.

### Phase 1: Immediate Impact — OSS Launch & Cloud Soft Open

**Goal:** Public repo with credible first-run value; cloud available for early paying users.

**Key initiatives and deliverables:**
- Close **NFR-8 recall eval gate** and set SM-10 precision/noise targets based on `nowing_evals`.
- Ship **FR-38 degradation** so self-host runs cleanly without the engine; make this a public-repo prerequisite.
- Ship **FR-37 cost metering** parsing `costDollars` from ChainLens SSE and `TokenUsage`.
- Ship **story 8.7 spend cap** (auto-extract item cap + wallet pre-check + rate-limit).
- Implement **FR-40 first-run value**: research/scrape run → `Memory` with `source_type = SCRAPER_RUN`, so `nowing_recall` returns useful content within M1 (≤ 15 minutes).
- Update README/landing/docs with: one-liner, Apache-2.0 + BSL 1.1 messaging, self-host vs cloud feature table, “deep research runs on Nowing’s hosted engine” wording.
- List `nowing_mcp` in MCP registries and publish Claude Code / Cursor / OpenCode example prompts.
- Soft-launch cloud with a pay-as-you-go credit wallet; no public subscription pricing yet.
- Add the **usage & credit dashboard** (NFR-7 / FR-31) so users can see costs.

**Hard gates before public repo:**
1. NFR-8 recall quality gate.
2. FR-38 degradation (self-host independence).
3. FR-37 real cost metering.
4. Story 8.7 spend cap.

*(baseline §7, lines 126-130; brief §1, lines 34-38; PRD §4.9, lines 632-669).*

### Phase 2: Foundation Building — Cloud Conversion & Metered Self-Host

**Goal:** Prove the conversion hypothesis and open a revenue path for self-hosters.

**Key initiatives and deliverables:**
- **Ratify pricing** using real cost data and the 1.5–2.5× margin target.
- **Publish cloud pricing** for:
  - LLM/embedding tokens (pass-through + platform fee).
  - Storage per GB-month.
  - Deep-research calls per mode (speed / balanced / quality), marked up from engine cost.
- Add **team workspace subscription tier** (per-seat fee + usage credit allowance) to reduce revenue volatility and unlock collaboration features.
- **Open Phase 2 metered deep research for self-host** via Nowing Cloud API only — never direct engine access.
- Validate `balanced` mode as default through `nowing_evals` and Nowing-side e2e benchmarks.
- Stay in **NFR-9 State A** (async deliverable) until p50/p95 targets are consistently met.
- Ship **FR-39 provenance re-validation** so memory can recall and re-execute the source query.
- Resolve **OQ-3 legal retention / right-to-delete** for memory and document retention before GA cloud.
- Build **automated cost alerts and budget controls** at workspace and user level.

**Decision gates for Phase 2:**
1. SM-11a real cost per mode stable and ratified.
2. SM-11b latency baseline meets State A thresholds.
3. SM-11c degradation/fallback rate acceptable.
4. Evidence of self-host demand (e.g., GitHub stars, install telemetry, MCP installs).
5. OQ-3 legal framework closed.

### Phase 3: Scale & Optimization

**Goal:** Scale distribution, improve margins, and expand revenue streams.

**Key initiatives and deliverables:**
- Scale OSS distribution: GitHub, HN, MCP registries, community events, contributor program.
- Add **vertical research packs** (competitive intelligence, product research, academic reviews) as premium deliverable templates.
- Launch **automated monitoring / agent loop products** (e.g., “track this competitor and update my workspace memory weekly”).
- Expand **connector ecosystem** through community and partner integrations.
- Offer **enterprise managed self-host** — support, BSL compliance guidance, and optional managed infrastructure for regulated customers.
- Optimize deep-research cost through provider routing, semantic caching (ChainLens `43-5`), and planner parallelization (ChainLens `43-2`).
- Open **State B** (sync chat-mode) only after p95 targets are hit and ratified by Nowing e2e benchmarks.
- Build a **partner/API marketplace** for premium MCP connectors, governed by quality standards.

**Decision gates for Phase 3:**
1. Cloud gross margin ≥ target range on steady-state usage.
2. Conversion rate self-host → cloud (or metered self-host) meets threshold.
3. Net revenue retention positive on team subscription cohorts.
4. State B latency/cost gates closed (optional, not a blocker if async remains dominant).

> **Tóm tắt lộ trình:** Phase 1 đóng các cổng chất lượng và launch OSS/cloud; Phase 2 chốt giá, mở metered cho self-host, và bổ sung subscription team; Phase 3 scale phân phối, pack nghiên cứu theo vertical, và tối ưu chi phí/margin.

---

## 📈 Success Metrics

### Leading Indicators

These signal whether the strategy is working before revenue materializes.

| Metric | What it validates | Source |
|---|---|---|
| SM-1 — Active workspaces (≥1 chat/scraper run in 7 days) | Product engagement | PRD §7, lines 914-918 |
| SM-2 — Successful scraper runs per week | Connector value | PRD §7, lines 914-918 |
| SM-7 — Memory operations (create/recall/update) per week | Memory adoption | PRD §7, lines 930-933 |
| SM-8 — % research threads continued | Research continuity | PRD §7, lines 930-933 |
| SM-9 — MCP memory tool calls per week | Agent-builder adoption | PRD §7, lines 930-933 |
| SM-3 — % chat messages with citation | Citation UX health | PRD §7, lines 914-918 |
| M1 — Time from signup to first useful `nowing_recall` | First-run value | brief §9, lines 308-313 |
| SM-10 — `nowing_recall` precision@k / noise rate | Recall quality (ship gate) | PRD NFR-8, lines 787-795 |
| SM-11a — Cost per deep-research call by mode | Pricing basis | PRD §7, lines 936-940 |
| SM-11b — p50/p95 latency per mode | State A / State B gate | PRD NFR-9, lines 797-867 |
| SM-11c — Degradation / fallback rate | Self-host reliability | PRD §7, lines 936-940 |
| Conversion rate: self-host → cloud usage | Business model health | baseline §9, lines 148-150 |

### Lagging Indicators

These measure business outcomes.

| Metric | Why it matters |
|---|---|
| Cloud gross margin | Is the pricing model sustainable? |
| Net revenue per active workspace | Are cloud users spending? |
| Team subscription MRR | Does subscription anchor reduce volatility? |
| Self-host → cloud / metered conversion rate | Is OSS generating paying users? |
| LTV / CAC | Is PLG efficient? |
| Net revenue retention | Are teams expanding usage? |
| Deep-research call volume | Is the conversion lever being pulled? |

### Decision Gates

| Gate | Go / No-Go | Trigger |
|---|---|---|
| NFR-8 recall eval gate | No public repo or launch if not closed. | `nowing_evals` precision/noise targets met. |
| FR-38 degradation | No public repo if self-host hard-fails without engine. | Degradation path tested for timeout / 5xx / unconfigured. |
| FR-37 cost metering | No pricing finalized. | `costDollars` parsed and reflected in `TokenUsage`; fallback rate known. |
| Story 8.7 spend cap | No auto-extract on production. | Item-cap + wallet pre-check + rate-limit live. |
| OQ-3 legal retention | No GA cloud. | Memory/document retention + right-to-delete policy implemented. |
| SM-11 price ratification | Phase 2 pricing public. | Stable cost per mode and margin model signed off. |
| State B latency gate | No sync chat-mode by default. | p50/p95 meet target in Nowing e2e benchmark. |
| Phase 2 demand gate | No metered self-host endpoint. | Evidence of meaningful self-host install base. |

---

## ⚠️ Risks and Mitigation

### Key Risks

1. **Recall quality fails to meet the ship gate.**
   - *Impact:* Positioning collapses; users will call Nowing “just another research workspace.”
   - *Mitigation:* Do not publicly launch until NFR-8 is closed. Treat `nowing_evals` as the final gate, not a checkbox.

2. **Self-hosters never convert to cloud.**
   - *Impact:* Revenue stalls; cloud becomes a small sidecar.
   - *Mitigation:* Make deep research cloud-only Phase 1 and metered Phase 2; add team collaboration features that require cloud sync; use usage limits on free cloud tier.

3. **Cost bleed / under-metering of deep research.**
   - *Impact:* Margins compress or turn negative.
   - *Mitigation:* FR-37 parses real `costDollars`; set fallback flat rate at ~$0.06; enforce spend caps (story 8.7); use balanced mode by default; route across search providers.

4. **Legal exposure from long-term storage of scraped UGC data.**
   - *Impact:* ToS, copyright, PII complaints; potential takedown or liability.
   - *Mitigation:* Resolve OQ-3 before GA cloud; implement retention and right-to-delete; clearly separate self-host vs. cloud responsibility; obtain legal review of ToS and data policies.

5. **License / open-source backlash.**
   - *Impact:* Community trust erosion; negative HN/Reddit coverage.
   - *Mitigation:* Always say “Apache-2.0 core + BSL 1.1 crawler engine”; never call the whole product “open source”; credit upstream where appropriate; be transparent about the feature table.

6. **Incumbent adds live-web ingestion to memory.**
   - *Impact:* Differentiator narrows.
   - *Mitigation:* Move faster on provenance re-validation (FR-39), deliverables, and automation; build community and integration depth that is hard to copy quickly.

7. **GTM-thin team cannot generate enough top-of-funnel.**
   - *Impact:* OSS adoption is slow; cloud revenue never reaches escape velocity.
   - *Mitigation:* Double down on MCP, GitHub, HN, and example-driven content; encourage user-generated tutorials; avoid paid marketing until product-market fit is proven.

8. **Deep-research engine latency or cost volatility.**
   - *Impact:* User experience is unpredictable; pricing becomes risky.
   - *Mitigation:* Stay in State A (async) until benchmarks prove State B; default to `balanced`; use cost-routing; maintain a fallback flat rate; publish p50/p95 per mode.

9. **Schema/implementation gaps in memory provenance.**
   - *Impact:* Cannot deliver the “live source, re-validate” story.
   - *Mitigation:* Treat FR-39 as P0 for the narrative; add `source_capability`, `source_input`, `source_run_id` to `Memory`; keep run recipe in memory so re-validation survives the 30-day `Run` retention (PRD §4.9, lines 670-702).

10. **Scope creep into consumer search or data-as-a-product.**
    - *Impact:* Resources spread thin; competitive in a red ocean.
    - *Mitigation:* Enforce non-goals NG-1, NG-2, NG-3; require any deviation to go through a formal SCP.

### Mitigation Strategies Summary

| Risk | Owner / function | Mitigation |
|---|---|---|
| Recall quality | Engineering / Evals | NFR-8 gate, `nowing_evals` harness, no public launch before close. |
| Conversion | Product / Growth | Deep-research cloud-only + metered self-host + team subscription. |
| Cost bleed | Engineering / Finance | FR-37, spend caps, balanced default, provider routing. |
| Legal / retention | Legal / Product | OQ-3 resolution, retention, right-to-delete, self-host/cloud split. |
| License backlash | Marketing / Community | Honest Apache-2.0 + BSL 1.1 messaging; credit upstream. |
| Incumbent replication | Product / Engineering | FR-39 re-validation, deliverables, automations, community. |
| GTM weakness | Growth / Community | MCP registry, GitHub, HN, example-driven content. |
| Engine volatility | Engineering / Ops | State A async, cost-routing, fallback rate, benchmark-driven State B. |
| Provenance gaps | Engineering | FR-39 schema + memory recipe; do not market live-source before ready. |
| Scope creep | Leadership / SCP | Enforce NG-1/2/3; formal SCP for any exception. |

---

## 🧭 Final Strategic Narrative

Nowing’s best path is to become the **default open-source research memory for AI agents**, monetized through a **metered cloud layer** that captures the most expensive and valuable workload: deep multi-step open-web research. The open-source core and self-host option build trust and distribution; the cloud option captures usage and funds further development. Honesty about licenses, strict gate-based quality, and a relentless focus on the live-source / provenance / re-validation differentiator are the only durable moats. Everything else — consumer search, raw data sales, a separate engine product — is a trap that the strategy explicitly avoids.

> **Tóm tắt cuối cùng (tiếng Việt):** Chiến lược đề xuất là đi theo mô hình open-core PLG: core Apache-2.0 self-host miễn phí, cloud trả theo dùng với deep-research là đòn bẩy conversion. Giá căn cứ trên `costDollars` thật và margin 1.5–2.5×. Không bán dữ liệu, không đua Perplexity, không tách ChainLens thành sản phẩm. Cần đóng các cổng chất lượng (recall, degradation, cost metering, spend cap) trước khi public, rồi mở metered cho self-host và subscription team ở Phase 2, scale ở Phase 3.

---

## 📚 Sources

- **Skill / template:**
  - `/.claude/skills/bmad-cis-innovation-strategy/SKILL.md` (workflow steps 1-9, lines 1-347)
  - `/.claude/skills/bmad-cis-innovation-strategy/template.md` (document structure, lines 1-189)
  - `/.claude/skills/bmad-cis-innovation-strategy/innovation-frameworks.csv` (framework catalog, lines 1-31)

- **Baseline / context:**
  - `/_bmad-output/planning-artifacts/business-plan-baseline-nowing-2026-08-04.md` (vision, business model, pricing signals, GTM, metrics, hard gates, competitive context, lines 1-165)

- **PRD:**
  - `/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` (product boundary, license tiers, deep-research engine integration, cost metering, degradation, provenance, NFR-8, NFR-9, success metrics, open questions)

- **Brief:**
  - `/_bmad-output/planning-artifacts/briefs/brief-Nowing-2026-07-25/brief.md` (one-liner, differentiation, license messaging, customer jobs, M1/M2, success criteria, decision trail, lines 1-416)

- **Config:**
  - `/_bmad/cis/config.yaml` (user, output, language settings, lines 1-13)

---

_Generated using BMAD Creative Intelligence Suite - Innovation Strategy Workflow_
