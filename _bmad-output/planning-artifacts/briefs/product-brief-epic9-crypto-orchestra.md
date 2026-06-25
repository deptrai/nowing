---
documentType: product-brief
relatedEpic: epic-09-advanced-crypto-agents
relatedStories:
  - 9.1 Tokenomics Analyst
  - 9.2 Whale Tracker
  - 9.3 Token Unlock Scheduler
  - 9.4 Yield Optimizer
  - 9.5 Governance Analyst
  - 9.6 Technical Analyst
author: Mary (Strategic Business Analyst)
date: 2026-04-23
status: draft-v2 (stakeholder-resolved)
audience: Stakeholder Go/No-Go decision
projectContext: brownfield (Nowing platform, Epic 1-2 crypto foundation hoàn thành, Chainlens Research đã wired qua Epic 7)
stakeholderDecisions:
  costCeiling: "Quality-first — không set hard cap, optimize cost sau khi đạt quality baseline"
  phase1LaunchCriteria: "Mary tự quyết (xem Section 8)"
  webResearchStrategy: "Dùng chainlens_deep_research (đã có sẵn) thay vì raw web_search"
  codename: "Approved — Crypto Orchestra (không có brand guidelines formal, tên neutral)"
  coordinatedLaunch: "Yes — marketing + content + PR sync với Phase gates"
---

# Product Brief — Nowing **Crypto Orchestra**
### Epic 9: Advanced Crypto Sub-Agents (Batch 2)

> *Codename "Crypto Orchestra"* — vì giá trị cốt lõi nằm ở việc **6 nhạc cụ chuyên biệt cùng chơi đồng bộ** dưới sự chỉ huy của main agent, tạo ra symphony phân tích mà không một "solo agent" nào có thể đạt được.

---

## 1. Executive Summary

Nowing đã hoàn thành **foundation crypto sub-agents** (Epic 1-2: 4 agents — DeFiLlama, Sentiment, News, Smart Contract) chạy song song qua kiến trúc LangGraph SubAgentMiddleware. **Crypto Orchestra (Epic 9)** mở rộng đội ngũ thêm **6 specialist agents** (Tokenomics, Whale Tracker, Token Unlock, Yield Optimizer, Governance, Technical Analysis) để biến Nowing từ "general crypto research tool" thành **AI-native Bloomberg Terminal cho crypto retail** — một category chưa có ai chiếm giữ.

Khác với competitors (Messari Pro, Nansen, Arkham, Bloomberg Terminal) chỉ cung cấp **dashboards + dữ liệu thô** với giá $99-$2000+/tháng, Nowing đẩy crypto research lên một tầng cao hơn: **multi-agent orchestration tự động phân tích song song và tổng hợp insight có thể hành động** — tận dụng đúng kiến trúc Local-first Agentic RAG đã chứng minh trong các epic trước.

**Recommendation:** Tiến hành Epic 9 theo **Phased rollout** (3 phases, không phải single big-bang) để giảm rủi ro chi phí token và validate orchestration smoothness trước khi mở full suite.

---

## 2. Problem Statement

### Pain hiện tại của crypto investor/trader

| Pain Point | Hiện trạng thị trường |
|-----------|----------------------|
| Thông tin **phân mảnh** trên 10+ tools (DeFiLlama, Etherscan, CoinGecko, Snapshot, TradingView, Arkham...) | User phải tự mở từng tab, copy-paste, tổng hợp thủ công |
| **Insights yêu cầu chuyên môn** (TA, tokenomics, governance) — không phải ai cũng đọc được biểu đồ vesting | Phải subscribe nhiều SaaS riêng lẻ ($99-$2000+/tháng) |
| **Real-time alpha** thường đến quá muộn — khi tin lan rộng thì giá đã chạy | Cần dedicated tools cho whale watching, unlock scheduling |
| Existing AI tools (ChatGPT, Perplexity, Grok) **không có domain-specific agents** — chỉ web_search rồi summarize, dễ hallucinate số liệu | Không deterministic, không đáng tin cho quyết định tài chính |

### Gap thị trường (Blue Ocean)

> **Chưa có sản phẩm nào** kết hợp:
> - **Multi-agent orchestration** (parallel specialists chạy đồng thời)
> - **Domain-specific tools** (DeFiLlama, GoPlus, CryptoPanic, Snapshot — không phải web search chung chung)
> - **Conversational interface** (chat tự nhiên, không phải dashboard click-through)
> - **Cost-efficient parallelism** (tận dụng deepagents framework, không gọi 10x LLM tuần tự)

Nowing là **người đi đầu** ở giao điểm này.

---

## 3. Solution Overview — Crypto Orchestra

### 3.1 Architecture Reuse

Epic 9 **không thêm infrastructure mới** — toàn bộ tận dụng:
- ✅ `SubAgentMiddleware` (đã proven Epic 2)
- ✅ Parallel `task()` qua LangGraph ToolNode (NFR-CS2)
- ✅ Stateless tool pattern `requires=[]` (NFR-CS4)
- ✅ Token budget < 500 cho system prompt (NFR-CS1)

### 3.2 Six Specialists

| # | Agent | "Khi nào tôi nên gọi anh ta?" | Primary Tools |
|---|-------|-------------------------------|---------------|
| 9.1 | **Tokenomics Analyst** | "Token X có tốt long-term không?" → vesting, supply, distribution | CoinGecko + `chainlens_deep_research` (Messari, CryptoRank) |
| 9.2 | **Whale Tracker** | "Có cá voi gom/xả không?" → wallet movements, accumulation/distribution | `chainlens_deep_research` (Arkham, Nansen) |
| 9.3 | **Token Unlock Scheduler** | "Sắp unlock chưa? Bao nhiêu %?" → upcoming vesting events, sell pressure | `chainlens_deep_research` (TokenUnlocks.app, Vesting.is) |
| 9.4 | **Yield Optimizer** | "Có pool nào APY cao mà an toàn không?" → risk-adjusted DeFi yields | DeFiLlama + GoPlus + check_token_security |
| 9.5 | **Governance Analyst** | "DAO này có healthy không?" → active proposals, voting outcomes | `chainlens_deep_research` (Snapshot, Tally) |
| 9.6 | **Technical Analyst** | "Vào hay đợi?" → MA/RSI/MACD, support/resistance | DexScreener + `chainlens_deep_research` (TradingView) |

> 🔑 **Chainlens Research Integration** (confirmed via code audit `nowing_backend/app/services/chainlens_research_service.py`): Tất cả agents phụ thuộc web data (9.1, 9.2, 9.3, 9.5, 9.6) sử dụng tool `chainlens_deep_research` đã wired sẵn — **không phải raw web_search**. Lợi ích:
> - ✅ **Quality**: Chainlens synthesize multiple sources thành structured report (tốt hơn raw search results)
> - ✅ **Authenticated**: Bearer token auth, rate limit 120 req/min, daily quota — không vi phạm ToS
> - ✅ **Timeout resilience**: 125s service timeout + 130s outer timeout + 1 retry với backoff (service đã implement)
> - ✅ **Graceful fallback**: Khi Chainlens unavailable → auto-fallback sang `generate_report(report_style="deep_research")` (pattern neutral, không expose provider cho user)
> - ✅ **Supported sources**: `web`, `discussions`, `academic` (VALID_SOURCES) — multi-source research

### 3.3 Orchestra in action — Example flow

> **User**: *"Phân tích toàn diện $UNI cho quyết định long position 6 tháng"*
>
> **Main agent** (orchestrator) → spawn song song trong **1 LangGraph step**:
> - 🎻 `tokenomics_analyst` — vesting schedule, FDV vs MC ratio
> - 🎺 `whale_tracker` — top holders pattern 30d
> - 🥁 `token_unlock_scheduler` — upcoming unlocks Q3-Q4
> - 🎷 `governance_analyst` — recent proposals, treasury health
> - 🎸 `technical_analyst` — weekly chart, key levels
> - 🎹 (existing) `defillama_analyst` + `news_analyst` + `sentiment_analyst`
>
> **Tổng thời gian** ≈ thời gian agent chậm nhất (≈ 30-45s), KHÔNG phải tổng (≈ 5 phút nếu tuần tự).
>
> **Response**: tổng hợp đa chiều, có thể hành động ngay.

---

## 4. Target Users (Broad — All-In)

| Persona | Pain Nowing giải quyết | Agents quan trọng nhất |
|---------|------------------------|------------------------|
| **Retail investor** (DIY, không có Bloomberg) | "Tôi không biết đọc tokenomics" | 9.1 Tokenomics, 9.4 Yield |
| **Active trader** | "Tôi cần TA + whale signals real-time" | 9.2 Whale, 9.6 Technical |
| **DeFi yield farmer** | "Pool nào safe + APY cao?" | 9.4 Yield, 9.1 Tokenomics |
| **DAO participant** | "Proposal nào đang vote? Tôi nên ủng hộ ai?" | 9.5 Governance |
| **Long-term holder** | "Sắp unlock chưa? Có bị dump không?" | 9.3 Token Unlock, 9.1 Tokenomics |

---

## 5. Strategic Positioning — Differentiation Play

### 5.1 Competitive Mapping

| Competitor | Họ làm gì | Họ THIẾU gì | Nowing thắng ở đâu |
|-----------|-----------|-------------|-------------------|
| **Messari Pro** ($349/mo) | Dashboards, reports | Conversational, parallel agents | Ask anything, get specialist answer instantly |
| **Nansen** ($150/mo) | Wallet labeling, smart money | Tokenomics + governance + TA | One tool covers all 6 domains |
| **Arkham** ($199/mo) | Entity analytics | Conversational interface | Chat naturally, không cần học UI |
| **Bloomberg Terminal** ($2k+/mo) | Pro-grade everything | Crypto-native + retail accessible | Designed for crypto-native workflows |
| **ChatGPT/Perplexity/Grok** (free-$20/mo) | General Q&A | Domain-specific tools, parallel agents, deterministic data | Real APIs (DeFiLlama, GoPlus) — không hallucinate số |
| **Kaito AI** | Crypto search engine | Multi-agent orchestration, deep analysis | Tổng hợp có insight, không chỉ link |

### 5.2 Core Defensibility (3 lớp)

1. **Architecture moat** — multi-agent parallel orchestration hard to replicate (cần deepagents + LangGraph expertise)
2. **Tool integration moat** — 11+ crypto-native tools đã wired (DeFiLlama, GoPlus, CryptoPanic, CoinGecko...)
3. **Data freshness moat** — real-time API calls, không phải pre-cached data như competitors

---

## 6. Success Metrics — **Quality-First**

> **North Star** (theo định hướng của bạn): *"6 sub-agents hoạt động song song mượt mà khi cần, trả kết quả chính xác và nhanh."*
> **Cost philosophy** (stakeholder-decided): *Quality ưu tiên số 1. Cost optimize sau — khi đã đạt quality baseline stable.*

### 6.1 Tier 1 — Primary Gates (Quality-First)

| Pillar | Metric | Target | Đo bằng |
|--------|--------|--------|---------|
| 🎯 **Accuracy** (P0) | Factual error rate (random sample QA vs ground truth raw APIs) | **< 3%** (stricter vì quality-first) | QA manual + automated cross-check với raw API responses |
| 🎵 **Smoothness** (Parallelism) (P0) | `total_time / max(individual_time)` ratio | **< 1.3x** — near-perfect parallelism | LangGraph trace logs (Story 8.2) |
| 🔥 **Reliability** (P0) | % requests có ≥ 1 agent error nhưng main agent vẫn trả response đúng | **> 98%** graceful degradation — 3-tier rate-limit ladder (parallel → natural sequential → paced sequential) guarantees completion dù provider RPM strict | Story 8.3 / 0.6b fallback metrics + Chainlens `status: fallback` telemetry + `GRACEFUL_DEGRADATION_COUNTER{outcome="rate_limit_degraded\|rate_limit_paced"}` |
| ⚡ **Speed** (P1) | P95 response time cho full-suite (6+ agents spawned) | **< 90s** (relaxed vì quality-first — cho phép Chainlens 125s timeout) | Production telemetry |
| 🧠 **Hallucination rate** (P0) | % responses chứa số liệu không có trong tool output (fabricated) | **< 1%** | Sample QA + regex pattern check |

### 6.2 Tier 2 — Secondary (Observed, không gate)

| Pillar | Metric | Baseline |
|--------|--------|----------|
| 💰 Cost per request | Token cost / full-analysis | Track only, không set cap — optimize sau Phase 3 |
| 🚀 Adoption proxy | % conversations có ≥ 3 advanced agents spawned | Track only |
| 🔄 Chainlens success rate | % `chainlens_deep_research` trả `status: success` vs `status: fallback` | > 85% expected |

---

## 7. Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| ~~**Token cost blowup**~~ — stakeholder đã deprioritize | 🟢 Accepted | Quality-first, track cost metric nhưng không gate |
| **API rate limit cascade** — CoinGecko 30 req/min vỡ khi 10 agents spawn | 🟡 Medium | Upgrade CoinGecko Pro (quality-first justifies) / NFR-CS3 degradation |
| **LLM provider RPM strict** (e.g., TrollLLM 10 RPM) — 6-parallel spawn triggers 429 → stream aborts | 🟡 Medium | **3-tier degradation ladder** (Story 0.6 + 0.6b): parallel → natural sequential → paced sequential với `asyncio.sleep(7)` sau 3 consecutive 429. Guarantees completion ~42-50s cho 6 agents |
| ~~**Web scraping fragility**~~ (Snapshot, TokenUnlocks, Arkham) | ✅ **RESOLVED** | Dùng `chainlens_deep_research` — không scrape trực tiếp, Chainlens là B2B service đã authenticated |
| ~~**Compliance Arkham/Nansen ToS**~~ | ✅ **RESOLVED** | Chainlens handle source aggregation — compliance offloaded to Chainlens B2B contract |
| **TA agent thiếu data source historical OHLCV** chuẩn cho RSI/MACD | 🟡 Medium | Story 9.6 spike riêng — evaluate DexScreener depth + Chainlens coverage cho TradingView data |
| **Hallucination risk** với research-based agents | 🟠 Low-Med | Chainlens trả structured report với sources → prompt ràng buộc "only cite sources from tool output" |
| **User overwhelm** — main agent spawn cả 10 khi user chỉ cần 2 | 🟠 Low-Med | "Smart selector" instruction trong main agent system prompt |
| **Chainlens single point of failure** — 5/6 agents depend on nó | 🟡 Medium | Fallback pattern đã có (`status: fallback` → `generate_report`). Phase 1 test fallback path explicitly |
| **Chainlens 125s timeout** — quality research có thể chậm | 🟠 Low-Med | Speed target relaxed < 90s P95 (quality-first). Run parallel với short-path agents để perceived speed tốt hơn |

---

## 8. Recommended Approach — **Balanced (Phased + Vision)**

### Option A — Phased Rollout (Recommended ✅)

| Phase | Stories | Rationale | Effort |
|-------|---------|-----------|--------|
| **Phase 1 — Quality Foundation** (4 weeks) | 9.1 Tokenomics, 9.4 Yield Optimizer | Tận dụng tools deterministic (CoinGecko, DeFiLlama, GoPlus). Validate accuracy baseline + parallelism với 6 agents (4 cũ + 2 mới). Chainlens chỉ dùng supplementary. | Low |
| **Phase 2 — Chainlens-Heavy Agents** (4 weeks) | 9.2 Whale Tracker, 9.5 Governance Analyst | Chainlens-first research. Prompt engineering để force "cite sources from tool output only". Validate Chainlens quality + fallback path. | Medium |
| **Phase 3 — Spike-Gated** (6 weeks) | 9.3 Token Unlock, 9.6 Technical Analyst | 9.3 spike Chainlens coverage cho TokenUnlocks.app data. 9.6 spike DexScreener OHLCV depth. | Medium-High |

**Pros**: Validate accuracy + parallelism mỗi phase. Coordinated marketing có thời gian build up (3 launch moments).
**Cons**: Total time ~14 weeks.

### Option B — Aggressive Full-Suite (Alternative)

Triển khai cả 6 agents trong 1 sprint dài 6-8 weeks, big-bang launch.

**Pros**: Marketing impact lớn, "10 specialist agents" headline. First-mover effect mạnh.
**Cons**: Chưa validate accuracy baseline → quality-first goal bị mâu thuẫn. Spike 9.3/9.6 có thể block toàn bộ.

### Mary's Recommendation: **Option A (Phased)**

> Matches North Star "smooth + accurate + fast" và stakeholder quality-first priority. Aggressive launch chỉ phù hợp nếu quality không phải top priority.

### Phase 1 Launch Criteria (Mary's decision — Section 10.2 stakeholder-delegated)

**GO Phase 2** khi đạt **tất cả** 4 gates sau trong 2 tuần production runtime của Phase 1:

| Gate | Metric | Threshold |
|------|--------|-----------|
| 🎯 G1 Accuracy | Factual error rate (sample 100 full-analysis queries) | **< 3%** |
| 🎵 G2 Parallelism | `total_time / max(individual_time)` ratio | **< 1.3x** |
| 🔥 G3 Reliability | Graceful degradation rate | **> 98%** |
| 🧠 G4 No hallucination | Fabricated numbers in responses | **< 1%** |

Nếu bất kỳ gate nào fail → **rollback Phase 1 cải thiện prompt / tool behavior** trước khi mở Phase 2. Không có hard deadline — quality-first.

### Phase 2 → 3 Launch Criteria

Giữ 4 gates Phase 1 **+ Chainlens success rate > 85%** (Chainlens trả success vs fallback).

---

## 9. Decision Matrix — Go/No-Go

| Tiêu chí | Status |
|---------|--------|
| ✅ Architecture đã proven (Epic 1-2) | Yes |
| ✅ Tool infrastructure đã sẵn (Epic 1) | Yes |
| ✅ Chainlens Research đã wired (Epic 7) — thay thế raw web scraping | Yes — verified via code audit |
| ⚠️ Epic 8 (integration tests) chưa hoàn thành | **GATE**: Phải xong Epic 8 trước Phase 1 |
| ⚠️ Accuracy baseline với 6 agents chưa benchmarked | **GATE**: Phase 1 validate 4 gates mới chạy Phase 2 |
| ⚠️ Spike Story 9.3 (Chainlens unlock coverage) + 9.6 (OHLCV) chưa làm | **GATE**: Trước Phase 3 |
| ✅ Blue ocean positioning xác lập | Yes — không có competitor cùng vertical |
| ✅ Reusable infrastructure → cost implementation thấp | Yes — chủ yếu là spec files + system prompts |
| ✅ Legal/compliance (web scraping) | ✅ Resolved — Chainlens B2B offload compliance |
| ✅ Brand alignment | ✅ Resolved — không có brand guidelines formal, "Crypto Orchestra" neutral |
| ✅ Marketing coordinated launch | ✅ Approved — sync với Phase 1/2/3 gates |

### Recommendation: **GO** với Phased Rollout, GATED bằng Epic 8 + Phase 1 4-gates + 2 spikes.

---

## 10. Stakeholder Decisions — **RESOLVED**

| # | Question | Decision |
|---|----------|----------|
| 1 | Cost ceiling per request | ✅ **Quality-first, no hard cap**. Cost track-only, optimize sau Phase 3 |
| 2 | Phase 1 launch criteria | ✅ Mary-delegated → Section 8 "Phase 1 Launch Criteria" (4 gates: Accuracy < 3%, Parallelism < 1.3x, Reliability > 98%, Hallucination < 1%) |
| 3 | Web research strategy | ✅ **Dùng `chainlens_deep_research`** (verified via code audit, không phải raw web_search) — compliance, quality, retry, fallback đã handle |
| 4 | Branding | ✅ **"Crypto Orchestra" approved** — không có brand guidelines formal trong repo, tên neutral và marketable |
| 5 | Coordinated marketing launch | ✅ **Yes** — 3 launch moments (Phase 1/2/3), mỗi phase có PR + content hooks |

---

## Appendix — Codename Rationale

**"Crypto Orchestra"** được chọn vì:
- 🎼 Chính xác metaphor: 6 specialist nhạc cụ + main agent conductor
- 🎯 Differentiator: Competitors là "solo instruments" (Nansen = whale violin, Messari = data piano) — Nowing là **dàn nhạc đầy đủ**
- 🚀 Marketable: dễ kể chuyện, dễ tạo visual, không quá kỹ thuật
- 🌐 Vietnamese-friendly: "Dàn nhạc Crypto" / "Crypto Orchestra" đều đọc tự nhiên

Alternatives đã cân nhắc và loại:
- ~~"Crypto Analyst Suite"~~ — quá khô, không khác competitors
- ~~"Nowing Alpha"~~ — bị overload nghĩa với "alpha leak" trong crypto culture
- ~~"DeepCrypto"~~ — confuse với "DeepSeek" và mất focus orchestration

---

## Appendix — Chainlens Research Integration (Code Audit)

**Verified files** (via SymDex + Serena code navigation):
- `nowing_backend/app/services/chainlens_research_service.py` — B2B service client
- `nowing_backend/app/agents/new_chat/tools/chainlens_research.py` — LangGraph tool wrapper

**Key technical properties** (đã implement, không cần làm mới):
- `ChainlensResearchService.research(query, sources)` — Bearer auth POST `/api/v1/b2b/research`
- `VALID_SOURCES = {"web", "discussions", "academic"}` — multi-source flexibility
- `is_available()` với in-process TTL cache + error cooldown 5s — self-protecting
- Retry logic: MAX_RETRIES=1, backoff 1s, timeout 125s (service) + 130s (outer tool)
- Fallback pattern: `{"status": "fallback", "provider": "nowing"}` → LLM tự chuyển sang `generate_report(report_style="deep_research", source_strategy="auto")` — **neutral UX**, không expose engine name cho user

**Impact cho Epic 9**: Stories 9.1, 9.2, 9.3, 9.5, 9.6 có thể reuse tool này — giảm effort implementation và automatic compliance/reliability inheritance.

---

## Appendix — Marketing Launch Plan (Coordinated — confirmed)

| Phase | Launch Theme | Marketing Hooks |
|-------|--------------|-----------------|
| **Phase 1** | *"Tokenomics + Yield — AI-native analysis đầu tiên"* | Blog post, Twitter thread, demo video (30s parallel agents), landing page section |
| **Phase 2** | *"Whale Tracker + Governance — the hidden signals"* | Case study (actual whale event detection), interactive demo, PR outreach crypto media |
| **Phase 3** | *"Crypto Orchestra — the full 10-agent symphony"* | Headline launch: "World's first 10-agent parallel crypto research platform", video walkthrough, influencer partnerships |

---

**Document status**: **Draft v2 — stakeholder-resolved** ✅
**All 5 Section 10 questions: RESOLVED**
**Next step**: Trigger `bmad-create-prd` hoặc `bmad-create-epics-and-stories` để chuyển brief → engineering-ready specs cho Phase 1.
