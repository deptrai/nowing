---
stepsCompleted:
  - Read skill instructions and research template
  - Read baseline, PRD, and brief
  - Conducted web research on market size, competition, customers, pricing, and GTM
  - Wrote structured research report
  - Cited all public sources with URLs
inputDocuments:
  - /Users/luisphan/Documents/GitHub/nowing/.claude/skills/bmad-market-research/SKILL.md
  - /Users/luisphan/Documents/GitHub/nowing/.claude/skills/bmad-market-research/research.template.md
  - /Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/business-plan-baseline-nowing-2026-08-04.md
  - /Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md
  - /Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/briefs/brief-Nowing-2026-07-25/brief.md
workflowType: research
lastStep: 6
research_type: market
research_topic: Open-source long-term research memory / AI agent memory / research workspace — with live web data and provenance
research_goals:
  - Size the TAM/SAM/SOM for AI agent memory + research workspace category
  - Update competitive landscape with latest public evidence
  - Find customer evidence for agent builders and research teams
  - Benchmark pricing/monetization for OSS + cloud pay-as-you-go products
  - Gather distribution/GTM insights for MCP registry, GitHub, Hacker News, self-host communities, and PLG
user_name: luisphan
date: 2026-08-04
web_research_enabled: true
source_verification: true
---

# Market Research Report: Nowing — Open-Core Research Memory for AI Agents

**Date:** 2026-08-04  
**Author:** bmad-market-research (autonomous run)  
**Research Topic:** Market for open-core long-term research memory / AI agent memory / research workspace — with live web data and provenance.

---

## Executive Summary

The market for AI agent memory and research workspaces is growing at 28–39% CAGR and is split into two battlegrounds: **memory-layer infrastructure** (persistence, recall, provenance) and **research/enterprise-search workspaces** (chat over documents, connectors, citations). Major platform players (OpenAI, Google, Microsoft, Anthropic, AWS) have made cross-session memory a free or bundled feature in 2025, which commoditizes a thin “memory API” but leaves three durable openings for Nowing:

1. **Live web / UGC ingestion into long-term memory** — competitors like Mem0, Zep, Cognee, and Supermemory are optimized for chat history, documents, and business data; none openly market live Reddit/YouTube/TikTok/Maps/Amazon ingest into a self-hosted memory graph.
2. **Self-host + privacy with an open-core license** — Nowing’s three-tier model (Apache-2.0 core, BSL 1.1 crawler, closed deep-research engine) matches how Open WebUI, Onyx, and LibreChat build community trust while reserving expensive cloud-only capabilities for monetization.
3. **MCP-native distribution** — the MCP ecosystem crossed ~19,000 public servers by mid-2026 and is the fastest distribution channel for agent builders. Being an MCP memory server first is now table stakes.

Customer evidence is strongest around three jobs-to-be-done: (a) agent builders who lose context across sessions and burn tokens re-prompting; (b) research teams that duplicate work because findings live in individual chat threads; and (c) data-sensitive organizations that cannot send research to a SaaS AI vendor. Pricing benchmarks show three viable open-source monetization models: usage-based credits (Zep, Supermemory), per-seat tiers (Onyx, Perplexity), and pay-per-token (Cognee). Open-source-to-paid conversion is typically 0.5–3%, with best-in-class PLG reaching 8–12%.

**Bottom line for Nowing:** the category is large ($12–15B in 2025 TAM across agentic memory + enterprise research search), but the competitive window for the live-web + provenance + self-host wedge is narrow. Success depends on rapid OSS adoption through MCP/GitHub, a transparent license story, and converting self-hosters to cloud for the metered deep-research capability.

> **Tóm tắt tiếng Việt cho đội:** Thị trường memory cho AI agent và workspace nghiên cứu đang tăng trưởng 28–39% CAGR. Các nền tảng lớn đã làm memory miễn phí, nhưng khoảng trống cho Nowing vẫn còn ở ba điểm: (1) live web/UGC chảy trực tiếp vào memory tự host; (2) mô hình open-core với BSL crawler + cloud deep-research; (3) phân phối qua MCP server. Khách hàng chính là agent builder mất context giữa các phiên, team nghiên cứu bị trùng lặp công việc, và tổ chức nhạy cảm với dữ liệu không muốn gửi lên cloud. Mức chuyển đổi từ OSS sang trả phí thường 0.5–3%. Nowing cần chạy nhanh trên MCP/GitHub và chuyển self-host sang cloud qua deep research trả tiền.

---

## Research Overview & Methodology

This report uses **public web data only**, collected via `web_search` and `webfetch` on 2026-08-04. Sources include primary vendor pricing pages, GitHub repositories, press releases, official documentation, analyst reports (Mordor Intelligence, Research and Markets, DataIntelo, S&P/Sacra estimates), and third-party aggregators. All claims that are not internal Nowing artifacts are linked to a URL in the [Sources](#sources) section.

Key caveats:
- Market-size figures from analyst firms are forward-looking estimates, not audited revenue.
- Some competitor data (funding, ARR, GitHub stars) comes from Crunchbase-style aggregators and may lag.
- Customer evidence is mostly vendor-published case studies; independent qualitative research would strengthen confidence.

---

## Market Size (TAM / SAM / SOM)

### TAM — Total Addressable Market

Two overlapping market definitions frame Nowing’s opportunity:

| Category | 2025 Size | 2030/31 Forecast | CAGR | Source |
|---|---|---|---|---|
| Agentic AI orchestration & memory systems | $6.27B | $28.45B (2030) | 35.3% | [Mordor Intelligence](https://www.mordorintelligence.com/industry-reports/agentic-artificial-intelligence-orchestration-and-memory-systems-market) |
| Agentic AI orchestration & memory (alt.) | $6.49B | $33.54B (2030) | 38.9% | [Research and Markets](https://www.researchandmarkets.com/reports/6231856/agentic-ai-orchestration-memory-systems-market) |
| Generative AI in enterprise knowledge management & search | $6.18B | $27.43B (2031) | 28.6% | [Mordor Intelligence](https://www.mordorintelligence.com/industry-reports/generative-ai-in-enterprise-knowledge-management-and-search-market) |
| AI enterprise search | $8.6B | $36.2B (2034) | 17.4% | [DataIntelo](https://dataintelo.com/report/ai-enterprise-search-market) |
| AI search engine (consumer + enterprise) | $12.5B | $202.8B (2034) | 42.0% | [MarketIntelo](https://marketintelo.com/report/ai-search-engine-market) |
| Conversational AI chatbot market | $14.6B | — | 21.3% (cloud) / 14.2% (on-prem) | [DataIntelo](https://dataintelo.com/report/conversational-ai-chatbot-market) |

**TAM framing for Nowing (2025): $12–15B.** We combine the ~$6.3B agentic-orchestration-and-memory market with the ~$6.2B generative-AI enterprise knowledge/search market. These are not additive in a strict accounting sense, but they jointly bound the spend on the two capabilities Nowing ships: long-term memory for agents and a collaborative research workspace with search/chat. The AI search-engine and chatbot numbers show the larger consumer/enterprise search opportunity but are less directly comparable because they include model-layer and advertising revenue.

### SAM — Serviceable Addressable Market

Not every buyer in the TAM is reachable by an open-source, self-host-first, MCP-native product. We narrow to the segment that:
- Values self-hosting / data sovereignty (on-premise and air-gapped buyers).
- Builds or deploys AI agents and values long-term memory / provenance.
- Uses or is willing to adopt MCP-style integrations.

| Filter | Rationale | Estimate |
|---|---|---|
| Share of enterprise search that is self-hosted / on-premise | ~26–33% of deployments by 2025 (DataIntelo; also [Verified Market Reports on-premises conversational AI](https://www.verifiedmarketreports.com/product/on-premises-conversational-ai-platforms-market/)) | ~25% |
| Developer/agent-builder portion of agentic memory market | Software development accounts for 67% of all MCP tools and 90% of MCP server downloads ([AISI, 177k MCP tools](https://www.aisi.gov.uk/blog/how-are-ai-agents-used-evidence-from-177000-ai-agent-tools)) | heavy developer skew |
| Cross-over (self-host + research workspace) | Blend of on-premise knowledge management and developer/agent tooling | ~15–20% of TAM |

**SAM (2025): ~$2.0–$2.8B.** This is the subset of the TAM that is technically and commercially reachable by an open-core, self-hostable research-memory product in the near term.

### SOM — Serviceable Obtainable Market (Nowing-specific)

Nowing’s SOM is not a market-research output; it is a function of execution. For an early-stage OSS/PLG product with a small team, a bottom-up triangulation is more honest than a top-down share:

| Assumption | Value | Source / Rationale |
|---|---|---|
| OSS-to-paid conversion for open-source infrastructure | 0.5–3% typical; 1–3% target for enterprise open-source; 3%+ exceptional | [OpenView / PulseRevOps PLG benchmarks](https://pulserevops.com/knowledge/q12731); [Monetizely OSS conversion analysis](https://www.getmonetizely.com/articles/whats-the-optimal-conversion-rate-from-free-to-paid-in-open-source-saas) |
| Target paying workspaces (Year 2–3) | 1,000–5,000 | derived from comparable OSS projects (Onyx 1,000+ organizations, Open WebUI 146k stars, Mem0 80,000+ cloud signups) |
| Average revenue per paying workspace | $100–$800/mo | blended usage of cloud deep-research + memory + storage; midpoint ~$300/mo |
| Implied ARR (Year 3) | $3.6M–$48M | low end = 1,000 workspaces × $300/mo × 12; high end = 5,000 × $800/mo × 12 |

**Conservative SOM target (Years 2–3): $10–$30M ARR.** This assumes Nowing achieves meaningful GitHub/MCP traction and converts a low-single-digit share of active workspaces to cloud. A more aggressive scenario reaches $50M+ if it captures a 1% share of SAM.

> **Tóm tắt thị trường:** TAM khoảng $12–15B năm 2025, SAM ~$2.0–$2.8B cho self-host/agent-builder, SOM thực tế cho Nowing trong 2–3 năm là $10–30M ARR nếu chuyển đổi OSS → cloud đạt 0.5–3%.

---

## Competitive Landscape

### Summary Table

| Product | Category | Funding / Valuation | GitHub Stars (public repo) | License | Self-host | Pricing model | Live web / UGC into memory? | Persistent memory? | Citations / provenance? | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| **Nowing** | Research memory + workspace | — | pre-public | Apache-2.0 core / BSL 1.1 crawler / closed deep-research | ✅ (full except deep-research) | Cloud pay-as-you-go (target 1.5–2.5× margin) | ✅ Reddit/YouTube/TikTok/Maps/Amazon/web | ✅ (workspace + MCP) | ✅ | Wedge: live web + provenance + self-host |
| **Mem0** | Memory layer API | $24.4M raised ([TechCrunch](https://techcrunch.com/2025/10/28/mem0-raises-24m-from-yc-peak-xv-and-basis-set-to-build-the-memory-layer-for-ai-apps/)) | ~62k ([GitHub](https://github.com/mem0ai/mem0)) | Apache-2.0 | ✅ OSS core | Free / $19 / $249 / Enterprise custom ([Mem0 pricing](https://mem0.ai/pricing)) | ❌ chat, docs, business data | ✅ user/agent memory | partial (graph memory) | AWS Agent SDK exclusive memory provider |
| **Zep** | Temporal context graph | ~$2.3M ([CB Insights](https://www.cbinsights.com/company/zep-2)) | getzep/zep ~5k; getzep/graphiti ~27k ([GitHub](https://github.com/getzep/zep)) | Graphiti Apache-2.0; full platform cloud | Graphiti only | Flex $125/mo, Flex Plus $375/mo, Enterprise custom ([Zep pricing](https://www.getzep.com/pricing)) | ❌ business data, chat | ✅ temporal context graph | ✅ (provenance graph) | Enterprise: Samsung, Zscaler, AGI Inc. |
| **Cognee** | Knowledge-graph memory | $7.5M seed ([Cognee blog](https://www.cognee.ai/blog/cognee-news/cognee-raises-seven-million-five-hundred-thousand-dollars-seed)) | ~29.7k ([GitHub](https://github.com/topoteretes/cognee)) | Apache-2.0 | ✅ full | Free 1M tokens; $2.50/1M tokens + $5/workspace ([Cognee pricing](https://cognee.ai/pricing)) | ❌ docs/Slack/Notion connectors | ✅ graph memory | ✅ (page-level provenance) | Customers: Bayer, University of Wyoming |
| **Supermemory** | Memory + context cloud | $2.6M seed ([Economic Times](https://economictimes.indiatimes.com/ai/ai-insights/the-19-year-old-mumbai-whiz-kid-who-created-supermemory-the-silicon-valley-shaking-next-gen-ai-memory-startup/articleshow/124714507.cms)) | ~28.7k ([GitHub](https://github.com/supermemoryai/supermemory)) | MIT | Scale / Enterprise only | Free / $19 / $100 / $399 / Enterprise; usage: $0.005/1K SM tokens ([Supermemory pricing](https://supermemory.ai/pricing/)) | ~ generic web crawler | ✅ memory graph, user profiles | yes | #1 on LongMemEval/LoCoMo/ConvoMem per self-report |
| **Onyx (ex-Danswer)** | Enterprise AI search / workspace | $10M seed ([Onyx blog](https://onyx.app/blog/seed-round)) | ~30.5k ([GitHub](https://github.com/onyx-dot-app/onyx)) | MIT (CE) / EE | ✅ CE free; EE licensed | Business $20/user/mo; Enterprise custom ([Onyx pricing](https://www.onyx.app/pricing)) | ❌ 40+ enterprise connectors, internal docs | ❌ (no long-term memory) | ✅ | Customers: Netflix, Ramp, Thales; closest shape to Nowing |
| **Open WebUI** | Self-hosted AI chat UI | community/sponsors | ~146k ([GitHub](https://github.com/open-webui/open-webui)) | Open WebUI License (branding clause) | ✅ free; Enterprise license for white-label | Free; Enterprise custom (white-label/SLA) ([Open WebUI Enterprise](https://docs.openwebui.com/enterprise)) | via web search plugin | ❌ chat threads only | partial | 146k stars; Samsung, JGU Mainz, Public Storage case studies |
| **LibreChat** | Multi-provider chat UI | acquired by ClickHouse (Nov 2025) but remains MIT | ~41k ([GitHub](https://github.com/danny-avila/LibreChat)) | MIT | ✅ free | Free self-host; managed by third parties; no first-party SaaS ([LibreChat for Business](https://www.areebi.com/resources/blog/librechat-for-business)) | via plugins | ❌ chat history | partial | Enterprise auth (OAuth/SAML/LDAP/RBAC) out of box |
| **Vane / Perplexica** | Open-source AI search | none / community | ~35.9k ([GitHub](https://github.com/ItzCrazyKns/Vane)) | MIT | ✅ | Free, no paid tiers ([self-hosted guide](https://joshuaopolko.com/perplexica-self-hosted-guide/)) | ✅ via SearXNG | ❌ (answer engine) | ✅ | “Privacy-focused Perplexity alternative,” single Docker |
| **Perplexity** | Consumer/enterprise research | ~$1.7B raised; ~$23B valuation; ~$450M ARR ([ValueAddVC](https://valueaddvc.com/blog/perplexity-ai-valuation-revenue-2026-23b-450m-arr)) | n/a (proprietary) | proprietary | ❌ | Free / $20 / $200 / Enterprise Pro $40/seat / Enterprise Max $325/seat ([Perplexity pricing](https://www.perplexity.ai/hub/pricing)) | ✅ live web | limited (spaces) | ✅ | 100M+ MAU; research-workspace leader, red-ocean consumer |
| **Google NotebookLM / Gemini Notebook** | Consumer/team research | bundled in Google One / Workspace | n/a (proprietary) | proprietary | ❌ | $0 / $4.99 / $19.99 / $99–$199; Workspace ~$9–14/user/mo ([NotebookLM support](https://support.google.com/notebooklm/answer/16213268?hl=en)) | limited | limited (per notebook) | ✅ source-grounded | 17M MAU; 80,000+ orgs before paid tier ([Neodrop](https://neodrop.ai/post/_pTDGfmZgdK)) |
| **Letta (ex-MemGPT)** | Stateful agent runtime | $10M seed ([TechCrunch](https://techcrunch.com/2024/09/23/letta-one-of-uc-berkeleys-most-anticipated-ai-startups-has-just-come-out-of-stealth/)) | ~23.3k (letta-ai/letta) | Apache-2.0 | ✅ | Free up to 3 agents; Pro $20/mo; Max $200/mo; Enterprise custom | no | ✅ self-editing memory | partial | Research-rooted; agent harness, not just memory API |

### Competitive Narrative

**Memory-layer competitors (Mem0, Zep, Cognee, Supermemory, Letta):** These companies have collectively raised >$40M and are racing to become the default “memory API” for AI agents. They differ on architecture (vector vs. graph vs. hybrid), deployment (cloud-only vs. open-source core), and pricing (requests, credits, tokens). None of them openly market ingestion of live Reddit / YouTube / TikTok / Maps / Amazon content into memory. They are strongest on chat history, business data, and documents. **This is Nowing’s primary wedge, but the gap is data acquisition, not schema.** As the Nowing brief notes, adding a `source_id` field is easy; building and maintaining 14 scraping verbs through anti-bot infrastructure is not.

**Research-workspace competitors (Onyx, Perplexity, Open WebUI, LibreChat, Vane, NotebookLM):** These products shape user expectations for chat-with-citations, self-hosting, and connectors. Onyx is the closest structural analog: MIT-licensed, enterprise connectors, citations, self-host, and a cloud paid tier. But Onyx does not have long-term project memory (per Nowing Product Brief, §4). Perplexity and NotebookLM validate that consumers and enterprises will pay for research, but they are proprietary and cannot self-host. Vane/Perplexica proves there is demand for a self-hosted Perplexity alternative but is not a memory platform.

**Platforms (OpenAI, Anthropic, Google, Microsoft, AWS):** Cross-chat memory is becoming free/table stakes. This is a strategic risk: if model labs decide to offer live-web memory, the thin “memory API” business model collapses. The Nowing response is to own the workspace, the provenance chain, and the self-host trust boundary — things a model lab will not easily replicate.

### Moat Assessment

- **Not a moat:** citations (table stakes), MCP-native (everyone has it), “cheaper than Perplexity” (red ocean).
- **Real moat:** head start + integration depth (connectors → index → provenanced memory → chat → deliverables → multi-client) and data-acquisition operations (live web/UGC ingestion).
- **Moat risk:** the live-web ingestion wedge is narrow. An incumbent (e.g., Onyx adding a web crawler, or Perplexity opening an API) could close it. The only defense is speed and depth in the research-deliverable loop. This aligns with a16z’s “Empty Promise of Data Moats” argument: raw data is not a durable moat unless it is exclusive or feeds a product flywheel.

> **Tóm tắt cạnh tranh:** Mem0/Zep/Cognee/Supermemory là đối thủ tầng memory; không ai đưa live web/UGC vào memory. Onyx là đối thủ gần nhất về hình dạng workspace nhưng thiếu memory lâu dài. Perplexity/NotebookLM chứng minh trả tiền cho nghiên cứu nhưng không self-host. Live web + provenance + self-host là khe cửa của Nowing, nhưng hẹp — cần chạy nhanh.

---

## Customer Segments & Jobs-to-be-Done

### Segment 1: AI Agent Builders (primary beachhead)

**Jobs:**
- Give my agent persistent memory across sessions without rebuilding context each time.
- Reduce token spend by recalling only relevant facts instead of dumping full chat history.
- Expose memory through a typed surface (MCP/REST) so Claude Code / Cursor / OpenCode can call it.

**Pains (public evidence):**
- Stateless agents force users to re-explain context every session; context windows are “whiteboards that get erased” ([Omoshola Owolabi, 2025](https://omoshola.me/posts/2025/building-a-memory-system-for-ai-agents/)).
- Production failures: horizontal scaling, deploys, and worker restarts wipe in-memory agent state, causing “silent amnesia” ([Medium post on agent memory](https://medium.com/@dilawarabbbas/why-your-ai-agent-forgets-customers-between-restarts-and-the-pattern-that-quietly-fixes-it-396363f95260)).
- Agent builders building internal memory spend 3–4 weeks of engineering and still lack retrieval quality (Mem0 Sunflower case: saved 3–4 weeks by buying a memory layer).

**Evaluation criteria:**
- Ease of integration (MCP server preferred).
- Latency and recall quality (LoCoMo, LongMemEval, BEAM benchmarks).
- Cost per memory operation.
- Self-host option for data privacy.

### Segment 2: Research Teams / Analysts

**Jobs:**
- Collect real-world opinions from Reddit, YouTube, TikTok, Maps, Amazon without writing custom scrapers.
- Continue a research thread across multiple sessions without losing prior findings.
- Share findings and decisions in a workspace with RBAC.

**Pains:**
- Research lives in individual chat threads and disappears; two researchers duplicate effort without knowing it (Nowing Product Brief, §3).
- Source-grounded citations are required, but manual copy-paste is error-prone.
- “Every session starts from zero” — agents cannot recall competitor research done last week.

**Evaluation criteria:**
- Connector breadth and live-web coverage.
- Citation accuracy and freshness.
- Workspace collaboration and permissioning.
- Export/deliverable quality (reports, podcasts, dashboards).

### Segment 3: Data-Sensitive Organizations / Self-Hosters

**Jobs:**
- Keep research data inside my infrastructure (air-gapped, VPC, on-prem).
- Use open-source / source-available software for audit and customization.
- Avoid per-seat SaaS lock-in.

**Pains:**
- Many AI tools require sending internal documents or research to a vendor cloud.
- Enterprise procurement for new AI tools is slow; an open-source trial with an internal champion bypasses this.
- Open-source AI UIs (Open WebUI, LibreChat) are great for chat but have no durable research memory or provenance.

**Evaluation criteria:**
- License permissiveness and code auditability.
- Ease of Docker/self-host deployment.
- Air-gapped / BYOK options.
- No forced cloud dependency for core features.

### Customer Evidence Snapshot

| Pain | Source | Quote / Stat |
|---|---|---|
| Cross-session amnesia wastes tokens | [Omoshola Owolabi](https://omoshola.me/posts/2025/building-a-memory-system-for-ai-agents/) | “The context window is not memory. It is a whiteboard that gets erased.” |
| 68% of production agent deployments now include a dedicated memory layer (up from 23% in 2024) | [Xelionlabs persistent agents guide](https://xelionlabs.com/blog/persistent-ai-agents-guide) | Persistent memory moved from research curiosity to production necessity. |
| Customer support memory changes workflow, not just greeting | [Mem0 cross-channel support blog](https://mem0.ai/blog/cross-channel-support-memory-with-mem0) | 73% of customers expect cross-channel continuity; 53% say they always have to repeat their issue when transferred. |
| Saved 3–4 weeks of memory infra work | [Mem0 Sunflower case study](https://mem0.ai/blog/how-sunflower-scaled-personalized-recovery-support-to-80-000-users-with-mem0) | “We were throwing the entire memory into context — not scalable.” |
| 40% token cost reduction | [Mem0 RevisionDojo case study](https://mem0.ai/blog/how-revisiondojo-enhanced-personalized-learning-with-mem0) | “Not only did we see a 40% reduction in token costs, but…” |
| Supermemory reduced RAG latency for Scira | [Supermemory Scira case](https://supermemory.ai/case-studies/why-scira-ai-switched) | 37.4% lower mean retrieval latency vs. Mem0. |
| Open WebUI enterprise adoption | [Open WebUI Enterprise](https://docs.openwebui.com/enterprise) | Samsung, Public Storage (~50% active adoption in 30 days), JGU Mainz (30,000+ students, 5,000+ employees). |

> **Tóm tắt khách hàng:** Ba nhóm chính: agent builder cần memory qua MCP để tiết kiệm token, team nghiên cứu cần workspace có citations và tiếp tục thread, tổ chức nhạy cảm cần self-host. Bằng chứng công khai chứng minh pain là thật: 68% production agent có memory layer, 73% khách hàng muốn liên tục cross-channel, case study tiết kiệm 40% token.

---

## Pricing & Monetization Benchmarks

### Pricing Models in the Space

| Model | Example | Price Points | Notes |
|---|---|---|---|
| **Usage-based requests** | Mem0 | Free: 10k add + 1k retrieval; $19: 50k add + 5k retrieval; $249: 500k add + 50k retrieval | Billed by memory operations; unlimited end users on paid tiers |
| **Credit-based (bytes ingested)** | Zep | Free 1,000 credits/mo; Flex $125/mo (50k credits); Flex Plus $375/mo (200k credits); Enterprise custom | 1 credit per 350 bytes; retrieval/storage free |
| **Token-based + workspace fee** | Cognee | Free 1M tokens + 1 workspace; $2.50/1M tokens + $5/workspace | Clear usage metric aligned to LLM cost |
| **Subscription + usage balance** | Supermemory | Free; $19; $100; $399; Enterprise; $0.005/1K SM tokens | “SM tokens” are deduplicated; pay-as-you-go top-up |
| **Per-seat SaaS** | Onyx | Business $20/user/mo; Enterprise custom | Traditional enterprise model; self-host via license |
| **Freemium + high-tier power** | Perplexity | Free; $20 Pro; $200 Max; Enterprise Pro $40/seat; Enterprise Max $325/seat | Agentic “Computer” credits drive usage-based upsell |
| **Bundled in ecosystem** | NotebookLM | Google One AI Premium $20/mo; Workspace ~$9–14/user/mo; Ultra $99–$199 | Bundled storage + models; not standalone |
| **Open-source + enterprise license** | Open WebUI | Free self-host; Enterprise custom for white-label / SLA | Revenue from branding/support, not per feature |
| **Open-source + third-party managed** | LibreChat | Free MIT; managed by Elestio/AWS Marketplace | No first-party monetization yet |

### Monetization Insights for Nowing

1. **Cloud pay-as-you-go is the norm for memory infrastructure.** Customers expect to pay for what they use (requests, credits, tokens). Seat-based pricing works for team workspaces but is harder to justify for a memory API.
2. **Open-source conversion is low but high-leverage.** MongoDB, Supabase, PostHog, and Airbyte built large ARR on single-digit conversion from free downloads/self-hosts. The playbook is: make self-host excellent, then monetize managed cloud and hard-to-self-host capabilities.
3. **“Expensive to self-host” is the conversion lever.** Airbyte explicitly markets its Cloud as “you own the upgrades, the 2am pages” ([Airbyte OSS→Cloud](https://airbyte.com/blog/airbyte-oss-to-cloud)). Nowing’s Phase 2 metered deep-research is a structurally similar lever: the capability is too costly/infrastructure-heavy to run locally.
4. **Margin expectations are thin at scale, healthy at the edge.** Bessemer’s 2025 State of AI notes top AI “supernovas” can reach $40M ARR in Year 1 but with ~25% gross margins ([Growth Equity Debrief](https://thegrowthequitydebrief.substack.com/p/the-memory-wars-how-context-creates)). Nowing’s internal target of 1.5–2.5× margin on full-pipeline cost is therefore realistic but depends on tightly metered deep-research calls and spend caps.
5. **Pricing packaging recommendation for Nowing:**
   - **Self-host:** free, unlimited core memory + connectors + chat (the wedge).
   - **Cloud:** pay-as-you-go by tokens/requests/credits for usage above a free tier; reserve deep multi-step open-web research as the primary paid feature.
   - **Enterprise:** seat- or commit-based tier for SSO, audit, BYOC, SLA.

> **Tóm tắt pricing:** Mô hình phổ biến là pay-as-you-go theo request/credit/token. Per-seat chỉ phù hợp khi đã là workspace. Chuyển đổi OSS → cloud thường 0.5–3%. Lever chuyển đổi là deep-research đắt tiền khó self-host. Mục tiêu margin 1.5–2.5× là thực tế nếu metering chặt.

---

## GTM & Distribution Insights

### Channel 1: MCP Registry & MCP-First Distribution

The Model Context Protocol is the most important distribution channel for Nowing.

- **Scale:** The official MCP Registry, Glama, mcp.so, and Smithery collectively index 15,000–26,000 servers. The official registry alone had 19,719 entries as of 2026-08-02 ([The Agent Almanac](https://agentalmanac.org/mcp)).
- **Adoption:** 67% of MCP tools are software-development / IT tools; 90% of downloads are dev tools. Claude Code dominates AI-assisted tool creation (66% of AI-co-authored servers) ([AISI, 177k MCP tools](https://www.aisi.gov.uk/blog/how-are-ai-agents-used-evidence-from-177000-ai-agent-tools)).
- **Monetization gap:** <5% of MCP servers are currently monetized ([AgentMarketCap](https://agentmarketcap.ai/blog/2026/04/11/mcp-developer-economy-2026)). Most are free community servers; the first viable monetization layers will be cloud-hosted, metered capabilities.
- **Implication for Nowing:** Ship `nowing_mcp` as a first-class, easy-to-install server. The registry is discovery; the README and one-command install are conversion.

### Channel 2: GitHub & Open-Source Community

- **GitHub is the top-of-funnel.** Mem0 (62k stars), Open WebUI (146k stars), LibreChat (41k), Onyx (30.5k), Cognee (29.7k), Supermemory (28.7k), Vane (35.9k) demonstrate that an open-source AI tool can reach tens of thousands of developers organically.
- **Stars are a lagging indicator; forks and issues are leading.** A healthy project needs clear self-host docs, a docker-compose one-liner, and a public roadmap.
- **License transparency matters.** Open WebUI’s branding clause and Onyx’s CE/EE split show the market accepts commercial open-core if the boundaries are honest. Nowing’s three-tier license (Apache/BSL/closed) must be explained clearly in the README to avoid HN backlash.

### Channel 3: Hacker News / Reddit / Self-Host Communities

- Hacker News rewards technical depth, authenticity, and “Show HN” posts with a live demo. Generic marketing is flagged ([HN strategy guide](https://www.marketingskills.sh/jonathimer/devmarketing-skills/hacker-news-strategy)).
- A successful “Show HN” can drive 500+ stars in 24 hours ([DEV community case](https://dev.to/bobsingor/how-i-got-500-stars-in-24-hours-on-my-first-public-github-repo-1afg)).
- Nowing should launch with a specific, technical hook: “Show HN: Nowing — long-term research memory for AI agents, with live web data and provenance.” Lead with the self-host one-liner and an MCP install command.
- r/selfhosted, r/LocalLLaMA, r/ClaudeAI, and Discord communities are natural amplification channels for an open-source, privacy-first tool.

### Channel 4: Cloud Conversion Motion (PLG)

- **Bottom-up, not sales-led.** Open-source infrastructure wins when individual developers or team leads adopt, then pull in a cloud subscription for production/team features.
- **Activation and expansion metrics:** PLG benchmarks show visitor→freemium signup ~6%, freemium→paid 2–5% median, activation 33% median, 65%+ top decile ([PulseRevOps](https://pulserevops.com/knowledge/q12731)).
- **For Nowing:** the cloud conversion path is: GitHub star → self-host install → active workspace → cloud account triggered by deep-research usage. The first-run value (≤15 minutes per Nowing Brief M1) is critical.

### GTM Recommendations

| Priority | Tactic | Rationale |
|---|---|---|
| 1 | Publish `nowing_mcp` to official MCP Registry and Smithery/Glama | MCP is where agent builders discover tools |
| 2 | Launch on HN “Show HN” with live self-host demo + one-command Docker | Authentic dev launch; drives GitHub stars and feedback |
| 3 | Build README around license transparency and quick self-host | Avoids HN license flame war; reduces install friction |
| 4 | Seed case studies and “memory pain” content | Customer evidence is currently thin; vendor-neutral blogs/Reddit posts help |
| 5 | Cloud pay-as-you-go with deep-research as the metered lever | Aligns monetization with the costliest, hardest-to-self-host capability |

> **Tóm tắt GTM:** MCP registry là kênh phân phối quan trọng nhất. GitHub + HN/Reddit/self-host community là top-of-funnel. Chuyển đổi cloud phải bottom-up, bắt đầu từ agent builder, kích hoạt ≤15 phút, đòn bẩy là deep-research trả tiền. Cần minh bạch license trên README.

---

## Key Risks & Evidence Gaps

### Strategic Risks

1. **Wedge can be closed by incumbents.** If Onyx adds a live-web crawler, or Perplexity exposes an MCP memory server, the “live web into memory” differentiator narrows. The defense is speed and deeper research-deliverable integration.
2. **Citations / provenance become table stakes.** OpenAI, Zep, Oracle, and others already ship “memory with receipts.” Nowing must move the story from “we have citations” to “we can re-validate and refresh those citations against live sources.”
3. **Model labs could bundle memory for free.** OpenAI, Google, and Microsoft have already crossed that threshold in 2025. A thin memory-API business is not defensible; the workspace + self-host + data-control bundle is.
4. **License story is complex and easy to misrepresent.** Calling the whole product “open source” would be inaccurate because the crawler is BSL 1.1 and deep-research is closed. A HN launch must be precise.
5. **Deep-research cost and quality must be proven before pricing.** FR-37 (cost parsing) and NFR-8 (recall eval gate) are launch gates. Without real cost numbers, the 1.5–2.5× margin target is speculative.

### Evidence Gaps

| Gap | Why it matters | Suggested follow-up |
|---|---|---|
| Independent customer research | Most pain quotes are vendor-published or blog posts | Run 5–10 user interviews with agent builders and research teams |
| Nowing-specific conversion data | SOM depends on self-host → cloud conversion, which does not exist yet | Instrument telemetry and define cohort conversion before public launch |
| Competitive live-web capabilities | Hard to verify whether competitors have live-web ingest in closed beta | Monitor release notes and run head-to-head tests |
| Legal / ToS around long-term web data retention | Long-term storage of scraped Reddit/YouTube/etc. has PII and copyright risk | Legal review before GA cloud; document retention/deletion policy |
| MCP monetization norms | <5% of MCP servers monetize; no established playbook | Publish an early paid MCP experiment and measure willingness-to-pay |
| Actual NotebookLM / Perplexity churn/retention | Proprietary; public estimates from Sacra/ValueAddVC are not audited | Use as directional only, not as a forecast input |

> **Tóm tắt rủi ro:** Rủi ro lớn nhất là khe cửa live-web + memory bị đối thủ lớn đóng nhanh; provenance đã thành table stakes; model lab có thể miễn phí memory. License cần trình bày chính xác. Cần bằng chứng thật về cost deep-research, chuyển đổi self-host → cloud, và pháp lý lưu trữ dữ liệu scrape dài hạn.

---

## Sources

1. Agentic AI Orchestration and Memory Systems Market — Mordor Intelligence: https://www.mordorintelligence.com/industry-reports/agentic-artificial-intelligence-orchestration-and-memory-systems-market
2. Agentic AI Orchestration and Memory Systems Market — Research and Markets: https://www.researchandmarkets.com/reports/6231856/agentic-ai-orchestration-memory-systems-market
3. Generative AI in Enterprise Knowledge Management and Search — Mordor Intelligence: https://www.mordorintelligence.com/industry-reports/generative-ai-in-enterprise-knowledge-management-and-search-market
4. Enterprise Search Market — Mordor Intelligence: https://www.mordorintelligence.com/industry-reports/enterprise-search-market
5. AI Enterprise Search Market — DataIntelo: https://dataintelo.com/report/ai-enterprise-search-market
6. AI Search Engine Market — MarketIntelo: https://marketintelo.com/report/ai-search-engine-market
7. Conversational AI Chatbot Market — DataIntelo: https://dataintelo.com/report/conversational-ai-chatbot-market
8. AI Memory & Context-Management Market 2025 — Mnemoverse: https://mnemoverse.com/docs/research/market-landscape
9. Mem0 raises $24M — TechCrunch: https://techcrunch.com/2025/10/28/mem0-raises-24m-from-yc-peak-xv-and-basis-set-to-build-the-memory-layer-for-ai-apps/
10. Mem0 GitHub: https://github.com/mem0ai/mem0
11. Mem0 pricing: https://mem0.ai/pricing
12. Zep GitHub: https://github.com/getzep/zep
13. Zep pricing: https://www.getzep.com/pricing
14. Zep product / customers: https://www.getzep.com/product/agent-memory/
15. Cognee raises $7.5M — Cognee blog: https://www.cognee.ai/blog/cognee-news/cognee-raises-seven-million-five-hundred-thousand-dollars-seed
16. Cognee GitHub: https://github.com/topoteretes/cognee
17. Cognee pricing: https://cognee.ai/pricing
18. Supermemory GitHub: https://github.com/supermemoryai/supermemory
19. Supermemory pricing: https://supermemory.ai/pricing/
20. Supermemory case studies: https://supermemory.ai/case-studies
21. Onyx GitHub: https://github.com/onyx-dot-app/onyx
22. Onyx pricing: https://www.onyx.app/pricing
23. Onyx $10M seed — Onyx blog: https://onyx.app/blog/seed-round
24. Onyx Ramp case study PDF: https://onyx.app/blog-assets/ramp-case-study.pdf
25. Open WebUI GitHub: https://github.com/open-webui/open-webui
26. Open WebUI Enterprise / license: https://docs.openwebui.com/enterprise
27. LibreChat GitHub: https://github.com/danny-avila/LibreChat
28. LibreChat for Business — Areebi: https://www.areebi.com/resources/blog/librechat-for-business
29. Vane / Perplexica GitHub: https://github.com/ItzCrazyKns/Vane
30. Vane self-hosted guide: https://joshuaopolko.com/perplexica-self-hosted-guide/
31. Perplexity Enterprise Pro: https://www.perplexity.ai/hub/blog/perplexity-launches-enterprise-pro
32. Perplexity pricing: https://www.perplexity.ai/hub/pricing
33. Perplexity revenue/valuation — ValueAddVC: https://valueaddvc.com/blog/perplexity-ai-valuation-revenue-2026-23b-450m-arr
34. Perplexity revenue — Sacra / Nathan Mzumara: https://nathanmzumara.com/insights/perplexity-500m-arr-business-model-agent-pricing-2026
35. Google NotebookLM Plus — TechCrunch: https://techcrunch.com/2025/02/10/google-expands-notebooklm-plus-to-individual-users/
36. NotebookLM growth playbook — Neodrop: https://neodrop.ai/post/_pTDGfmZgdK
37. NotebookLM / Gemini Notebook plans: https://support.google.com/notebooklm/answer/16213268?hl=en
38. Bessemer State of AI 2025: https://dev.editor.bvp.com/atlas/the-state-of-ai-2025
39. The Empty Promise of Data Moats — a16z: https://a16z.com/the-empty-promise-of-data-moats/
40. How are AI agents used? 177,000 MCP tools — UK AISI: https://www.aisi.gov.uk/blog/how-are-ai-agents-used-evidence-from-177000-ai-agent-tools
41. MCP Registry launch — Model Context Protocol blog: https://blog.modelcontextprotocol.io/posts/2025-09-08-mcp-registry-preview/
42. MCP Registry GitHub: https://github.com/modelcontextprotocol/registry
43. MCP Developer Economy — AgentMarketCap: https://agentmarketcap.ai/blog/2026/04/11/mcp-developer-economy-2026
44. MCP Census: https://mcpcensus.pages.dev/report
45. MCP ecosystem by the numbers — Sideband: https://www.sideband.pub/p/the-mcp-ecosystem-by-the-numbers
46. PLG conversion benchmarks — PulseRevOps: https://pulserevops.com/knowledge/q12731
47. Open Source PLG / OSS flywheel — PLG Handbook: https://plghandbook.com/open-source/
48. OSS SaaS conversion rate — Monetizely: https://www.getmonetizely.com/articles/whats-the-optimal-conversion-rate-from-free-to-paid-in-open-source-saas
49. Airbyte OSS to Cloud: https://airbyte.com/blog/airbyte-oss-to-cloud
50. Plausible self-hosted vs cloud: https://plausible.io/self-hosted-web-analytics
51. Mem0 Sunflower case study: https://mem0.ai/blog/how-sunflower-scaled-personalized-recovery-support-to-80-000-users-with-mem0
52. Mem0 RevisionDojo case study: https://mem0.ai/blog/how-revisiondojo-enhanced-personalized-learning-with-mem0
53. Mem0 cross-channel support: https://mem0.ai/blog/cross-channel-support-memory-with-mem0
54. Building a Memory System for AI Agents — Omoshola Owolabi: https://omoshola.me/posts/2025/building-a-memory-system-for-ai-agents/
55. Persistent AI Agents Guide — Xelionlabs: https://xelionlabs.com/blog/persistent-ai-agents-guide
56. Supermemory Scira case: https://supermemory.ai/case-studies/why-scira-ai-switched
57. Hacker News Strategy — Marketing Skills: https://www.marketingskills.sh/jonathimer/devmarketing-skills/hacker-news-strategy
58. How I got 500 GitHub stars in 24 hours — DEV: https://dev.to/bobsingor/how-i-got-500-stars-in-24-hours-on-my-first-public-github-repo-1afg
59. Letta raises $10M — TechCrunch: https://techcrunch.com/2024/09/23/letta-one-of-uc-berkeleys-most-anticipated-ai-startups-has-just-come-out-of-stealth/
60. Letta GitHub: https://github.com/letta-ai/letta
61. Zep funding — CB Insights: https://www.cbinsights.com/company/zep-2
62. On-premises conversational AI platforms — Verified Market Reports: https://www.verifiedmarketreports.com/product/on-premises-conversational-ai-platforms-market/
63. The Memory Wars — Growth Equity Debrief (Bessemer margin data): https://thegrowthequitydebrief.substack.com/p/the-memory-wars-how-context-creates

---

*Report generated autonomously by the `bmad-market-research` skill. All market figures, competitor data, and pricing are sourced from public web pages as of 2026-08-04. Forward-looking estimates should be treated as directional, not audited.*
