---
stepsCompleted: ["step-01"]
inputDocuments:
  - nowing_backend/docs/crypto-subagents-guide.md
---

> ⚠️ **SUPERSEDED** — Nội dung trong file này đã được merge vào [`epics.md`](./epics.md) (Epic 0 + Epic 9). File này chỉ giữ lại cho historical reference. **Đừng edit file này nữa.**

# Nowing Crypto Sub-Agents - Epic Breakdown

## Overview

Tài liệu này phân rã yêu cầu từ `crypto-subagents-guide.md` thành các epics và stories có thể triển khai, tổ chức theo giá trị người dùng và thứ tự ưu tiên.

## Requirements Inventory

### Functional Requirements

FR1: Tạo `tools/defillama.py` cung cấp 5 tools: `get_defillama_protocol`, `get_defillama_tvl_overview`, `get_defillama_yields`, `get_defillama_stablecoins`, `get_defillama_bridges` — gọi DeFiLlama API (miễn phí, không giới hạn)
FR2: Tạo `tools/crypto_sentiment.py` cung cấp 2 tools: `get_cmc_sentiment` (Fear & Greed Index), `get_reddit_crypto_sentiment` (Reddit public API)
FR3: Tạo `tools/crypto_news.py` cung cấp 2 tools: `get_crypto_news` (CryptoPanic), `get_coingecko_info` (CoinGecko)
FR4: Tạo `tools/contract_analysis.py` cung cấp 2 tools: `get_contract_info` (block explorer), `check_token_security` (GoPlus Security)
FR5: Đăng ký tất cả tools mới vào `registry.py` dưới dạng `ToolDefinition` với `requires=[]`
FR6: Tạo SubAgent spec files cho 6 agents chuyên biệt: `defillama_analyst`, `smart_contract_analyst`, `sentiment_analyst`, `news_analyst`, `portfolio_analyst`, `onchain_analyst`
FR7: Wire tất cả 6 crypto sub-agents vào `chat_deepagent.py` thông qua `SubAgentMiddleware`
FR8: Mỗi sub-agent nhận scoped tool list (chỉ tools liên quan, không phải toàn bộ) để tránh context confusion
FR9: Cập nhật system prompt của main agent với hướng dẫn orchestrate crypto agents song song
FR10: Test toàn bộ luồng song song: full analysis request → main agent gọi tất cả sub-agents qua `task()` → tổng hợp kết quả
FR11: Tạo `Tokenomics Analyst` sub-agent — phân tích supply schedule, vesting, token distribution, inflation/deflation
FR12: Tạo `Whale Tracker` sub-agent — theo dõi large wallets và smart money flows (Arkham, Nansen)
FR13: Tạo `Token Unlock Scheduler` sub-agent — track vesting events sắp tới, selling pressure (TokenUnlocks.app)
FR14: Tạo `Yield Optimizer` sub-agent — tối ưu yield theo risk preference, impermanent loss analysis
FR15: Tạo `Governance Analyst` sub-agent — theo dõi DAO proposals, Snapshot.org, Tally
FR16: Tạo `Technical Analysis` sub-agent — chart patterns, support/resistance, RSI/MACD signals

### Non-Functional Requirements

NFR1: Sub-agent system prompts phải < 500 tokens để tiết kiệm cost khi spawn nhiều agents đồng thời
NFR2: Parallel execution thực sự: LangGraph ToolNode chạy tất cả `task()` calls trong 1 response đồng thời
NFR3: Fallback sang `web_search` khi free APIs thất bại (CoinGecko 429, GoPlus unavailable)
NFR4: API rate limit awareness: CoinGecko 30 req/min, DeFiLlama unlimited, GoPlus 2000 req/day, CryptoPanic public
NFR5: Không cần DB dependencies cho crypto tools (`requires=[]`) — tất cả gọi external APIs

### Additional Requirements (Technical Architecture)

- SubAgent pattern: TypedDict với `name`, `system_prompt`, `model`, `tools`, `middleware` — spec files chỉ định nghĩa `name` + `system_prompt`, runtime fields inject từ `chat_deepagent.py`
- gp_middleware (shared): TodoList + Memory + NowingFilesystem + summarization + PatchToolCalls + AnthropicPromptCaching
- Tool factory pattern: `factory=lambda deps: create_xyz_tool()` trong registry
- Parallel spawn qua `task` tool của deepagents framework

### UX Design Requirements

N/A — đây là backend implementation, không có UI components.

### FR Coverage Map

{{requirements_coverage_map}}

## Epic List

- **Epic 1**: Core Crypto Tool Infrastructure (FR1-FR5) — ❌ **CHƯA IMPLEMENT**
- **Epic 2**: Sub-Agent Implementation & Wiring (FR6-FR9) — ❌ **CHƯA IMPLEMENT**
- **Epic 3**: Integration Testing & Validation (FR10)
- **Epic 4**: Advanced Crypto Agents — Batch 2 (FR11-FR16)

---

## Epic 1: Core Crypto Tool Infrastructure

**Mục tiêu**: Xây dựng nền tảng tool infrastructure để các crypto sub-agents có thể gọi external APIs. Tất cả tools là stateless, không cần DB, gọi free APIs.

> ❌ **Trạng thái (2026-04-23 audit)**: CHƯA IMPLEMENT — audit code phát hiện `nowing_backend/app/agents/new_chat/tools/` chỉ có `chainlens_research.py` và `crypto_realtime.py`. Các tools `defillama.py`, `crypto_sentiment.py`, `crypto_news.py`, `contract_analysis.py` **chưa tồn tại**.

### Story 1.1: DeFiLlama Tool Suite

As a crypto analyst agent,
I want to query DeFiLlama API for DeFi market data,
So that I can provide accurate TVL, yield, and protocol information to users.

**Acceptance Criteria:**

**Given** agent nhận yêu cầu về DeFi protocol
**When** gọi `get_defillama_protocol(protocol_slug="uniswap")`
**Then** trả về TVL, chains, change_1d, change_7d, mcap, fdv, audit_links
**And** nếu protocol không tồn tại, trả về `{"error": "Protocol 'x' not found"}`

**Given** agent cần overview thị trường DeFi
**When** gọi `get_defillama_tvl_overview(chain=None, limit=20)`
**Then** trả về danh sách top protocols sorted by TVL, total_tvl_usd
**And** nếu có `chain` filter, chỉ trả về protocols có chain đó

**Given** agent tìm yield opportunities
**When** gọi `get_defillama_yields(symbol="USDC", min_tvl=1_000_000)`
**Then** trả về pools sorted by APY với tvl_usd, apy_base, apy_reward, il_risk
**And** chỉ bao gồm pools có TVL >= min_tvl

**Given** agent cần stablecoin overview
**When** gọi `get_defillama_stablecoins(limit=20)`
**Then** trả về stablecoins sorted by market cap với peg_type, peg_mechanism, price

**Given** agent cần bridge volume data
**When** gọi `get_defillama_bridges(limit=20)`
**Then** trả về bridges sorted by lastDailyVolume với volume_24h, 7d, monthly

---

### Story 1.2: Smart Contract Security Tools

As a smart contract analyst agent,
I want to analyze contract source code and token security indicators,
So that I can identify rug pull risks, honeypots, and security vulnerabilities.

**Acceptance Criteria:**

**Given** agent có contract address trên Ethereum
**When** gọi `get_contract_info(contract_address="0x...", chain="ethereum")`
**Then** trả về is_verified, compiler_version, proxy status, security_analysis dict
**And** security_analysis bao gồm: has_ownable, has_pausable, has_upgradeable, has_mint_function, has_blacklist, uses_reentrancy_guard

**Given** agent cần token security check nhanh
**When** gọi `check_token_security(contract_address="0x...", chain_id="1")`
**Then** trả về risk_level (LOW/MEDIUM/HIGH), risks_detected list với emoji indicators
**And** honeypot detection, buy/sell tax info, owner_percent, top10HolderPercent

**Given** chain không được hỗ trợ
**When** gọi `get_contract_info(chain="unsupported_chain")`
**Then** trả về error message liệt kê các chains được hỗ trợ

---

### Story 1.3: Sentiment & News Tools

As a sentiment/news analyst agent,
I want to gather community sentiment and news from public sources,
So that I can analyze market psychology and news catalysts.

**Acceptance Criteria:**

**Given** agent cần Fear & Greed Index
**When** gọi `get_cmc_sentiment(symbol="BTC")`
**Then** trả về fear_greed_index với value, value_classification, timestamp

**Given** agent cần Reddit sentiment cho token
**When** gọi `get_reddit_crypto_sentiment(symbol="ETH", subreddit="ethereum", limit=25)`
**Then** trả về posts với score, num_comments, upvote_ratio
**And** avg_score và avg_upvote_ratio được tính từ tất cả posts

**Given** agent cần tin tức crypto mới nhất
**When** gọi `get_crypto_news(symbol="UNI", kind="news", limit=20)`
**Then** trả về news list với title, published_at, source, votes (positive/negative/important)
**And** sentiment_signal với positive/negative ratio

**Given** agent cần thông tin chính thức về token
**When** gọi `get_coingecko_info(coin_id="uniswap")`
**Then** trả về description, links (homepage, twitter, telegram, github), community_data, market_data
**And** nếu rate limit 429, trả về error message với hướng dẫn retry

---

### Story 1.4: Tool Registry Integration

As a backend developer,
I want all new crypto tools registered in registry.py,
So that the dependency injection system can instantiate them correctly.

**Acceptance Criteria:**

**Given** registry.py được load
**When** hệ thống khởi động
**Then** tất cả 11 tool definitions xuất hiện trong BUILTIN_TOOLS list
**And** mỗi ToolDefinition có `requires=[]` (không cần DB deps)
**And** `factory` là lambda function trả về tool instance

---

## Epic 2: Sub-Agent Implementation & Wiring

**Mục tiêu**: Tạo 6 specialized sub-agents và kết nối chúng vào hệ thống, cho phép main agent orchestrate song song.

> ❌ **Trạng thái (2026-04-23 audit)**: CHƯA IMPLEMENT — audit code phát hiện `nowing_backend/app/agents/new_chat/subagents/crypto/` **directory rỗng**; `chat_deepagent.py:472` chỉ wire `general_purpose_spec`, không có crypto sub-agent nào.

### Story 2.1: DeFiLlama Analyst Sub-Agent

As a main agent,
I want to delegate DeFi analysis to a specialized defillama_analyst sub-agent,
So that DeFi market data is analyzed in parallel with other crypto research.

**Acceptance Criteria:**

**Given** main agent nhận yêu cầu phân tích DeFi
**When** gọi `task(agent="defillama_analyst", task="Phân tích top DeFi protocols by TVL")`
**Then** defillama_analyst nhận task với scoped tools: defillama tools + get_live_token_price + web_search
**And** agent KHÔNG có access tới tools không liên quan (contract_analysis, sentiment, v.v.)
**And** response có format: 📊 Key metrics, 🔗 Chain distribution, 📈 Trend, 💡 Insights, ⚠️ Risk

---

### Story 2.2: Smart Contract Analyst Sub-Agent

As a main agent,
I want to delegate contract security analysis to smart_contract_analyst,
So that security checks run in parallel with other analyses.

**Acceptance Criteria:**

**Given** main agent có contract address cần phân tích
**When** gọi `task(agent="smart_contract_analyst", task="Security check contract 0x...")`
**Then** agent chạy security checklist: open source, no backdoors, no mint-without-limit, reentrancy guard, SafeMath, timelock, audit, no honeypot, LP locked
**And** response có risk level 🟢/🟡/🔴 và risks list cụ thể

---

### Story 2.3: Sentiment & News Analyst Sub-Agents

As a main agent,
I want sentiment_analyst and news_analyst to run in parallel,
So that social sentiment and news catalysts are captured simultaneously.

**Acceptance Criteria:**

**Given** main agent cần full sentiment picture
**When** spawn sentiment_analyst và news_analyst đồng thời
**Then** sentiment_analyst dùng: get_cmc_sentiment, get_reddit_crypto_sentiment, web_search, scrape_webpage
**And** news_analyst dùng: get_crypto_news, get_coingecko_info, web_search, scrape_webpage
**And** cả hai chạy song song, không block nhau

---

### Story 2.4: Portfolio & On-Chain Analyst Sub-Agents

As a main agent,
I want portfolio_analyst and onchain_analyst specialized agents,
So that portfolio optimization and on-chain signals are available on demand.

**Acceptance Criteria:**

**Given** user yêu cầu portfolio analysis với holdings list
**When** main agent spawn portfolio_analyst
**Then** agent tính: Portfolio Value, Allocation %, Risk Score, Diversification theo chains/sectors
**And** phân loại theo risk: 🔵 Conservative, 🟢 Large Cap, 🟡 Mid Cap, 🔴 Small Cap, ⚫ Micro Cap

**Given** user cần on-chain analysis
**When** main agent spawn onchain_analyst
**Then** agent check: whale activity, DEX flow (buy/sell ratio), holder count trend, LP health
**And** flag red flags: unusual outflows, whale dumping, LP removal

---

### Story 2.5: SubAgentMiddleware Wiring

As a backend developer,
I want all 6 crypto sub-agents registered in SubAgentMiddleware,
So that main agent can spawn any specialist via the task() tool.

**Acceptance Criteria:**

**Given** chat_deepagent.py khởi động
**When** SubAgentMiddleware được khởi tạo
**Then** có đúng 7 sub-agents: general_purpose + 6 crypto specialists
**And** mỗi crypto agent có scoped tool list (không phải tất cả tools)
**And** tất cả agents dùng gp_middleware stack

---

### Story 2.6: Main Agent Orchestration Prompt

As a main agent,
I want clear instructions on when and how to spawn crypto sub-agents in parallel,
So that I can coordinate multiple specialists efficiently for comprehensive analysis.

**Acceptance Criteria:**

**Given** user yêu cầu "Phân tích toàn diện token $UNI"
**When** main agent xử lý request
**Then** system prompt hướng dẫn gọi đồng thời: defillama_analyst + sentiment_analyst + news_analyst + smart_contract_analyst
**And** có bảng lookup: agent name → chuyên môn → khi nào dùng
**And** có ví dụ cụ thể về parallel task() calls

---

## Epic 3: Integration Testing & Validation

**Mục tiêu**: Xác minh toàn bộ hệ thống hoạt động đúng end-to-end với real API calls và parallel execution.

### Story 3.1: API Integration Tests

As a developer,
I want to verify each crypto tool connects to its API correctly,
So that I know the integration works before production deployment.

**Acceptance Criteria:**

**Given** DeFiLlama API available
**When** gọi `get_defillama_tvl_overview(limit=5)`
**Then** trả về ít nhất 5 protocols với TVL > 0
**And** response time < 5 giây

**Given** CoinGecko API available (không bị rate limit)
**When** gọi `get_coingecko_info(coin_id="bitcoin")`
**Then** trả về name="Bitcoin", symbol="BTC", current_price_usd > 0

**Given** GoPlus API available
**When** gọi `check_token_security(contract_address="0x1f9840a85d5af5bf1d1762f925bdaddc4201f984", chain_id="1")`
**Then** trả về token_name="Uniswap", risk_level IN ["LOW", "MEDIUM", "HIGH"]

**Given** CryptoPanic public API available
**When** gọi `get_crypto_news(symbol="BTC", limit=10)`
**Then** trả về ít nhất 1 news item với title, published_at, source

---

### Story 3.2: Parallel Execution Test

As a developer,
I want to verify multiple sub-agents run truly in parallel,
So that full analysis doesn't take 5x longer than single agent.

**Acceptance Criteria:**

**Given** main agent nhận yêu cầu full analysis
**When** spawn 4 agents đồng thời: defillama + sentiment + news + contract analysts
**Then** tất cả 4 agents start trong cùng 1 graph node (LangGraph ToolNode parallel)
**And** total execution time ≈ max(individual times), không phải sum
**And** kết quả của tất cả 4 agents được tổng hợp trước khi trả lời user

---

### Story 3.3: Error Handling & Fallback Validation

As a developer,
I want to verify graceful degradation when APIs fail,
So that partial failures don't break the entire analysis.

**Acceptance Criteria:**

**Given** CoinGecko trả về 429 rate limit
**When** `get_coingecko_info` được gọi
**Then** trả về `{"error": "CoinGecko rate limit reached, try again in 1 minute"}`
**And** agent fallback sang `web_search` để tìm thông tin thay thế

**Given** GoPlus API unavailable (timeout)
**When** `check_token_security` được gọi
**Then** trả về `{"error": "GoPlus API unavailable"}`
**And** smart_contract_analyst tiếp tục dùng get_contract_info + web_search

---

## Epic 4: Advanced Crypto Agents — Batch 2

**Mục tiêu**: Triển khai 6 agents chuyên biệt bổ sung để hoàn thiện crypto analysis coverage.

### Story 4.1: Tokenomics Analyst

As a crypto investor,
I want a specialist agent that analyzes token economics deeply,
So that I can evaluate long-term value accrual and inflation risks.

**Acceptance Criteria:**

**Given** user hỏi về tokenomics của token X
**When** main agent spawn tokenomics_analyst
**Then** agent phân tích: circulating supply vs total vs max supply, vesting schedule, token distribution (team/investors/community/treasury)
**And** đánh giá: inflation/deflation mechanics, token utility và demand drivers
**And** tools: get_coingecko_info, web_search (CryptoRank, Messari, official docs)

---

### Story 4.2: Whale Tracker Agent

As a crypto trader,
I want to track large wallet movements and smart money flows,
So that I can identify accumulation/distribution phases early.

**Acceptance Criteria:**

**Given** user hỏi về whale activity cho token X
**When** main agent spawn whale_tracker
**Then** agent identify: known whale wallets (exchanges, funds, insiders), inflow/outflow patterns
**And** phân biệt: accumulation phase vs distribution phase
**And** tools: web_search (Arkham Intelligence, Nansen, Etherscan token holders)

---

### Story 4.3: Token Unlock Scheduler

As a crypto investor,
I want to know upcoming token unlock events,
So that I can anticipate selling pressure before it happens.

**Acceptance Criteria:**

**Given** user hỏi về vesting/unlock schedule của token X
**When** main agent spawn token_unlock_scheduler
**Then** agent trả về: upcoming unlock dates, % supply được unlock, historical price action sau unlock events
**And** risk assessment cho short-term holds dựa trên unlock magnitude
**And** tools: web_search (TokenUnlocks.app, Vesting.is, CryptoRank)

---

### Story 4.4: Yield Optimizer Agent

As a DeFi investor,
I want personalized yield recommendations based on my risk tolerance,
So that I can maximize returns on idle capital safely.

**Acceptance Criteria:**

**Given** user có capital nhàn rỗi và risk preference (conservative/moderate/aggressive)
**When** main agent spawn yield_optimizer
**Then** agent filter yields phù hợp risk level, tính impermanent loss risk cho LP positions
**And** so sánh protocol security score trước khi recommend
**And** tools: get_defillama_yields, get_defillama_protocol, check_token_security

---

### Story 4.5: Governance Analyst

As a DAO participant,
I want to track active governance proposals and voting outcomes,
So that I can participate in protocol decisions and assess governance health.

**Acceptance Criteria:**

**Given** user hỏi về governance của protocol X
**When** main agent spawn governance_analyst
**Then** agent trả về: active proposals, vote outcomes, governance participation rate, treasury size/management
**And** flag controversial decisions hoặc governance attacks
**And** tools: web_search (Snapshot.org, Tally, Commonwealth, protocol forum)

---

### Story 4.6: Technical Analysis Agent

As a crypto trader,
I want chart pattern analysis and technical indicator signals,
So that I can time my entries and exits more effectively.

**Acceptance Criteria:**

**Given** user yêu cầu technical analysis cho token X
**When** main agent spawn technical_analyst
**Then** agent phân tích: key support/resistance levels, 50MA/200MA cross, RSI overbought/oversold, MACD signals
**And** identify chart patterns: head & shoulders, cup & handle, double bottom/top
**And** tools: get_live_token_data (DexScreener), web_search (TradingView, CoinGecko charts)
